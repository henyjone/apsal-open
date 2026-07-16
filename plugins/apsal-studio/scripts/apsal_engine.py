from __future__ import annotations

import hashlib
import base64
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
import urllib.request
import uuid
import zipfile
from pathlib import Path
from typing import Any

try:
    from apsal_yaml import YamlError, dumps as dump_yaml, loads as load_yaml_text
except ModuleNotFoundError:  # Supports direct importlib loading in tests and embedders.
    _yaml_spec = importlib.util.spec_from_file_location("apsal_yaml", Path(__file__).with_name("apsal_yaml.py"))
    if _yaml_spec is None or _yaml_spec.loader is None:
        raise
    _yaml_module = importlib.util.module_from_spec(_yaml_spec)
    sys.modules[_yaml_spec.name] = _yaml_module
    _yaml_spec.loader.exec_module(_yaml_module)
    YamlError = _yaml_module.YamlError
    dump_yaml = _yaml_module.dumps
    load_yaml_text = _yaml_module.loads

ENGINE_VERSION = "0.5.0"
SEMANTIC_CONTRACT_VERSION = "0.3.0"
CATEGORIES = ("character", "style", "environment", "lighting", "composition", "shot", "qa")
PROTOCOL_TYPES = ("subject", "world", "style", "look", "emotion", "event", "camera", "light", "color_post", "quality_control", "content", "sequence", "job")
CREATIVE_FIELDS = ("framing", "action", "hands", "gaze", "composition")
COMPILE_TARGETS = ("design", "image", "qa")
INTERACTION_STAGES = ("character", "world", "scene", "photo")
STAGE_TYPES = {
    "character": ("character",),
    "world": ("environment",),
    "scene": ("composition", "shot"),
    "photo": ("style", "lighting"),
}
SESSION_STATES = (
    "character_pending", "world_pending", "scene_pending", "photo_pending",
    "review_pending", "ready", "generating", "completed", "partial",
)
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
SAFE_ID = re.compile(r"^[A-Z][A-Z0-9-]*$")
SAFE_ASSET_ID = re.compile(r"^[A-Z][A-Z0-9_]*$")
SAFE_NAMESPACE = re.compile(r"^[a-z][a-z0-9-]*$")
SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
REFERENCE_USES = {"style", "world", "prop", "wardrobe", "composition", "identity"}
LIVE_ACTION_FORBID = (
    "illustrated_human", "anime", "painting", "3d_rendered_person",
    "mannequin", "doll", "wax_figure", "clay_character",
)
NATIVE_4K_OUTPUT = {
    "aspect_ratio": "9:16", "size": "2160x3840", "quality": "high",
    "format": "png", "provider_native": True,
}


class ValidationError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def plugin_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: expected a JSON object")
    return value


def load_document(path: Path) -> dict[str, Any]:
    """Load canonical JSON or safe authoring YAML into the same data model."""
    suffixes = path.name.lower()
    if suffixes.endswith((".yaml", ".yml")):
        value = load_yaml_text(path.read_text(encoding="utf-8"))
    elif suffixes.endswith(".json"):
        value = json.loads(path.read_text(encoding="utf-8"))
    else:
        raise ValidationError(f"{path}: expected .json, .yaml, or .yml")
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: expected an object at the document root")
    return value


