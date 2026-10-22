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
    roots = [("project", project_root / ".apsal" / "registry"), ("personal", home / "registry")]
    extensions = home / "extensions"
    if extensions.is_dir():
        roots.extend(("extension", path) for path in sorted(extensions.glob("*/*/*/registry")) if path.is_dir())
    return roots


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
    if "discovery" in asset:
        errors.extend(validate_discovery_metadata(asset["discovery"]))
        semantic_registry = load_semantic_registry(); mapped_roles = set(semantic_registry.get("dna_to_protocol", {}).get(asset.get("type"), []))
        tag_roles = {item["id"]: set(item.get("roles", [])) for item in semantic_registry.get("tags", [])}
        incompatible = [tag for tag in asset["discovery"].get("semantic_tags", []) if not (tag_roles.get(tag, set()) & mapped_roles)] if isinstance(asset["discovery"], dict) else []
        if incompatible: errors.append(f"DNA discovery: tags incompatible with {asset.get('type')} DNA {sorted(incompatible)}")
        allowed_prefixes = DISCOVERY_FACET_PREFIXES.get(asset.get("type"), ())
        incompatible_facets = [key for key in asset["discovery"].get("facets", {}) if not any(key.startswith(prefix) for prefix in allowed_prefixes)] if isinstance(asset["discovery"], dict) and isinstance(asset["discovery"].get("facets"), dict) else []
        if incompatible_facets: errors.append(f"DNA discovery: facets incompatible with {asset.get('type')} DNA {sorted(incompatible_facets)}")
    return errors


def validate_discovery_metadata(value: Any) -> list[str]:
    if not isinstance(value, dict): return ["DNA discovery: must be an object"]
    errors: list[str] = []
    tags = value.get("semantic_tags")
    if not isinstance(tags, list) or not tags or any(not isinstance(tag, str) for tag in tags):
        errors.append("DNA discovery: semantic_tags must be a non-empty string array")
    else:
        if len(tags) != len(set(tags)): errors.append("DNA discovery: semantic_tags must be unique")
        unknown = set(tags) - allowed_semantic_tags()
        if unknown: errors.append(f"DNA discovery: unknown semantic_tags {sorted(unknown)}")
    facets = value.get("facets")
    if not isinstance(facets, dict):
        errors.append("DNA discovery: facets must be an object")
    else:
        unknown_facets = set(facets) - DISCOVERY_FACETS
        if unknown_facets: errors.append(f"DNA discovery: unknown facets {sorted(unknown_facets)}")
        for key, facet_value in facets.items():
            values = facet_value if isinstance(facet_value, list) else [facet_value]
            if not values or any(not isinstance(item, str) or not item.strip() for item in values):
                errors.append(f"DNA discovery: facet {key} must contain non-empty strings")
    keywords = value.get("keywords", [])
    if not isinstance(keywords, list) or len(keywords) > 32 or any(not isinstance(item, str) or not item.strip() for item in keywords):
        errors.append("DNA discovery: keywords must be an array of at most 32 non-empty strings")
    if value.get("source") not in {"auto", "creator_confirmed"}:
        errors.append("DNA discovery: source must be auto or creator_confirmed")
    return errors


def _detect_recommendation_context(text: str) -> dict[str, Any]:
    folded = text.casefold(); tags: set[str] = set(); facets: dict[str, set[str]] = {}; signals: list[str] = []
    for signal in load_recommendation_registry().get("signals", []):
        if any(str(term).casefold() in folded for term in signal.get("terms", [])):
            signals.append(signal["id"]); tags.update(signal.get("tags", []))
            for key, value in signal.get("facets", {}).items():
                facets.setdefault(key, set()).add(str(value))
    return {
        "signals": signals, "semantic_tags": sorted(tags),
        "facets": {key: sorted(values) if len(values) > 1 else next(iter(values)) for key, values in sorted(facets.items())},
    }


