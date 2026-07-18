#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable, Iterator

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback keeps the API usable.
    fcntl = None  # type: ignore[assignment]

from apsal_engine import (
    CREATIVE_LAYERS,
    ENGINE_VERSION,
    LAYER_ROLES,
    ValidationError,
    commit_element_layer,
    digest,
    element_attribute_display,
    element_display_projection,
    finalize_design_session,
    get_next_codex_job,
    init_workspace,
    load_design_session,
    load_json,
    present_element_layer,
    record_generation_result,
    record_model_visual_qa,
    session_interface_language,
    set_session_language,
    stage_preview_cards,
    start_design_session,
    start_generation_run,
)


PROTOCOL_VERSION = "0.15.0"
PROJECT_SCHEMA_VERSION = "0.15.0"
VIEW_SCHEMA_VERSION = "0.1.0"

_OPERATION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_PREVIEW_ID_RE = re.compile(r"^PREVIEW-[A-F0-9]{12}$")

ROLE_TO_STUDIO_TYPE = {
    "content": "global_control",
    "emotion": "global_control",
    "subject": "character",
    "world": "scene",
    "look": "styling",
    "event": "custom_prompt",
    "sequence": "generate_container",
    "camera": "camera",
    "light": "light",
    "style": "postprocess",
    "color_post": "postprocess",
    "job": "generate_container",
    "quality_control": "custom_prompt",
}

ROLE_LABELS = {
    "content": {"zh-CN": "创作命题", "en": "Content"},
    "emotion": {"zh-CN": "情绪", "en": "Emotion"},
    "subject": {"zh-CN": "人物", "en": "Subject"},
    "world": {"zh-CN": "世界", "en": "World"},
    "look": {"zh-CN": "妆造", "en": "Look"},
    "event": {"zh-CN": "事件", "en": "Event"},
    "sequence": {"zh-CN": "序列", "en": "Sequence"},
    "camera": {"zh-CN": "相机", "en": "Camera"},
    "light": {"zh-CN": "灯光", "en": "Light"},
    "style": {"zh-CN": "风格", "en": "Style"},
    "color_post": {"zh-CN": "色彩与后期", "en": "Color/Post"},
    "job": {"zh-CN": "生成任务", "en": "Job"},
    "quality_control": {"zh-CN": "质量检查", "en": "Quality Control"},
}


def _workspace(project_root: Path) -> Path:
    return project_root.expanduser().resolve() / ".apsal"


def _manifest_path(project_root: Path) -> Path:
    return _workspace(project_root) / "project.json"


def _operation_path(project_root: Path) -> Path:
    return _workspace(project_root) / "cache" / "protocol-operations.json"


def _transaction_path(project_root: Path) -> Path:
    return _workspace(project_root) / "cache" / "protocol-transaction.json"


def _proposal_dir(project_root: Path, session_id: str) -> Path:
    base = (_workspace(project_root) / "drafts").resolve()
    target = (base / session_id / "proposals").resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValidationError("invalid session id") from exc
    return target


def _history_dir(project_root: Path, operation_id: str) -> Path:
    if not _OPERATION_ID_RE.fullmatch(operation_id):
        raise ValidationError("operation_id must be a safe 1-128 character token")
    return _workspace(project_root) / "cache" / "history" / operation_id


def _view_path(project_root: Path) -> Path:
    return _workspace(project_root) / "studio" / "view.json"


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextlib.contextmanager
def _project_lock(project_root: Path) -> Iterator[None]:
    lock_path = _workspace(project_root) / "project.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            lock_path.chmod(0o600)
        except OSError:
            pass
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _compatibility_errors(value: dict[str, Any]) -> list[str]:
    errors = []
    expected = {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "engine_version": ENGINE_VERSION,
    }
    for key, wanted in expected.items():
        if value.get(key) != wanted:
            errors.append(f"{key}={value.get(key)!r}, expected {wanted!r}")
    if not value.get("project_id"):
        errors.append("project_id is missing")
    if not isinstance(value.get("revision"), int) or int(value.get("revision", -1)) < 0:
        errors.append("revision must be a non-negative integer")
    return errors


def _require_compatible_manifest(project_root: Path) -> dict[str, Any]:
    path = _manifest_path(project_root)
    if not path.is_file():
        raise ValidationError("APSAL project is not initialized; call project.init in a new directory")
    value = load_json(path)
    errors = _compatibility_errors(value)
    if errors:
        raise ValidationError(
            "incompatible APSAL project; 0.15 projects are not upgraded in place: " + "; ".join(errors)
        )
    return value


