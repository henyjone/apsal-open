from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import re
import sys
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

ENGINE_VERSION = "0.3.0"
SEMANTIC_CONTRACT_VERSION = "0.3.0"
CATEGORIES = ("character", "style", "environment", "lighting", "composition", "shot", "qa")
PROTOCOL_TYPES = ("subject", "world", "style", "look", "emotion", "event", "camera", "light", "color_post", "quality_control", "content", "sequence", "job")
CREATIVE_FIELDS = ("framing", "action", "hands", "gaze", "composition")
COMPILE_TARGETS = ("design", "image", "qa")
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
SAFE_ID = re.compile(r"^[A-Z][A-Z0-9-]*$")


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


def catalog_index() -> dict[tuple[str, str, str, str], dict[str, Any]]:
    assets = load_catalog().get("assets", [])
    return {(a["namespace"], a["id"], a["type"], a["version"]): a for a in assets}


def asset_ref(asset: dict[str, Any]) -> dict[str, str]:
    return {
        "namespace": asset["namespace"], "id": asset["id"], "type": asset["type"],
        "version": asset["version"], "content_digest": digest(asset),
    }


def new_theme(theme_id: str, name: str, shot_count: int = 9) -> dict[str, Any]:
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
            "output_filename": f"{theme_id.lower()}_{i:02d}.jpg",
        })
    return {
        "schema_version": "1.0.0", "id": theme_id, "version": "1.0.0", "name": name,
        "parent_version": None, "changed_fields": ["initial_version"],
        "change_summary": "Initial original APSAL Open theme.", "dna": refs,
        "output": {"count": shot_count, "aspect_ratio": "2:3", "independent_images": True,
                   "forbid": ["collage", "grid", "contact sheet", "text", "logo", "watermark"]},
        "shots": shots,
        "rights": {"license": "CC-BY-4.0", "status": "original_open_content", "attribution": "APSAL Open contributors"},
        "qa_status": "visual_qa_pending",
    }


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


def new_semantic_theme(theme_id: str, name: str, shot_count: int = 9) -> dict[str, Any]:
    """Create a Protocol 0.3 authoring theme with complete generic semantics."""
    theme = new_theme(theme_id, name, shot_count)
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


def validate_theme(theme: dict[str, Any]) -> list[str]:
    errors = validate_catalog()
    for key in ("schema_version", "id", "version", "name", "parent_version", "changed_fields", "change_summary", "dna", "output", "shots", "rights", "qa_status"):
        if key not in theme:
            errors.append(f"theme: missing {key}")
    if theme.get("schema_version") not in {"1.0.0", "1.1.0"}: errors.append("theme: unsupported schema_version")
    if not SAFE_ID.fullmatch(str(theme.get("id", ""))): errors.append("theme: invalid id")
    if not SEMVER.fullmatch(str(theme.get("version", ""))): errors.append("theme: invalid semantic version")
    refs = theme.get("dna", [])
    if not isinstance(refs, list):
        errors.append("theme: dna must be an array"); refs = []
    index = catalog_index()
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
        positive = f"{shared}, {instruction}"
        compiled.append({"shot_id": shot["shot_id"], "title": shot["title"], "positive_prompt": positive,
                         "negative_prompt": negative, "prompt_digest": digest({"positive": positive, "negative": negative})})
    return {"target": "image", "shots": compiled}


def _compile_design(theme: dict[str, Any], assets: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "target": "design",
        "semantic_contract_version": theme.get("semantic_contract_version"),
        "priority_order": [
            "identity_and_rights", "world_physics_and_continuity", "event_and_shot_function",
            "camera_light_and_color", "style_rhetoric",
        ],
        "theme_semantics": theme.get("semantics"),
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
        shots.append({"shot_id": shot["shot_id"], "title": shot["title"], "output_filename": shot["output_filename"], "checks": checks})
    return {"target": "qa", "global_checks": global_checks, "shots": shots}


def compile_theme(theme: dict[str, Any], target: str = "image") -> dict[str, Any]:
    if target not in COMPILE_TARGETS:
        raise ValidationError(f"compile target must be one of {', '.join(COMPILE_TARGETS)}")
    errors = validate_theme(theme)
    if errors: raise ValidationError("\n".join(errors))
    index = catalog_index()
    assets = [index[tuple(ref[k] for k in ("namespace", "id", "type", "version"))] for ref in theme["dna"]]
    payload = _compile_image(theme, assets) if target == "image" else _compile_design(theme, assets) if target == "design" else _compile_qa(theme)
    result = {"engine_version": ENGINE_VERSION, "theme_id": theme["id"], "theme_version": theme["version"],
              "theme_digest": digest(theme), **payload}
    result["compiled_digest"] = digest(result)
    return result


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


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, files[name])
    return stream.getvalue()


def pack_theme(theme: dict[str, Any], output_dir: Path, source_yaml: bytes | None = None) -> tuple[Path, str]:
    compiled = compile_theme(theme, "image")
    design = compile_theme(theme, "design") if theme.get("schema_version") == "1.1.0" else None
    qa = compile_theme(theme, "qa") if theme.get("schema_version") == "1.1.0" else None
    slug = f"{theme['id'].lower()}-{theme['version'].replace('.', '-')}"
    manifest = {"schema_version": "1.0.0", "engine_version": ENGINE_VERSION, "skill_id": theme["id"],
                "skill_version": theme["version"], "theme_digest": digest(theme), "compiled_digest": compiled["compiled_digest"],
                "credentials_included": False, "private_media_included": False}
    if theme.get("semantic_contract_version"):
        manifest["semantic_contract_version"] = theme["semantic_contract_version"]
    skill = f'''---
name: {slug}
description: Generate the fixed APSAL Open photography set “{theme['name']}” from its bundled, validated theme and compiled shot plan.
---

# {theme['name']}

Read `references/theme.json`, `references/design_context.json`, `references/compiled.json`, and `references/qa_checklist.json` when present. Use the semantic design context to understand why each scene exists, but send only the observable compiled image instructions to the image model. Generate each shot as one independent finished image in order. Preserve the locked adult identity and continuity. Never create a collage, grid, contact sheet, text, logo, or watermark. Static validation is not human visual QA.
'''
    prefix = f"{slug}/"
    files = {
        prefix + "SKILL.md": skill.encode(),
        prefix + "references/theme.json": (json.dumps(theme, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "references/compiled.json": (json.dumps(compiled, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "references/manifest.json": (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "LICENSE-CONTENT.md": b"Theme content is licensed CC BY 4.0. Attribution: APSAL Open contributors.\n",
    }
    if design is not None and qa is not None:
        files[prefix + "references/design_context.json"] = (json.dumps(design, ensure_ascii=False, indent=2) + "\n").encode()
        files[prefix + "references/qa_checklist.json"] = (json.dumps(qa, ensure_ascii=False, indent=2) + "\n").encode()
    if source_yaml is not None:
        files[prefix + "references/theme.apsal.yaml"] = source_yaml
    content = _zip_bytes(files); sha = hashlib.sha256(content).hexdigest()
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{slug}.zip"; path.write_bytes(content)
    path.with_suffix(".zip.sha256").write_text(f"{sha}  {path.name}\n", encoding="utf-8")
    return path, sha