def suggest_discovery_metadata(asset: dict[str, Any], brief: str = "") -> dict[str, Any]:
    """Suggest deterministic controlled tags; creators confirm or edit before formal save."""
    text = " ".join(str(asset.get(key, "")) for key in ("id", "type", "change_summary", "prompt_fragment", "negative_fragment"))
    context = _detect_recommendation_context(f"{brief} {text}")
    defaults = load_recommendation_registry().get("default_tags", {}).get(asset.get("type"), [])
    semantic_registry = load_semantic_registry(); mapped_roles = set(semantic_registry.get("dna_to_protocol", {}).get(asset.get("type"), []))
    tag_roles = {item["id"]: set(item.get("roles", [])) for item in semantic_registry.get("tags", [])}
    tags = sorted(tag for tag in set(defaults) | set(context["semantic_tags"]) if tag_roles.get(tag, set()) & mapped_roles)
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", text.casefold())
    keywords = sorted(dict.fromkeys(word for word in words if word not in DISCOVERY_STOPWORDS))[:16]
    facet_prefixes = DISCOVERY_FACET_PREFIXES.get(asset.get("type"), ())
    facets = {key: value for key, value in context["facets"].items() if any(key.startswith(prefix) for prefix in facet_prefixes)}
    return {
        "schema_version": "0.6.0", "semantic_tags": tags, "facets": facets,
        "keywords": keywords, "source": "auto", "source_brief_digest": hashlib.sha256(brief.encode()).hexdigest() if brief else "not_reported",
    }


def confirm_discovery_metadata(value: dict[str, Any]) -> dict[str, Any]:
    confirmed = json.loads(json.dumps(value)); confirmed["source"] = "creator_confirmed"
    errors = validate_discovery_metadata(confirmed)
    if errors: raise ValidationError("\n".join(errors))
    return confirmed


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
        return {"scope": scope, "path": str(target), "ref": asset_ref(current), "created": False}
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
    return {"scope": scope, "path": str(target), "ref": asset_ref(asset), "created": True}


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
    scope_rank = {"project": 0, "personal": 1, "extension": 2, "official": 3}
    for record in load_layered_registry(project_root, home):
        asset = record["asset"]
        if asset["type"] not in allowed: continue
        haystack = (" ".join(str(asset.get(key, "")) for key in ("id", "type", "change_summary", "prompt_fragment")) + " " + canonical_json(asset.get("discovery", {}))).casefold()
        if terms and not all(term in haystack for term in terms): continue
        score = sum(haystack.count(term) for term in terms)
        scored.append((-score, scope_rank[record["scope"]], record))
    scored.sort(key=lambda item: (item[0], item[1], item[2]["asset"]["type"], item[2]["asset"]["id"]))
    return [record for _, _, record in scored[:max(1, min(limit, 50))]]


def _usage_events_path(home: Path) -> Path:
    return _inside(home, home / "usage" / "events.jsonl")


def _append_usage_event(event: dict[str, Any], home: Path) -> None:
    path = _usage_events_path(home); _mkdir_private(path.parent)
    value = {"schema_version": "0.6.0", "recorded_at": _utc_now(), **event}
    with path.open("a", encoding="utf-8") as stream: stream.write(canonical_json(value) + "\n")
    try: path.chmod(0o600)
    except OSError: pass


def _usage_weights(home: Path) -> dict[tuple[str, str, str, str], int]:
    path = _usage_events_path(home); weights: dict[tuple[str, str, str, str], int] = {}
    if not path.is_file(): return weights
    values = {"accepted": 2, "rejected": -6, "successful": 6, "failed": -3, "selected": 1, "remembered": 3}
    for line in path.read_text(encoding="utf-8").splitlines():
        try: event = json.loads(line)
        except json.JSONDecodeError: continue
        ref = event.get("ref", {}); key = tuple(str(ref.get(name, "")) for name in ("namespace", "id", "type", "version"))
        if all(key): weights[key] = weights.get(key, 0) + values.get(event.get("outcome"), 0)
    return weights


