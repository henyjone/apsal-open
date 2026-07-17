#!/usr/bin/env python3
"""Validate and inspect an APSAL Codex Prompt Skill without network access."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "references"
PROMPTS = ROOT / "prompts"


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise RuntimeError(f"{path}: expected an object")
    return value


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate() -> tuple[str, list[dict]]:
    manifest = read_json(REFERENCES / "manifest.json")
    references = read_json(REFERENCES / "reference_manifest.json")
    preview_path = REFERENCES / "preview_manifest.json"
    previews = read_json(preview_path) if preview_path.is_file() else None
    if manifest.get("direct_api_calls") is not False or manifest.get("generation_surface") != "codex_imagegen":
        raise RuntimeError("this package is not a Codex-native, no-direct-API Prompt Skill")
    claimed = references.pop("reference_manifest_digest", None)
    if claimed is not None:
        if claimed != digest(references): raise RuntimeError("reference manifest digest mismatch")
        references["reference_manifest_digest"] = claimed
    for item in references.get("references", []):
        path = ROOT / item["packaged_file"]
        if not path.is_file(): raise RuntimeError(f"missing reference image: {item['reference_id']}")
        if sha256(path) != item["packaged_sha256"]: raise RuntimeError(f"reference digest mismatch: {item['reference_id']}")
    anchor = references.get("core_visual_anchor_reference_id")
    reference_ids = {item.get("reference_id") for item in references.get("references", [])}
    marked_anchors = [item.get("reference_id") for item in references.get("references", []) if item.get("core_visual_anchor") is True]
    if references.get("schema_version") == "0.6.0":
        if anchor:
            if anchor not in reference_ids or marked_anchors != [anchor]: raise RuntimeError("invalid core visual anchor")
        elif reference_ids or marked_anchors:
            raise RuntimeError("real references require exactly one core visual anchor")
    if previews is None:
        if manifest.get("schema_version") == "0.10.0": raise RuntimeError("missing preview manifest")
    else:
        preview_claimed = previews.pop("preview_manifest_digest", None)
        if preview_claimed != digest(previews): raise RuntimeError("preview manifest digest mismatch")
        previews["preview_manifest_digest"] = preview_claimed
        if previews.get("generation_input") is not False or previews.get("stage_count") != 5:
            raise RuntimeError("stage previews must be five semantic non-generation assets")
        if manifest.get("preview_manifest_digest") != preview_claimed:
            raise RuntimeError("package and preview manifest digests differ")
        covered = {(item.get("locale"), item.get("layer")) for item in previews.get("assets", [])}
        expected = {(locale, layer) for locale in ("zh-CN", "en") for layer in ("direction", "worldbuilding", "narrative", "image", "delivery")}
        if covered != expected: raise RuntimeError("preview manifest does not cover all five stages in both languages")
        for item in previews.get("assets", []):
            if item.get("generation_input") is not False: raise RuntimeError(f"preview may not be a generation input: {item.get('preview_id')}")
            path = ROOT / item["file"]
            if not path.is_file(): raise RuntimeError(f"missing stage preview: {item.get('preview_id')}")
            if sha256(path) != item.get("sha256"): raise RuntimeError(f"stage preview digest mismatch: {item.get('preview_id')}")
            if "assets/references/" in item["file"]: raise RuntimeError("stage preview must remain separate from generation references")
    if manifest.get("source_kind") == "legacy_run_import":
        label = f"{manifest.get('theme_id', 'APSAL-IMPORTED-RUN')}@{manifest.get('theme_version', 'legacy')}"
        source_jobs = manifest.get("jobs", [])
    else:
        theme = read_json(REFERENCES / "theme.json")
        compiled = read_json(REFERENCES / "compiled.json")
        label = f"{theme['id']}@{theme['version']}"
        source_jobs = [{"shot_id": shot["shot_id"], "reference_ids": shot.get("reference_ids", []), "compiled": shot} for shot in compiled.get("shots", [])]
    rows = []
    expected_files = manifest.get("prompt_files", {})
    for source_job in source_jobs:
        shot_id = source_job["shot_id"]
        positive = PROMPTS / f"{shot_id}.prompt.txt"
        negative = PROMPTS / f"{shot_id}.negative.txt"
        full = PROMPTS / f"{shot_id}.full.txt"
        for path in (positive, negative, full):
            relative = str(path.relative_to(ROOT))
            if not path.is_file(): raise RuntimeError(f"missing Prompt file: {relative}")
            if expected_files.get(relative) != sha256(path): raise RuntimeError(f"Prompt checksum mismatch: {relative}")
        compiled_shot = source_job.get("compiled")
        if compiled_shot:
            expected_full = compiled_shot["positive_prompt"] + "\n\nNegative constraints:\n" + compiled_shot["negative_prompt"] + "\n"
            if positive.read_text(encoding="utf-8") != compiled_shot["positive_prompt"] + "\n": raise RuntimeError(f"positive Prompt differs: {shot_id}")
            if negative.read_text(encoding="utf-8") != compiled_shot["negative_prompt"] + "\n": raise RuntimeError(f"negative Prompt differs: {shot_id}")
            if full.read_text(encoding="utf-8") != expected_full: raise RuntimeError(f"full Prompt differs: {shot_id}")
        rows.append({"shot_id": shot_id, "full_prompt": str(full.relative_to(ROOT)), "reference_ids": source_job.get("reference_ids", [])})
    if len(rows) != len(source_jobs): raise RuntimeError("Prompt count differs from Job count")
    return label, rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an APSAL Codex Prompt Skill")
    parser.add_argument("--list", action="store_true", help="List Jobs, full Prompt files and reference IDs")
    args = parser.parse_args()
    label, rows = validate()
    if args.list:
        print(json.dumps({"theme": label, "jobs": rows}, ensure_ascii=False, indent=2))
    else:
        print(f"valid Codex Prompt Skill: {label}, {len(rows)} independent Jobs, no direct API calls")
    return 0


if __name__ == "__main__": raise SystemExit(main())