def write_canonical_json(value: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_semantic_registry() -> dict[str, Any]:
    return load_json(plugin_root() / "assets" / "semantics" / "registry.json")


def allowed_semantic_tags() -> set[str]:
    return {item["id"] for item in load_semantic_registry().get("tags", [])}


def load_catalog() -> dict[str, Any]:
    return load_json(plugin_root() / "assets" / "dna" / "catalog.json")


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def apsal_home() -> Path:
    """Return the user-owned APSAL data root without creating it."""
    configured = os.environ.get("APSAL_HOME")
    return Path(configured).expanduser().resolve() if configured else (Path.home() / ".apsal").resolve()


def _safe_part(value: str, label: str) -> str:
    if not SAFE_COMPONENT.fullmatch(value) or value in {".", ".."}:
        raise ValidationError(f"{label}: unsafe path component")
    return value


def _inside(root: Path, candidate: Path) -> Path:
    root = root.expanduser().resolve()
    candidate = candidate.expanduser().resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValidationError(f"path escapes APSAL root: {candidate}") from exc
    return candidate


def _write_private_json(value: dict[str, Any], path: Path) -> None:
    write_canonical_json(value, path)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _mkdir_private(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass


def project_root_from(start: Path | None = None) -> Path:
    """Discover an initialized APSAL project, otherwise use the supplied directory."""
    current = (start or Path.cwd()).expanduser().resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".apsal" / "project.json").is_file():
            return candidate
    return current


def init_workspace(project_root: Path, home: Path | None = None) -> dict[str, str]:
    """Initialize local-first APSAL storage. Existing files are never overwritten."""
    project_root = project_root.expanduser().resolve()
    home = (home or apsal_home()).expanduser().resolve()
    _mkdir_private(home)
    for relative in ("registry", "vault", "vault/sha256", "cache"):
        _mkdir_private(_inside(home, home / relative))
    workspace = project_root / ".apsal"
    _mkdir_private(workspace)
    for relative in ("drafts", "registry", "themes", "runs", "cache"):
        _mkdir_private(_inside(workspace, workspace / relative))
    project_file = workspace / "project.json"
    if not project_file.exists():
        _write_private_json({
            "schema_version": "0.5.0", "project_id": f"PROJECT-{uuid.uuid4().hex[:12].upper()}",
            "created_at": _utc_now(), "storage": "local_first",
        }, project_file)
    ignore = workspace / ".gitignore"
    if not ignore.exists():
        ignore.write_text("drafts/\nruns/\ncache/\nvault/\n", encoding="utf-8")
    return {"project_root": str(project_root), "workspace": str(workspace), "apsal_home": str(home)}


def _asset_key(asset: dict[str, Any]) -> tuple[str, str, str, str]:
    return tuple(str(asset.get(key, "")) for key in ("namespace", "id", "type", "version"))  # type: ignore[return-value]


def _ref_label(key: tuple[str, str, str, str]) -> str:
    namespace, asset_id, asset_type, version = key
    return f"{namespace}/{asset_id}@{version} ({asset_type})"


def _official_preview_index() -> dict[tuple[str, str, str, str], dict[str, Any]]:
    path = plugin_root() / "assets" / "previews" / "catalog.json"
    if not path.is_file():
        return {}
    value = load_json(path)
    result: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for item in value.get("previews", []):
        ref = item.get("ref", {})
        result[tuple(str(ref.get(key, "")) for key in ("namespace", "id", "type", "version"))] = item
    return result


def _webp_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValidationError("preview image must be WebP")
    chunk = data[12:16]
    if chunk == b"VP8X":
        return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
    if chunk == b"VP8 ":
        marker = data.find(b"\x9d\x01\x2a", 20)
        if marker < 0 or marker + 7 > len(data):
            raise ValidationError("invalid VP8 preview")
        return struct.unpack_from("<H", data, marker + 3)[0] & 0x3FFF, struct.unpack_from("<H", data, marker + 5)[0] & 0x3FFF
    if chunk == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    raise ValidationError("unsupported WebP preview encoding")


def validate_preview_file(image: Path, metadata: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not image.is_file():
        return [f"preview: missing image {image}"]
    data = image.read_bytes()
    try:
        width, height = _webp_dimensions(data)
    except ValidationError as exc:
        return [f"preview {image.name}: {exc}"]
    if (width, height) != (768, 576):
        errors.append(f"preview {image.name}: expected 768x576, got {width}x{height}")
    if len(data) > 300_000:
        errors.append(f"preview {image.name}: exceeds 300 KB")
    actual = hashlib.sha256(data).hexdigest()
    if metadata.get("sha256") != actual:
        errors.append(f"preview {image.name}: SHA-256 mismatch")
    for key in ("license", "status", "attribution"):
        if not metadata.get("rights", {}).get(key):
            errors.append(f"preview {image.name}: missing rights.{key}")
    if not metadata.get("qa_status") or not metadata.get("visual_qa_status"):
        errors.append(f"preview {image.name}: QA status is required")
    if metadata.get("disclaimer") != "Design preview; not generated-image quality evidence.":
        errors.append(f"preview {image.name}: design-preview disclaimer is required")
    return errors


def validate_official_previews() -> list[str]:
    errors: list[str] = []
    assets = load_catalog().get("assets", [])
    previews = _official_preview_index()
    for asset in assets:
        key = _asset_key(asset)
        item = previews.get(key)
        if not item:
            errors.append(f"preview catalog: missing {_ref_label(key)}"); continue
        if item.get("ref", {}).get("content_digest") != digest(asset):
            errors.append(f"preview catalog: DNA digest mismatch for {_ref_label(key)}")
        image = plugin_root() / "assets" / "previews" / str(item.get("image", ""))
        errors.extend(validate_preview_file(image, item))
    extra = set(previews) - {_asset_key(asset) for asset in assets}
    if extra:
        errors.append(f"preview catalog: unknown references {[ _ref_label(key) for key in sorted(extra) ]}")
    return errors


def _registry_asset_dirs(project_root: Path, home: Path) -> list[tuple[str, Path]]:
    return [("project", project_root / ".apsal" / "registry"), ("personal", home / "registry")]


def _iter_registry_assets(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(path for path in root.rglob("asset.apsal.json") if path.is_file())


def validate_registry_asset(asset: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = (
        "schema_version", "namespace", "id", "type", "version", "status", "parent_version",
        "changed_fields", "change_summary", "prompt_fragment", "negative_fragment", "rights", "qa_status",
    )
    for key in required:
        if key not in asset: errors.append(f"DNA asset: missing {key}")
    if not SAFE_NAMESPACE.fullmatch(str(asset.get("namespace", ""))): errors.append("DNA asset: invalid namespace")
    if not SAFE_ASSET_ID.fullmatch(str(asset.get("id", ""))): errors.append("DNA asset: invalid id")
    if asset.get("type") not in CATEGORIES: errors.append("DNA asset: unsupported type")
    if not SEMVER.fullmatch(str(asset.get("version", ""))): errors.append("DNA asset: invalid version")
    if not isinstance(asset.get("changed_fields"), list) or not asset.get("changed_fields"):
        errors.append("DNA asset: changed_fields cannot be empty")
    rights = asset.get("rights", {})
    for key in ("license", "status", "attribution"):
        if not rights.get(key): errors.append(f"DNA asset: missing rights.{key}")
    return errors


def _registry_asset_path(root: Path, asset: dict[str, Any]) -> Path:
    namespace, asset_id, asset_type, version = _asset_key(asset)
    for value, label in ((namespace, "namespace"), (asset_id, "id"), (asset_type, "type"), (version, "version")):
        _safe_part(value, label)
    return _inside(root, root / namespace / asset_type / asset_id / version / "asset.apsal.json")


def _fallback_preview(asset_type: str) -> tuple[Path, dict[str, Any]]:
    asset = next((item for item in load_catalog()["assets"] if item["type"] == asset_type), None)
    if not asset:
        raise ValidationError(f"no official preview fallback for {asset_type}")
    item = _official_preview_index().get(_asset_key(asset))
    if not item:
        raise ValidationError(f"no official preview metadata for {asset_type}")
    return plugin_root() / "assets" / "previews" / item["image"], item


def save_registry_asset(
    asset: dict[str, Any], *, scope: str, project_root: Path, home: Path | None = None,
    preview_path: Path | None = None, preview_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Save an immutable DNA asset and a presentation-only preview sidecar."""
    errors = validate_registry_asset(asset)
    if errors: raise ValidationError("\n".join(errors))
    if scope not in {"project", "personal"}: raise ValidationError("registry scope must be project or personal")
    home = (home or apsal_home()).resolve(); project_root = project_root.resolve()
    init_workspace(project_root, home)
    root = project_root / ".apsal" / "registry" if scope == "project" else home / "registry"
    target = _registry_asset_path(root, asset)
    if target.exists():
        current = load_json(target)
        if digest(current) != digest(asset):
            raise ValidationError(f"immutable DNA conflict for {_ref_label(_asset_key(asset))}")
        return {"scope": scope, "path": str(target), "ref": asset_ref(current)}
    _mkdir_private(target.parent)
    _write_private_json(asset, target)
    source, fallback = (preview_path, preview_metadata) if preview_path else _fallback_preview(asset["type"])
    if source is None: raise ValidationError("preview source is required")
    source = source.resolve()
    metadata = dict(fallback or {})
    if preview_metadata:
        metadata.update(preview_metadata)
    image_data = source.read_bytes()
    preview_target = target.parent / "preview.webp"
    preview_target.write_bytes(image_data)
    metadata.update({
        "schema_version": "0.1.0", "image": "preview.webp", "sha256": hashlib.sha256(image_data).hexdigest(),
        "ref": asset_ref(asset), "kind": metadata.get("kind", "semantic_card"),
        "qa_status": metadata.get("qa_status", "static_validated"),
        "visual_qa_status": metadata.get("visual_qa_status", "not_applicable_semantic_card"),
        "disclaimer": "Design preview; not generated-image quality evidence.",
    })
    preview_errors = validate_preview_file(preview_target, metadata)
    if preview_errors:
        target.unlink(missing_ok=True); preview_target.unlink(missing_ok=True)
        raise ValidationError("\n".join(preview_errors))
    _write_private_json(metadata, target.parent / "preview.json")
    return {"scope": scope, "path": str(target), "ref": asset_ref(asset)}


def load_layered_registry(project_root: Path, home: Path | None = None) -> list[dict[str, Any]]:
    """Load project, personal and official assets with immutable collision checks."""
    project_root = project_root.resolve(); home = (home or apsal_home()).resolve()
    records: list[dict[str, Any]] = []
    previews = _official_preview_index()
    for scope, root in _registry_asset_dirs(project_root, home):
        for path in _iter_registry_assets(root):
            asset = load_json(path)
            errors = validate_registry_asset(asset)
            if errors: raise ValidationError(f"{path}: {'; '.join(errors)}")
            preview_path = path.parent / "preview.webp"; preview_meta_path = path.parent / "preview.json"
            if not preview_meta_path.is_file(): raise ValidationError(f"{path}: missing preview.json")
            metadata = load_json(preview_meta_path)
            preview_errors = validate_preview_file(preview_path, metadata)
            if preview_errors: raise ValidationError("\n".join(preview_errors))
            records.append({"scope": scope, "asset": asset, "asset_path": path, "preview_path": preview_path, "preview": metadata})
    for asset in load_catalog().get("assets", []):
        item = previews.get(_asset_key(asset))
        if not item: raise ValidationError(f"official DNA missing preview: {_ref_label(_asset_key(asset))}")
        preview_path = plugin_root() / "assets" / "previews" / item["image"]
        preview_errors = validate_preview_file(preview_path, item)
        if preview_errors: raise ValidationError("\n".join(preview_errors))
        records.append({
            "scope": "official", "asset": asset, "asset_path": plugin_root() / "assets" / "dna" / "catalog.json",
            "preview_path": preview_path, "preview": item,
        })
    chosen: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for record in records:
        key = _asset_key(record["asset"])
        if key in chosen:
            if digest(chosen[key]["asset"]) != digest(record["asset"]):
                raise ValidationError(f"registry digest conflict for {_ref_label(key)}")
            continue
        chosen[key] = record
    return list(chosen.values())


def registry_assets(project_root: Path, home: Path | None = None) -> list[dict[str, Any]]:
    return [record["asset"] for record in load_layered_registry(project_root, home)]


def search_registry(project_root: Path, query: str = "", stage: str | None = None, home: Path | None = None, limit: int = 12) -> list[dict[str, Any]]:
    if stage is not None and stage not in INTERACTION_STAGES:
        raise ValidationError(f"unknown interaction stage: {stage}")
    terms = [term.casefold() for term in query.split() if term]
    allowed = set(STAGE_TYPES[stage]) if stage else set(CATEGORIES)
    scored: list[tuple[int, int, dict[str, Any]]] = []
    scope_rank = {"project": 0, "personal": 1, "official": 2}
    for record in load_layered_registry(project_root, home):
        asset = record["asset"]
        if asset["type"] not in allowed: continue
        haystack = " ".join(str(asset.get(key, "")) for key in ("id", "type", "change_summary", "prompt_fragment")).casefold()
        if terms and not all(term in haystack for term in terms): continue
        score = sum(haystack.count(term) for term in terms)
        scored.append((-score, scope_rank[record["scope"]], record))
    scored.sort(key=lambda item: (item[0], item[1], item[2]["asset"]["type"], item[2]["asset"]["id"]))
    return [record for _, _, record in scored[:max(1, min(limit, 50))]]


def dna_card(record: dict[str, Any]) -> dict[str, Any]:
    asset = record["asset"]; preview_path: Path = record["preview_path"]
    data = base64.b64encode(preview_path.read_bytes()).decode("ascii")
    return {
        "ref": asset_ref(asset), "scope": record["scope"], "title": asset["id"], "type": asset["type"],
        "summary": asset["change_summary"], "version": asset["version"], "locks": asset.get("locks", []),
        "core_attributes": asset.get("locks") or [asset["prompt_fragment"]],
        "rights": asset["rights"], "qa_status": asset["qa_status"],
        "preview": f"data:image/webp;base64,{data}", "preview_metadata": record["preview"],
    }


def promote_registry_asset(ref: dict[str, str], *, project_root: Path, home: Path | None = None) -> dict[str, Any]:
    home = (home or apsal_home()).resolve()
    key = tuple(ref.get(name, "") for name in ("namespace", "id", "type", "version"))
    matches = [record for record in load_layered_registry(project_root, home) if _asset_key(record["asset"]) == key]
    if not matches: raise ValidationError(f"unresolved DNA reference {_ref_label(key)}")
    record = matches[0]
    if record["scope"] == "official": raise ValidationError("official DNA is already globally available and cannot be promoted")
    return save_registry_asset(
        record["asset"], scope="personal", project_root=project_root, home=home,
        preview_path=record["preview_path"], preview_metadata=record["preview"],
    )


def catalog_index() -> dict[tuple[str, str, str, str], dict[str, Any]]:
    assets = load_catalog().get("assets", [])
    return {(a["namespace"], a["id"], a["type"], a["version"]): a for a in assets}


def _asset_index(assets: list[dict[str, Any]] | None = None) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    values = assets if assets is not None else load_catalog().get("assets", [])
    return {_asset_key(asset): asset for asset in values}


def asset_ref(asset: dict[str, Any]) -> dict[str, str]:
    return {
        "namespace": asset["namespace"], "id": asset["id"], "type": asset["type"],
        "version": asset["version"], "content_digest": digest(asset),
    }


def live_action_rendering_contract() -> dict[str, Any]:
    return {
        "medium": "live_action_photography",
        "subject_representation": "real_adult_human",
        "environment_style_may_be_handmade": True,
        "must_preserve": [
            "natural_skin_texture", "plausible_human_anatomy", "optical_depth_of_field",
            "physically_plausible_light", "photographic_material_response",
        ],
        "forbid": list(LIVE_ACTION_FORBID),
        "priority": 100,
        "instruction": {
            "en": "The set and props may use hand-drawn, crayon, or handmade textures; the adult subject must always be rendered as a real human in live-action photography.",
            "zh": "布景和道具可以具有手绘、蜡笔与手工质感；成年人物必须始终是真实人物的实拍摄影呈现。",
        },
    }


def new_theme(
    theme_id: str, name: str, shot_count: int = 9, *, native_4k: bool = True,
    live_action: bool = True,
) -> dict[str, Any]:
    if not SAFE_ID.fullmatch(theme_id):
        raise ValidationError("theme id must match ^[A-Z][A-Z0-9-]*$")
    if not 1 <= shot_count <= 24:
        raise ValidationError("shot count must be between 1 and 24")
    assets = load_catalog()["assets"]
    refs = [asset_ref(next(a for a in assets if a["type"] == category)) for category in CATEGORIES]
    framings = ("environment", "full", "medium", "close-up", "detail")
    shots = []
    for i in range(1, shot_count + 1):
        shots.append({
            "shot_id": f"SHOT_{i:02d}", "title": f"Scene {i}",
            "narrative_purpose": "Describe the unique story function of this frame.",
            "framing": framings[(i - 1) % len(framings)],
            "action": "Describe an observable action before the pose.",
            "hands": "Describe both hands or state that they are naturally outside frame.",
            "gaze": "Describe gaze direction and motivation.",
            "composition": "Describe subject placement, depth, foreground and background.",
            "continuity": {"identity": "locked", "wardrobe": "LOOK_A", "phase": f"PHASE_{((i - 1) * 3 // shot_count) + 1}"},
            "output_filename": f"{theme_id.lower()}_{i:02d}.{'png' if native_4k else 'jpg'}",
        })
    output = {"count": shot_count, "aspect_ratio": "2:3", "independent_images": True,
              "forbid": ["collage", "grid", "contact sheet", "text", "logo", "watermark"]}
    if native_4k: output.update(NATIVE_4K_OUTPUT)
    theme = {
        "schema_version": "1.0.0", "id": theme_id, "version": "1.0.0", "name": name,
        "parent_version": None, "changed_fields": ["initial_version"],
        "change_summary": "Initial original APSAL Open theme.", "dna": refs,
        "output": output,
        "shots": shots,
        "rights": {"license": "CC-BY-4.0", "status": "original_open_content", "attribution": "APSAL Open contributors"},
        "qa_status": "visual_qa_pending",
    }
    if live_action: theme["rendering_contract"] = live_action_rendering_contract()
    return theme


def _statement(statement_id: str, en: str, zh: str) -> dict[str, str]:
    return {"id": statement_id, "en": en, "zh": zh}


def _role_contract(role: str, role_value: dict[str, Any], tag: str) -> dict[str, Any]:
    return {
        "purpose": {"en": role_value["question_en"], "zh": role_value["question_zh"]},
        "affects": [f"{role}.output"],
        "must_preserve": ["subject.identity", "rights.provenance"],
        "may_vary": [f"{role}.declared_variables"],
        "expected_effects": [_statement(f"{role}.coherent", f"The {role} decision is observable and coherent.", f"{role_value['zh']}决定可观察且保持连贯。")],
        "qa_expectations": [_statement(f"{role}.intent", f"The output matches the declared {role} purpose.", f"输出符合已声明的{role_value['zh']}目的。")],
        "semantic_tags": [tag],
        "priority": role_value["priority"],
    }


def _generic_field_intent(field_name: str, field: dict[str, Any]) -> dict[str, Any]:
    return {
        "purpose": {"en": field["en"], "zh": field["zh"]},
        "affects": field["affects"],
        "expected_effects": [_statement(f"{field_name}.observable", f"The declared {field_name} is visually observable.", f"已声明的{field_name}在画面中可观察。")],
        "qa_expectations": [
            _statement(item, item.replace("_", " ").capitalize() + ".", item.replace("_", " ") + "。")
            for item in field["qa"]
        ],
    }


def new_semantic_theme(
    theme_id: str, name: str, shot_count: int = 9, *, native_4k: bool = True,
    live_action: bool = True,
) -> dict[str, Any]:
    """Create a Protocol 0.3 authoring theme with complete generic semantics."""
    theme = new_theme(theme_id, name, shot_count, native_4k=native_4k, live_action=live_action)
    registry = load_semantic_registry()
    theme["schema_version"] = "1.1.0"
    theme["semantic_contract_version"] = SEMANTIC_CONTRACT_VERSION
    theme["protocol_mapping"] = registry["dna_to_protocol"]
    theme["semantics"] = {
        "purpose": {"en": "Define a coherent photographic world before selecting its viewpoints.", "zh": "在选择摄影视点之前，定义一个连贯的摄影世界。"},
        "affects": ["element_semantics", "shots", "output"],
        "must_preserve": ["subject.identity", "world.geometry", "rights.provenance"],
        "may_vary": ["job.viewpoint", "event.action", "camera.framing"],
        "expected_effects": [_statement("theme.world_coherence", "All Jobs remain inferably inside one world.", "所有 Job 均可被推断为处于同一世界。")],
        "qa_expectations": [_statement("theme.distinct_jobs", "Every Job has a distinct narrative function and one output.", "每个 Job 都有不同叙事职能并只输出一张图。")],
        "semantic_tags": ["sequence.function.progression", "job.output.independent"],
        "priority": 95,
    }
    tags_by_role = {
        role: next(item["id"] for item in registry["tags"] if role in item["roles"])
        for role in PROTOCOL_TYPES
    }
    theme["element_semantics"] = {
        role: _role_contract(role, registry["roles"][role], tags_by_role[role]) for role in PROTOCOL_TYPES
    }
    for shot in theme["shots"]:
        shot["intent"] = {
            "purpose": {"en": shot["narrative_purpose"], "zh": "定义本镜独立且不可替代的叙事职能。"},
            "affects": ["event", "camera", "sequence", "job"],
            "must_preserve": ["subject.identity", "world.geometry", "look.wardrobe"],
            "may_vary": ["camera.framing", "event.action", "emotion.external_expression"],
            "expected_effects": [_statement("shot.distinct", "This frame adds information not duplicated by another Job.", "本镜增加其他 Job 未重复的信息。")],
            "qa_expectations": [_statement("shot.intent", "The narrative purpose is visually legible without explanatory text.", "无需解释文字即可看出本镜叙事目的。")],
            "semantic_tags": ["job.output.independent", "camera.viewpoint.single"],
            "priority": 82,
        }
        shot["field_intents"] = {
            field_name: _generic_field_intent(field_name, registry["fields"][f"shots.*.{field_name}"])
            for field_name in CREATIVE_FIELDS
        }
    return theme


def validate_catalog() -> list[str]:
    errors: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    categories: set[str] = set()
    for pos, asset in enumerate(load_catalog().get("assets", []), 1):
        label = f"catalog asset {pos}"
        for key in ("namespace", "id", "type", "version", "parent_version", "changed_fields", "change_summary", "prompt_fragment", "negative_fragment", "rights", "qa_status"):
            if key not in asset:
                errors.append(f"{label}: missing {key}")
        if asset.get("type") not in CATEGORIES:
            errors.append(f"{label}: unsupported type")
        else:
            categories.add(asset["type"])
        if not SEMVER.fullmatch(str(asset.get("version", ""))):
            errors.append(f"{label}: invalid semantic version")
        key = (str(asset.get("namespace")), str(asset.get("id")), str(asset.get("version")))
        if key in seen:
            errors.append(f"{label}: duplicate ID/version")
        seen.add(key)
        rights = asset.get("rights", {})
        if rights.get("status") != "original_open_content" or rights.get("license") != "CC-BY-4.0":
            errors.append(f"{label}: not approved for the starter catalog")
        if rights.get("reference_images_included") is not False:
            errors.append(f"{label}: reference images must not be bundled")
    missing = set(CATEGORIES) - categories
    if missing:
        errors.append(f"catalog: missing categories {sorted(missing)}")
    return errors


def validate_semantic_registry() -> list[str]:
    errors: list[str] = []
    try:
        registry = load_semantic_registry()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"semantic registry: unreadable: {exc}"]
    if registry.get("semantic_contract_version") != SEMANTIC_CONTRACT_VERSION:
        errors.append("semantic registry: contract version mismatch")
    roles = registry.get("roles", {})
    if set(roles) != set(PROTOCOL_TYPES):
        errors.append("semantic registry: roles must contain exactly the thirteen protocol types")
    tags = registry.get("tags", [])
    ids = [item.get("id") for item in tags if isinstance(item, dict)]
    if len(ids) != len(set(ids)):
        errors.append("semantic registry: duplicate tag id")
    for item in tags:
        if not isinstance(item, dict):
            errors.append("semantic registry: tag must be an object"); continue
        for key in ("id", "en", "zh", "roles"):
            if not item.get(key): errors.append(f"semantic registry tag: missing {key}")
        unknown_roles = set(item.get("roles", [])) - set(PROTOCOL_TYPES)
        if unknown_roles: errors.append(f"semantic registry tag {item.get('id')}: unknown roles {sorted(unknown_roles)}")
    mappings = registry.get("dna_to_protocol", {})
    if set(mappings) != set(CATEGORIES):
        errors.append("semantic registry: DNA mapping must contain all seven catalog categories")
    covered = {role for values in mappings.values() for role in values}
    if covered != set(PROTOCOL_TYPES):
        errors.append("semantic registry: DNA mapping must cover all thirteen protocol roles")
    fields = registry.get("fields", {})
    for name in CREATIVE_FIELDS:
        field = fields.get(f"shots.*.{name}", {})
        for key in ("en", "zh", "role", "affects", "compile_stage", "qa"):
            if not field.get(key): errors.append(f"semantic registry field {name}: missing {key}")
    return errors


def _localized(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, dict) or not str(value.get("en", "")).strip() or not str(value.get("zh", "")).strip():
        errors.append(f"{label}: must contain non-empty en and zh text")


def _semantic_statements(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{label}: must be a non-empty array"); return
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            errors.append(f"{label}: statement must be an object"); continue
        statement_id = item.get("id")
        if not statement_id or statement_id in seen:
            errors.append(f"{label}: statement ids must be present and unique")
        seen.add(str(statement_id))
        _localized(item, f"{label}.{statement_id or '?'}", errors)


def validate_semantic_contract(value: Any, label: str, *, field_level: bool = False) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{label}: semantic contract must be an object"]
    required = ("purpose", "affects", "expected_effects", "qa_expectations") if field_level else (
        "purpose", "affects", "must_preserve", "may_vary", "expected_effects",
        "qa_expectations", "semantic_tags", "priority",
    )
    for key in required:
        if key not in value: errors.append(f"{label}: missing {key}")
    _localized(value.get("purpose"), f"{label}.purpose", errors)
    for key in ("affects",) if field_level else ("affects", "must_preserve", "may_vary"):
        items = value.get(key)
        if not isinstance(items, list) or not items or any(not isinstance(item, str) or not item for item in items):
            errors.append(f"{label}.{key}: must be a non-empty string array")
    _semantic_statements(value.get("expected_effects"), f"{label}.expected_effects", errors)
    _semantic_statements(value.get("qa_expectations"), f"{label}.qa_expectations", errors)
    if not field_level:
        tags = value.get("semantic_tags")
        if not isinstance(tags, list) or not tags:
            errors.append(f"{label}.semantic_tags: must be a non-empty array")
        else:
            unknown = set(tags) - allowed_semantic_tags()
            if unknown: errors.append(f"{label}.semantic_tags: unknown tags {sorted(unknown)}")
        priority = value.get("priority")
        if not isinstance(priority, int) or isinstance(priority, bool) or not 0 <= priority <= 100:
            errors.append(f"{label}.priority: must be an integer from 0 through 100")
    return errors


def validate_semantic_theme(theme: dict[str, Any]) -> list[str]:
    errors = validate_semantic_registry()
    if theme.get("semantic_contract_version") != SEMANTIC_CONTRACT_VERSION:
        errors.append("theme: semantic_contract_version must be 0.3.0")
    errors.extend(validate_semantic_contract(theme.get("semantics"), "theme.semantics"))
    mappings = theme.get("protocol_mapping")
    expected_mapping = load_semantic_registry().get("dna_to_protocol", {}) if not errors or (plugin_root() / "assets/semantics/registry.json").exists() else {}
    if mappings != expected_mapping:
        errors.append("theme: protocol_mapping must match the registered seven-to-thirteen role mapping")
    role_semantics = theme.get("element_semantics")
    if not isinstance(role_semantics, dict) or set(role_semantics) != set(PROTOCOL_TYPES):
        errors.append("theme: element_semantics must contain exactly the thirteen protocol roles")
    else:
        for role in PROTOCOL_TYPES:
            errors.extend(validate_semantic_contract(role_semantics[role], f"theme.element_semantics.{role}"))
            valid_for_role = {item["id"] for item in load_semantic_registry()["tags"] if role in item["roles"]}
            invalid = set(role_semantics[role].get("semantic_tags", [])) - valid_for_role
            if invalid: errors.append(f"theme.element_semantics.{role}: tags not valid for role {sorted(invalid)}")
    for shot in theme.get("shots", []):
        shot_id = shot.get("shot_id", "?")
        errors.extend(validate_semantic_contract(shot.get("intent"), f"shot {shot_id}.intent"))
        field_intents = shot.get("field_intents")
        if not isinstance(field_intents, dict):
            errors.append(f"shot {shot_id}: field_intents must be an object"); continue
        for field in CREATIVE_FIELDS:
            errors.extend(validate_semantic_contract(field_intents.get(field), f"shot {shot_id}.field_intents.{field}", field_level=True))
    return errors


def validate_rendering_contract(value: Any) -> list[str]:
    if not isinstance(value, dict): return ["rendering_contract: must be an object"]
    errors: list[str] = []
    if value.get("medium") != "live_action_photography": errors.append("rendering_contract: medium must be live_action_photography")
    if value.get("subject_representation") != "real_adult_human": errors.append("rendering_contract: subject_representation must be real_adult_human")
    if value.get("environment_style_may_be_handmade") is not True: errors.append("rendering_contract: handmade environment allowance must be explicit")
    preserve = value.get("must_preserve")
    required_preserve = set(live_action_rendering_contract()["must_preserve"])
    if not isinstance(preserve, list) or not required_preserve.issubset(set(preserve)):
        errors.append("rendering_contract: live-action preservation rules are incomplete")
    forbidden = value.get("forbid")
    if not isinstance(forbidden, list) or not set(LIVE_ACTION_FORBID).issubset(set(forbidden)):
        errors.append("rendering_contract: illustrated/CGI human prohibitions are incomplete")
    if value.get("priority") != 100: errors.append("rendering_contract: priority must be 100")
    instruction = value.get("instruction", {})
    if not instruction.get("en") or not instruction.get("zh"): errors.append("rendering_contract: bilingual instruction is required")
    return errors


def validate_reference_metadata(references: Any, theme: dict[str, Any] | None = None) -> list[str]:
    if references is None: return []
    if not isinstance(references, list): return ["references: must be an array"]
    errors: list[str] = []; ids: set[str] = set(); digests: set[str] = set()
    shot_ids = {shot.get("shot_id") for shot in (theme or {}).get("shots", [])}
    for pos, ref in enumerate(references, 1):
        label = f"reference {pos}"
        if not isinstance(ref, dict): errors.append(f"{label}: must be an object"); continue
        ref_id = str(ref.get("reference_id", ""))
        if not SAFE_ASSET_ID.fullmatch(ref_id): errors.append(f"{label}: invalid reference_id")
        if ref_id in ids: errors.append(f"{label}: duplicate reference_id {ref_id}")
        ids.add(ref_id)
        sha = str(ref.get("original_sha256", ""))
        if not re.fullmatch(r"[a-f0-9]{64}", sha): errors.append(f"{label}: invalid original_sha256")
        if sha in digests: errors.append(f"{label}: duplicate original_sha256")
        digests.add(sha)
        filename = ref.get("original_filename")
        if not isinstance(filename, str) or not filename or Path(filename).name != filename:
            errors.append(f"{label}: original_filename must be one safe filename")
        uses_value = ref.get("uses"); uses = set(uses_value) if isinstance(uses_value, list) else set()
        if not isinstance(uses_value, list) or not uses or uses - REFERENCE_USES:
            errors.append(f"{label}: uses must be selected from {sorted(REFERENCE_USES)}")
        for key in ("allowed_uses", "forbidden_uses", "applies_to"):
            value = ref.get(key)
            if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item for item in value):
                errors.append(f"{label}: {key} must be a non-empty string array")
        applies_value = ref.get("applies_to"); applies = set(applies_value) if isinstance(applies_value, list) else set()
        if theme is not None:
            unknown_shots = applies - shot_ids - {"*"}
            if unknown_shots: errors.append(f"{label}: unknown Jobs {sorted(unknown_shots)}")
        elif any(item != "*" and not re.fullmatch(r"SHOT_[0-9]{2,3}", item) for item in applies):
            errors.append(f"{label}: applies_to contains an invalid Job ID")
        rights_value = ref.get("rights"); rights = rights_value if isinstance(rights_value, dict) else {}
        if not isinstance(rights_value, dict): errors.append(f"{label}: rights must be an object")
        for key in ("copyright_status", "portrait_rights", "attribution", "redistribution_allowed"):
            if key not in rights: errors.append(f"{label}: missing rights.{key}")
        for key in ("copyright_status", "portrait_rights", "attribution"):
            if key in rights and (not isinstance(rights[key], str) or not rights[key].strip()):
                errors.append(f"{label}: rights.{key} must be a non-empty string")
        if "redistribution_allowed" in rights and not isinstance(rights["redistribution_allowed"], bool):
            errors.append(f"{label}: rights.redistribution_allowed must be boolean")
        forbidden_value = ref.get("forbidden_uses"); forbidden = set(forbidden_value) if isinstance(forbidden_value, list) else set()
        if "identity" not in uses and "identity" not in forbidden:
            errors.append(f"{label}: non-identity reference must explicitly forbid identity use")
    analysis_value = (theme or {}).get("reference_analysis", {}); analysis = analysis_value if isinstance(analysis_value, dict) else {}
    expected = {item.get("sha256") for item in analysis.get("references", []) if isinstance(item, dict)}
    actual = {item.get("original_sha256") for item in references if isinstance(item, dict)}
    if expected and expected != actual: errors.append("references: digests must match reference_analysis exactly")
    if analysis.get("identity_usage") == "none" and any("identity" in ref.get("uses", []) for ref in references if isinstance(ref, dict)):
        errors.append("references: identity usage conflicts with reference_analysis.identity_usage=none")
    return errors


def _reference_rights_allow_public(ref: dict[str, Any]) -> bool:
    rights = ref.get("rights", {})
    if not isinstance(rights, dict) or rights.get("redistribution_allowed") is not True:
        return False
    unresolved = ("unverified", "unknown", "unresolved", "pending", "private_only")
    for key in ("copyright_status", "portrait_rights"):
        value = str(rights.get(key, "")).lower()
        if not value or any(token in value for token in unresolved): return False
    return bool(str(rights.get("attribution", "")).strip())


def validate_theme(theme: dict[str, Any], assets: list[dict[str, Any]] | None = None) -> list[str]:
    errors = validate_catalog() if assets is None else []
    for key in ("schema_version", "id", "version", "name", "parent_version", "changed_fields", "change_summary", "dna", "output", "shots", "rights", "qa_status"):
        if key not in theme:
            errors.append(f"theme: missing {key}")
    if theme.get("schema_version") not in {"1.0.0", "1.1.0"}: errors.append("theme: unsupported schema_version")
    if not SAFE_ID.fullmatch(str(theme.get("id", ""))): errors.append("theme: invalid id")
    if not SEMVER.fullmatch(str(theme.get("version", ""))): errors.append("theme: invalid semantic version")
    refs = theme.get("dna", [])
    if not isinstance(refs, list):
        errors.append("theme: dna must be an array"); refs = []
    index = _asset_index(assets)
    ref_types: set[str] = set()
    for ref in refs:
        if not isinstance(ref, dict): errors.append("theme: invalid DNA reference"); continue
        key = tuple(ref.get(k, "") for k in ("namespace", "id", "type", "version"))
        asset = index.get(key)
        if not asset: errors.append(f"theme: unresolved DNA reference {key}"); continue
        ref_types.add(ref["type"])
        if ref.get("content_digest") != digest(asset): errors.append(f"theme: DNA digest mismatch for {ref['id']}")
    missing = set(CATEGORIES) - ref_types
    if missing: errors.append(f"theme: missing DNA categories {sorted(missing)}")
    shots = theme.get("shots", [])
    if not isinstance(shots, list) or not 1 <= len(shots) <= 24:
        errors.append("theme: shots must contain 1-24 entries"); shots = []
    output = theme.get("output", {})
    if output.get("count") != len(shots): errors.append("theme: output count does not match shots")
    if output.get("independent_images") is not True: errors.append("theme: outputs must be independent images")
    if output.get("provider_native") is True:
        expected_output = NATIVE_4K_OUTPUT
        for key, expected in expected_output.items():
            if output.get(key) != expected: errors.append(f"theme: native 4K output {key} must be {expected}")
    required = ("shot_id", "title", "narrative_purpose", "framing", "action", "hands", "gaze", "composition", "continuity", "output_filename")
    ids, filenames = set(), set()
    for shot in shots:
        for key in required:
            if not shot.get(key): errors.append(f"shot: missing {key}")
        if shot.get("shot_id") in ids: errors.append(f"shot: duplicate id {shot.get('shot_id')}")
        if shot.get("output_filename") in filenames: errors.append(f"shot: duplicate filename {shot.get('output_filename')}")
        ids.add(shot.get("shot_id")); filenames.add(shot.get("output_filename"))
    rights = theme.get("rights", {})
    if rights.get("status") != "original_open_content": errors.append("theme: rights status must be original_open_content")
    if theme.get("qa_status") == "visual_qa_passed" and not theme.get("visual_qa_evidence"):
        errors.append("theme: visual_qa_passed requires evidence")
    if "rendering_contract" in theme: errors.extend(validate_rendering_contract(theme["rendering_contract"]))
    if "references" in theme:
        errors.extend(validate_reference_metadata(theme["references"], theme))
        if any(not _reference_rights_allow_public(ref) for ref in theme.get("references", []) if isinstance(ref, dict)):
            if theme.get("distribution") != "private_only": errors.append("theme: unredistributable references require distribution=private_only")
    if theme.get("schema_version") == "1.1.0":
        if theme.get("parent_version"):
            if theme.get("version") == theme.get("parent_version"):
                errors.append("theme: child version must differ from parent_version")
            if not {"semantics", "element_semantics", "shots[*].intent", "protocol_mapping"}.issubset(set(theme.get("changed_fields", []))):
                errors.append("theme: semantic extension changed_fields are incomplete")
        elif "initial_version" not in theme.get("changed_fields", []):
            errors.append("theme: new semantic asset without a parent must declare initial_version")
        errors.extend(validate_semantic_theme(theme))
    return errors


def validate_protocol_package(root: Path) -> list[str]:
    """Validate the publishable APSAL Open Protocol boundary of an extracted package."""
    errors: list[str] = []
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return ["package: missing manifest.json"]
    try:
        manifest = load_json(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"package: invalid manifest.json: {exc}"]
    required = ("protocol", "protocol_version", "id", "version", "parent_version", "changed_fields", "change_summary", "license", "rights", "modules", "sequence", "jobs", "checksums", "output", "qa_status")
    for key in required:
        if key not in manifest: errors.append(f"manifest: missing {key}")
    if manifest.get("protocol") != "apsal-open": errors.append("manifest: protocol must be apsal-open")
    for key in ("protocol_version", "version"):
        if not SEMVER.fullmatch(str(manifest.get(key, ""))): errors.append(f"manifest: invalid {key}")
    if manifest.get("protocol_version") == "0.3.0" and manifest.get("semantic_contract_version") != SEMANTIC_CONTRACT_VERSION:
        errors.append("manifest: Protocol 0.3 requires semantic_contract_version 0.3.0")
    if not manifest.get("changed_fields"): errors.append("manifest: changed_fields cannot be empty")
    licenses = manifest.get("license", {})
    if not licenses.get("code") or not licenses.get("content"): errors.append("manifest: code and content licenses are required")
    rights = manifest.get("rights", {})
    for key in ("status", "attribution", "reference_media", "ai_disclosure"):
        if key not in rights: errors.append(f"manifest rights: missing {key}")
    if rights.get("status") not in {"original_open_content", "authorized_open_content"}:
        errors.append("manifest rights: content is not approved for open redistribution")
    if rights.get("reference_media") not in {"none", "separately_licensed"}:
        errors.append("manifest rights: reference_media must be none or separately_licensed")
    modules = manifest.get("modules", {})
    if not isinstance(modules, dict): errors.append("manifest: modules must be an object"); modules = {}
    missing = set(PROTOCOL_TYPES[:11]) - set(modules)
    if missing: errors.append(f"manifest: missing module roles {sorted(missing)}")
    jobs = manifest.get("jobs", [])
    if not isinstance(jobs, list) or not 1 <= len(jobs) <= 24: errors.append("manifest: jobs must contain 1-24 paths"); jobs = []
    listed = list(modules.values()) + ([manifest.get("sequence")] if manifest.get("sequence") else []) + jobs
    checksums = manifest.get("checksums", {})
    filenames: set[str] = set()
    for rel in listed:
        if not isinstance(rel, str): errors.append("manifest: package path must be a string"); continue
        candidate = (root / rel).resolve()
        try: candidate.relative_to(root.resolve())
        except ValueError: errors.append(f"package: path escapes root: {rel}"); continue
        if not candidate.is_file(): errors.append(f"package: missing file {rel}"); continue
        actual = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if checksums.get(rel) != actual: errors.append(f"package: checksum mismatch for {rel}")
        try: value = load_json(candidate)
        except (OSError, ValueError, json.JSONDecodeError) as exc: errors.append(f"package: invalid JSON {rel}: {exc}"); continue
        kind = "job" if rel in jobs else "sequence" if rel == manifest.get("sequence") else next((k for k,v in modules.items() if v == rel), "")
        for key in ("schema_version", "namespace", "id", "type", "version", "parent_version", "changed_fields", "change_summary", "dependencies", "rights", "qa_status", "payload"):
            if key not in value: errors.append(f"{rel}: missing {key}")
        if value.get("type") != kind: errors.append(f"{rel}: type must be {kind}")
        if not SEMVER.fullmatch(str(value.get("version", ""))): errors.append(f"{rel}: invalid semantic version")
        if value.get("schema_version") == "1.1.0":
            errors.extend(validate_semantic_contract(value.get("semantics"), f"{rel}.semantics"))
        module_rights = value.get("rights", {})
        if not module_rights.get("license") or not module_rights.get("attribution"): errors.append(f"{rel}: incomplete rights")
        if value.get("qa_status") == "visual_qa_passed" and not value.get("visual_qa_evidence"): errors.append(f"{rel}: visual QA evidence required")
        if kind == "job":
            output = value.get("payload", {}).get("output", {})
            if output.get("independent_image") is not True: errors.append(f"{rel}: job must output one independent image")
            filename = output.get("filename")
            if not filename: errors.append(f"{rel}: output filename required")
            elif filename in filenames: errors.append(f"{rel}: duplicate output filename {filename}")
            filenames.add(filename)
    output = manifest.get("output", {})
    if output.get("one_job_one_image") is not True: errors.append("manifest: one_job_one_image must be true")
    if output.get("count") != len(jobs): errors.append("manifest: output count does not match jobs")
    if manifest.get("qa_status") == "visual_qa_passed" and not manifest.get("visual_qa_evidence"):
        errors.append("manifest: visual_qa_passed requires evidence")
    return errors


def _english_statements(contract: dict[str, Any], key: str) -> list[str]:
    return [item["en"] for item in contract.get(key, []) if isinstance(item, dict) and item.get("en")]


def _compile_image(theme: dict[str, Any], assets: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(assets, key=lambda a: CATEGORIES.index(a["type"]))
    shared = ", ".join(a["prompt_fragment"] for a in ordered)
    negative = ", ".join(a["negative_fragment"] for a in ordered)
    rendering = theme.get("rendering_contract")
    medium_prefix = ""
    if rendering:
        medium_prefix = (
            "MEDIUM CONTRACT — LIVE-ACTION PHOTOGRAPHY. Create a photograph of a real adult human captured by a physical camera, "
            "with natural skin texture, plausible anatomy, optical depth of field, physically plausible light, and photographic material response. "
            "The set and props may use hand-drawn, crayon, or handmade textures; the adult subject must never become an illustration, anime figure, "
            "painting, 3D-rendered person, mannequin, doll, wax figure, or clay character. "
        )
        negative = f"{', '.join(rendering['forbid'])}, illustrated person, cartoon human, synthetic 3D human, {negative}"
    compiled = []
    for shot in theme["shots"]:
        observable = _english_statements(shot.get("intent", {}), "expected_effects")
        observable_text = f" Observable results: {'; '.join(observable)}." if observable else ""
        instruction = (
            f"Create exactly one independent finished vertical photograph for {shot['shot_id']} ({shot['title']}). "
            f"Narrative purpose: {shot['narrative_purpose']}. Framing: {shot['framing']}. Action: {shot['action']}. "
            f"Hands: {shot['hands']}. Gaze: {shot['gaze']}. Composition: {shot['composition']}. "
            f"Continuity: {canonical_json(shot['continuity'])}. Output file: {shot['output_filename']}."
            f"{observable_text}"
        )
        positive = f"{medium_prefix}{shared}, {instruction}"
        reference_ids = [
            ref["reference_id"] for ref in theme.get("references", [])
            if "*" in ref.get("applies_to", []) or shot["shot_id"] in ref.get("applies_to", [])
        ]
        compiled.append({"shot_id": shot["shot_id"], "title": shot["title"], "positive_prompt": positive,
                         "negative_prompt": negative, "reference_ids": reference_ids,
                         "prompt_digest": digest({"positive": positive, "negative": negative, "references": reference_ids})})
    return {"target": "image", "rendering_contract": rendering, "output_contract": theme.get("output"), "shots": compiled}


def _compile_design(theme: dict[str, Any], assets: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "target": "design",
        "semantic_contract_version": theme.get("semantic_contract_version"),
        "priority_order": [
            "identity_and_rights", "world_physics_and_continuity", "event_and_shot_function",
            "camera_light_and_color", "style_rhetoric",
        ],
        "theme_semantics": theme.get("semantics"),
        "rendering_contract": theme.get("rendering_contract"),
        "reference_summary": [{"reference_id": ref["reference_id"], "uses": ref["uses"], "applies_to": ref["applies_to"]} for ref in theme.get("references", [])],
        "output_contract": theme.get("output"),
        "protocol_mapping": theme.get("protocol_mapping"),
        "element_semantics": theme.get("element_semantics"),
        "dna": [{"id": asset["id"], "type": asset["type"], "version": asset["version"]} for asset in assets],
        "shots": [
            {
                "shot_id": shot["shot_id"], "title": shot["title"],
                "narrative_purpose": shot["narrative_purpose"], "framing": shot["framing"],
                "action": shot["action"], "hands": shot["hands"], "gaze": shot["gaze"],
                "composition": shot["composition"], "continuity": shot["continuity"],
                "intent": shot.get("intent"), "field_intents": shot.get("field_intents"),
                "output_filename": shot["output_filename"],
            } for shot in theme["shots"]
        ],
    }


def _compile_qa(theme: dict[str, Any]) -> dict[str, Any]:
    global_checks = []
    quality = theme.get("element_semantics", {}).get("quality_control", {})
    for item in quality.get("qa_expectations", []):
        global_checks.append({"id": item["id"], "en": item["en"], "zh": item["zh"], "scope": "theme"})
    if theme.get("rendering_contract"):
        global_checks.extend([
            {"id": "medium.live_action", "en": "The adult subject is unmistakably a real human in live-action photography, while handmade styling remains confined to set and props.", "zh": "成年人物明确呈现为真人实拍摄影；手绘和手工风格仅作用于布景与道具。", "scope": "theme"},
            {"id": "medium.skin_eyes_hands", "en": "Skin pores, both eyes when visible, and all visible hands are anatomically and photographically plausible.", "zh": "可见皮肤毛孔、双眼与手部在解剖和摄影表现上均可信。", "scope": "theme"},
            {"id": "medium.optics_light", "en": "Depth of field, light falloff, shadows and material response behave like physical photography rather than illustration or CGI.", "zh": "景深、光线衰减、阴影与材质响应符合物理摄影，而非插画或 CGI。", "scope": "theme"},
        ])
    shots = []
    for shot in theme["shots"]:
        checks: list[dict[str, Any]] = []
        seen: set[str] = set()
        sources = [("intent", shot.get("intent", {}))] + [
            (field, shot.get("field_intents", {}).get(field, {})) for field in CREATIVE_FIELDS
        ]
        for source, contract in sources:
            for item in contract.get("qa_expectations", []):
                check_id = f"{source}.{item['id']}"
                if check_id in seen: continue
                seen.add(check_id)
                checks.append({"id": check_id, "en": item["en"], "zh": item["zh"], "source": source})
        checks.extend([
            {"id": "continuity.identity", "en": "The same fictional adult identity is preserved.", "zh": "保持同一虚构成年人物身份。", "source": "continuity"},
            {"id": "output.independent", "en": "The output is one independent finished image with no text or grid.", "zh": "输出为一张无文字、无拼图的独立完成图。", "source": "output"},
        ])
        if theme.get("rendering_contract"):
            checks.append({"id": "medium.real_adult_human", "en": "This Job depicts a real adult human in live-action photography, not an illustrated, painted, doll-like, wax, clay or 3D-rendered person.", "zh": "本 Job 呈现真人成年人的实拍摄影，而非插画、绘画、玩偶、蜡像、黏土或 3D 人物。", "source": "rendering_contract"})
        shots.append({"shot_id": shot["shot_id"], "title": shot["title"], "output_filename": shot["output_filename"], "checks": checks})
    return {"target": "qa", "model_visual_qa": "required_before_delivery", "human_visual_qa": "pending_until_evidence", "global_checks": global_checks, "shots": shots}


def compile_theme(
    theme: dict[str, Any], target: str = "image", assets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if target not in COMPILE_TARGETS:
        raise ValidationError(f"compile target must be one of {', '.join(COMPILE_TARGETS)}")
    errors = validate_theme(theme, assets)
    if errors: raise ValidationError("\n".join(errors))
    index = _asset_index(assets)
    selected = [index[tuple(ref[k] for k in ("namespace", "id", "type", "version"))] for ref in theme["dna"]]
    payload = _compile_image(theme, selected) if target == "image" else _compile_design(theme, selected) if target == "design" else _compile_qa(theme)
    result = {"engine_version": ENGINE_VERSION, "theme_id": theme["id"], "theme_version": theme["version"],
              "theme_digest": digest(theme), **payload}
    result["compiled_digest"] = digest(result)
    return result


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
    theme_path.write_text(dump_yaml(theme), encoding="utf-8")
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
    shot_count: int = 9, home: Path | None = None,
) -> dict[str, Any]:
    """Start a resumable four-stage natural-language design session."""
    brief = brief.strip()
    if not brief: raise ValidationError("creative brief cannot be empty")
    project_root = project_root.expanduser().resolve(); init_workspace(project_root, home)
    theme_id = theme_id or _new_theme_id()
    theme = new_semantic_theme(theme_id, (name or brief[:80]).strip(), shot_count, native_4k=True, live_action=True)
    session_id = f"SESSION-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:10].upper()}"
    session = {
        "schema_version": "0.5.0", "session_id": session_id, "brief": brief,
        "project_root": str(project_root), "state": "character_pending", "shot_count": shot_count,
        "stages": {stage: {"status": "pending", "selection": [], "confirmed_at": None} for stage in INTERACTION_STAGES},
        "private_references": [], "invalidations": [], "created_at": _utc_now(), "updated_at": _utc_now(),
        "theme_artifact": None,
    }
    _write_session(session, theme, project_root)
    return session


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


def commit_session_stage(
    session_id: str, stage: str, refs: list[dict[str, str]], *, project_root: Path,
    home: Path | None = None, shots: list[dict[str, Any]] | None = None,
    reference_path: Path | None = None, reference_bindings: list[dict[str, Any]] | None = None,
    draft_assets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Confirm or revise one interaction stage and invalidate every affected downstream stage."""
    if stage not in INTERACTION_STAGES: raise ValidationError(f"unknown interaction stage: {stage}")
    project_root = project_root.expanduser().resolve(); session, theme = load_design_session(session_id, project_root)
    if session["state"] in {"ready", "generating", "completed", "partial"}:
        raise ValidationError("a finalized or generated theme cannot be edited; create a new theme version")
    proposed_assets = draft_assets or []
    for asset in proposed_assets:
        if asset.get("type") not in STAGE_TYPES[stage]:
            raise ValidationError(f"draft DNA type {asset.get('type')} does not belong to {stage}")
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
    if any(session["stages"][stage]["status"] != "confirmed" for stage in INTERACTION_STAGES):
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
    session["state"] = "ready"; session["theme_artifact"] = {
        "path": str(root), "theme_id": theme["id"], "version": theme["version"], "digest": digest(theme),
        "reference_count": len(session.get("private_references", [])), "distribution": theme.get("distribution", "public"),
        "rendering_medium": theme.get("rendering_contract", {}).get("medium", "not_declared"), "output": theme["output"],
    }
    _write_session(session, theme, project_root)
    return session


def _run_dir(project_root: Path, run_id: str) -> Path:
    run_id = _safe_part(run_id, "run id"); root = project_root / ".apsal" / "runs"
    return _inside(root, root / run_id)


def load_generation_run(run_id: str, project_root: Path) -> dict[str, Any]:
    path = _run_dir(project_root.expanduser().resolve(), run_id) / "run.json"
    if not path.is_file(): raise ValidationError(f"unknown generation run: {run_id}")
    return load_json(path)


def _write_run(run: dict[str, Any], project_root: Path) -> None:
    run["updated_at"] = _utc_now()
    _write_private_json(run, _run_dir(project_root, run["run_id"]) / "run.json")


def _generation_run_status(run: dict[str, Any]) -> str:
    jobs = run.get("jobs", [])
    if any(job.get("status") == "failed" for job in jobs): return "partial"
    if jobs and all(job.get("status") == "succeeded" for job in jobs):
        if run.get("rendering_contract", {}).get("medium") == "live_action_photography":
            return "completed" if all(job.get("model_visual_qa") == "passed" for job in jobs) else "generating"
        return "completed"
    return "generating"


def start_generation_run(
    session_id: str, *, project_root: Path, confirmed: bool = False, mode: str = "generate",
    adapter: str = "openai-image-api", model: str = "gpt-image-2", parameters: dict[str, Any] | None = None,
    resume_run_id: str | None = None, home: Path | None = None,
) -> dict[str, Any]:
    """Create or resume a nine-Job run without calling a remote image provider."""
    if mode not in {"generate", "prompts", "skill"}: raise ValidationError("run mode must be generate, prompts, or skill")
    if mode == "generate" and confirmed is not True:
        raise ValidationError("explicit confirmation is required before generating images")
    project_root = project_root.expanduser().resolve(); session, theme = load_design_session(session_id, project_root)
    if session["state"] not in {"ready", "partial", "completed"} or not session.get("theme_artifact"):
        raise ValidationError("finalize the design session before starting a run")
    if resume_run_id:
        run = load_generation_run(resume_run_id, project_root)
        if run["session_id"] != session_id: raise ValidationError("run does not belong to this session")
        failed_jobs = [job for job in run["jobs"] if job.get("status") == "failed"]
        if not failed_jobs: raise ValidationError("generation run has no failed Jobs to resume")
        run["resume_count"] += 1
        for job in failed_jobs: job["status"] = "pending"; job["error"] = None
        run["status"] = "generating"
        _write_run(run, project_root); session["state"] = "generating"; _write_session(session, theme, project_root)
        return run
    theme_root = Path(session["theme_artifact"]["path"]); compiled = load_json(theme_root / "compiled" / "image.json")
    reference_manifest_path = theme_root / "references" / "reference_manifest.json"
    reference_manifest = load_json(reference_manifest_path) if reference_manifest_path.is_file() else {
        "schema_version": "0.5.0", "references": [], "reference_count": 0, "distribution": "public",
    }
    output_contract = theme.get("output", {})
    effective_parameters = {
        "size": output_contract.get("size", "not_reported"), "quality": output_contract.get("quality", "not_reported"),
        "output_format": output_contract.get("format", "not_reported"), "n": 1,
    }
    if parameters is not None:
        unsupported = set(parameters) - set(effective_parameters)
        if unsupported: raise ValidationError(f"unsupported image parameters: {sorted(unsupported)}")
        effective_parameters.update(parameters)
    if effective_parameters.get("n") != 1: raise ValidationError("APSAL generation requires n=1 for every independent Job")
    if output_contract.get("provider_native") is True:
        expected_parameters = {"size": output_contract["size"], "quality": output_contract["quality"], "output_format": output_contract["format"]}
        for key, value in expected_parameters.items():
            if effective_parameters.get(key) != value: raise ValidationError(f"provider-native parameter {key} must be {value}")
    run_id = f"RUN-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8].upper()}"
    root = _run_dir(project_root, run_id)
    for relative in ("prompts", "outputs", "qa"): _mkdir_private(root / relative)
    jobs = []
    for shot in compiled["shots"]:
        shot_id = _safe_part(shot["shot_id"], "shot id")
        (root / "prompts" / f"{shot_id}.prompt.txt").write_text(shot["positive_prompt"] + "\n", encoding="utf-8")
        (root / "prompts" / f"{shot_id}.negative.txt").write_text(shot["negative_prompt"] + "\n", encoding="utf-8")
        jobs.append({
            "shot_id": shot_id, "status": "pending" if mode == "generate" else "saved",
            "prompt_digest": shot["prompt_digest"], "reference_ids": shot.get("reference_ids", []),
            "attempts": [], "output": None, "error": None, "model_visual_qa": "pending",
            "human_visual_qa": "pending",
        })
    run = {
        "schema_version": "0.5.0", "run_id": run_id, "session_id": session_id, "mode": mode,
        "status": "generating" if mode == "generate" else "completed", "theme": session["theme_artifact"],
        "dna": theme["dna"], "engine_version": ENGINE_VERSION, "adapter": adapter,
        "model": model or "not_reported", "parameters": effective_parameters, "output_contract": output_contract,
        "rendering_contract": theme.get("rendering_contract", {"status": "not_declared_legacy"}),
        "reference_manifest": {key: value for key, value in reference_manifest.items() if key != "references"} | {
            "references": [{key: value for key, value in item.items() if key != "vault_uri"} for item in reference_manifest.get("references", [])]
        },
        "jobs": jobs, "resume_count": 0, "created_at": _utc_now(), "updated_at": _utc_now(),
        "lineage_note": "Prompts and reference IDs are the exact local payload prepared for one independent request and image per Job; n is always 1.",
    }
    if mode == "skill":
        assets = registry_assets(project_root, home)
        reference_paths = {item["reference_id"]: _vault_reference_path(item["vault_uri"], home) for item in reference_manifest.get("references", [])}
        path, sha = pack_theme(theme, root, (theme_root / "theme.apsal.yaml").read_bytes(), assets=assets, reference_paths=reference_paths)
        run["skill"] = {"path": str(path), "sha256": sha}
    _write_run(run, project_root)
    session["state"] = "generating" if mode == "generate" else "completed"; _write_session(session, theme, project_root)
    return run


def record_generation_result(
    run_id: str, shot_id: str, status: str, *, project_root: Path, output_path: Path | None = None,
    artifact_uri: str | None = None, provider_metadata: dict[str, Any] | None = None, error: str | None = None,
) -> dict[str, Any]:
    """Record one provider result, preserving successful Jobs across retries."""
    if status not in {"succeeded", "failed"}: raise ValidationError("generation status must be succeeded or failed")
    project_root = project_root.expanduser().resolve(); run = load_generation_run(run_id, project_root)
    job = next((item for item in run["jobs"] if item["shot_id"] == shot_id), None)
    if not job: raise ValidationError(f"unknown shot in run: {shot_id}")
    if job["status"] == "succeeded": raise ValidationError(f"successful output is immutable: {shot_id}")
    attempt = {
        "attempt": len(job["attempts"]) + 1, "status": status, "recorded_at": _utc_now(),
        "provider_metadata": provider_metadata if provider_metadata is not None else "not_reported",
    }
    if status == "failed":
        message = (error or "provider_error_not_reported").strip()
        attempt["error"] = message; job["error"] = message
    else:
        if output_path is None and not artifact_uri:
            raise ValidationError("successful generation requires an output path or artifact URI")
        if run.get("output_contract", {}).get("provider_native") is True and output_path is None:
            raise ValidationError("provider-native output requires a local file for format and dimension validation")
        output: dict[str, Any] = {"artifact_uri": artifact_uri or "not_reported", "sha256": "not_reported"}
        if output_path is not None:
            source = output_path.expanduser().resolve()
            if not source.is_file(): raise ValidationError(f"generated output not found: {source}")
            data = source.read_bytes()
            dimensions = _validate_output_image(data, run.get("output_contract", {}))
            suffix = source.suffix.lower() if re.fullmatch(r"\.[a-z0-9]{1,8}", source.suffix.lower()) else ".bin"
            target = _run_dir(project_root, run_id) / "outputs" / f"{shot_id}{suffix}"
            if target.exists(): raise ValidationError(f"output already exists: {target.name}")
            shutil.copyfile(source, target)
            output.update({"path": str(target), "sha256": hashlib.sha256(data).hexdigest(), "size": target.stat().st_size})
            if dimensions: output.update({"width": dimensions[0], "height": dimensions[1]})
        attempt["output"] = output; job["output"] = output; job["error"] = None
        job["model_visual_qa"] = "pending"; job["human_visual_qa"] = "pending"
    job["attempts"].append(attempt); job["status"] = status
    qa = {
        "schema_version": "0.5.0", "run_id": run_id, "shot_id": shot_id,
        "static_record_status": "recorded", "visual_qa_status": "pending" if status == "succeeded" else "not_available",
        "model_visual_qa_status": "pending" if status == "succeeded" else "not_available",
        "human_visual_qa_status": "pending" if status == "succeeded" else "not_available", "human_conclusion": "not_reported",
    }
    _write_private_json(qa, _run_dir(project_root, run_id) / "qa" / f"{shot_id}.json")
    run["status"] = _generation_run_status(run)
    _write_run(run, project_root)
    session, theme = load_design_session(run["session_id"], project_root)
    session["state"] = run["status"]; _write_session(session, theme, project_root)
    return run


def _image_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        return struct.unpack(">II", data[16:24])
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP": return _webp_dimensions(data)
    raise ValidationError("generated output has an unsupported or invalid image header")


def _validate_output_image(data: bytes, output_contract: dict[str, Any]) -> tuple[int, int] | None:
    """Validate concrete bytes whenever an image contract declares a format or native size."""
    if not output_contract.get("format") and not output_contract.get("provider_native"):
        return None
    if output_contract.get("format") == "png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValidationError("provider output format is not PNG")
    width, height = _image_dimensions(data)
    size = str(output_contract.get("size", ""))
    if output_contract.get("provider_native") is True:
        if not re.fullmatch(r"[1-9][0-9]*x[1-9][0-9]*", size):
            raise ValidationError("provider-native output contract has an invalid size")
        expected = tuple(int(value) for value in size.split("x", 1))
        if (width, height) != expected:
            raise ValidationError(f"provider output dimensions {width}x{height}, expected {size}")
    return width, height


def _multipart_image_request(fields: dict[str, str], images: list[Path]) -> tuple[bytes, str]:
    boundary = "apsal-" + uuid.uuid4().hex; body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    for path in images:
        suffix = path.suffix.lower(); mime = "image/png" if suffix == ".png" else "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/webp"
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"image[]\"; filename=\"{path.name}\"\r\nContent-Type: {mime}\r\n\r\n".encode())
        body.extend(path.read_bytes()); body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def _openai_image_api_request(request: dict[str, Any], references: list[Path], api_key: str) -> dict[str, Any]:
    if not api_key: raise ValidationError("OPENAI_API_KEY is required for openai-image-api generation")
    endpoint = "https://api.openai.com/v1/images/edits" if references else "https://api.openai.com/v1/images/generations"
    fields = {key: str(request[key]) for key in ("model", "prompt", "size", "quality", "output_format", "n")}
    if references: payload, content_type = _multipart_image_request(fields, references)
    else: payload, content_type = json.dumps(fields).encode(), "application/json"
    http_request = urllib.request.Request(endpoint, data=payload, method="POST", headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": content_type,
    })
    try:
        with urllib.request.urlopen(http_request, timeout=600) as response:
            value = json.loads(response.read()); request_id = response.headers.get("x-request-id", "not_reported")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise ValidationError(f"OpenAI Image API HTTP {exc.code}: {detail}") from exc
    try: image_data = base64.b64decode(value["data"][0]["b64_json"], validate=True)
    except Exception as exc: raise ValidationError("OpenAI Image API response did not contain valid image data") from exc
    return {"image_bytes": image_data, "provider_metadata": {
        "request_id": request_id, "endpoint": "edits" if references else "generations",
        "usage": value.get("usage", "not_reported"),
    }}


def record_model_visual_qa(
    run_id: str, shot_id: str, status: str, *, project_root: Path, findings: list[str] | None = None,
) -> dict[str, Any]:
    if status not in {"passed", "failed"}: raise ValidationError("model visual QA status must be passed or failed")
    project_root = project_root.expanduser().resolve(); run = load_generation_run(run_id, project_root)
    job = next((item for item in run["jobs"] if item["shot_id"] == shot_id), None)
    if not job or job.get("status") != "succeeded" or not job.get("output"):
        raise ValidationError(f"model visual QA requires a successful output for {shot_id}")
    qa_path = _run_dir(project_root, run_id) / "qa" / f"{shot_id}.json"
    qa = load_json(qa_path) if qa_path.is_file() else {"schema_version": "0.5.0", "run_id": run_id, "shot_id": shot_id}
    qa.update({"model_visual_qa_status": status, "model_visual_qa_findings": findings or [], "human_visual_qa_status": "pending", "reviewed_at": _utc_now()})
    job["model_visual_qa"] = status
    if status == "failed":
        source = Path(job["output"].get("path", "")); rejected_root = _run_dir(project_root, run_id) / "qa" / "rejected"
        _mkdir_private(rejected_root)
        if source.is_file():
            rejected = rejected_root / f"{shot_id}-attempt-{len(job['attempts'])}{source.suffix}"
            shutil.move(source, rejected); qa["rejected_output"] = str(rejected)
        job["output"] = None; job["status"] = "failed"; job["error"] = "model_visual_qa_failed"
    run["status"] = _generation_run_status(run)
    _write_private_json(qa, qa_path); _write_run(run, project_root)
    session, theme = load_design_session(run["session_id"], project_root)
    session["state"] = run["status"]; _write_session(session, theme, project_root)
    return run


def execute_generation_run(
    run_id: str, *, project_root: Path, home: Path | None = None, max_retries: int = 2,
    max_jobs: int | None = None, adapter_callable: Any | None = None, visual_qa_callable: Any | None = None,
) -> dict[str, Any]:
    """Execute distinct Jobs sequentially. No request ever uses n > 1."""
    if not 0 <= max_retries <= 5: raise ValidationError("max_retries must be between 0 and 5")
    if max_jobs is not None and not 1 <= max_jobs <= 24: raise ValidationError("max_jobs must be between 1 and 24")
    project_root = project_root.expanduser().resolve(); home = (home or apsal_home()).resolve()
    run = load_generation_run(run_id, project_root)
    if run.get("mode") != "generate": raise ValidationError("only generate-mode runs can be executed")
    if run.get("adapter") != "openai-image-api" and adapter_callable is None:
        raise ValidationError("native 4K execution requires the openai-image-api adapter")
    if run.get("output_contract", {}).get("provider_native") is True:
        for key, value in NATIVE_4K_OUTPUT.items():
            if run["output_contract"].get(key) != value: raise ValidationError(f"run output contract mismatch: {key}")
    pending_visual = next((job for job in run["jobs"] if job.get("status") == "succeeded" and job.get("model_visual_qa") == "pending"), None)
    if pending_visual and run.get("rendering_contract", {}).get("medium") == "live_action_photography" and visual_qa_callable is None:
        raise ValidationError(f"record model visual QA for {pending_visual['shot_id']} before continuing")
    session, theme = load_design_session(run["session_id"], project_root)
    theme_root = Path(session["theme_artifact"]["path"]); compiled = load_json(theme_root / "compiled" / "image.json")
    compiled_by_id = {shot["shot_id"]: shot for shot in compiled["shots"]}
    local_manifest = load_json(theme_root / "references" / "reference_manifest.json") if (theme_root / "references" / "reference_manifest.json").is_file() else {"references": []}
    reference_records = {item["reference_id"]: item for item in local_manifest.get("references", [])}
    executed = 0; api_key = os.environ.get("OPENAI_API_KEY", "")
    run_parameters = run.get("parameters") if isinstance(run.get("parameters"), dict) else {}
    for job in run["jobs"]:
        if job["status"] not in {"pending", "failed"}: continue
        if max_jobs is not None and executed >= max_jobs: break
        shot = compiled_by_id[job["shot_id"]]
        reference_paths = [_vault_reference_path(reference_records[ref_id]["vault_uri"], home) for ref_id in job.get("reference_ids", [])]
        identity_anchor = _run_dir(project_root, run_id) / "outputs" / "SHOT_01.png"
        anchor_used = job["shot_id"] != "SHOT_01" and identity_anchor.is_file()
        if anchor_used: reference_paths.append(identity_anchor)
        runtime_reference_ids = [*job.get("reference_ids", [])]
        if anchor_used: runtime_reference_ids.append("RUNTIME_IDENTITY_ANCHOR_SHOT_01")
        anchor_instruction = (
            " Use the SHOT_01 image only to preserve the fictional adult identity and facial continuity; do not inherit its pose, camera, background, wardrobe, action, or composition."
            if anchor_used else ""
        )
        prompt = shot["positive_prompt"] + anchor_instruction + " Negative constraints: " + shot["negative_prompt"]
        (_run_dir(project_root, run_id) / "prompts" / f"{job['shot_id']}.prompt.txt").write_text(prompt + "\n", encoding="utf-8")
        request = {
            "model": run.get("model") or "gpt-image-2", "prompt": prompt,
            "size": run_parameters.get("size", run["output_contract"].get("size", "auto")),
            "quality": run_parameters.get("quality", run["output_contract"].get("quality", "high")),
            "output_format": run_parameters.get("output_format", run["output_contract"].get("format", "png")), "n": 1,
            "shot_id": job["shot_id"], "reference_ids": job.get("reference_ids", []),
            "runtime_reference_ids": runtime_reference_ids, "identity_anchor_used": anchor_used,
        }
        request_record = {key: value for key, value in request.items() if key != "prompt"}
        request_record["prompt_digest"] = hashlib.sha256(prompt.encode()).hexdigest()
        for attempt_index in range(max_retries + 1):
            try:
                response = adapter_callable(request, reference_paths) if adapter_callable else _openai_image_api_request(request, reference_paths, api_key)
                data = response["image_bytes"]
                dimensions = _validate_output_image(data, run.get("output_contract", {}))
                if dimensions is None: raise ValidationError("generation run has no concrete image output contract")
                width, height = dimensions
                with tempfile.TemporaryDirectory() as temporary:
                    candidate = Path(temporary) / f"{job['shot_id']}.png"; candidate.write_bytes(data)
                    visual = visual_qa_callable(candidate, run["rendering_contract"], job["shot_id"]) if visual_qa_callable else {"status": "pending", "findings": []}
                    if visual is False or isinstance(visual, dict) and visual.get("status") in {"failed", "fail"}:
                        raise ValidationError("model visual QA rejected live-action human medium")
                    provider = response.get("provider_metadata", "not_reported")
                    if isinstance(provider, dict): provider.update({"request": request_record, "actual_width": width, "actual_height": height, "references": runtime_reference_ids, "identity_anchor_used": anchor_used})
                    run = record_generation_result(run_id, job["shot_id"], "succeeded", project_root=project_root, output_path=candidate, provider_metadata=provider)
                if visual_qa_callable:
                    findings = visual.get("findings", []) if isinstance(visual, dict) else []
                    run = record_model_visual_qa(run_id, job["shot_id"], "passed", project_root=project_root, findings=findings)
                break
            except Exception as exc:
                run = record_generation_result(run_id, job["shot_id"], "failed", project_root=project_root, error=str(exc), provider_metadata={"request": request_record})
                job = next(item for item in run["jobs"] if item["shot_id"] == request["shot_id"])
                if attempt_index == max_retries: break
        executed += 1
        latest_job = next(item for item in run["jobs"] if item["shot_id"] == request["shot_id"])
        if latest_job["status"] != "succeeded": break
        if run.get("rendering_contract", {}).get("medium") == "live_action_photography" and visual_qa_callable is None:
            break
    return load_generation_run(run_id, project_root)


def explain_theme_path(theme: dict[str, Any], dotted_path: str) -> dict[str, Any]:
    """Explain a value using the field registry and the nearest instance intent."""
    parts = [part for part in dotted_path.split(".") if part]
    if not parts:
        raise ValidationError("explain path cannot be empty")
    current: Any = theme
    shot: dict[str, Any] | None = None
    normalized: list[str] = []
    for part in parts:
        if isinstance(current, list):
            match = next((item for item in current if isinstance(item, dict) and item.get("shot_id") == part), None)
            if match is None: raise ValidationError(f"path not found at {part}")
            current = match; shot = match; normalized.append("*")
        elif isinstance(current, dict) and part in current:
            current = current[part]; normalized.append(part)
            if part == "shots": continue
        else:
            raise ValidationError(f"path not found at {part}")
    registry_key = ".".join(normalized)
    field = load_semantic_registry().get("fields", {}).get(registry_key)
    field_name = parts[-1]
    instance_intent = shot.get("field_intents", {}).get(field_name) if shot else None
    return {
        "path": dotted_path, "normalized_path": registry_key, "value": current,
        "field_definition": field, "instance_intent": instance_intent,
        "shot_intent": shot.get("intent") if shot else None,
    }


def check_sync(root: Path) -> list[str]:
    errors: list[str] = []
    yaml_paths = sorted([*root.rglob("*.apsal.yaml"), *root.rglob("*.apsal.yml")])
    if not yaml_paths:
        return ["sync: no .apsal.yaml source files found"]
    for source in yaml_paths:
        canonical = source.with_suffix("").with_suffix(".apsal.json")
        if not canonical.is_file():
            errors.append(f"sync: missing canonical JSON for {source.relative_to(root)}"); continue
        try:
            source_value = load_document(source); canonical_value = load_document(canonical)
        except (OSError, ValueError, json.JSONDecodeError, YamlError) as exc:
            errors.append(f"sync: {exc}"); continue
        if canonical_json(source_value) != canonical_json(canonical_value):
            errors.append(f"sync: canonical JSON differs from {source.relative_to(root)}")
    return errors


def _sanitize_reference_bytes(data: bytes, suffix: str) -> tuple[bytes, str]:
    """Strip transport metadata without altering decoded pixels."""
    suffix = suffix.lower()
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        output = bytearray(data[:8]); offset = 8
        keep = {b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS", b"sRGB", b"gAMA", b"cHRM", b"iCCP"}
        while offset + 12 <= len(data):
            length = int.from_bytes(data[offset:offset + 4], "big"); end = offset + 12 + length
            if end > len(data): raise ValidationError("reference PNG is truncated")
            chunk_type = data[offset + 4:offset + 8]
            if chunk_type in keep: output.extend(data[offset:end])
            offset = end
            if chunk_type == b"IEND": break
        return bytes(output), ".png"
    if data.startswith(b"\xff\xd8"):
        output = bytearray(b"\xff\xd8"); offset = 2
        while offset < len(data):
            if data[offset] != 0xFF: raise ValidationError("reference JPEG marker is invalid")
            marker = data[offset + 1]
            if marker == 0xD9: output.extend(b"\xff\xd9"); break
            if marker == 0xDA:
                output.extend(data[offset:]); break
            if offset + 4 > len(data): raise ValidationError("reference JPEG is truncated")
            length = int.from_bytes(data[offset + 2:offset + 4], "big"); end = offset + 2 + length
            if end > len(data): raise ValidationError("reference JPEG segment is truncated")
            if marker not in {0xE1, 0xED, 0xFE}: output.extend(data[offset:end])
            offset = end
        return bytes(output), ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        chunks = bytearray(); offset = 12
        while offset + 8 <= len(data):
            name = data[offset:offset + 4]; length = int.from_bytes(data[offset + 4:offset + 8], "little")
            end = offset + 8 + length + (length % 2)
            if end > len(data): raise ValidationError("reference WebP is truncated")
            if name not in {b"EXIF", b"XMP "}: chunks.extend(data[offset:end])
            offset = end
        return b"RIFF" + (len(chunks) + 4).to_bytes(4, "little") + b"WEBP" + bytes(chunks), ".webp"
    raise ValidationError(f"unsupported reference image format: {suffix or 'unknown'}")


def build_reference_manifest(
    theme: dict[str, Any], reference_paths: dict[str, Path] | None = None,
    *, distribution: str = "auto",
) -> tuple[dict[str, Any], dict[str, bytes]]:
    references = theme.get("references", [])
    errors = validate_reference_metadata(references, theme)
    if errors: raise ValidationError("\n".join(errors))
    reference_paths = reference_paths or {}
    if distribution not in {"auto", "private_only", "public"}: raise ValidationError("distribution must be auto, private_only, or public")
    redistributable = all(_reference_rights_allow_public(ref) for ref in references)
    resolved_distribution = "private_only" if distribution == "auto" and not redistributable else "public" if distribution == "auto" else distribution
    if theme.get("distribution") == "private_only" and resolved_distribution == "public":
        raise ValidationError("private-only theme cannot be exported for public redistribution")
    if resolved_distribution == "public" and not redistributable:
        raise ValidationError("public Skill export rejected: one or more references are not redistributable")
    packaged: list[dict[str, Any]] = []; files: dict[str, bytes] = {}
    for ref in references:
        ref_id = ref["reference_id"]; source = reference_paths.get(ref_id)
        if source is None: raise ValidationError(f"reference file is required for {ref_id}")
        source = source.expanduser().resolve()
        if not source.is_file(): raise ValidationError(f"reference file not found for {ref_id}: {source}")
        original = source.read_bytes(); actual = hashlib.sha256(original).hexdigest()
        if actual != ref["original_sha256"]: raise ValidationError(f"reference digest mismatch for {ref_id}")
        sanitized, suffix = _sanitize_reference_bytes(original, source.suffix)
        packaged_name = f"{ref_id.lower()}{suffix}"
        packaged_ref = {key: value for key, value in ref.items() if key not in {"vault_uri", "path"}}
        packaged_ref.update({
            "packaged_file": f"assets/references/{packaged_name}",
            "packaged_sha256": hashlib.sha256(sanitized).hexdigest(), "metadata_sanitized": True,
        })
        packaged.append(packaged_ref); files[packaged_name] = sanitized
    manifest = {
        "schema_version": "0.5.0", "theme_id": theme["id"], "theme_version": theme["version"],
        "distribution": resolved_distribution, "private_media_included": bool(packaged) and resolved_distribution == "private_only",
        "redistribution_allowed": redistributable, "reference_count": len(packaged), "references": packaged,
    }
    manifest["reference_manifest_digest"] = digest(manifest)
    return manifest, files


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, files[name])
    return stream.getvalue()


def pack_theme(
    theme: dict[str, Any], output_dir: Path, source_yaml: bytes | None = None,
    *, assets: list[dict[str, Any]] | None = None, reference_paths: dict[str, Path] | None = None,
    distribution: str = "auto",
) -> tuple[Path, str]:
    compiled = compile_theme(theme, "image", assets)
    design = compile_theme(theme, "design", assets) if theme.get("schema_version") == "1.1.0" else None
    qa = compile_theme(theme, "qa", assets) if theme.get("schema_version") == "1.1.0" else None
    reference_manifest, reference_files = build_reference_manifest(theme, reference_paths, distribution=distribution)
    slug = f"{theme['id'].lower()}-{theme['version'].replace('.', '-')}"
    manifest = {"schema_version": "0.5.0", "engine_version": ENGINE_VERSION, "skill_id": theme["id"],
                "skill_version": theme["version"], "theme_digest": digest(theme), "compiled_digest": compiled["compiled_digest"],
                "reference_manifest_digest": reference_manifest["reference_manifest_digest"],
                "credentials_included": False, "private_media_included": reference_manifest["private_media_included"],
                "distribution": reference_manifest["distribution"],
                "redistribution_allowed": reference_manifest["redistribution_allowed"],
                "output_contract": theme.get("output"), "rendering_contract_required": bool(theme.get("rendering_contract"))}
    if theme.get("semantic_contract_version"):
        manifest["semantic_contract_version"] = theme["semantic_contract_version"]
    medium_instruction = (
        "The adult subject must remain a real human in live-action photography. Handmade, crayon, painted, or illustrated styling may affect only the set and props. "
        "Reject any illustrated, anime, painted, doll-like, wax, clay, mannequin, or 3D-rendered person."
        if theme.get("rendering_contract") else
        "This legacy theme does not declare a live-action rendering contract; do not claim that it guarantees a real-human photographic result."
    )
    output = theme.get("output", {})
    execution_instruction = (
        f"After one explicit confirmation, generate {output.get('count', len(theme['shots']))} Jobs sequentially with `scripts/generate_set.py --confirm`, one request and one independent {output['size']} {str(output['format']).upper()} per Job."
        if output.get("provider_native") is True else
        f"Generate {output.get('count', len(theme['shots']))} Jobs sequentially, one request and one independent image per Job. This legacy theme does not guarantee native 4K output dimensions."
    )
    skill = f'''---
name: {slug}
description: Generate the fixed APSAL Open photography set “{theme['name']}” from its bundled, validated theme and compiled shot plan.
---

# {theme['name']}

Read `references/theme.json`, `references/design_context.json`, `references/compiled.json`, `references/qa_checklist.json`, `references/reference_manifest.json`, and `references/rendering_contract.json`. Pass every reference listed for a Job to the image model; never substitute its text summary for the actual image. Respect each reference's allowed and forbidden uses.

{medium_instruction}

{execution_instruction} The first `--confirm` is persisted for this run. For live-action themes the executor stops after each candidate: inspect it, record `--model-qa-shot SHOT_ID --model-qa-status pass|fail`, then invoke the executor again without asking the creator to reconfirm. Never use one `n=9` request, collage, grid, contact sheet, text, logo, or watermark. Use SHOT_01 only as a runtime identity anchor for later Jobs; never inherit its pose, camera, background, wardrobe, or composition. Record model visual QA separately from human visual QA. Resume failed Jobs without replacing successful outputs.
'''
    prefix = f"{slug}/"
    files = {
        prefix + "SKILL.md": skill.encode(),
        prefix + "references/theme.json": (json.dumps(theme, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "references/compiled.json": (json.dumps(compiled, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "references/manifest.json": (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "references/reference_manifest.json": (json.dumps(reference_manifest, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "references/rendering_contract.json": (json.dumps(theme.get("rendering_contract", {"status": "not_declared_legacy"}), ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "scripts/generate_set.py": (plugin_root() / "assets" / "templates" / "generate_set.py").read_bytes(),
        prefix + "LICENSE-CONTENT.md": (
            "Theme specification content is licensed CC BY 4.0. Attribution: APSAL Open contributors.\n"
            "Bundled reference images retain the independent rights recorded in references/reference_manifest.json.\n"
            f"Distribution: {reference_manifest['distribution']}; redistribution allowed: {str(reference_manifest['redistribution_allowed']).lower()}.\n"
        ).encode(),
    }
    for name, data in reference_files.items(): files[prefix + "assets/references/" + name] = data
    if design is not None and qa is not None:
        files[prefix + "references/design_context.json"] = (json.dumps(design, ensure_ascii=False, indent=2) + "\n").encode()
        files[prefix + "references/qa_checklist.json"] = (json.dumps(qa, ensure_ascii=False, indent=2) + "\n").encode()
    if source_yaml is not None:
        files[prefix + "references/theme.apsal.yaml"] = source_yaml
    content = _zip_bytes(files); sha = hashlib.sha256(content).hexdigest()
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = "-private" if reference_manifest["distribution"] == "private_only" else ""
    path = output_dir / f"{slug}{suffix}.zip"; path.write_bytes(content)
    checksum_path = path.with_suffix(".zip.sha256"); checksum_path.write_text(f"{sha}  {path.name}\n", encoding="utf-8")
    if reference_manifest["distribution"] == "private_only":
        for private_path in (path, checksum_path):
            try: private_path.chmod(0o600)
            except OSError: pass
    return path, sha
