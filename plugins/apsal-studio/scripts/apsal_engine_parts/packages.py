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
    packaged_ids = {item["reference_id"] for item in packaged}
    anchor = theme.get("core_visual_anchor_reference_id")
    if anchor is not None and anchor not in packaged_ids:
        raise ValidationError("core visual anchor does not resolve to a packaged reference")
    if anchor is None and packaged:
        anchor = next((item["reference_id"] for item in packaged if "identity" in item.get("uses", [])), None)
        anchor = anchor or next((item["reference_id"] for item in packaged if "*" in item.get("applies_to", [])), None)
        anchor = anchor or packaged[0]["reference_id"]
    for item in packaged: item["core_visual_anchor"] = item["reference_id"] == anchor
    manifest = {
        "schema_version": "0.6.0", "theme_id": theme["id"], "theme_version": theme["version"],
        "distribution": resolved_distribution, "private_media_included": bool(packaged) and resolved_distribution == "private_only",
        "redistribution_allowed": redistributable, "reference_count": len(packaged),
        "core_visual_anchor_reference_id": anchor, "core_visual_anchor_status": "bound" if anchor else "not_bound",
        "references": packaged,
    }
    manifest["reference_manifest_digest"] = digest(manifest)
    return manifest, files


def build_skill_preview_manifest(theme: dict[str, Any]) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Build localized semantic thumbnails with an integrity ledger separate from references."""
    assets: list[dict[str, Any]] = []; files: dict[str, bytes] = {}
    for locale in SUPPORTED_INTERFACE_LANGUAGES:
        for index, layer in enumerate(CREATIVE_LAYERS, 1):
            data = build_stage_preview_svg(theme, layer, locale=locale)
            path = f"assets/previews/stages/{locale}/{index:02d}-{layer}.svg"
            title, summary, _ = _stage_preview_copy(layer, locale)
            files[path] = data
            assets.append({
                "preview_id": f"STAGE_{index:02d}_{locale}", "layer": layer, "locale": locale,
                "title": title, "alt_text": f"{title} — {summary}", "file": path,
                "mime_type": "image/svg+xml", "width": 768, "height": 576,
                "sha256": hashlib.sha256(data).hexdigest(), "generation_input": False,
                "visual_kind": "semantic_stage_summary", "qa_status": "deterministic_static_validated",
            })
    manifest = {
        "schema_version": STAGE_PREVIEW_SCHEMA_VERSION, "theme_id": theme["id"], "theme_version": theme["version"],
        "stage_count": len(CREATIVE_LAYERS), "asset_count": len(assets),
        "generation_input": False, "relationship_to_reference_manifest": "strictly_separate",
        "rights": {"license": "CC-BY-4.0", "attribution": "APSAL Open contributors", "status": "original_generated_vector_assets"},
        "assets": assets,
    }
    manifest["preview_manifest_digest"] = digest(manifest)
    return manifest, files


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, files[name])
    return stream.getvalue()


def _dna_rights_allow_public(asset: dict[str, Any], preview: dict[str, Any]) -> bool:
    private_tokens = ("private", "unverified", "unknown", "unresolved", "pending", "all-rights-reserved")
    for rights in (asset.get("rights", {}), preview.get("rights", {})):
        license_name = str(rights.get("license", "")).lower(); status = str(rights.get("status", "")).lower()
        if not license_name or not status or any(token in f"{license_name} {status}" for token in private_tokens): return False
        if not str(rights.get("attribution", "")).strip(): return False
    return True


def export_dna_pack(
    refs: list[dict[str, str]], *, pack_id: str, namespace: str, version: str, name: str,
    description: str, project_root: Path, output_dir: Path, home: Path | None = None,
    distribution: str = "auto",
) -> tuple[Path, str]:
    """Export selected immutable DNA as a deterministic standalone Extension Pack."""
    if not SAFE_NAMESPACE.fullmatch(pack_id): raise ValidationError("DNA pack id must use lower-case letters, digits, and hyphens")
    if not SAFE_NAMESPACE.fullmatch(namespace): raise ValidationError("DNA pack namespace is invalid")
    if namespace == "official": raise ValidationError("DNA Extension Packs must use a contributor-owned namespace")
    if not SEMVER.fullmatch(version): raise ValidationError("DNA pack version must be semantic")
    if not name.strip() or not description.strip(): raise ValidationError("DNA pack name and description are required")
    if not refs: raise ValidationError("DNA pack requires at least one DNA reference")
    if distribution not in {"auto", "private_only", "public"}: raise ValidationError("DNA pack distribution must be auto, private_only, or public")
    project_root = project_root.resolve(); home = (home or apsal_home()).resolve()
    records = load_layered_registry(project_root, home); by_key = {_asset_key(item["asset"]): item for item in records}
    selected = []; seen_refs: set[tuple[str, str, str, str]] = set()
    for ref in refs:
        key = tuple(str(ref.get(field, "")) for field in ("namespace", "id", "type", "version")); record = by_key.get(key)
        if not record: raise ValidationError(f"unresolved DNA reference {_ref_label(key)}")
        if key in seen_refs: raise ValidationError(f"duplicate DNA Pack reference {_ref_label(key)}")
        seen_refs.add(key)
        if ref.get("content_digest") and ref["content_digest"] != digest(record["asset"]): raise ValidationError(f"DNA digest mismatch for {_ref_label(key)}")
        if record["asset"]["namespace"] != namespace: raise ValidationError("every DNA in a pack must use the pack namespace")
        if "discovery" not in record["asset"]: raise ValidationError(f"shared DNA requires confirmed discovery metadata: {_ref_label(key)}")
        selected.append(record)
    public_allowed = all(
        _dna_rights_allow_public(item["asset"], item["preview"])
        and item["asset"].get("discovery", {}).get("source") == "creator_confirmed"
        for item in selected
    )
    resolved_distribution = "public" if distribution == "auto" and public_allowed else "private_only" if distribution == "auto" else distribution
    if resolved_distribution == "public" and not public_allowed: raise ValidationError("public DNA Pack export rejected: rights or attribution are unresolved")
    payload: dict[str, bytes] = {}
    assets_manifest = []
    for record in sorted(selected, key=lambda item: _asset_key(item["asset"])):
        asset = record["asset"]; base = f"registry/{namespace}/{asset['type']}/{asset['id']}/{asset['version']}"
        asset_path = f"{base}/asset.apsal.json"; preview_path = f"{base}/preview.webp"; preview_meta_path = f"{base}/preview.json"
        payload[asset_path] = (json.dumps(asset, ensure_ascii=False, indent=2) + "\n").encode()
        payload[preview_path] = record["preview_path"].read_bytes()
        preview_meta = json.loads(json.dumps(record["preview"])); preview_meta["ref"] = asset_ref(asset); preview_meta["image"] = "preview.webp"
        payload[preview_meta_path] = (json.dumps(preview_meta, ensure_ascii=False, indent=2) + "\n").encode()
        assets_manifest.append({"ref": asset_ref(asset), "asset_path": asset_path, "preview_path": preview_path, "preview_metadata_path": preview_meta_path, "dependencies": asset.get("dependencies", [])})
    license_lines = [f"DNA Pack: {name}", f"Distribution: {resolved_distribution}", "Each DNA and preview retains the independent license and attribution in its metadata.", "Reference media is not included."]
    payload["LICENSE-CONTENT.md"] = ("\n".join(license_lines) + "\n").encode()
    payload["README.md"] = (f"# {name}\n\n{description}\n\nAPSAL DNA Extension Pack `{namespace}/{pack_id}@{version}`. Install with `apsal registry install <zip>`; assets remain immutable and participate in explained scene recommendations.\n").encode()
    files = {path: hashlib.sha256(data).hexdigest() for path, data in sorted(payload.items())}
    manifest = {
        "schema_version": DNA_PACK_SCHEMA_VERSION, "protocol": "apsal-open", "protocol_version": OPEN_PROTOCOL_VERSION,
        "pack_id": pack_id, "namespace": namespace, "version": version, "name": name, "description": description,
        "distribution": resolved_distribution, "redistribution_allowed": public_allowed,
        "assets": assets_manifest, "asset_count": len(assets_manifest), "files": files,
    }
    checksum_text = "".join(f"{sha}  {path}\n" for path, sha in sorted(files.items()))
    archive_files = {**payload, "apsal-dna-pack.json": (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode(), "checksums.sha256": checksum_text.encode()}
    content = _zip_bytes(archive_files); sha = hashlib.sha256(content).hexdigest()
    output_dir.mkdir(parents=True, exist_ok=True); suffix = "-private" if resolved_distribution == "private_only" else ""
    path = output_dir / f"{pack_id}-v{version}{suffix}.zip"; path.write_bytes(content)
    checksum_path = path.with_suffix(".zip.sha256"); checksum_path.write_text(f"{sha}  {path.name}\n", encoding="utf-8")
    if resolved_distribution == "private_only":
        for item in (path, checksum_path):
            try: item.chmod(0o600)
            except OSError: pass
    return path, sha


def _resolve_dna_pack_source(source: str | Path) -> tuple[bytes, str]:
    value = str(source)
    if value.startswith("github:"):
        match = re.fullmatch(r"github:([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)@([^#]+)#([A-Za-z0-9_.-]+\.zip)", value)
        if not match: raise ValidationError("GitHub DNA Pack source must be github:owner/repo@tag#asset.zip")
        owner, repo, tag, asset = match.groups()
        value = f"https://github.com/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/releases/download/{urllib.parse.quote(tag, safe='')}/{urllib.parse.quote(asset)}"
    if value.startswith("https://"):
        parsed = urllib.parse.urlparse(value)
        if parsed.hostname not in {"github.com", "objects.githubusercontent.com"}: raise ValidationError("remote DNA Packs must use a public GitHub release URL")
        request = urllib.request.Request(value, headers={"User-Agent": "APSAL-Studio/0.6"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response: data = response.read(50_000_001)
        except urllib.error.URLError as exc: raise ValidationError(f"DNA Pack download failed: {exc}") from exc
        if len(data) > 50_000_000: raise ValidationError("DNA Pack exceeds 50 MB")
        return data, value
    path = Path(value).expanduser().resolve()
    if not path.is_file(): raise ValidationError(f"DNA Pack not found: {path}")
    if path.stat().st_size > 50_000_000: raise ValidationError("DNA Pack exceeds 50 MB")
    return path.read_bytes(), str(path)


def _inspect_dna_pack(data: bytes) -> tuple[dict[str, Any], dict[str, bytes]]:
    try: archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc: raise ValidationError("DNA Pack is not a valid ZIP") from exc
    names = archive.namelist()
    if len(names) != len(set(names)): raise ValidationError("DNA Pack contains duplicate paths")
    files: dict[str, bytes] = {}
    total_uncompressed = 0
    for info in archive.infolist():
        path = Path(info.filename)
        if info.is_dir(): continue
        if path.is_absolute() or ".." in path.parts or len(path.parts) > 8: raise ValidationError(f"unsafe DNA Pack path: {info.filename}")
        if (info.external_attr >> 16) & 0o170000 == 0o120000: raise ValidationError(f"DNA Pack symlink rejected: {info.filename}")
        total_uncompressed += info.file_size
        if info.file_size > 10_000_000 or total_uncompressed > 100_000_000: raise ValidationError("DNA Pack expanded content exceeds safety limits")
        files[info.filename] = archive.read(info)
    for required in ("apsal-dna-pack.json", "checksums.sha256", "README.md", "LICENSE-CONTENT.md"):
        if required not in files: raise ValidationError(f"DNA Pack missing {required}")
    try: manifest = json.loads(files["apsal-dna-pack.json"])
    except json.JSONDecodeError as exc: raise ValidationError("DNA Pack manifest is invalid JSON") from exc
    if not isinstance(manifest, dict): raise ValidationError("DNA Pack manifest must be an object")
    if manifest.get("schema_version") != DNA_PACK_SCHEMA_VERSION or manifest.get("protocol") != "apsal-open": raise ValidationError("DNA Pack manifest version or protocol is unsupported")
    if not SAFE_NAMESPACE.fullmatch(str(manifest.get("pack_id", ""))) or not SAFE_NAMESPACE.fullmatch(str(manifest.get("namespace", ""))): raise ValidationError("DNA Pack id or namespace is invalid")
    if manifest.get("namespace") == "official": raise ValidationError("DNA Extension Pack cannot use the official namespace")
    if not SEMVER.fullmatch(str(manifest.get("version", ""))): raise ValidationError("DNA Pack version is invalid")
    declared = manifest.get("files")
    if not isinstance(declared, dict): raise ValidationError("DNA Pack files ledger is missing")
    if set(declared) != set(files) - {"apsal-dna-pack.json", "checksums.sha256"}: raise ValidationError("DNA Pack files ledger does not match archive")
    for path, sha in declared.items():
        if not re.fullmatch(r"[a-f0-9]{64}", str(sha)) or hashlib.sha256(files[path]).hexdigest() != sha: raise ValidationError(f"DNA Pack checksum mismatch: {path}")
    expected_ledger = "".join(f"{sha}  {path}\n" for path, sha in sorted(declared.items())).encode()
    if files["checksums.sha256"] != expected_ledger: raise ValidationError("DNA Pack checksum ledger is not canonical")
    assets = manifest.get("assets")
    if not isinstance(assets, list) or len(assets) != manifest.get("asset_count") or not assets: raise ValidationError("DNA Pack asset count is invalid")
    seen = set()
    for entry in assets:
        if not isinstance(entry, dict): raise ValidationError("DNA Pack asset entry must be an object")
        for field in ("asset_path", "preview_path", "preview_metadata_path"):
            if entry.get(field) not in files: raise ValidationError(f"DNA Pack asset entry missing {field}")
        try: asset = json.loads(files[entry["asset_path"]]); preview = json.loads(files[entry["preview_metadata_path"]])
        except json.JSONDecodeError as exc: raise ValidationError("DNA Pack asset or preview metadata is invalid JSON") from exc
        if not isinstance(asset, dict) or not isinstance(preview, dict): raise ValidationError("DNA Pack asset and preview metadata must be objects")
        errors = validate_registry_asset(asset)
        if errors: raise ValidationError("\n".join(errors))
        if asset.get("namespace") != manifest["namespace"]: raise ValidationError("DNA Pack asset namespace mismatch")
        if entry.get("ref") != asset_ref(asset): raise ValidationError("DNA Pack asset reference digest mismatch")
        key = _asset_key(asset)
        if key in seen: raise ValidationError(f"DNA Pack duplicate asset {_ref_label(key)}")
        seen.add(key)
        with tempfile.TemporaryDirectory() as temporary:
            preview_path = Path(temporary) / "preview.webp"; preview_path.write_bytes(files[entry["preview_path"]])
            preview_errors = validate_preview_file(preview_path, preview)
        if preview_errors: raise ValidationError("\n".join(preview_errors))
        dependencies = entry.get("dependencies", [])
        if not isinstance(dependencies, list) or any(not isinstance(dep, dict) for dep in dependencies): raise ValidationError("DNA Pack dependencies must be reference objects")
        entry["_asset"] = asset
    return manifest, files


def validate_dna_pack(source: str | Path) -> dict[str, Any]:
    data, origin = _resolve_dna_pack_source(source); manifest, _ = _inspect_dna_pack(data)
    return {"valid": True, "origin": origin, "sha256": hashlib.sha256(data).hexdigest(), "pack_id": manifest["pack_id"], "namespace": manifest["namespace"], "version": manifest["version"], "distribution": manifest["distribution"], "asset_count": manifest["asset_count"]}


def install_dna_pack(source: str | Path, *, project_root: Path, home: Path | None = None) -> dict[str, Any]:
    """Install a validated local or public-GitHub DNA Pack as a read-only extension layer."""
    project_root = project_root.resolve(); home = (home or apsal_home()).resolve(); init_workspace(project_root, home)
    data, origin = _resolve_dna_pack_source(source); pack_sha = hashlib.sha256(data).hexdigest(); manifest, files = _inspect_dna_pack(data)
    target = home / "extensions" / manifest["namespace"] / manifest["pack_id"] / manifest["version"]
    existing_zip = target / "pack.zip"
    if existing_zip.is_file():
        if hashlib.sha256(existing_zip.read_bytes()).hexdigest() != pack_sha: raise ValidationError("immutable DNA Pack version conflict")
        return {"installed": False, "reason": "already_installed", "path": str(target), "sha256": pack_sha, "manifest": {key: value for key, value in manifest.items() if key != "assets"}}
    official_keys = {_asset_key(asset) for asset in load_catalog().get("assets", [])}
    existing_keys = {_asset_key(item["asset"]) for item in load_layered_registry(project_root, home)}
    pack_keys = {_asset_key(entry["_asset"]) for entry in manifest["assets"]}
    official_conflicts = pack_keys & official_keys
    if official_conflicts: raise ValidationError(f"DNA Pack cannot override official ID/version: {sorted(_ref_label(key) for key in official_conflicts)}")
    conflicts = pack_keys & existing_keys
    if conflicts: raise ValidationError(f"DNA Pack conflicts with installed Registry assets: {sorted(_ref_label(key) for key in conflicts)}")
    available = existing_keys | pack_keys
    for entry in manifest["assets"]:
        for dep in entry.get("dependencies", []):
            key = tuple(str(dep.get(field, "")) for field in ("namespace", "id", "type", "version"))
            if key not in available: raise ValidationError(f"DNA Pack unresolved dependency {_ref_label(key)}")
    temporary = target.with_name(target.name + f".tmp-{uuid.uuid4().hex[:8]}"); _mkdir_private(temporary)
    try:
        for name, value in files.items():
            path = _inside(temporary, temporary / name); path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(value)
        (temporary / "pack.zip").write_bytes(data)
        target.parent.mkdir(parents=True, exist_ok=True); temporary.rename(target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True); raise
    for path in target.rglob("*"):
        try: path.chmod(0o500 if path.is_dir() else 0o400)
        except OSError: pass
    return {"installed": True, "origin": origin, "path": str(target), "sha256": pack_sha, "manifest": {key: value for key, value in manifest.items() if key != "assets"}}


def pack_theme(
    theme: dict[str, Any], output_dir: Path, source_yaml: bytes | None = None,
    *, assets: list[dict[str, Any]] | None = None, reference_paths: dict[str, Path] | None = None,
    distribution: str = "auto",
) -> tuple[Path, str]:
    compiled = compile_theme(theme, "image", assets)
    design = compile_theme(theme, "design", assets) if theme.get("schema_version") == "1.1.0" else None
    qa = compile_theme(theme, "qa", assets) if theme.get("schema_version") == "1.1.0" else None
    reference_manifest, reference_files = build_reference_manifest(theme, reference_paths, distribution=distribution)
    preview_manifest, preview_files = build_skill_preview_manifest(theme)
    slug = f"{theme['id'].lower()}-{theme['version'].replace('.', '-')}"
    canonical_output = theme.get("output", {})
    output = codex_delivery_contract(canonical_output, len(theme["shots"]))
    medium_instruction = (
        "The adult subject must remain a real human in live-action photography. Handmade, crayon, painted, or illustrated styling may affect only the set and props. "
        "Reject any illustrated, anime, painted, doll-like, wax, clay, mannequin, or 3D-rendered person."
        if theme.get("rendering_contract") else
        "This legacy theme does not declare a live-action rendering contract; do not claim that it guarantees a real-human photographic result."
    )
    requested_size = output.get("requested_size") or output.get("size", "not_reported")
    execution_instruction = (
        f"Use Codex's built-in image-generation capability directly for {output.get('count', len(theme['shots']))} sequential Jobs. "
        "Do not call an image API, do not ask for an API key, and do not run an HTTP generation script. "
        f"Request {output.get('aspect_ratio', 'the declared aspect ratio')} and high quality; {requested_size} is a creative delivery request, not a guaranteed returned pixel size."
    )
    skill = f'''---
name: {slug}
description: Generate the fixed APSAL Open photography set “{theme['name']}” in Codex from its bundled Prompts, references, rendering contract and QA plan. Use when the creator asks to use this theme, generate or continue its shots, inspect its Prompt package, or reproduce the set without configuring an image API.
---

# {theme['name']}

Read `PROMPT_GUIDE.en.md` for English creators or `PROMPT_GUIDE.zh-CN.md` for Chinese creators, plus `references/theme.json`, `references/compiled.json`, `references/reference_manifest.json`, `references/preview_manifest.json`, and `references/rendering_contract.json`. Also read `references/design_context.json` and `references/qa_checklist.json` when present. For a specific Job, use `prompts/SHOT_XX.full.txt` as the exact provider-neutral Prompt and pass every listed reference image from `assets/references/`; never replace the actual image with its text summary. Respect each reference's allowed and forbidden uses. Files under `assets/previews/` are semantic progress thumbnails only and must never be sent to image generation.

{medium_instruction}

{execution_instruction}

Generate exactly one independent image per Codex image-generation call. After emitting an image, stop; when the creator says “继续” or “下一张”, continue with the next uncompleted Job. If all required references have local paths, pass those paths. Otherwise use the smallest recent-image count that includes the immediately previous accepted shot and use it only for facial identity continuity; never combine mutually exclusive reference mechanisms. Do not inherit the anchor's pose, action, hands, gaze, face direction, expression, camera, background, composition, makeup, hair, wardrobe, focal length, or lighting.

Never use a grid, collage, contact sheet, typography, logo, or watermark. Inspect every returned image for live-action medium, identity, skin, eyes, hands, anatomy, optics, physical light, materials, prop ownership, continuity and shot intent. Keep Codex visual review separate from human visual QA. Record actual dimensions or format only when Codex reports them; otherwise use `not_reported` and never claim native 4K.
'''
    prefix = f"{slug}/"
    prompt_files: dict[str, bytes] = {}
    for shot in compiled["shots"]:
        shot_id = shot["shot_id"]
        prompt_files[f"prompts/{shot_id}.prompt.txt"] = (shot["positive_prompt"] + "\n").encode()
        prompt_files[f"prompts/{shot_id}.negative.txt"] = (shot["negative_prompt"] + "\n").encode()
        prompt_files[f"prompts/{shot_id}.full.txt"] = (shot["positive_prompt"] + "\n\nNegative constraints:\n" + shot["negative_prompt"] + "\n").encode()
    prompt_checksums = {name: hashlib.sha256(data).hexdigest() for name, data in prompt_files.items()}
    packaged_reference_files = {
        item["reference_id"]: item["packaged_file"] for item in reference_manifest.get("references", [])
    }
    run_manifest = {
        "schema_version": "0.16.0",
        "theme_id": theme["id"],
        "theme_version": theme["version"],
        "theme_digest": digest(theme),
        "status": "not_started",
        "generation_surface": "codex_imagegen",
        "jobs": [
            {
                "shot_id": shot["shot_id"],
                "prompt_digest": shot["prompt_digest"],
                "reference_ids": shot.get("reference_ids", []),
                "reference_files": [packaged_reference_files[ref_id] for ref_id in shot.get("reference_ids", []) if ref_id in packaged_reference_files],
                "generation_status": "pending",
                "model_visual_qa": "pending",
                "human_visual_qa": "pending",
            }
            for shot in compiled["shots"]
        ],
    }
    manifest = {
        "schema_version": "0.10.0", "engine_version": ENGINE_VERSION, "skill_id": theme["id"],
        "skill_version": theme["version"], "theme_digest": digest(theme), "compiled_digest": compiled["compiled_digest"],
        "reference_manifest_digest": reference_manifest["reference_manifest_digest"],
        "preview_manifest_digest": preview_manifest["preview_manifest_digest"],
        "core_visual_anchor_reference_id": reference_manifest["core_visual_anchor_reference_id"],
        "credentials_included": False, "api_key_required": False, "direct_api_calls": False,
        "generation_surface": "codex_imagegen", "private_media_included": reference_manifest["private_media_included"],
        "distribution": reference_manifest["distribution"], "redistribution_allowed": reference_manifest["redistribution_allowed"],
        "reference_files_by_job": {
            shot["shot_id"]: [packaged_reference_files[ref_id] for ref_id in shot.get("reference_ids", []) if ref_id in packaged_reference_files]
            for shot in compiled["shots"]
        },
        "output_request": output, "returned_dimensions_guaranteed": False,
        "rendering_contract_required": bool(theme.get("rendering_contract")), "prompt_files": prompt_checksums,
        "run_manifest_digest": digest(run_manifest),
    }
    if theme.get("semantic_contract_version"): manifest["semantic_contract_version"] = theme["semantic_contract_version"]
    guide_zh = f'''# {theme['name']} — Codex Prompt 使用包

这个 ZIP 同时是可安装的 Codex Skill 和可独立阅读的 Prompt 包。它不会调用图像 API，也不需要 `OPENAI_API_KEY`。

## 在 Codex 中使用

1. 解压后把 `{slug}` 目录放进 Codex Skills 目录，或在 Codex 中直接提供这个目录。
2. 新建任务并说：“使用 `${slug}` 生成第一张图。”
3. Codex 读取 `prompts/SHOT_01.full.txt`，附加本镜在 `references/reference_manifest.json` 中声明的真实参考图，并直接调用 Codex 内置图像生成。
4. 每次只生成一张。看完后说“继续下一张”，Codex 会按 SHOT_02 到最后一镜依次执行。
5. 若只想复制 Prompt，直接打开任一 `prompts/SHOT_XX.full.txt`；`.prompt.txt` 与 `.negative.txt` 分别保存正向与负向部分。

## 重要说明

- 请求画幅：{output.get('aspect_ratio', 'not_reported')}；请求尺寸：{requested_size}。
- Codex 管理实际图像模型、格式和像素尺寸；除非返回元数据明确报告，否则它们记为 `not_reported`。本包不承诺原生 4K。
- 一次调用只生成一个 Job，不生成九宫格、拼图、联系表、文字、标志或水印。
- `assets/references/` 中的图片必须按用途、禁止用途与权利清单实际传入；文字分析不能替代图片。
- identity 参考图只锁定同一个人物的面部身份；不得继承原图姿势、动作、手势、眼神、面部朝向、表情、场景、构图、妆发服装、焦段、灯光或背景。
- `references/reference_manifest.json` 会指定一张核心视觉锚点；它仍然只能用于各镜头明确允许的范围。若状态为 `not_bound`，表示本主题没有真实参考图，不能拿缩略图代替。
- `assets/previews/` 是五阶段中文/英文语义缩略图，只帮助理解设计进度，绝不能传给图像生成。
- 后续镜头若使用上一张图保持人物身份，只继承身份，不继承姿势、机位、背景、动作、服装或构图。

Run `python3 scripts/validate_prompt_pack.py --list` to verify checksums and list every Job without making a network request.
'''
    guide_en = f'''# {theme['name']} — Codex Prompt package

This ZIP is both an installable Codex Skill and a directly readable Prompt package. It does not call an image API and does not require `OPENAI_API_KEY`.

## Use it in Codex

1. Unzip the package and place the `{slug}` folder in your Codex Skills directory, or provide the directory directly to Codex.
2. Start a new task and say: “Use `${slug}` to generate the first image.”
3. Codex reads `prompts/SHOT_01.full.txt`, attaches the real reference files declared for that shot in `references/reference_manifest.json`, and calls Codex built-in image generation.
4. Generate one image at a time. After reviewing it, say “continue to the next image.” Codex advances from SHOT_02 through the final shot.
5. To copy a Prompt without generating, open any `prompts/SHOT_XX.full.txt`. The `.prompt.txt` and `.negative.txt` files contain the positive and negative parts separately.

## Important constraints

- Requested aspect ratio: {output.get('aspect_ratio', 'not_reported')}; requested delivery size: {requested_size}.
- Codex manages the actual image model, format, and pixel dimensions. Unless returned metadata explicitly reports them, they remain `not_reported`. This package does not promise native 4K.
- One call creates one Job. Never create a grid, collage, contact sheet, text, logo, or watermark.
- Images under `assets/references/` must be passed according to their allowed uses, forbidden uses, and rights manifest. A prose analysis cannot replace the actual image.
- An identity reference preserves the same adult facial identity only. Never inherit its pose, action, hands, gaze, face direction, expression, scene, composition, makeup, hair, wardrobe, focal length, lighting, or background.
- `references/reference_manifest.json` designates one core visual anchor when real references exist. Its declared shot scope still applies. `not_bound` means no real reference is available; never substitute a thumbnail.
- Files under `assets/previews/` are localized semantic thumbnails for reviewing the five design stages. Never send them to image generation.
- A prior accepted shot may preserve identity only. It must not transfer pose, camera, background, action, wardrobe, or composition.

Run `python3 scripts/validate_prompt_pack.py --list` to verify checksums and list every Job without making a network request.
'''
    guide_index = f'''# {theme['name']} — Prompt/Skill package

- [English instructions](PROMPT_GUIDE.en.md)
- [中文使用说明](PROMPT_GUIDE.zh-CN.md)

Codex should open the guide that matches the current conversation language. The frozen image Prompts are identical in both workflows.
'''
    files = {
        prefix + "SKILL.md": skill.encode(),
        prefix + "PROMPT_GUIDE.md": guide_index.encode(),
        prefix + "PROMPT_GUIDE.en.md": guide_en.encode(),
        prefix + "PROMPT_GUIDE.zh-CN.md": guide_zh.encode(),
        prefix + "references/theme.json": (json.dumps(theme, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "references/compiled.json": (json.dumps(compiled, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "references/manifest.json": (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "references/reference_manifest.json": (json.dumps(reference_manifest, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "references/preview_manifest.json": (json.dumps(preview_manifest, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "references/rendering_contract.json": (json.dumps(theme.get("rendering_contract", {"status": "not_declared_legacy"}), ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "references/run_manifest.json": (json.dumps(run_manifest, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "scripts/validate_prompt_pack.py": (plugin_root() / "assets" / "templates" / "validate_prompt_pack.py").read_bytes(),
        prefix + "LICENSE-CONTENT.md": (
            "Theme specification content is licensed CC BY 4.0. Attribution: APSAL Open contributors.\n"
            "Bundled reference images retain the independent rights recorded in references/reference_manifest.json.\n"
            f"Distribution: {reference_manifest['distribution']}; redistribution allowed: {str(reference_manifest['redistribution_allowed']).lower()}.\n"
        ).encode(),
    }
    for name, data in prompt_files.items(): files[prefix + name] = data
    for name, data in reference_files.items(): files[prefix + "assets/references/" + name] = data
    for name, data in preview_files.items(): files[prefix + name] = data
    if design is not None and qa is not None:
        files[prefix + "references/design_context.json"] = (json.dumps(design, ensure_ascii=False, indent=2) + "\n").encode()
        files[prefix + "references/qa_checklist.json"] = (json.dumps(qa, ensure_ascii=False, indent=2) + "\n").encode()
    if source_yaml is not None:
        files[prefix + "references/theme.apsal.yaml"] = source_yaml
    checksum_ledger = "".join(
        f"{hashlib.sha256(data).hexdigest()}  {name[len(prefix):]}\n"
        for name, data in sorted(files.items())
    )
    files[prefix + "checksums.sha256"] = checksum_ledger.encode("utf-8")
    content = _zip_bytes(files); sha = hashlib.sha256(content).hexdigest()
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = "-private" if reference_manifest["distribution"] == "private_only" else ""
    path = output_dir / f"{slug}-codex-prompt-skill{suffix}.zip"; path.write_bytes(content)
    checksum_path = path.with_suffix(".zip.sha256"); checksum_path.write_text(f"{sha}  {path.name}\n", encoding="utf-8")
    if reference_manifest["distribution"] == "private_only":
        for private_path in (path, checksum_path):
            try: private_path.chmod(0o600)
            except OSError: pass
    return path, sha
