from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any

ENGINE_VERSION = "0.2.0"
CATEGORIES = ("character", "style", "environment", "lighting", "composition", "shot", "qa")
PROTOCOL_TYPES = ("subject", "world", "style", "look", "emotion", "event", "camera", "light", "color_post", "quality_control", "content", "sequence", "job")
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


def validate_theme(theme: dict[str, Any]) -> list[str]:
    errors = validate_catalog()
    for key in ("schema_version", "id", "version", "name", "parent_version", "changed_fields", "change_summary", "dna", "output", "shots", "rights", "qa_status"):
        if key not in theme:
            errors.append(f"theme: missing {key}")
    if theme.get("schema_version") != "1.0.0": errors.append("theme: unsupported schema_version")
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


def compile_theme(theme: dict[str, Any]) -> dict[str, Any]:
    errors = validate_theme(theme)
    if errors: raise ValidationError("\n".join(errors))
    index = catalog_index()
    assets = [index[tuple(ref[k] for k in ("namespace", "id", "type", "version"))] for ref in theme["dna"]]
    ordered = sorted(assets, key=lambda a: CATEGORIES.index(a["type"]))
    shared = ", ".join(a["prompt_fragment"] for a in ordered)
    negative = ", ".join(a["negative_fragment"] for a in ordered)
    compiled = []
    for shot in theme["shots"]:
        instruction = (
            f"Create exactly one independent finished vertical photograph for {shot['shot_id']} ({shot['title']}). "
            f"Narrative purpose: {shot['narrative_purpose']}. Framing: {shot['framing']}. Action: {shot['action']}. "
            f"Hands: {shot['hands']}. Gaze: {shot['gaze']}. Composition: {shot['composition']}. "
            f"Continuity: {canonical_json(shot['continuity'])}. Output file: {shot['output_filename']}."
        )
        positive = f"{shared}, {instruction}"
        compiled.append({"shot_id": shot["shot_id"], "title": shot["title"], "positive_prompt": positive,
                         "negative_prompt": negative, "prompt_digest": digest({"positive": positive, "negative": negative})})
    result = {"engine_version": ENGINE_VERSION, "theme_id": theme["id"], "theme_version": theme["version"],
              "theme_digest": digest(theme), "shots": compiled}
    result["compiled_digest"] = digest(result)
    return result


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, files[name])
    return stream.getvalue()


def pack_theme(theme: dict[str, Any], output_dir: Path) -> tuple[Path, str]:
    compiled = compile_theme(theme)
    slug = f"{theme['id'].lower()}-{theme['version'].replace('.', '-')}"
    manifest = {"schema_version": "1.0.0", "engine_version": ENGINE_VERSION, "skill_id": theme["id"],
                "skill_version": theme["version"], "theme_digest": digest(theme), "compiled_digest": compiled["compiled_digest"],
                "credentials_included": False, "private_media_included": False}
    skill = f'''---
name: {slug}
description: Generate the fixed APSAL Open photography set “{theme['name']}” from its bundled, validated theme and compiled shot plan.
---

# {theme['name']}

Read `references/theme.json` and `references/compiled.json`. Generate each shot as one independent finished image in order. Preserve the locked adult identity and continuity. Never create a collage, grid, contact sheet, text, logo, or watermark. Static validation is not human visual QA.
'''
    prefix = f"{slug}/"
    files = {
        prefix + "SKILL.md": skill.encode(),
        prefix + "references/theme.json": (json.dumps(theme, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "references/compiled.json": (json.dumps(compiled, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "references/manifest.json": (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "LICENSE-CONTENT.md": b"Theme content is licensed CC BY 4.0. Attribution: APSAL Open contributors.\n",
    }
    content = _zip_bytes(files); sha = hashlib.sha256(content).hexdigest()
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{slug}.zip"; path.write_bytes(content)
    path.with_suffix(".zip.sha256").write_text(f"{sha}  {path.name}\n", encoding="utf-8")
    return path, sha