def init_protocol_project(project_root: Path) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = _manifest_path(root)
    existed = manifest_path.is_file()
    if existed:
        manifest = _require_compatible_manifest(root)
    init_workspace(root)
    (_workspace(root) / "studio").mkdir(parents=True, exist_ok=True)
    (_workspace(root) / "cache" / "history").mkdir(parents=True, exist_ok=True)
    with _project_lock(root):
        if existed:
            _recover_incomplete_transaction(root)
            manifest = _require_compatible_manifest(root)
        else:
            initial = load_json(manifest_path)
            manifest = {
                "schema_version": PROJECT_SCHEMA_VERSION,
                "project_id": initial.get("project_id") or f"PROJECT-{uuid.uuid4().hex[:12].upper()}",
                "protocol_version": PROTOCOL_VERSION,
                "engine_version": ENGINE_VERSION,
                "active_session_id": None,
                "revision": 0,
                "storage": "local_first",
                "created_at": initial.get("created_at"),
            }
            _atomic_json(manifest_path, manifest)
    return {"project_root": str(root), "project": manifest, "compatible": True, "read_only": False}


def project_manifest(project_root: Path) -> dict[str, Any]:
    return _require_compatible_manifest(project_root.expanduser().resolve())


def _operations(project_root: Path) -> dict[str, Any]:
    path = _operation_path(project_root)
    if not path.is_file():
        return {"schema_version": "0.1.0", "operations": {}}
    value = load_json(path)
    if not isinstance(value.get("operations"), dict):
        return {"schema_version": "0.1.0", "operations": {}}
    return value


def _remember_operation(project_root: Path, operation_id: str, value: dict[str, Any]) -> None:
    ledger = _operations(project_root)
    ledger["operations"][operation_id] = value
    if len(ledger["operations"]) > 200:
        keys = list(ledger["operations"])
        for key in keys[:-200]:
            ledger["operations"].pop(key, None)
    _atomic_json(_operation_path(project_root), ledger)


def _known_operation(project_root: Path, operation_id: str) -> dict[str, Any] | None:
    return _operations(project_root)["operations"].get(operation_id)


def _intent_digest(kind: str, payload: dict[str, Any]) -> str:
    return digest({"kind": kind, "payload": payload})


