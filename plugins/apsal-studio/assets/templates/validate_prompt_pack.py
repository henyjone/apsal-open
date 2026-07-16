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


def validate() -> tuple[dict, list[dict]]:
    theme = read_json(REFERENCES / "theme.json")
    compiled = read_json(REFERENCES / "compiled.json")
    manifest = read_json(REFERENCES / "manifest.json")
    references = read_json(REFERENCES / "reference_manifest.json")
    if manifest.get("direct_api_calls") is not False or manifest.get("generation_surface") != "codex_imagegen":
        raise RuntimeError("this package is not a Codex-native, no-direct-API Prompt Skill")
    claimed = references.pop("reference_manifest_digest", None)
    if claimed != digest(references): raise RuntimeError("reference manifest digest mismatch")
    references["reference_manifest_digest"] = claimed
    for item in references.get("references", []):
        path = ROOT / item["packaged_file"]
        if not path.is_file(): raise RuntimeError(f"missing reference image: {item['reference_id']}")
        if sha256(path) != item["packaged_sha256"]: raise RuntimeError(f"reference digest mismatch: {item['reference_id']}")
    rows = []
    expected_files = manifest.get("prompt_files", {})
    for shot in compiled.get("shots", []):
        shot_id = shot["shot_id"]
        positive = PROMPTS / f"{shot_id}.prompt.txt"
        negative = PROMPTS / f"{shot_id}.negative.txt"
        full = PROMPTS / f"{shot_id}.full.txt"
        for path in (positive, negative, full):
            relative = str(path.relative_to(ROOT))
            if not path.is_file(): raise RuntimeError(f"missing Prompt file: {relative}")
            if expected_files.get(relative) != sha256(path): raise RuntimeError(f"Prompt checksum mismatch: {relative}")
        expected_full = shot["positive_prompt"] + "\n\nNegative constraints:\n" + shot["negative_prompt"] + "\n"
        if positive.read_text(encoding="utf-8") != shot["positive_prompt"] + "\n": raise RuntimeError(f"positive Prompt differs: {shot_id}")
        if negative.read_text(encoding="utf-8") != shot["negative_prompt"] + "\n": raise RuntimeError(f"negative Prompt differs: {shot_id}")
        if full.read_text(encoding="utf-8") != expected_full: raise RuntimeError(f"full Prompt differs: {shot_id}")
        rows.append({"shot_id": shot_id, "full_prompt": str(full.relative_to(ROOT)), "reference_ids": shot.get("reference_ids", [])})
    if len(rows) != theme.get("output", {}).get("count"): raise RuntimeError("Prompt count differs from theme output count")
    return theme, rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an APSAL Codex Prompt Skill")
    parser.add_argument("--list", action="store_true", help="List Jobs, full Prompt files and reference IDs")
    args = parser.parse_args()
    theme, rows = validate()
    if args.list:
        print(json.dumps({"theme": f"{theme['id']}@{theme['version']}", "jobs": rows}, ensure_ascii=False, indent=2))
    else:
        print(f"valid Codex Prompt Skill: {theme['id']}@{theme['version']}, {len(rows)} independent Jobs, no direct API calls")
    return 0


if __name__ == "__main__": raise SystemExit(main())
