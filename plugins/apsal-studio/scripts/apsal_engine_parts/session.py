# Executed by apsal_engine/__init__.py into that module. Not an importable submodule.
from __future__ import annotations

import hashlib
import html
import datetime as dt
import importlib.util
import io
import json
import os
import re
import shutil
import struct
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path
from typing import Any

def _session_dir(project_root: Path, session_id: str) -> Path:
    session_id = _safe_part(session_id, "session id")
    return _inside(project_root / ".apsal" / "drafts", project_root / ".apsal" / "drafts" / session_id)


def _session_paths(project_root: Path, session_id: str) -> tuple[Path, Path, Path]:
    root = _session_dir(project_root, session_id)
    return root, root / "session.json", root / "theme.apsal.yaml"


def _write_session(session: dict[str, Any], theme: dict[str, Any], project_root: Path) -> None:
    root, session_path, theme_path = _session_paths(project_root, session["session_id"])
    _mkdir_private(root)
    session["updated_at"] = _utc_now()
    session["theme_digest"] = digest(theme)
    _atomic_write_text(theme_path, dump_yaml(theme), 0o600)
    _write_private_json(session, session_path)


def load_design_session(session_id: str, project_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    project_root = project_root.expanduser().resolve()
    _, session_path, theme_path = _session_paths(project_root, session_id)
    if not session_path.is_file() or not theme_path.is_file():
        raise ValidationError(f"unknown design session: {session_id}")
    session = load_json(session_path)
    theme = load_document(theme_path)
    if session.get("theme_digest") != digest(theme):
        raise ValidationError(f"design session draft digest mismatch: {session_id}")
    return session, theme


def _new_theme_id() -> str:
    return f"APSAL-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def start_design_session(
    brief: str, *, project_root: Path, theme_id: str | None = None, name: str | None = None,
    shot_count: int = 9, home: Path | None = None, language: str | None = "auto",
    set_strategy: str | None = None, authoring_mode: str = "guided",
    reference_path: Path | None = None, reference_bindings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Start a resumable five-layer, thirteen-element natural-language design session."""
    brief = brief.strip()
    if not brief: raise ValidationError("creative brief cannot be empty")
    if authoring_mode not in AUTHORING_MODES: raise ValidationError(f"authoring mode must be one of {list(AUTHORING_MODES)}")
    if authoring_mode != "automatic" and (reference_path is not None or reference_bindings):
        raise ValidationError("start-time reference bindings are only used by automatic authoring; guided mode binds them during worldbuilding confirmation")
    project_root = project_root.expanduser().resolve(); init_workspace(project_root, home)
    theme_id = theme_id or _new_theme_id()
    theme = new_semantic_theme(theme_id, (name or brief[:80]).strip(), shot_count, native_4k=False, live_action=True)
    theme["output"] = codex_imagegen_output_contract(shot_count)
    for shot in theme["shots"]: shot["output_filename"] = f"{theme_id.lower()}_{int(shot['shot_id'].split('_')[-1]):02d}.png"
    chosen_strategy = set_strategy or infer_set_strategy(brief)
    apply_set_strategy(theme, chosen_strategy)
    theme["element_decisions"] = propose_element_decisions(brief, theme)
    theme["interaction_model"] = "five_layer_thirteen_element"
    session_id = f"SESSION-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:10].upper()}"
    session = {
        "schema_version": "0.7.0", "interaction_model": "five_layer_thirteen_element",
        "session_id": session_id, "brief": brief, "set_strategy": theme["set_strategy"], "authoring_mode": authoring_mode,
        "project_root": str(project_root), "state": "direction_pending", "shot_count": shot_count,
        "language": resolve_interface_language(brief, language),
        "layers": {
            layer: {"status": "pending", "roles": list(LAYER_ROLES[layer]), "selection": [], "confirmed_at": None}
            for layer in CREATIVE_LAYERS
        },
        "private_references": [], "core_visual_anchor_reference_id": None,
        "automatic_reference_path": str(reference_path) if reference_path is not None else None,
        "automatic_reference_bindings": list(reference_bindings or []),
        "memory_offers": [], "invalidations": [], "created_at": _utc_now(), "updated_at": _utc_now(),
        "theme_artifact": None,
    }
    _write_session(session, theme, project_root)
    if authoring_mode == "automatic" and session_interface_language(session)["status"] == "confirmed":
        return complete_design_session_automatically(session_id, project_root=project_root, home=home)
    return session


def set_session_language(session_id: str, language: str, *, project_root: Path) -> dict[str, Any]:
    """Set creator-facing language without changing photographic generation intent."""
    project_root = project_root.expanduser().resolve()
    session, theme = load_design_session(session_id, project_root)
    session["language"] = resolve_interface_language("", language)
    _write_session(session, theme, project_root)
    if session.get("authoring_mode") == "automatic":
        return complete_design_session_automatically(session_id, project_root=project_root)
    return session


def set_authoring_mode(
    session_id: str, authoring_mode: str, *, project_root: Path,
    language: str | None = None, home: Path | None = None,
) -> dict[str, Any]:
    """Switch a resumable session between guided and automatic authoring."""
    if authoring_mode not in AUTHORING_MODES: raise ValidationError(f"authoring mode must be one of {list(AUTHORING_MODES)}")
    project_root = project_root.expanduser().resolve(); session, theme = load_design_session(session_id, project_root)
    if session["state"] in {"generating", "completed", "partial"}: raise ValidationError("generation has already started; authoring mode can no longer change")
    session["authoring_mode"] = authoring_mode
    if language and language != "auto": session["language"] = resolve_interface_language("", language)
    _write_session(session, theme, project_root)
    if authoring_mode == "automatic" and session_interface_language(session)["status"] == "confirmed":
        return complete_design_session_automatically(session_id, project_root=project_root, home=home)
    return session


def complete_design_session_automatically(
    session_id: str, *, project_root: Path, home: Path | None = None,
) -> dict[str, Any]:
    """Choose the best valid DNA per layer, confirm all proposals, and package the theme."""
    project_root = project_root.expanduser().resolve(); session, _ = load_design_session(session_id, project_root)
    if session.get("authoring_mode") != "automatic": raise ValidationError("automatic completion requires authoring_mode=automatic")
    if session_interface_language(session)["status"] != "confirmed": return session
    if session["state"] == "ready": return session
    if session["state"] in {"generating", "completed", "partial"}: raise ValidationError("generation has already started; automatic authoring cannot run")
    for layer in CREATIVE_LAYERS:
        if session["layers"][layer]["status"] == "confirmed": continue
        recommendation = recommend_layer_dna(
            session["brief"], layer, project_root=project_root, home=home,
            session_id=session_id, limit_per_type=1,
        )
        refs = []
        for asset_type in LAYER_TYPES[layer]:
            candidates = recommendation["by_type"].get(asset_type, [])
            if not candidates: raise ValidationError(f"automatic authoring could not find required {asset_type} DNA for {layer}")
            refs.append(asset_ref(candidates[0]["record"]["asset"]))
        session = commit_element_layer(
            session_id, layer, refs, project_root=project_root, home=home,
            reference_path=Path(session["automatic_reference_path"]) if layer == "worldbuilding" and session.get("automatic_reference_path") else None,
            reference_bindings=session.get("automatic_reference_bindings") if layer == "worldbuilding" else None,
        )
        if layer == "worldbuilding":
            session, theme = load_design_session(session_id, project_root)
            session.pop("automatic_reference_path", None); session.pop("automatic_reference_bindings", None)
            _write_session(session, theme, project_root)
    return finalize_design_session(session_id, project_root=project_root, home=home)


def _stage_preview_copy(layer: str, locale: str) -> tuple[str, str, str]:
    """Return fully localized, creator-facing copy for a semantic stage preview."""
    if locale == "zh-CN":
        copy = {
            "direction": ("创作命题与情绪", "命题、情绪与套片基调", "内容 · 情绪"),
            "worldbuilding": ("人物与世界陈设", "人物、空间与妆造关系", "人物 · 世界 · 妆造"),
            "narrative": ("事件与叙事序列", "事件推进与九镜头节奏", "事件 · 序列"),
            "image": ("摄影与成像语言", "相机、灯光、风格与色调", "相机 · 灯光 · 风格 · 色调后期"),
            "delivery": ("执行与验证", "单镜执行、输出与质量检查", "任务 · 质量检查"),
        }
    else:
        copy = {
            "direction": ("Direction & Emotion", "Theme, emotion, and set tone", "Content · Emotion"),
            "worldbuilding": ("Subject & World", "Subject, space, and styling", "Subject · World · Look"),
            "narrative": ("Event & Sequence", "Event progression and nine-shot rhythm", "Event · Sequence"),
            "image": ("Photography Language", "Camera, light, style, and color", "Camera · Light · Style · Color/Post"),
            "delivery": ("Execution & QA", "One-job execution, output, and review", "Job · Quality Control"),
        }
    return copy[layer]


def build_stage_preview_svg(
    theme: dict[str, Any], layer: str, *, locale: str = "zh-CN", status: str | None = None,
) -> bytes:
    """Build a deterministic semantic thumbnail; it is never a generation reference."""
    if layer not in CREATIVE_LAYERS: raise ValidationError(f"unknown creative layer: {layer}")
    if locale not in SUPPORTED_INTERFACE_LANGUAGES: raise ValidationError(f"unsupported preview language: {locale}")
    decisions = theme.get("element_decisions", {})
    confirmed = all(decisions.get(role, {}).get("status") == "confirmed" for role in LAYER_ROLES[layer])
    state = status or ("confirmed" if confirmed else "proposed")
    title, subtitle, roles = _stage_preview_copy(layer, locale)
    state_label = ("已确认" if state == "confirmed" else "设计提案") if locale == "zh-CN" else ("CONFIRMED" if state == "confirmed" else "PROPOSAL")
    disclaimer = "语义缩略图 · 不作为生成参考图" if locale == "zh-CN" else "Semantic thumbnail · never a generation reference"
    accent, accent_dark = STAGE_PREVIEW_COLORS[layer]
    layer_index = CREATIVE_LAYERS.index(layer)
    seed = digest({"layer": layer, "decisions": {role: decisions.get(role, {}) for role in LAYER_ROLES[layer]}})
    nodes = []
    for index in range(6):
        value = int(seed[index * 2:index * 2 + 2], 16)
        x = 95 + index * 105
        y = 352 + (value % 92)
        radius = 7 + value % 7
        nodes.append(f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{accent}" fill-opacity="{0.38 + index * 0.07:.2f}"/>')
    progress = []
    for index, item in enumerate(CREATIVE_LAYERS):
        fill = STAGE_PREVIEW_COLORS[item][0] if index <= layer_index else "#3D3427"
        progress.append(f'<circle cx="{112 + index * 136}" cy="505" r="8" fill="{fill}"/>')
        if index < len(CREATIVE_LAYERS) - 1:
            progress.append(f'<path d="M{120 + index * 136} 505 H{240 + index * 136}" stroke="#3D3427" stroke-width="2"/>')
    escaped = [html.escape(item, quote=True) for item in (title, subtitle, roles, state_label, disclaimer)]
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="768" height="576" viewBox="0 0 768 576" role="img" aria-labelledby="title desc" data-generation-input="false">
<title id="title">{escaped[0]}</title><desc id="desc">{escaped[1]}. {escaped[4]}</desc>
<rect width="768" height="576" rx="34" fill="#080606"/>
<rect x="28" y="28" width="712" height="520" rx="26" fill="#110D09" stroke="#3D3427"/>
<path d="M66 76 H702 M66 468 H702" stroke="#2F281E"/>
<rect x="66" y="76" width="8" height="176" rx="4" fill="{accent}"/>
<text x="98" y="112" fill="{accent}" font-family="system-ui,-apple-system,'PingFang SC','Microsoft YaHei',sans-serif" font-size="16" font-weight="700" letter-spacing="2">APSAL · {layer_index + 1:02d}</text>
<text x="98" y="169" fill="#F0E9DA" font-family="system-ui,-apple-system,'PingFang SC','Microsoft YaHei',sans-serif" font-size="34" font-weight="760">{escaped[0]}</text>
<text x="98" y="211" fill="#C9BDA2" font-family="system-ui,-apple-system,'PingFang SC','Microsoft YaHei',sans-serif" font-size="18">{escaped[1]}</text>
<rect x="98" y="244" width="544" height="42" rx="21" fill="{accent_dark}"/>
<text x="120" y="271" fill="{accent}" font-family="system-ui,-apple-system,'PingFang SC','Microsoft YaHei',sans-serif" font-size="16" font-weight="650">{escaped[2]}</text>
<g>{''.join(nodes)}</g><path d="M95 400 C200 330 298 452 410 371 S598 330 650 397" fill="none" stroke="{accent}" stroke-opacity=".44" stroke-width="2"/>
<rect x="570" y="95" width="110" height="34" rx="17" fill="{accent}"/><text x="625" y="117" text-anchor="middle" fill="#101411" font-family="system-ui,-apple-system,'PingFang SC','Microsoft YaHei',sans-serif" font-size="13" font-weight="800">{escaped[3]}</text>
<g>{''.join(progress)}</g>
<text x="66" y="535" fill="#8E8368" font-family="system-ui,-apple-system,'PingFang SC','Microsoft YaHei',sans-serif" font-size="12">{escaped[4]}</text>
</svg>'''
    return svg.encode("utf-8")


def stage_preview_cards(session: dict[str, Any], theme: dict[str, Any], locale: str) -> list[dict[str, Any]]:
    """Return all five localized progress thumbnails for the MCP card strip."""
    current = next((item for item in CREATIVE_LAYERS if session["layers"][item]["status"] != "confirmed"), None)
    cards = []
    for layer in CREATIVE_LAYERS:
        status = session["layers"][layer]["status"]
        title, subtitle, _ = _stage_preview_copy(layer, locale)
        svg = build_stage_preview_svg(theme, layer, locale=locale, status=status)
        cards.append({
            "layer": layer, "title": title, "summary": subtitle, "status": status,
            "status_label": ("已确认" if status == "confirmed" else "当前设计" if layer == current else "待确认") if locale == "zh-CN" else ("Confirmed" if status == "confirmed" else "Current" if layer == current else "Pending"),
            "current": layer == current, "alt_text": f"{title} — {subtitle}",
            "data_uri": "data:image/svg+xml;charset=utf-8," + urllib.parse.quote(svg.decode("utf-8")),
            "generation_input": False,
        })
    return cards


def present_element_layer(session_id: str, layer: str, *, project_root: Path) -> dict[str, Any]:
    """Return creator-facing text cards for one layer without exposing YAML or JSON."""
    if layer not in CREATIVE_LAYERS: raise ValidationError(f"unknown creative layer: {layer}")
    session, theme = load_design_session(session_id, project_root.resolve())
    if session.get("schema_version") != "0.7.0": raise ValidationError("element layers require an APSAL Studio 0.7 session")
    language = session_interface_language(session)
    if language["status"] != "confirmed":
        raise ValidationError("Choose English or Chinese before continuing / 请先选择 English 或中文")
    locale = language["code"]
    layer_spec = next(item for item in load_creative_layers()["layers"] if item["id"] == layer)
    cards = []
    for role in LAYER_ROLES[layer]:
        role_meta = load_semantic_registry()["roles"][role]; decision = theme["element_decisions"][role]
        card = {
            "role": role, "title": role_meta["en"] if locale == "en" else role_meta["zh"],
            "title_en": role_meta["en"], "title_zh": role_meta["zh"],
            "question": role_meta["question_en"] if locale == "en" else role_meta["question_zh"],
            "question_en": role_meta["question_en"], "question_zh": role_meta["question_zh"],
            "status": decision["status"], "source": decision["source"],
            "intent": decision["intent"], "values": decision["values"], "observable": decision["observable"],
            "must_preserve": decision["must_preserve"], "qa_expectations": decision["qa_expectations"],
            "basis": decision["basis"], "dna_refs": decision.get("dna_refs", []),
        }
        card.update(element_display_projection(role, decision, session["brief"], locale))
        cards.append(card)
    result = {
        "session_id": session_id, "layer": layer, "language": locale,
        "title": layer_spec["en"] if locale == "en" else layer_spec["zh"],
        "title_en": layer_spec["en"], "title_zh": layer_spec["zh"],
        "layer_label": layer_spec["en"] if locale == "en" else layer_spec["zh"],
        "roles": list(LAYER_ROLES[layer]), "required_dna_types": list(LAYER_TYPES[layer]),
        "cards": cards, "status": session["layers"][layer]["status"],
        "stage_previews": stage_preview_cards(session, theme, locale),
        "preview_policy": "semantic_ui_only_never_generation_input",
    }
    if layer == "direction": result["emotion_taxonomy"] = load_creative_layers()["emotion_taxonomy"]
    return result


def _resolve_layer_refs(
    refs: list[dict[str, str]], layer: str, project_root: Path, home: Path | None,
) -> list[dict[str, Any]]:
    required = set(LAYER_TYPES[layer])
    if not required:
        if refs: raise ValidationError(f"{layer} layer does not select Registry DNA")
        return []
    records = load_layered_registry(project_root, home); by_key = {_asset_key(record["asset"]): record for record in records}
    selected = []
    for ref in refs:
        key = tuple(str(ref.get(name, "")) for name in ("namespace", "id", "type", "version")); record = by_key.get(key)
        if not record: raise ValidationError(f"unresolved DNA reference {_ref_label(key)}")
        if ref.get("content_digest") and ref["content_digest"] != digest(record["asset"]): raise ValidationError(f"DNA digest mismatch for {_ref_label(key)}")
        selected.append(record)
    actual = [record["asset"]["type"] for record in selected]
    if set(actual) != required or len(actual) != len(required): raise ValidationError(f"{layer} layer requires exactly one of {sorted(required)}")
    return selected


def _decision_compare(value: dict[str, Any]) -> dict[str, Any]:
    return {key: value.get(key) for key in ("intent", "values", "observable", "must_preserve", "qa_expectations", "basis")}


def _resolve_refs(
    refs: list[dict[str, str]], stage: str, project_root: Path, home: Path | None,
) -> list[dict[str, Any]]:
    records = load_layered_registry(project_root, home)
    by_key = {_asset_key(record["asset"]): record for record in records}
    selected: list[dict[str, Any]] = []
    for ref in refs:
        key = tuple(str(ref.get(name, "")) for name in ("namespace", "id", "type", "version"))
        record = by_key.get(key)
        if not record: raise ValidationError(f"unresolved DNA reference {_ref_label(key)}")
        if ref.get("content_digest") and ref["content_digest"] != digest(record["asset"]):
            raise ValidationError(f"DNA digest mismatch for {_ref_label(key)}")
        selected.append(record)
    required = set(STAGE_TYPES[stage]); actual = [record["asset"]["type"] for record in selected]
    if set(actual) != required or len(actual) != len(required):
        raise ValidationError(f"{stage} stage requires exactly one of {sorted(required)}")
    return selected


def store_private_reference(
    path: Path, *, home: Path | None = None, reference_id: str | None = None,
    uses: list[str] | None = None, allowed_uses: list[str] | None = None,
    forbidden_uses: list[str] | None = None, applies_to: list[str] | None = None,
    rights: dict[str, Any] | None = None, expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Copy a user reference into the private content-addressed vault."""
    source = path.expanduser().resolve()
    if not source.is_file(): raise ValidationError(f"reference image not found: {source}")
    data = source.read_bytes(); sha = hashlib.sha256(data).hexdigest()
    if expected_sha256 and expected_sha256 != sha: raise ValidationError(f"reference digest mismatch for {source.name}")
    reference_id = reference_id or f"REF_{sha[:12].upper()}"
    if not SAFE_ASSET_ID.fullmatch(reference_id): raise ValidationError("reference_id must match ^[A-Z][A-Z0-9_]*$")
    uses = uses or ["identity"]
    if not uses or set(uses) - REFERENCE_USES: raise ValidationError(f"reference uses must be selected from {sorted(REFERENCE_USES)}")
    allowed_uses = allowed_uses or list(uses)
    forbidden_uses = forbidden_uses or [item for item in sorted(REFERENCE_USES) if item not in uses]
    if "identity" not in uses and "identity" not in forbidden_uses: forbidden_uses.append("identity")
    applies_to = applies_to or ["*"]
    rights = rights or {
        "copyright_status": "user_provided_unverified", "portrait_rights": "user_provided_unverified",
        "attribution": "User-provided private reference", "redistribution_allowed": False,
    }
    home = (home or apsal_home()).resolve(); root = home / "vault" / "sha256" / sha[:2] / sha
    suffix = source.suffix.lower() if re.fullmatch(r"\.[a-z0-9]{1,8}", source.suffix.lower()) else ".bin"
    _sanitize_reference_bytes(data, suffix)
    target = root / f"reference{suffix}"
    metadata = {
        "schema_version": "0.5.0", "reference_id": reference_id, "original_sha256": sha, "sha256": sha,
        "size": len(data), "original_filename": source.name, "uses": uses,
        "allowed_uses": allowed_uses, "forbidden_uses": forbidden_uses, "applies_to": applies_to,
        "rights": rights, "rights_status": "private_user_provided_not_redistributable", "visibility": "private",
        "created_at": _utc_now(),
    }
    metadata_errors = validate_reference_metadata([metadata])
    if metadata_errors: raise ValidationError("\n".join(metadata_errors))
    for directory in (home, home / "vault", home / "vault" / "sha256", root.parent, root): _mkdir_private(directory)
    if not target.exists(): target.write_bytes(data)
    try: target.chmod(0o600)
    except OSError: pass
    metadata_path = root / "reference.json"
    if metadata_path.exists():
        existing = load_json(metadata_path)
        if existing.get("original_sha256") not in {None, sha}: raise ValidationError("vault reference digest conflict")
    _write_private_json(metadata, metadata_path)
    return {**metadata, "vault_uri": f"vault:sha256:{sha}"}


def _vault_reference_path(vault_uri: str, home: Path | None = None) -> Path:
    if not vault_uri.startswith("vault:sha256:"): raise ValidationError("unsupported private reference URI")
    sha = vault_uri.rsplit(":", 1)[-1]
    if not re.fullmatch(r"[a-f0-9]{64}", sha): raise ValidationError("invalid private reference URI")
    root = (home or apsal_home()).resolve() / "vault" / "sha256" / sha[:2] / sha
    matches = sorted(path for path in root.glob("reference.*") if path.name != "reference.json")
    if len(matches) != 1: raise ValidationError(f"vault reference is missing or ambiguous: {sha}")
    if hashlib.sha256(matches[0].read_bytes()).hexdigest() != sha: raise ValidationError(f"vault reference digest mismatch: {sha}")
    return matches[0]


def _validate_shot_replacement(shots: list[dict[str, Any]], expected_count: int) -> None:
    if len(shots) != expected_count: raise ValidationError(f"scene stage requires {expected_count} shots")
    ids = [shot.get("shot_id") for shot in shots]; filenames = [shot.get("output_filename") for shot in shots]
    if len(set(ids)) != len(ids) or len(set(filenames)) != len(filenames):
        raise ValidationError("scene shots require unique IDs and output filenames")


def commit_element_layer(
    session_id: str, layer: str, refs: list[dict[str, str]], *, project_root: Path,
    decisions: dict[str, dict[str, Any]] | None = None, home: Path | None = None,
    shots: list[dict[str, Any]] | None = None, reference_path: Path | None = None,
    reference_bindings: list[dict[str, Any]] | None = None,
    draft_assets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Confirm one of five creator layers and its complete subset of thirteen element decisions."""
    if layer not in CREATIVE_LAYERS: raise ValidationError(f"unknown creative layer: {layer}")
    project_root = project_root.expanduser().resolve(); session, theme = load_design_session(session_id, project_root)
    if session.get("schema_version") != "0.7.0": raise ValidationError("five-layer confirmation requires an APSAL Studio 0.7 session")
    if session_interface_language(session)["status"] != "confirmed": raise ValidationError("confirm the session language before confirming creative layers")
    if session["state"] in {"ready", "generating", "completed", "partial"}: raise ValidationError("a finalized or generated theme cannot be edited; create a new theme version")
    layer_index = CREATIVE_LAYERS.index(layer)
    for prior in CREATIVE_LAYERS[:layer_index]:
        if session["layers"][prior]["status"] != "confirmed": raise ValidationError(f"confirm {prior} before {layer}")

    proposed_assets = [json.loads(json.dumps(asset)) for asset in (draft_assets or [])]
    for asset in proposed_assets:
        if asset.get("type") not in LAYER_TYPES[layer]: raise ValidationError(f"draft DNA type {asset.get('type')} does not belong to {layer}")
        if "discovery" not in asset: asset["discovery"] = suggest_discovery_metadata(asset, session["brief"])
        errors = validate_registry_asset(asset)
        if errors: raise ValidationError("\n".join(errors))
        target = _registry_asset_path(project_root / ".apsal" / "registry", asset)
        if target.exists() and digest(load_json(target)) != digest(asset): raise ValidationError(f"immutable DNA conflict for {_ref_label(_asset_key(asset))}")
    created_assets = [save_registry_asset(asset, scope="project", project_root=project_root, home=home) for asset in proposed_assets]
    if proposed_assets:
        # Discovery metadata may be derived immediately before an asset is
        # written.  Always resolve a just-created draft by the digest of the
        # bytes that actually became immutable Registry content, not by a
        # caller's pre-enrichment draft digest.
        created_refs = {_asset_key(asset): created["ref"] for asset, created in zip(proposed_assets, created_assets)}
        if refs:
            refs = [created_refs.get(tuple(str(ref.get(name, "")) for name in ("namespace", "id", "type", "version")), ref) for ref in refs]
        else:
            refs = list(created_refs.values())
    records = _resolve_layer_refs(refs, layer, project_root, home)
    next_selection = [asset_ref(record["asset"]) for record in records]
    selected_types = set(LAYER_TYPES[layer])
    theme["dna"] = [ref for ref in theme["dna"] if ref["type"] not in selected_types]
    theme["dna"].extend(next_selection); theme["dna"].sort(key=lambda ref: CATEGORIES.index(ref["type"]))

    shots_changed = shots is not None and digest(shots) != digest(theme["shots"])
    if shots is not None:
        if layer != "narrative": raise ValidationError("shot changes are only allowed in the narrative layer")
        _validate_shot_replacement(shots, session["shot_count"]); theme["shots"] = shots

    bound_references: list[dict[str, Any]] = []; reference_changed = False; requested_anchor_ids: list[str] = []
    if reference_path is not None:
        if layer != "worldbuilding": raise ValidationError("identity references belong to the worldbuilding layer")
        bound_references.append(store_private_reference(reference_path, home=home))
    for binding in reference_bindings or []:
        if not isinstance(binding, dict) or not binding.get("path"): raise ValidationError("reference binding requires a path")
        stored = store_private_reference(
            Path(binding["path"]), home=home, reference_id=binding.get("reference_id"), uses=binding.get("uses"),
            allowed_uses=binding.get("allowed_uses"), forbidden_uses=binding.get("forbidden_uses"),
            applies_to=binding.get("applies_to"), rights=binding.get("rights"), expected_sha256=binding.get("expected_sha256"),
        )
        bound_references.append(stored)
        if binding.get("core_visual_anchor") is True: requested_anchor_ids.append(stored["reference_id"])
    if len(set(requested_anchor_ids)) > 1: raise ValidationError("only one reference may be the core visual anchor")
    for stored in bound_references:
        previous = next((item for item in session["private_references"] if item.get("reference_id") == stored["reference_id"]), None)
        if previous != stored:
            session["private_references"] = [item for item in session["private_references"] if item.get("reference_id") != stored["reference_id"]]
            session["private_references"].append(stored); reference_changed = True
        public_metadata = {key: value for key, value in stored.items() if key not in {"vault_uri", "visibility", "created_at", "size"}}
        theme.setdefault("references", []); theme["references"] = [item for item in theme["references"] if item.get("reference_id") != stored["reference_id"]]
        theme["references"].append(public_metadata); theme["references"].sort(key=lambda item: item["reference_id"])
        if stored["rights"].get("redistribution_allowed") is not True: theme["distribution"] = "private_only"
    if bound_references:
        known_reference_ids = {item["reference_id"] for item in theme.get("references", [])}
        existing_anchor = theme.get("core_visual_anchor_reference_id")
        preferred = next(iter(set(requested_anchor_ids)), None)
        if preferred is None and existing_anchor in known_reference_ids: preferred = existing_anchor
        if preferred is None:
            preferred = next((item["reference_id"] for item in theme["references"] if "identity" in item.get("uses", [])), None)
        if preferred is None: preferred = theme["references"][0]["reference_id"]
        if theme.get("core_visual_anchor_reference_id") != preferred: reference_changed = True
        theme["core_visual_anchor_reference_id"] = preferred
        session["core_visual_anchor_reference_id"] = preferred

    submitted = decisions or {}
    unknown_roles = set(submitted) - set(LAYER_ROLES[layer])
    if unknown_roles: raise ValidationError(f"{layer} decisions contain roles outside the layer: {sorted(unknown_roles)}")
    previous_decisions = {role: _decision_compare(theme["element_decisions"][role]) for role in LAYER_ROLES[layer]}
    previous_strategy = theme.get("set_strategy")
    confirmed_selections = [
        ref for prior in CREATIVE_LAYERS[:layer_index] for ref in session["layers"][prior].get("selection", [])
    ] + next_selection
    mapping = load_semantic_registry()["dna_to_protocol"]
    automatic_confirmation = session.get("authoring_mode") == "automatic"
    confirmation_source = "automatic_default" if automatic_confirmation else "creator_confirmed"
    confirmation_basis = "automatic_mode_selection" if automatic_confirmation else "creator_confirmation"
    for role in LAYER_ROLES[layer]:
        current = json.loads(json.dumps(theme["element_decisions"][role])); supplied = submitted.get(role, {})
        if not isinstance(supplied, dict): raise ValidationError(f"{layer}.{role}: decision must be an object")
        for key in ("intent", "observable", "must_preserve", "qa_expectations", "basis"):
            if key in supplied: current[key] = supplied[key]
        if "values" in supplied:
            if not isinstance(supplied["values"], dict): raise ValidationError(f"{layer}.{role}.values must be an object")
            current["values"] = {**current.get("values", {}), **supplied["values"]}
        role_refs = [ref for ref in confirmed_selections if role in mapping.get(ref["type"], [])]
        current.update({
            "role": role, "layer": layer, "status": "confirmed", "source": confirmation_source,
            "dna_refs": role_refs, "confirmed_at": _utc_now(),
        })
        if confirmation_basis not in current["basis"]: current["basis"].append(confirmation_basis)
        theme["element_decisions"][role] = current
    if layer == "direction":
        next_strategy = theme["element_decisions"]["content"].get("values", {}).get("set_strategy")
        if next_strategy is not None:
            if next_strategy not in SET_STRATEGIES: raise ValidationError(f"direction.content.values.set_strategy must be one of {list(SET_STRATEGIES)}")
            session["set_strategy"] = next_strategy
            if next_strategy != previous_strategy:
                apply_set_strategy(theme, next_strategy)
                refreshed = propose_element_decisions(session["brief"], theme)
                for later in CREATIVE_LAYERS[1:]:
                    for later_role in LAYER_ROLES[later]: theme["element_decisions"][later_role] = refreshed[later_role]
    errors = validate_element_decisions(theme["element_decisions"], require_confirmed=False)
    if errors: raise ValidationError("\n".join(errors))

    changed = (
        session["layers"][layer].get("selection") != next_selection or shots_changed or reference_changed
        or previous_decisions != {role: _decision_compare(theme["element_decisions"][role]) for role in LAYER_ROLES[layer]}
    )
    session["layers"][layer] = {
        "status": "confirmed", "roles": list(LAYER_ROLES[layer]), "selection": next_selection,
        "confirmed_at": _utc_now(), "created_project_assets": created_assets,
        "reference_ids": [item["reference_id"] for item in bound_references],
    }
    resolved_home = (home or apsal_home()).resolve()
    for record in records:
        _append_usage_event({"event": "dna_selection", "outcome": "selected", "stage": layer, "ref": asset_ref(record["asset"]), "context": _detect_recommendation_context(session["brief"])}, resolved_home)
    existing_offer_keys = {tuple(item.get("ref", {}).get(name, "") for name in ("namespace", "id", "type", "version")) for item in session.get("memory_offers", [])}
    for record in records:
        key = _asset_key(record["asset"])
        if record["scope"] != "project" or _registry_asset_path(resolved_home / "registry", record["asset"]).is_file() or key in existing_offer_keys: continue
        session["memory_offers"].append({
            "offer_id": f"MEMORY-{uuid.uuid4().hex[:10].upper()}", "status": "pending", "stage": layer,
            "ref": asset_ref(record["asset"]), "title": record["asset"]["id"],
            "reason": "New or revised project DNA can be reused and recommended across future projects.",
            "discovery": record["asset"].get("discovery"),
            "tag_confirmation_required": record["asset"].get("discovery", {}).get("source") != "creator_confirmed",
            "options": ["save_personal", "project_only", "not_now"],
        })
    if changed:
        for later in CREATIVE_LAYERS[layer_index + 1:]:
            if session["layers"][later]["status"] == "confirmed": session["invalidations"].append({"source": layer, "invalidated": later, "at": _utc_now()})
            session["layers"][later] = {"status": "pending", "roles": list(LAYER_ROLES[later]), "selection": [], "confirmed_at": None}
            for role in LAYER_ROLES[later]:
                stale = theme["element_decisions"][role]; stale["status"] = "proposed"
                stale["source"] = "system_policy" if role in {"job", "quality_control"} else "proposed_from_brief"
                stale.pop("confirmed_at", None); stale["dna_refs"] = []
        session["theme_artifact"] = None
    pending = next((item for item in CREATIVE_LAYERS if session["layers"][item]["status"] != "confirmed"), None)
    session["state"] = f"{pending}_pending" if pending else "review_pending"
    _write_session(session, theme, project_root)
    return session


def commit_session_stage(
    session_id: str, stage: str, refs: list[dict[str, str]], *, project_root: Path,
    home: Path | None = None, shots: list[dict[str, Any]] | None = None,
    reference_path: Path | None = None, reference_bindings: list[dict[str, Any]] | None = None,
    draft_assets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Confirm or revise one interaction stage and invalidate every affected downstream stage."""
    if stage not in INTERACTION_STAGES: raise ValidationError(f"unknown interaction stage: {stage}")
    project_root = project_root.expanduser().resolve(); session, theme = load_design_session(session_id, project_root)
    if session.get("schema_version") == "0.7.0": raise ValidationError("this session uses five-layer confirmation; call commit_element_layer")
    if session["state"] in {"ready", "generating", "completed", "partial"}:
        raise ValidationError("a finalized or generated theme cannot be edited; create a new theme version")
    proposed_assets = [json.loads(json.dumps(asset)) for asset in (draft_assets or [])]
    for asset in proposed_assets:
        if asset.get("type") not in STAGE_TYPES[stage]:
            raise ValidationError(f"draft DNA type {asset.get('type')} does not belong to {stage}")
        if "discovery" not in asset: asset["discovery"] = suggest_discovery_metadata(asset, session["brief"])
        errors = validate_registry_asset(asset)
        if errors: raise ValidationError("\n".join(errors))
        target = _registry_asset_path(project_root / ".apsal" / "registry", asset)
        if target.exists() and digest(load_json(target)) != digest(asset):
            raise ValidationError(f"immutable DNA conflict for {_ref_label(_asset_key(asset))}")
    created_assets = []
    for asset in proposed_assets:
        created_assets.append(save_registry_asset(asset, scope="project", project_root=project_root, home=home))
    if not refs and proposed_assets:
        refs = [asset_ref(asset) for asset in proposed_assets]
    records = _resolve_refs(refs, stage, project_root, home)
    resolved_home = (home or apsal_home()).resolve()
    stage_index = INTERACTION_STAGES.index(stage)
    for later in INTERACTION_STAGES[:stage_index]:
        if session["stages"][later]["status"] != "confirmed":
            raise ValidationError(f"confirm {later} before {stage}")
    selected_types = set(STAGE_TYPES[stage])
    next_selection = [asset_ref(record["asset"]) for record in records]
    shots_changed = shots is not None and digest(shots) != digest(theme["shots"])
    reference_changed = False; bound_references: list[dict[str, Any]] = []
    theme["dna"] = [ref for ref in theme["dna"] if ref["type"] not in selected_types]
    theme["dna"].extend(next_selection)
    theme["dna"].sort(key=lambda ref: CATEGORIES.index(ref["type"]))
    if shots is not None:
        if stage != "scene": raise ValidationError("shot changes are only allowed in the scene stage")
        _validate_shot_replacement(shots, session["shot_count"])
        theme["shots"] = shots
    if reference_path is not None:
        if stage != "character": raise ValidationError("private references belong to the character stage")
        stored = store_private_reference(reference_path, home=home)
        bound_references.append(stored)
    for binding in reference_bindings or []:
        if not isinstance(binding, dict) or not binding.get("path"): raise ValidationError("reference binding requires a path")
        stored = store_private_reference(
            Path(binding["path"]), home=home, reference_id=binding.get("reference_id"), uses=binding.get("uses"),
            allowed_uses=binding.get("allowed_uses"), forbidden_uses=binding.get("forbidden_uses"),
            applies_to=binding.get("applies_to"), rights=binding.get("rights"), expected_sha256=binding.get("expected_sha256"),
        )
        bound_references.append(stored)
    for stored in bound_references:
        previous = next((item for item in session["private_references"] if item.get("reference_id") == stored["reference_id"]), None)
        if previous != stored:
            session["private_references"] = [item for item in session["private_references"] if item.get("reference_id") != stored["reference_id"]]
            session["private_references"].append(stored); reference_changed = True
        public_metadata = {key: value for key, value in stored.items() if key not in {"vault_uri", "visibility", "created_at", "size"}}
        theme.setdefault("references", [])
        theme["references"] = [item for item in theme["references"] if item.get("reference_id") != stored["reference_id"]]
        theme["references"].append(public_metadata)
        theme["references"].sort(key=lambda item: item["reference_id"])
        if stored["rights"].get("redistribution_allowed") is not True: theme["distribution"] = "private_only"
    changed = session["stages"][stage].get("selection") != next_selection or shots_changed or reference_changed
    session["stages"][stage] = {
        "status": "confirmed", "selection": next_selection,
        "confirmed_at": _utc_now(), "created_project_assets": created_assets,
        "reference_ids": [item["reference_id"] for item in bound_references],
    }
    for record in records:
        _append_usage_event({"event": "dna_selection", "outcome": "selected", "stage": stage, "ref": asset_ref(record["asset"]), "context": _detect_recommendation_context(session["brief"])}, resolved_home)
    existing_offer_keys = {tuple(item.get("ref", {}).get(name, "") for name in ("namespace", "id", "type", "version")) for item in session.get("memory_offers", [])}
    for record in records:
        key = _asset_key(record["asset"])
        if record["scope"] != "project" or _registry_asset_path(resolved_home / "registry", record["asset"]).is_file() or key in existing_offer_keys: continue
        offer = {
            "offer_id": f"MEMORY-{uuid.uuid4().hex[:10].upper()}", "status": "pending", "stage": stage,
            "ref": asset_ref(record["asset"]), "title": record["asset"]["id"],
            "reason": "New or revised project DNA can be reused and recommended across future projects.",
            "discovery": record["asset"].get("discovery"),
            "tag_confirmation_required": record["asset"].get("discovery", {}).get("source") != "creator_confirmed",
            "options": ["save_personal", "project_only", "not_now"],
        }
        session["memory_offers"].append(offer)
    if changed:
        for later in INTERACTION_STAGES[stage_index + 1:]:
            previous = session["stages"][later]["status"]
            if previous == "confirmed":
                session["invalidations"].append({"source": stage, "invalidated": later, "at": _utc_now()})
            session["stages"][later] = {"status": "pending", "selection": [], "confirmed_at": None}
        session["theme_artifact"] = None
    pending = next((item for item in INTERACTION_STAGES if session["stages"][item]["status"] != "confirmed"), None)
    session["state"] = f"{pending}_pending" if pending else "review_pending"
    _write_session(session, theme, project_root)
    return session


def resolve_dna_memory_offer(
    session_id: str, offer_id: str, action: str, *, project_root: Path, home: Path | None = None,
) -> dict[str, Any]:
    if action not in {"save_personal", "project_only", "not_now"}:
        raise ValidationError("memory action must be save_personal, project_only, or not_now")
    project_root = project_root.resolve(); home = (home or apsal_home()).resolve()
    session, theme = load_design_session(session_id, project_root)
    offer = next((item for item in session.get("memory_offers", []) if item.get("offer_id") == offer_id), None)
    if not offer: raise ValidationError(f"unknown DNA memory offer: {offer_id}")
    if offer.get("status") != "pending": raise ValidationError(f"DNA memory offer is already resolved: {offer_id}")
    result = None
    if action == "save_personal":
        result = promote_registry_asset(offer["ref"], project_root=project_root, home=home)
        _append_usage_event({"event": "dna_memory", "outcome": "remembered", "ref": offer["ref"], "session_id": session_id}, home)
    offer.update({"status": "saved" if action == "save_personal" else action, "resolved_at": _utc_now()})
    _write_session(session, theme, project_root)
    return {"offer": offer, "personal_asset": result, "next_action": "Continue the current design session; future recommendations now include this preference." if action == "save_personal" else "Keep the DNA in the current project only."}


def _theme_dir(project_root: Path, theme: dict[str, Any]) -> Path:
    theme_id = _safe_part(theme["id"], "theme id"); version = _safe_part(theme["version"], "theme version")
    root = project_root / ".apsal" / "themes"
    return _inside(root, root / theme_id / version)


def _write_theme_prompts(compiled: dict[str, Any], root: Path) -> dict[str, str]:
    prompts = root / "prompts"; _mkdir_private(prompts)
    result: dict[str, str] = {}
    for shot in compiled["shots"]:
        shot_id = _safe_part(shot["shot_id"], "shot id")
        positive = prompts / f"{shot_id}.prompt.txt"; negative = prompts / f"{shot_id}.negative.txt"
        positive.write_text(shot["positive_prompt"] + "\n", encoding="utf-8")
        negative.write_text(shot["negative_prompt"] + "\n", encoding="utf-8")
        result[shot_id] = shot["prompt_digest"]
    return result


def finalize_design_session(
    session_id: str, *, project_root: Path, home: Path | None = None,
) -> dict[str, Any]:
    """Freeze a confirmed draft as YAML source, canonical JSON and three compiled targets."""
    project_root = project_root.expanduser().resolve(); session, theme = load_design_session(session_id, project_root)
    if session.get("schema_version") == "0.7.0":
        if any(session["layers"][layer]["status"] != "confirmed" for layer in CREATIVE_LAYERS):
            raise ValidationError("all five creative layers and thirteen elements must be confirmed before finalization")
        decision_errors = validate_element_decisions(theme.get("element_decisions"), require_confirmed=True)
        if decision_errors: raise ValidationError("\n".join(decision_errors))
    elif any(session["stages"][stage]["status"] != "confirmed" for stage in INTERACTION_STAGES):
        raise ValidationError("all four DNA stages must be confirmed before finalization")
    assets = registry_assets(project_root, home)
    errors = validate_theme(theme, assets)
    if errors: raise ValidationError("\n".join(errors))
    root = _theme_dir(project_root, theme)
    canonical_path = root / "theme.apsal.json"
    if canonical_path.exists():
        current = load_json(canonical_path)
        if digest(current) != digest(theme):
            raise ValidationError(f"immutable theme conflict for {theme['id']}@{theme['version']}")
    else:
        _mkdir_private(root / "compiled"); _mkdir_private(root / "references")
        (root / "theme.apsal.yaml").write_text(dump_yaml(theme), encoding="utf-8")
        write_canonical_json(theme, canonical_path)
        compiled = {target: compile_theme(theme, target, assets) for target in COMPILE_TARGETS}
        for target, value in compiled.items(): write_canonical_json(value, root / "compiled" / f"{target}.json")
        prompt_digests = _write_theme_prompts(compiled["image"], root)
        reference_manifest = {
            "schema_version": "0.5.0", "theme_id": theme["id"], "theme_version": theme["version"],
            "distribution": theme.get("distribution", "public"),
            "private_media_included": bool(session.get("private_references")),
            "redistribution_allowed": all(item.get("rights", {}).get("redistribution_allowed") is True for item in session.get("private_references", [])),
            "references": session.get("private_references", []),
        }
        write_canonical_json(reference_manifest, root / "references" / "reference_manifest.json")
        write_canonical_json(theme.get("rendering_contract", {"status": "not_declared_legacy"}), root / "references" / "rendering_contract.json")
        files = sorted(path for path in root.rglob("*") if path.is_file())
        manifest = {
            "schema_version": "0.5.0", "theme_id": theme["id"], "theme_version": theme["version"],
            "theme_digest": digest(theme), "engine_version": ENGINE_VERSION, "prompt_digests": prompt_digests,
            "reference_manifest_digest": digest(reference_manifest), "reference_count": len(reference_manifest["references"]),
            "distribution": reference_manifest["distribution"], "output_contract": theme["output"],
            "files": {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files},
            "visual_qa_status": "pending",
        }
        write_canonical_json(manifest, root / "artifact_manifest.json")
    reference_paths = {
        item["reference_id"]: _vault_reference_path(item["vault_uri"], home)
        for item in session.get("private_references", []) if item.get("vault_uri")
    }
    prompt_package_path, prompt_package_sha = pack_theme(
        theme, root / "exports", (root / "theme.apsal.yaml").read_bytes(), assets=assets,
        reference_paths=reference_paths, distribution=theme.get("distribution", "auto"),
    )
    artifact_manifest_path = root / "artifact_manifest.json"
    artifact_manifest = load_json(artifact_manifest_path)
    artifact_manifest["engine_version"] = ENGINE_VERSION
    artifact_manifest["prompt_package"] = {
        "path": str(prompt_package_path.relative_to(root)), "sha256": prompt_package_sha,
        "generation_surface": "codex_imagegen", "api_key_required": False,
        "returned_dimensions_guaranteed": False,
    }
    artifact_manifest["files"] = {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(path for path in root.rglob("*") if path.is_file() and path != artifact_manifest_path)
    }
    write_canonical_json(artifact_manifest, artifact_manifest_path)
    session["state"] = "ready"; session["theme_artifact"] = {
        "path": str(root), "theme_id": theme["id"], "version": theme["version"], "digest": digest(theme),
        "reference_count": len(session.get("private_references", [])), "distribution": theme.get("distribution", "public"),
        "rendering_medium": theme.get("rendering_contract", {}).get("medium", "not_declared"), "output": theme["output"],
        "prompt_package": {"path": str(prompt_package_path), "sha256": prompt_package_sha,
                           "generation_surface": "codex_imagegen", "api_key_required": False},
    }
    _write_session(session, theme, project_root)
    return session