def record_dna_feedback(
    ref: dict[str, str], outcome: str, *, project_root: Path, home: Path | None = None,
    context: str = "", note: str = "",
) -> dict[str, Any]:
    if outcome not in FEEDBACK_OUTCOMES: raise ValidationError(f"feedback outcome must be one of {sorted(FEEDBACK_OUTCOMES)}")
    project_root = project_root.resolve(); home = (home or apsal_home()).resolve(); init_workspace(project_root, home)
    key = tuple(str(ref.get(name, "")) for name in ("namespace", "id", "type", "version"))
    record = next((item for item in load_layered_registry(project_root, home) if _asset_key(item["asset"]) == key), None)
    if not record: raise ValidationError(f"unresolved DNA reference {_ref_label(key)}")
    detected = _detect_recommendation_context(context)
    event = {
        "event": "dna_feedback", "outcome": outcome, "ref": asset_ref(record["asset"]),
        "context": detected, "context_digest": hashlib.sha256(context.encode()).hexdigest() if context else "not_reported",
        "note": note[:240],
    }
    _append_usage_event(event, home)
    return {"recorded": True, "outcome": outcome, "ref": event["ref"], "preference_weight": _usage_weights(home).get(key, 0)}


def recommend_dna(
    brief: str, stage: str, *, project_root: Path, home: Path | None = None,
    session_id: str | None = None, limit: int = 6, _asset_types: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Rank DNA for one scene stage and explain every recommendation."""
    if not brief.strip(): raise ValidationError("recommendation brief cannot be empty")
    if stage not in INTERACTION_STAGES and stage not in CREATIVE_LAYERS: raise ValidationError(f"unknown interaction stage: {stage}")
    project_root = project_root.resolve(); home = (home or apsal_home()).resolve()
    allowed_types = _asset_types or (STAGE_TYPES[stage] if stage in STAGE_TYPES else LAYER_TYPES[stage])
    context = _detect_recommendation_context(brief); context_tags = set(context["semantic_tags"])
    context_facets = {key: set(value if isinstance(value, list) else [value]) for key, value in context["facets"].items()}
    selected_refs: list[dict[str, str]] = []
    if session_id:
        session, _ = load_design_session(session_id, project_root)
        if session.get("schema_version") == "0.7.0" and stage in CREATIVE_LAYERS:
            for prior in CREATIVE_LAYERS[:CREATIVE_LAYERS.index(stage)]: selected_refs.extend(session["layers"][prior].get("selection", []))
        elif stage in INTERACTION_STAGES:
            for prior in INTERACTION_STAGES[:INTERACTION_STAGES.index(stage)]: selected_refs.extend(session["stages"][prior].get("selection", []))
    selected_keys = {tuple(str(ref.get(name, "")) for name in ("namespace", "id", "type", "version")) for ref in selected_refs}
    weights = _usage_weights(home); scope_bonus = {"project": 3, "personal": 2, "extension": 1, "official": 0}
    brief_terms = {term for term in re.findall(r"[a-z0-9-]{2,}", brief.casefold())}
    recommendations: list[tuple[int, int, str, dict[str, Any]]] = []
    for record in load_layered_registry(project_root, home):
        asset = record["asset"]
        if asset["type"] not in allowed_types: continue
        discovery = asset.get("discovery") or suggest_discovery_metadata(asset)
        tags = set(discovery.get("semantic_tags", [])); matched_tags = sorted(tags & context_tags)
        facets = discovery.get("facets", {}); matched_facets = []
        for key, wanted in context_facets.items():
            actual_value = facets.get(key); actual = set(actual_value if isinstance(actual_value, list) else [actual_value]) if actual_value is not None else set()
            if actual & wanted: matched_facets.append(key)
        text = " ".join(str(asset.get(key, "")) for key in ("id", "change_summary", "prompt_fragment")).casefold()
        matched_terms = sorted(term for term in brief_terms if term in text)
        key = _asset_key(asset); score = scope_bonus[record["scope"]] + len(matched_tags) * 8 + len(matched_facets) * 5 + len(matched_terms) * 2
        preference = max(-10, min(10, weights.get(key, 0))); score += preference
        reasons = []
        if matched_tags: reasons.append(f"semantic match: {', '.join(matched_tags)}")
        if matched_facets: reasons.append(f"scene facets: {', '.join(matched_facets)}")
        if matched_terms: reasons.append(f"brief terms: {', '.join(matched_terms[:5])}")
        dependencies = {tuple(str(dep.get(name, "")) for name in ("namespace", "id", "type", "version")) for dep in asset.get("dependencies", []) if isinstance(dep, dict)}
        if dependencies & selected_keys: score += 10; reasons.append("explicitly compatible with confirmed upstream DNA")
        if preference: reasons.append(f"personal usage memory: {preference:+d}")
        reasons.append(f"{record['scope']} Registry; {asset['qa_status']} QA; rights {asset['rights']['status']}")
        recommendations.append((-score, {"project": 0, "personal": 1, "extension": 2, "official": 3}[record["scope"]], asset["id"], {
            "score": score, "reasons": reasons, "matched_tags": matched_tags, "matched_facets": matched_facets,
            "record": record, "discovery": discovery,
        }))
    recommendations.sort(key=lambda item: item[:3]); selected = [item[3] for item in recommendations[:max(1, min(limit, 12))]]
    return {
        "stage": stage, "context": context, "selected_upstream_refs": selected_refs,
        "recommendations": selected, "count": len(selected),
        "ranking_policy": ["identity_rights_medium", "scene_intent", "dependency_compatibility", "photo_language", "personal_memory", "qa_scope"],
    }


def recommend_layer_dna(
    brief: str, layer: str, *, project_root: Path, home: Path | None = None,
    session_id: str | None = None, limit_per_type: int = 3,
) -> dict[str, Any]:
    """Recommend at least one explained candidate for every DNA type required by a creative layer."""
    if layer not in CREATIVE_LAYERS: raise ValidationError(f"unknown creative layer: {layer}")
    by_type: dict[str, list[dict[str, Any]]] = {}
    for asset_type in LAYER_TYPES[layer]:
        value = recommend_dna(brief, layer, project_root=project_root, home=home, session_id=session_id,
                              limit=limit_per_type, _asset_types=(asset_type,))
        by_type[asset_type] = value["recommendations"]
    return {
        "layer": layer, "required_types": list(LAYER_TYPES[layer]), "by_type": by_type,
        "count": sum(len(items) for items in by_type.values()),
        "ranking_policy": ["identity_rights_medium", "scene_intent", "dependency_compatibility", "photo_language", "personal_memory", "qa_scope"],
    }


ZH_OFFICIAL_DNA = {
    "OPEN_CHAR_ADULT_001": {
        "title": "稳定成年人物基线", "summary": "原创虚构成年人物身份基线。",
        "core": ["虚构东亚成年女性，年龄二十八至三十五岁", "自然面部结构与真实皮肤质感", "整组锁定年龄、发型和身体比例"],
    },
    "OPEN_STYLE_EDITORIAL_001": {
        "title": "克制的当代编辑摄影", "summary": "克制、真实并保留材质触感的当代编辑摄影风格。",
        "core": ["真实材质与轻微胶片颗粒", "受控反差和自然色彩分离", "避免过度修饰与人工光泽"],
    },
    "OPEN_ENV_WINDOW_001": {
        "title": "静谧窗边空间", "summary": "原创、连续且物理关系清楚的安静窗边环境。",
        "core": ["灰泥墙、东向高窗、浅色木地板与亚麻帘", "低矮木桌和稳定空间几何", "全部镜头属于同一房间"],
    },
    "OPEN_LIGHT_WINDOW_001": {
        "title": "三阶段自然窗光", "summary": "从冷调进入到温暖余晖的三阶段自然窗光。",
        "core": ["柔和定向窗光与可信衰减", "冷调进入、中性日间、温暖余晖", "每个阶段保持一致阴影方向"],
    },
    "OPEN_COMP_SEQUENCE_001": {
        "title": "均衡的多镜头覆盖", "summary": "兼顾叙事变化和画面呼吸的多镜头编辑摄影覆盖。",
        "core": ["环境、全身、中景、近景与细节有意变化", "主体分离清楚", "负空间服务叙事而非装饰"],
    },
    "OPEN_SHOT_NINE_001": {
        "title": "九镜独立成图基线", "summary": "九个镜头分别完成叙事职能，并各自输出一张独立成图。",
        "core": ["每镜都有不同叙事职能", "先设计可观察动作，再设计姿态", "不生成九宫格、拼图、文字或水印"],
    },
    "OPEN_QA_PORTRAIT_001": {
        "title": "人像套片质量检查", "summary": "覆盖身份、人体结构、连续性和输出规则的人像套片检查方案。",
        "core": ["检查身份、手部、人体结构和服装连续性", "检查道具归属、空间几何、反射和灯光方向", "检查镜头意图、非目标漂移及文字水印"],
    },
}


def _zh_rights_label(rights: dict[str, Any]) -> str:
    status = str(rights.get("status", ""))
    if status in {"original_open_content", "authorized_open_content"}: return "权利清晰的开放内容"
    if status == "private_user_content": return "仅限私人使用的内容"
    return "权利状态已记录"


def dna_card(record: dict[str, Any], locale: str = "en") -> dict[str, Any]:
    """Return the compact text-card projection used by conversational clients.

    Registry previews remain available for rights review and Extension Pack
    validation, but are deliberately excluded from interactive selection data.
    """
    asset = record["asset"]
    card = {
        "ref": asset_ref(asset), "scope": record["scope"], "title": asset["id"], "type": asset["type"],
        "summary": asset["change_summary"], "version": asset["version"], "locks": asset.get("locks", []),
        "core_attributes": asset.get("locks") or [asset["prompt_fragment"]],
        "rights": asset["rights"], "qa_status": asset["qa_status"],
    }
    if locale != "zh-CN":
        card.update({
            "type_label": asset["type"], "scope_label": record["scope"], "qa_status_label": asset["qa_status"],
            "reference_label": f"{asset['namespace']}/{asset['id']} · v{asset['version']} · {record['scope']}",
            "rights_label": f"{asset['rights'].get('license', '')} · {asset['rights'].get('attribution', '')}",
        })
        return card
    official = ZH_OFFICIAL_DNA.get(asset["id"])
    summary_text = str(asset.get("change_summary", ""))
    has_zh_summary = bool(re.search(r"[\u3400-\u9fff]", summary_text)) and not _contains_latin(summary_text)
    type_label = ZH_UI_LABELS["types"].get(asset["type"], "创作资源")
    card.update({
        "title": official["title"] if official else (asset["change_summary"] if has_zh_summary else "自定义" + type_label),
        "type_label": type_label, "scope_label": ZH_UI_LABELS["scopes"].get(record["scope"], "资源库"),
        "summary": official["summary"] if official else (asset["change_summary"] if has_zh_summary else "已按当前创作方案记录的可复用资源。"),
        "core_attributes": official["core"] if official else ["核心约束已记录", "正式版本不可原地覆盖"],
        "qa_status_label": ZH_UI_LABELS["qa"].get(asset["qa_status"], "质量状态已记录"),
        "reference_label": f"{ZH_UI_LABELS['scopes'].get(record['scope'], '资源库')} · 版本 {asset['version']} · 摘要已校验",
        "rights_label": _zh_rights_label(asset["rights"]),
    })
    return card


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


def codex_imagegen_output_contract(shot_count: int) -> dict[str, Any]:
    """Return the honest output request for Codex-managed image generation.

    Aspect ratio and quality are creative requests. The built-in Codex image
    tool owns its concrete format and pixel dimensions, so APSAL never turns a
    requested 4K size into a provider-native guarantee.
    """
    return {
        "count": shot_count, **CODEX_IMAGEGEN_OUTPUT, "independent_images": True,
        "forbid": ["collage", "grid", "contact sheet", "text", "logo", "watermark"],
    }


def codex_delivery_contract(output: dict[str, Any], shot_count: int) -> dict[str, Any]:
    """Translate any canonical output request into an honest Codex handoff."""
    contract = codex_imagegen_output_contract(shot_count)
    contract["aspect_ratio"] = output.get("aspect_ratio", contract["aspect_ratio"])
    requested_size = output.get("requested_size")
    if not requested_size and re.fullmatch(r"[1-9][0-9]*x[1-9][0-9]*", str(output.get("size", ""))):
        requested_size = output["size"]
    contract["requested_size"] = requested_size or "not_reported"
    return contract