def _replay_result(
    operation_id: str,
    known: dict[str, Any],
    *,
    kind: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    wanted = _intent_digest(kind, payload)
    if known.get("intent_digest") != wanted:
        raise ValidationError(f"operation_id is already bound to a different intent: {operation_id}")
    return {**copy.deepcopy(known["result"]), "idempotent_replay": True}


def _require_revision(manifest: dict[str, Any], expected_revision: int) -> None:
    current = int(manifest.get("revision", 0))
    if expected_revision != current:
        raise ValidationError(f"revision mismatch: expected {expected_revision}, current {current}")


def _snapshot_before_mutation(
    project_root: Path,
    operation_id: str,
    session_id: str | None,
    recovery_paths: tuple[str, ...] = (),
) -> Path:
    target = _history_dir(project_root, operation_id)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    manifest = _manifest_path(project_root)
    if manifest.is_file():
        shutil.copy2(manifest, target / "project.json")
    if session_id:
        source = _workspace(project_root) / "drafts" / session_id
        if source.is_dir():
            shutil.copytree(source, target / "session")
    else:
        source = _workspace(project_root) / "drafts"
        if source.is_dir():
            shutil.copytree(source, target / "drafts")
    for relative in recovery_paths:
        if relative not in {"registry", "themes", "runs"}:
            raise ValidationError(f"unsupported recovery path: {relative}")
        source = _workspace(project_root) / relative
        if source.is_dir():
            shutil.copytree(source, target / relative)
    return target


def _restore_history(project_root: Path, history: Path, session_id: str | None) -> None:
    if (history / "project.json").is_file():
        shutil.copy2(history / "project.json", _manifest_path(project_root))
    if session_id:
        destination = _workspace(project_root) / "drafts" / session_id
        shutil.rmtree(destination, ignore_errors=True)
        if (history / "session").is_dir():
            shutil.copytree(history / "session", destination)
    elif (history / "drafts").is_dir():
        destination = _workspace(project_root) / "drafts"
        shutil.rmtree(destination, ignore_errors=True)
        shutil.copytree(history / "drafts", destination)
    for relative in ("registry", "themes", "runs"):
        if (history / relative).is_dir():
            destination = _workspace(project_root) / relative
            shutil.rmtree(destination, ignore_errors=True)
            shutil.copytree(history / relative, destination)


def _recover_incomplete_transaction(project_root: Path) -> None:
    path = _transaction_path(project_root)
    if not path.is_file():
        return
    try:
        transaction = load_json(path)
        history_value = str(transaction.get("history") or "")
        if history_value:
            history = Path(history_value).expanduser().resolve()
            history.relative_to((_workspace(project_root) / "cache" / "history").resolve())
            if history.is_dir():
                _restore_history(project_root, history, transaction.get("session_id"))
                shutil.rmtree(history, ignore_errors=True)
    finally:
        path.unlink(missing_ok=True)


def _mutation(
    project_root: Path,
    *,
    expected_revision: int,
    operation_id: str,
    operation_kind: str,
    operation_payload: dict[str, Any],
    session_id: str | None,
    apply: Callable[[], dict[str, Any]],
    undoable: bool = True,
    recovery_paths: tuple[str, ...] = (),
) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    if not _OPERATION_ID_RE.fullmatch(operation_id):
        raise ValidationError("operation_id must be a safe 1-128 character token")
    init_protocol_project(root)
    with _project_lock(root):
        duplicate = _known_operation(root, operation_id)
        if duplicate is not None:
            return _replay_result(
                operation_id, duplicate, kind=operation_kind, payload=operation_payload
            )
        manifest = _require_compatible_manifest(root)
        _require_revision(manifest, expected_revision)
        history = _snapshot_before_mutation(root, operation_id, session_id, recovery_paths)
        _atomic_json(_transaction_path(root), {
            "schema_version": "0.1.0",
            "operation_id": operation_id,
            "session_id": session_id,
            "revision_before": int(manifest["revision"]),
            "history": str(history),
        })
        try:
            result = apply()
        except Exception:
            _restore_history(root, history, session_id)
            shutil.rmtree(history, ignore_errors=True)
            _transaction_path(root).unlink(missing_ok=True)
            raise
        revision_before = int(manifest["revision"])
        manifest["revision"] = revision_before + 1
        manifest["engine_version"] = ENGINE_VERSION
        manifest["protocol_version"] = PROTOCOL_VERSION
        if result.get("session_id"):
            manifest["active_session_id"] = result["session_id"]
        _atomic_json(_manifest_path(root), manifest)
        enriched = {
            **result,
            "project_id": manifest["project_id"],
            "protocol_version": PROTOCOL_VERSION,
            "revision_before": revision_before,
            "revision": manifest["revision"],
            "operation_id": operation_id,
            "undoable": undoable,
        }
        _remember_operation(root, operation_id, {
            "status": "applied",
            "operation_kind": operation_kind,
            "intent_digest": _intent_digest(operation_kind, operation_payload),
            "session_id": manifest.get("active_session_id"),
            "revision_before": revision_before,
            "revision_after": manifest["revision"],
            "history": str(history) if undoable else "",
            "undoable": undoable,
            "result": enriched,
        })
        if not undoable:
            shutil.rmtree(history, ignore_errors=True)
        _transaction_path(root).unlink(missing_ok=True)
        return enriched


def start_project_design(
    brief: str,
    *,
    project_root: Path,
    expected_revision: int,
    operation_id: str,
    theme_id: str | None = None,
    name: str | None = None,
    shot_count: int = 9,
    language: str = "auto",
    set_strategy: str | None = None,
) -> dict[str, Any]:
    return _mutation(
        project_root,
        expected_revision=expected_revision,
        operation_id=operation_id,
        operation_kind="design.start",
        operation_payload={
            "brief": brief,
            "theme_id": theme_id,
            "name": name,
            "shot_count": shot_count,
            "language": language,
            "set_strategy": set_strategy,
        },
        session_id=None,
        apply=lambda: start_design_session(
            brief,
            project_root=project_root,
            theme_id=theme_id,
            name=name,
            shot_count=shot_count,
            language=language,
            set_strategy=set_strategy,
        ),
    )


def _active_session_id(project_root: Path, requested: str | None = None) -> str:
    if requested:
        return requested
    active = project_manifest(project_root).get("active_session_id")
    if not active:
        raise ValidationError("APSAL project has no active design session")
    return str(active)


def _element_projection(session: dict[str, Any], theme: dict[str, Any]) -> list[dict[str, Any]]:
    locale = session_interface_language(session).get("code") or "zh-CN"
    theme_id = theme["id"]
    elements: list[dict[str, Any]] = []
    for layer in CREATIVE_LAYERS:
        for index, role in enumerate(LAYER_ROLES[layer]):
            decision = theme["element_decisions"][role]
            label = ROLE_LABELS[role].get(locale, ROLE_LABELS[role]["en"])
            values = decision.get("values", {})
            presentation = element_display_projection(role, decision, session.get("brief", ""), locale)
            attributes = []
            for key, value in values.items():
                display_name, display_value = element_attribute_display(role, str(key), value, locale)
                attributes.append({
                    "id": f"{theme_id}:{role}:{key}",
                    "name": display_name,
                    "value": display_value if isinstance(display_value, str) else json.dumps(display_value, ensure_ascii=False),
                    "raw_value": value,
                })
            elements.append({
                "protocol_element_id": f"{theme_id}:{role}",
                "ghost": False,
                "participatesInPrompt": True,
                "layer_id": layer,
                "role_id": role,
                "label": label,
                "studio_type": ROLE_TO_STUDIO_TYPE[role],
                "status": decision.get("status", "proposed"),
                "intent": presentation["display_intent"],
                "attributes": attributes,
                "observable": presentation["display_observable"],
                "must_preserve": presentation["display_must_preserve"],
                "qa_expectations": presentation["display_qa_expectations"],
                "order": CREATIVE_LAYERS.index(layer) * 100 + index * 10,
            })
    return elements


def _project_snapshot_unlocked(
    root: Path, manifest: dict[str, Any], session_id: str | None = None
) -> dict[str, Any]:
    selected = session_id or manifest.get("active_session_id")
    base: dict[str, Any] = {
        "project_root": str(root),
        "project": manifest,
        "compatible": True,
        "read_only": False,
        "revision": int(manifest.get("revision", 0)),
        "protocol_version": PROTOCOL_VERSION,
        "engine_version": ENGINE_VERSION,
        "session": None,
        "elements": [],
        "stage_previews": [],
        "previews": [],
    }
    if not selected:
        return base
    session, theme = load_design_session(str(selected), root)
    locale = session_interface_language(session).get("code") or "zh-CN"
    base.update({
        "session": {
            "session_id": session["session_id"],
            "state": session["state"],
            "brief": session["brief"],
            "shot_count": session["shot_count"],
            "set_strategy": session.get("set_strategy"),
            "language": session.get("language"),
            "layers": session.get("layers", {}),
            "invalidations": session.get("invalidations", []),
            "theme_artifact": session.get("theme_artifact"),
        },
        "theme": {
            "id": theme["id"],
            "version": theme["version"],
            "name": theme.get("name"),
            "digest": digest(theme),
        },
        "elements": _element_projection(session, theme),
        "stage_previews": stage_preview_cards(session, theme, locale),
        "previews": _saved_previews(root, session, theme, int(manifest.get("revision", 0))),
    })
    return base


def _incompatible_snapshot(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    errors = _compatibility_errors(manifest)
    return {
        "project_root": str(root),
        "project": manifest,
        "compatible": False,
        "read_only": True,
        "compatibility_error": "; ".join(errors),
        "required_protocol_version": PROTOCOL_VERSION,
        "required_engine_version": ENGINE_VERSION,
        "revision": int(manifest.get("revision", 0)) if isinstance(manifest.get("revision"), int) else 0,
        "protocol_version": manifest.get("protocol_version"),
        "engine_version": manifest.get("engine_version"),
        "session": None,
        "elements": [],
        "stage_previews": [],
        "previews": [],
    }


def project_snapshot(project_root: Path, session_id: str | None = None) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    path = _manifest_path(root)
    if not path.is_file():
        raise ValidationError("APSAL project is not initialized; call project.init in a new directory")
    initial = load_json(path)
    if _compatibility_errors(initial):
        return _incompatible_snapshot(root, initial)
    with _project_lock(root):
        _recover_incomplete_transaction(root)
        manifest = _require_compatible_manifest(root)
        return _project_snapshot_unlocked(root, manifest, session_id)


def present_project_layer(project_root: Path, session_id: str, layer: str) -> dict[str, Any]:
    _require_compatible_manifest(project_root.expanduser().resolve())
    result = present_element_layer(session_id, layer, project_root=project_root.expanduser().resolve())
    result["revision"] = int(project_manifest(project_root).get("revision", 0))
    result["protocol_version"] = PROTOCOL_VERSION
    return result


def _preview_projection(
    session: dict[str, Any],
    theme: dict[str, Any],
    layer: str,
    decisions: dict[str, Any],
    preview_id: str,
) -> list[dict[str, Any]]:
    overlaid = copy.deepcopy(theme)
    for role, supplied in decisions.items():
        if role not in LAYER_ROLES[layer] or not isinstance(supplied, dict):
            continue
        current = overlaid["element_decisions"][role]
        for key in ("intent", "observable", "must_preserve", "qa_expectations", "basis"):
            if key in supplied:
                current[key] = supplied[key]
        if isinstance(supplied.get("values"), dict):
            current["values"] = {**current.get("values", {}), **supplied["values"]}
        current["status"] = "preview"
    projected = _element_projection(session, overlaid)
    role_ids = set(LAYER_ROLES[layer])
    ghosts = []
    for item in projected:
        if item["role_id"] not in role_ids:
            continue
        item["ghost"] = True
        item["participatesInPrompt"] = False
        item["preview_id"] = preview_id
        item["preview_element_id"] = f"{preview_id}:{item['role_id']}"
        ghosts.append(item)
    return ghosts


def _saved_previews(
    project_root: Path,
    session: dict[str, Any],
    theme: dict[str, Any],
    revision: int,
) -> list[dict[str, Any]]:
    root = _proposal_dir(project_root, session["session_id"])
    if not root.is_dir():
        return []
    previews: list[dict[str, Any]] = []
    for path in sorted(root.glob("PREVIEW-*.json")):
        proposal = load_json(path)
        if proposal.get("status") != "pending":
            continue
        base_revision = int(proposal.get("base_revision", -1))
        status = "pending" if base_revision == revision else "stale"
        layer = str(proposal.get("layer"))
        previews.append({
            "preview_id": proposal["preview_id"],
            "operation_id": proposal.get("operation_id"),
            "session_id": proposal.get("session_id"),
            "layer": layer,
            "base_revision": base_revision,
            "revision": revision,
            "status": status,
            "stale_reason": None if status == "pending" else "revision_changed",
            "invalidates_if_applied": list(CREATIVE_LAYERS[CREATIVE_LAYERS.index(layer) + 1 :]),
            "elements": _preview_projection(
                session, theme, layer, proposal.get("decisions", {}), proposal["preview_id"]
            ),
        })
    return previews


def propose_changes(
    *,
    project_root: Path,
    session_id: str,
    layer: str,
    decisions: dict[str, Any] | None,
    refs: list[dict[str, Any]] | None,
    expected_revision: int,
    operation_id: str,
    shots: list[dict[str, Any]] | None = None,
    reference_path: str | None = None,
    reference_bindings: list[dict[str, Any]] | None = None,
    draft_assets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if layer not in CREATIVE_LAYERS:
        raise ValidationError(f"unknown creative layer: {layer}")
    root = project_root.expanduser().resolve()
    def create_proposal() -> dict[str, Any]:
        session, theme = load_design_session(session_id, root)
        submitted = decisions or {}
        outside = set(submitted) - set(LAYER_ROLES[layer])
        if outside:
            raise ValidationError(f"{layer} decisions contain roles outside the layer: {sorted(outside)}")
        preview_id = f"PREVIEW-{uuid.uuid4().hex[:12].upper()}"
        proposal = {
            "schema_version": "0.1.0",
            "preview_id": preview_id,
            "operation_id": operation_id,
            "session_id": session_id,
            "layer": layer,
            "base_revision": expected_revision + 1,
            "status": "pending",
            "decisions": submitted,
            "refs": refs or [],
            "shots": shots,
            "reference_path": reference_path,
            "reference_bindings": reference_bindings or [],
            "draft_assets": draft_assets or [],
        }
        path = _proposal_dir(root, session_id) / f"{preview_id}.json"
        _atomic_json(path, proposal)
        later = list(CREATIVE_LAYERS[CREATIVE_LAYERS.index(layer) + 1 :])
        return {
            "preview_id": preview_id,
            "operation_id": operation_id,
            "session_id": session_id,
            "layer": layer,
            "base_revision": expected_revision + 1,
            "status": "pending",
            "invalidates_if_applied": later,
            "elements": _preview_projection(session, theme, layer, submitted, preview_id),
        }

    return _mutation(
        root,
        expected_revision=expected_revision,
        operation_id=operation_id,
        operation_kind="design.propose",
        operation_payload={
            "session_id": session_id,
            "layer": layer,
            "decisions": decisions,
            "refs": refs,
            "shots": shots,
            "reference_path": reference_path,
            "reference_bindings": reference_bindings,
            "draft_assets": draft_assets,
        },
        session_id=session_id,
        apply=create_proposal,
        recovery_paths=("registry",),
    )


def _proposal(project_root: Path, session_id: str, preview_id: str) -> tuple[Path, dict[str, Any]]:
    if not _PREVIEW_ID_RE.fullmatch(preview_id):
        raise ValidationError("invalid preview id")
    path = _proposal_dir(project_root, session_id) / f"{preview_id}.json"
    if not path.is_file():
        raise ValidationError(f"unknown preview: {preview_id}")
    return path, load_json(path)


def apply_preview(
    *,
    project_root: Path,
    session_id: str,
    preview_id: str,
    expected_revision: int,
    operation_id: str,
) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    intent = {"session_id": session_id, "preview_id": preview_id}
    path, proposal = _proposal(root, session_id, preview_id)
    if proposal.get("status") == "applied":
        duplicate = _known_operation(root, operation_id)
        if duplicate:
            return _replay_result(
                operation_id,
                duplicate,
                kind="design.commit_preview",
                payload=intent,
            )
        raise ValidationError(f"preview is already applied: {preview_id}")
    if proposal.get("status") != "pending":
        raise ValidationError(f"preview is not pending: {preview_id}")
    if int(proposal.get("base_revision", -1)) != expected_revision:
        raise ValidationError("preview revision is stale; create a new preview")

    def commit() -> dict[str, Any]:
        session = commit_element_layer(
            session_id,
            proposal["layer"],
            proposal.get("refs", []),
            project_root=root,
            decisions=proposal.get("decisions"),
            shots=proposal.get("shots"),
            reference_path=Path(proposal["reference_path"]) if proposal.get("reference_path") else None,
            reference_bindings=proposal.get("reference_bindings"),
            draft_assets=proposal.get("draft_assets"),
        )
        proposal["status"] = "applied"
        proposal["applied_operation_id"] = operation_id
        _atomic_json(path, proposal)
        return {"session_id": session["session_id"], "state": session["state"], "preview_id": preview_id}

    result = _mutation(
        root,
        expected_revision=expected_revision,
        operation_id=operation_id,
        operation_kind="design.commit_preview",
        operation_payload=intent,
        session_id=session_id,
        apply=commit,
        recovery_paths=("registry",),
    )
    return {**result, "snapshot": project_snapshot(root, session_id)}


def reject_preview(
    *,
    project_root: Path,
    session_id: str,
    preview_id: str,
    expected_revision: int,
    operation_id: str,
) -> dict[str, Any]:
    root = project_root.expanduser().resolve()

    def reject() -> dict[str, Any]:
        path, proposal = _proposal(root, session_id, preview_id)
        if proposal.get("status") == "applied":
            raise ValidationError("an applied preview cannot be rejected; undo its operation instead")
        proposal["status"] = "rejected"
        _atomic_json(path, proposal)
        return {"session_id": session_id, "preview_id": preview_id, "status": "rejected"}

    return _mutation(
        root,
        expected_revision=expected_revision,
        operation_id=operation_id,
        operation_kind="design.reject_preview",
        operation_payload={"session_id": session_id, "preview_id": preview_id},
        session_id=session_id,
        apply=reject,
    )


def commit_project_layer(
    *,
    project_root: Path,
    session_id: str,
    layer: str,
    expected_revision: int,
    operation_id: str,
    decisions: dict[str, Any] | None = None,
    refs: list[dict[str, Any]] | None = None,
    shots: list[dict[str, Any]] | None = None,
    reference_path: str | None = None,
    reference_bindings: list[dict[str, Any]] | None = None,
    draft_assets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    result = _mutation(
        project_root,
        expected_revision=expected_revision,
        operation_id=operation_id,
        operation_kind="design.commit_layer",
        operation_payload={
            "session_id": session_id,
            "layer": layer,
            "decisions": decisions,
            "refs": refs,
            "shots": shots,
            "reference_path": reference_path,
            "reference_bindings": reference_bindings,
            "draft_assets": draft_assets,
        },
        session_id=session_id,
        apply=lambda: commit_element_layer(
            session_id,
            layer,
            refs or [],
            project_root=project_root,
            decisions=decisions,
            shots=shots,
            reference_path=Path(reference_path) if reference_path else None,
            reference_bindings=reference_bindings,
            draft_assets=draft_assets,
        ),
        recovery_paths=("registry",),
    )
    return {**result, "snapshot": project_snapshot(project_root, session_id)}


def finalize_project(
    *, project_root: Path, session_id: str, expected_revision: int, operation_id: str
) -> dict[str, Any]:
    result = _mutation(
        project_root,
        expected_revision=expected_revision,
        operation_id=operation_id,
        operation_kind="design.finalize",
        operation_payload={"session_id": session_id},
        session_id=session_id,
        apply=lambda: finalize_design_session(session_id, project_root=project_root),
        recovery_paths=("themes",),
    )
    return {**result, "snapshot": project_snapshot(project_root, session_id)}


def undo_operation(
    *, project_root: Path, target_operation_id: str, expected_revision: int, operation_id: str
) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    init_protocol_project(root)
    target = _known_operation(root, target_operation_id)
    if not target or target.get("status") != "applied" or not target.get("undoable", True):
        raise ValidationError(f"operation cannot be undone: {target_operation_id}")
    history = Path(target["history"])
    session_id = target.get("session_id")
    history_root = (_workspace(root) / "cache" / "history").resolve()
    try:
        history.resolve().relative_to(history_root)
    except ValueError as exc:
        raise ValidationError(f"undo history is outside the APSAL project: {target_operation_id}") from exc
    if not history.is_dir() or not (history / "project.json").is_file():
        raise ValidationError(f"undo history is missing: {target_operation_id}")

    def restore() -> dict[str, Any]:
        _restore_history(root, history, str(session_id) if session_id else None)
        restored_target = _known_operation(root, target_operation_id) or copy.deepcopy(target)
        restored_target["status"] = "undone"
        ledger = _operations(root)
        ledger["operations"][target_operation_id] = restored_target
        _atomic_json(_operation_path(root), ledger)
        return {"session_id": session_id, "undone_operation_id": target_operation_id}

    result = _mutation(
        root,
        expected_revision=expected_revision,
        operation_id=operation_id,
        operation_kind="project.undo",
        operation_payload={"target_operation_id": target_operation_id},
        session_id=str(session_id) if session_id else None,
        apply=restore,
        undoable=False,
        recovery_paths=("registry", "themes", "runs"),
    )
    return {
        **result,
        "snapshot": project_snapshot(root, str(session_id) if session_id else None),
    }


def load_studio_view(project_root: Path) -> dict[str, Any]:
    path = _view_path(project_root)
    default = {
        "schema_version": VIEW_SCHEMA_VERSION,
        "view_revision": 0,
        "nodes": {},
        "viewport": {},
    }
    if not path.is_file():
        return default
    try:
        value = load_json(path)
    except (OSError, json.JSONDecodeError, ValidationError):
        return {**default, "recovered_from_invalid_view": True}
    if value.get("schema_version") != VIEW_SCHEMA_VERSION:
        return {**default, "recovered_from_invalid_view": True}
    value.setdefault("schema_version", VIEW_SCHEMA_VERSION)
    value.setdefault("view_revision", 0)
    value.setdefault("nodes", {})
    value.setdefault("viewport", {})
    return value


def save_studio_view(project_root: Path, view: dict[str, Any]) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    init_protocol_project(root)
    with _project_lock(root):
        current = load_studio_view(root)
        next_view = {
            "schema_version": VIEW_SCHEMA_VERSION,
            "view_revision": int(current.get("view_revision", 0)) + 1,
            "nodes": view.get("nodes", {}),
            "viewport": view.get("viewport", {}),
            "selected_element_id": view.get("selected_element_id"),
            "expanded_cards": view.get("expanded_cards", []),
        }
        _atomic_json(_view_path(root), next_view)
    return next_view


def _meta(params: dict[str, Any], root: Path, prefix: str) -> tuple[int, str]:
    del root, prefix
    expected_value = params.get("expected_revision", params.get("expectedRevision"))
    operation_value = params.get("operation_id", params.get("operationId"))
    if expected_value is None:
        raise ValidationError("expected_revision is required for semantic writes")
    if not operation_value:
        raise ValidationError("operation_id is required for semantic writes")
    expected = int(expected_value)
    operation_id = str(operation_value)
    if not _OPERATION_ID_RE.fullmatch(operation_id):
        raise ValidationError("operation_id must be a safe 1-128 character token")
    return expected, operation_id


def handle_domain_method(method: str, params: dict[str, Any]) -> dict[str, Any]:
    root = Path(params.get("project_root") or Path.cwd()).expanduser().resolve()
    if method == "project.init":
        return init_protocol_project(root)
    if method in {"project.open", "project.snapshot"}:
        return project_snapshot(root, params.get("session_id"))
    if method == "project.undo":
        expected, operation_id = _meta(params, root, "UNDO")
        return undo_operation(
            project_root=root,
            target_operation_id=params["target_operation_id"],
            expected_revision=expected,
            operation_id=operation_id,
        )
    if method == "design.start":
        expected, operation_id = _meta(params, root, "START")
        result = start_project_design(
            params["brief"],
            project_root=root,
            expected_revision=expected,
            operation_id=operation_id,
            theme_id=params.get("theme_id"),
            name=params.get("name"),
            shot_count=int(params.get("shot_count", 9)),
            language=params.get("language", "auto"),
            set_strategy=params.get("set_strategy"),
        )
        return {**result, "snapshot": project_snapshot(root, result["session_id"])}
    if method == "design.present":
        return present_project_layer(root, params["session_id"], params["layer"])
    if method == "design.language":
        expected, operation_id = _meta(params, root, "LANGUAGE")
        result = _mutation(
            root,
            expected_revision=expected,
            operation_id=operation_id,
            operation_kind="design.language",
            operation_payload={
                "session_id": params["session_id"],
                "language": params["language"],
            },
            session_id=params["session_id"],
            apply=lambda: set_session_language(
                params["session_id"], params["language"], project_root=root
            ),
        )
        return {**result, "snapshot": project_snapshot(root, params["session_id"])}
    if method == "design.propose":
        expected, operation_id = _meta(params, root, "PROPOSE")
        result = propose_changes(
            project_root=root,
            session_id=params["session_id"],
            layer=params["layer"],
            decisions=params.get("decisions"),
            refs=params.get("refs"),
            expected_revision=expected,
            operation_id=operation_id,
            shots=params.get("shots"),
            reference_path=params.get("reference_path", params.get("referencePath")),
            reference_bindings=params.get("reference_bindings"),
            draft_assets=params.get("draft_assets"),
        )
        return {**result, "snapshot": project_snapshot(root, params["session_id"])}
    if method == "design.commit_preview":
        expected, operation_id = _meta(params, root, "APPLY")
        return apply_preview(
            project_root=root,
            session_id=params["session_id"],
            preview_id=params["preview_id"],
            expected_revision=expected,
            operation_id=operation_id,
        )
    if method == "design.reject_preview":
        expected, operation_id = _meta(params, root, "REJECT")
        result = reject_preview(
            project_root=root,
            session_id=params["session_id"],
            preview_id=params["preview_id"],
            expected_revision=expected,
            operation_id=operation_id,
        )
        return {**result, "snapshot": project_snapshot(root, params["session_id"])}
    if method == "design.commit_layer":
        expected, operation_id = _meta(params, root, "COMMIT")
        return commit_project_layer(
            project_root=root,
            session_id=params["session_id"],
            layer=params["layer"],
            expected_revision=expected,
            operation_id=operation_id,
            decisions=params.get("decisions"),
            refs=params.get("refs"),
            shots=params.get("shots"),
            reference_path=params.get("reference_path", params.get("referencePath")),
            reference_bindings=params.get("reference_bindings"),
            draft_assets=params.get("draft_assets"),
        )
    if method in {"design.finalize", "finalize_theme"}:
        expected, operation_id = _meta(params, root, "FINALIZE")
        return finalize_project(
            project_root=root,
            session_id=params["session_id"],
            expected_revision=expected,
            operation_id=operation_id,
        )
    if method == "generation.start":
        expected, operation_id = _meta(params, root, "RUN")
        result = _mutation(
            root,
            expected_revision=expected,
            operation_id=operation_id,
            operation_kind="generation.start",
            operation_payload={
                "session_id": params["session_id"],
                "confirmed": params.get("confirmed", False),
                "mode": params.get("mode", "generate"),
                "resume_run_id": params.get("resume_run_id"),
            },
            session_id=params["session_id"],
            undoable=False,
            recovery_paths=("runs",),
            apply=lambda: start_generation_run(
                params["session_id"],
                project_root=root,
                confirmed=params.get("confirmed", False),
                mode=params.get("mode", "generate"),
                resume_run_id=params.get("resume_run_id"),
            ),
        )
        return {**result, "snapshot": project_snapshot(root, params["session_id"])}
    if method == "generation.next":
        _require_compatible_manifest(root)
        return get_next_codex_job(params["run_id"], project_root=root)
    if method == "generation.record":
        expected, operation_id = _meta(params, root, "RESULT")
        result = _mutation(
            root,
            expected_revision=expected,
            operation_id=operation_id,
            operation_kind="generation.record",
            operation_payload={
                "run_id": params["run_id"],
                "shot_id": params["shot_id"],
                "status": params["status"],
                "output_path": params.get("output_path"),
                "artifact_uri": params.get("artifact_uri"),
                "provider_metadata": params.get("provider_metadata"),
                "error": params.get("error"),
            },
            session_id=project_manifest(root).get("active_session_id"),
            undoable=False,
            recovery_paths=("runs",),
            apply=lambda: record_generation_result(
                params["run_id"],
                params["shot_id"],
                params["status"],
                project_root=root,
                output_path=Path(params["output_path"]) if params.get("output_path") else None,
                artifact_uri=params.get("artifact_uri"),
                provider_metadata=params.get("provider_metadata"),
                error=params.get("error"),
            ),
        )
        return {**result, "snapshot": project_snapshot(root)}
    if method == "qa.record":
        expected, operation_id = _meta(params, root, "QA")
        result = _mutation(
            root,
            expected_revision=expected,
            operation_id=operation_id,
            operation_kind="qa.record",
            operation_payload={
                "run_id": params["run_id"],
                "shot_id": params["shot_id"],
                "status": params["status"],
                "findings": params.get("findings"),
            },
            session_id=project_manifest(root).get("active_session_id"),
            undoable=False,
            recovery_paths=("runs",),
            apply=lambda: record_model_visual_qa(
                params["run_id"],
                params["shot_id"],
                params["status"],
                project_root=root,
                findings=params.get("findings"),
            ),
        )
        return {**result, "snapshot": project_snapshot(root)}
    if method == "studio.view.get":
        return load_studio_view(root)
    if method == "studio.view.save":
        return save_studio_view(root, params.get("view", {}))
    raise ValidationError(f"unknown APSAL protocol method: {method}")
