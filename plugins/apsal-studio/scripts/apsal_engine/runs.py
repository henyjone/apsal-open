# Part of apsal_engine. __init__.py executes this file in the package namespace.
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


def _advisory_library_reconcile(project_root: Path) -> str | None:
    """Update the rebuildable creative library without failing an authoritative run."""
    try:
        from apsal_creative import reconcile_library
        reconcile_library(project_root)
    except Exception as exc:  # The project run remains authoritative and repairable.
        return f"library_reconcile_pending: {type(exc).__name__}: {exc}"
    return None


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
    adapter: str = "codex-imagegen", model: str = "not_reported", parameters: dict[str, Any] | None = None,
    resume_run_id: str | None = None, home: Path | None = None,
) -> dict[str, Any]:
    """Prepare or resume a Codex-managed run without invoking an image API."""
    if mode not in {"generate", "prompts", "skill"}: raise ValidationError("run mode must be generate, prompts, or skill")
    if mode == "generate" and confirmed is not True:
        raise ValidationError("explicit confirmation is required before generating images")
    if adapter != "codex-imagegen": raise ValidationError("APSAL Studio uses Codex built-in image generation; direct image API adapters are disabled")
    if model not in {"", "not_reported", "codex-managed"}: raise ValidationError("Codex manages the image model; do not set a provider model")
    if parameters: raise ValidationError("Codex manages image parameters; provider API parameters are not accepted")
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
    output_contract = codex_delivery_contract(theme.get("output", {}), len(compiled["shots"]))
    run_id = f"RUN-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8].upper()}"
    root = _run_dir(project_root, run_id)
    for relative in ("prompts", "outputs", "qa"): _mkdir_private(root / relative)
    jobs = []
    for shot in compiled["shots"]:
        shot_id = _safe_part(shot["shot_id"], "shot id")
        (root / "prompts" / f"{shot_id}.prompt.txt").write_text(shot["positive_prompt"] + " Negative constraints: " + shot["negative_prompt"] + "\n", encoding="utf-8")
        (root / "prompts" / f"{shot_id}.negative.txt").write_text(shot["negative_prompt"] + "\n", encoding="utf-8")
        jobs.append({
            "shot_id": shot_id, "status": "pending" if mode == "generate" else "saved",
            "prompt_digest": shot["prompt_digest"], "reference_ids": shot.get("reference_ids", []),
            "attempts": [], "output": None, "error": None, "model_visual_qa": "pending",
            "human_visual_qa": "pending",
        })
    run = {
        "schema_version": "0.9.0", "run_id": run_id, "session_id": session_id, "mode": mode,
        "status": "generating" if mode == "generate" else "completed", "theme": session["theme_artifact"],
        "dna": theme["dna"], "engine_version": ENGINE_VERSION, "adapter": "codex-imagegen",
        "model": "not_reported", "parameters": "not_reported", "output_contract": output_contract,
        "generation_surface": "codex_imagegen", "direct_api_calls": False, "api_key_required": False,
        "returned_dimensions_guaranteed": False,
        "rendering_contract": theme.get("rendering_contract", {"status": "not_declared_legacy"}),
        "reference_manifest": {key: value for key, value in reference_manifest.items() if key != "references"} | {
            "references": [{key: value for key, value in item.items() if key != "vault_uri"} for item in reference_manifest.get("references", [])]
        },
        "jobs": jobs, "resume_count": 0, "created_at": _utc_now(), "updated_at": _utc_now(),
        "lineage_note": "Prompts and reference IDs are frozen locally before Codex generates one independent image per Job. Concrete model, format and dimensions remain not_reported unless Codex returns them.",
    }
    package = session["theme_artifact"].get("prompt_package")
    if package: run["prompt_package"] = package
    if mode == "skill" and package: run["skill"] = package
    _write_run(run, project_root)
    session["state"] = "generating" if mode == "generate" else "completed"; _write_session(session, theme, project_root)
    return run


def _read_apsal_run_bundle(source: Path) -> tuple[dict[str, Any], dict[str, bytes], str, str]:
    """Read one legacy run directory or ZIP without trusting archive paths."""
    source = source.expanduser().resolve()
    files: dict[str, bytes] = {}
    if source.is_dir():
        candidates = [
            path for path in source.rglob("run.json")
            if "__MACOSX" not in path.parts and len(path.relative_to(source).parts) <= 4
        ]
        if len(candidates) != 1: raise ValidationError("APSAL package must contain exactly one run.json")
        bundle_root = candidates[0].parent
        total = 0
        for path in sorted(item for item in bundle_root.rglob("*") if item.is_file() and "__MACOSX" not in item.parts):
            relative = path.relative_to(bundle_root)
            if len(relative.parts) > 8: raise ValidationError(f"APSAL package path is too deep: {relative}")
            size = path.stat().st_size; total += size
            if size > 20_000_000 or total > 150_000_000: raise ValidationError("APSAL package exceeds safe import limits")
            files[relative.as_posix()] = path.read_bytes()
        origin = str(source)
    elif source.is_file() and source.suffix.lower() == ".zip":
        try: archive = zipfile.ZipFile(source)
        except zipfile.BadZipFile as exc: raise ValidationError("APSAL package is not a valid ZIP") from exc
        infos = [item for item in archive.infolist() if not item.is_dir() and "__MACOSX" not in Path(item.filename).parts]
        names = [item.filename for item in infos]
        if len(names) != len(set(names)): raise ValidationError("APSAL package contains duplicate paths")
        candidates = [item for item in infos if Path(item.filename).name == "run.json"]
        if len(candidates) != 1: raise ValidationError("APSAL package must contain exactly one run.json")
        prefix = Path(candidates[0].filename).parent
        total = 0
        for info in infos:
            path = Path(info.filename)
            if path.is_absolute() or ".." in path.parts or len(path.parts) > 12:
                raise ValidationError(f"unsafe APSAL package path: {info.filename}")
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValidationError(f"APSAL package symlink rejected: {info.filename}")
            try: relative = path.relative_to(prefix)
            except ValueError: continue
            if not relative.parts: continue
            total += info.file_size
            if info.file_size > 20_000_000 or total > 150_000_000:
                raise ValidationError("APSAL package exceeds safe import limits")
            files[relative.as_posix()] = archive.read(info)
        origin = str(source)
    else:
        raise ValidationError("APSAL package must be a run directory or ZIP")
    if "run.json" not in files: raise ValidationError("APSAL package is missing run.json")
    try: run = json.loads(files["run.json"])
    except json.JSONDecodeError as exc: raise ValidationError("APSAL run.json is invalid JSON") from exc
    if not isinstance(run, dict): raise ValidationError("APSAL run.json must be an object")
    source_sha = hashlib.sha256(files["run.json"]).hexdigest()
    return run, files, origin, source_sha


def _legacy_reference_candidate(
    reference: dict[str, Any], files: dict[str, bytes], home: Path,
) -> tuple[bytes, str, str] | None:
    expected = str(reference.get("original_sha256") or reference.get("sha256") or "")
    if not re.fullmatch(r"[a-f0-9]{64}", expected): return None
    declared = [reference.get(key) for key in ("packaged_file", "path", "source_path", "original_path")]
    image_suffixes = {".png", ".jpg", ".jpeg", ".webp"}
    for value in declared:
        if not isinstance(value, str) or not value: continue
        candidate = Path(value)
        if not candidate.is_absolute():
            normalized = candidate.as_posix().lstrip("./")
            data = files.get(normalized)
            if data is not None and hashlib.sha256(data).hexdigest() == expected:
                return data, candidate.suffix.lower() or ".bin", "package"
    for name, data in files.items():
        if Path(name).suffix.lower() in image_suffixes and hashlib.sha256(data).hexdigest() == expected:
            return data, Path(name).suffix.lower(), "package_digest_scan"
    vault_dir = home / "vault" / "sha256" / expected[:2] / expected
    if vault_dir.is_dir():
        for candidate in sorted(vault_dir.glob("reference.*")):
            if candidate.suffix.lower() not in image_suffixes: continue
            data = candidate.read_bytes()
            if hashlib.sha256(data).hexdigest() == expected:
                return data, candidate.suffix.lower(), "local_vault"
    return None


def _import_reference_conflicts(reference: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    forbidden = " ".join(str(item).lower() for item in reference.get("forbidden_uses", []))
    uses = {str(item).lower() for item in reference.get("uses", [])}
    if "identity" in uses and any(token in forbidden for token in ("identity", "身份", "面容", "face")):
        warnings.append("identity is declared and forbidden simultaneously; the forbidden identity rule takes precedence")
    rights = reference.get("rights") if isinstance(reference.get("rights"), dict) else {}
    if rights.get("redistribution_allowed") is not True:
        warnings.append("reference is private-only and must not be redistributed")
    return warnings


def _imported_prompt_package(run: dict[str, Any], run_root: Path) -> tuple[Path, str]:
    """Create a deterministic private Codex Skill from a fully resolved imported run."""
    missing = run.get("missing_references", [])
    if missing: raise ValidationError("cannot package imported run until every declared reference is restored")
    theme = run.get("theme", {}) if isinstance(run.get("theme"), dict) else {}
    theme_id = str(theme.get("theme_id") or "APSAL-IMPORTED-RUN")
    theme_version = str(theme.get("version") or "legacy")
    slug = re.sub(r"[^a-z0-9-]+", "-", theme_id.lower()).strip("-") or "apsal-imported-run"
    prefix = f"{slug}-codex-import/"
    references = run.get("reference_manifest", {}).get("references", [])
    jobs = []
    prompt_files: dict[str, str] = {}
    files: dict[str, bytes] = {}
    for job in run["jobs"]:
        shot_id = job["shot_id"]
        for suffix in ("prompt", "negative", "full"):
            relative = f"prompts/{shot_id}.{suffix}.txt"
            data = (run_root / relative).read_bytes()
            files[prefix + relative] = data; prompt_files[relative] = hashlib.sha256(data).hexdigest()
        jobs.append({"shot_id": shot_id, "full_prompt": f"prompts/{shot_id}.full.txt", "reference_ids": job.get("reference_ids", [])})
    packaged_references = []
    for item in references:
        local_path = Path(str(item["local_path"]))
        name = f"{item['reference_id']}{local_path.suffix.lower()}"
        data = local_path.read_bytes(); packaged = f"assets/references/{name}"
        files[prefix + packaged] = data
        packaged_references.append({key: value for key, value in item.items() if key != "local_path"} | {
            "packaged_file": packaged, "packaged_sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "schema_version": "0.9.0", "engine_version": ENGINE_VERSION, "source_kind": "legacy_run_import",
        "theme_id": theme_id, "theme_version": theme_version, "source_run_sha256": run["source"]["run_json_sha256"],
        "generation_surface": "codex_imagegen", "direct_api_calls": False, "api_key_required": False,
        "distribution": "private_only", "redistribution_allowed": False,
        "returned_dimensions_guaranteed": False, "output_request": run["output_contract"],
        "prompt_files": prompt_files, "jobs": jobs,
    }
    reference_manifest = {
        "schema_version": "0.9.0", "distribution": "private_only", "redistribution_allowed": False,
        "reference_count": len(packaged_references), "references": packaged_references,
    }
    guide_zh = f"""# {theme_id} — Codex 直接使用说明

这是由 APSAL Studio 从旧版 `run.json` 自动迁移的私人 Codex Prompt/Skill 包。旧包中的 `openai-image-api`、模型名和 API 参数只作为历史血缘保留；本包不会调用图像 API，也不需要 API Key。

## 最简单的用法

1. 在 Codex 中提供这个 Skill 目录并说：“使用 `{slug}-codex-import` 生成第一张。”
2. Codex 读取 `prompts/SHOT_01.full.txt`，实际传入该镜声明的 `assets/references/` 图片，然后用 Codex 内置图像生成一张真实摄影作品。
3. 看完说“继续”，Codex 依次生成后续未完成镜头。每次只生成一张，不生成编程界面、九宫格、拼图、文字、标志或水印。
4. 如果只需要提示词，直接打开任一 `prompts/SHOT_XX.full.txt`。

目标画幅为 {run['output_contract'].get('aspect_ratio', 'not_reported')}；{run['output_contract'].get('requested_size', 'not_reported')} 只是创作交付目标，不保证 Codex 返回该像素尺寸。

运行 `python3 scripts/validate_prompt_pack.py --list` 可以离线核对文件并列出全部镜头；它不会生成图片或访问网络。
"""
    guide_en = f"""# {theme_id} — Direct use in Codex

APSAL Studio migrated this private Codex Prompt/Skill package from a legacy `run.json`. Any previous `openai-image-api`, model name, or API parameters are preserved only as historical lineage. This package does not call an image API and does not require an API key.

## Fastest workflow

1. Provide this Skill folder to Codex and say: “Use `{slug}-codex-import` to generate the first image.”
2. Codex reads `prompts/SHOT_01.full.txt`, passes the actual declared files from `assets/references/`, and uses Codex built-in image generation for one live-action photograph.
3. After reviewing it, say “continue.” Codex advances through the remaining unfinished shots. It creates one image per turn—never a programming screen, grid, collage, text, logo, or watermark.
4. If you only need a Prompt, open any `prompts/SHOT_XX.full.txt` file directly.

The requested aspect ratio is {run['output_contract'].get('aspect_ratio', 'not_reported')}. The requested {run['output_contract'].get('requested_size', 'not_reported')} delivery size is a creative target and is not a guaranteed returned pixel dimension.

Run `python3 scripts/validate_prompt_pack.py --list` to verify files and list all shots offline. The validator does not generate images or access the network.
"""
    guide_index = f"""# {theme_id} — Prompt/Skill package

- [English instructions](PROMPT_GUIDE.en.md)
- [中文使用说明](PROMPT_GUIDE.zh-CN.md)

Codex should open the guide that matches the current conversation language. The frozen image Prompts are identical in both workflows.
"""
    skill = f"""---
name: {slug}-codex-import
description: Generate or continue the imported APSAL set {theme_id} in Codex using its frozen Prompts and restored private references. Use when the creator asks to generate, continue, inspect, or reuse this migrated legacy run without an image API.
---

# {theme_id}

Read `PROMPT_GUIDE.en.md` for English creators or `PROMPT_GUIDE.zh-CN.md` for Chinese creators, plus `references/manifest.json` and `references/reference_manifest.json`. For the next unfinished Job, use its `prompts/SHOT_XX.full.txt` and pass every declared real reference image from `assets/references/` to Codex built-in image generation.

Generate exactly one live-action photograph per turn. Never render a programming interface, JSON, terminal, prompt sheet, grid, collage, text, logo or watermark. After emitting one image, stop. On “continue”, advance to the next unfinished Job. A reference's forbidden uses outrank its declared uses. Preserve identity only when identity use is explicitly allowed; never inherit pose, camera, background or composition from a continuity anchor.

Do not call an image API, request an API key, or claim guaranteed returned dimensions. Keep Codex visual QA separate from human QA.
"""
    summary = {
        "schema_version": "0.9.0", "original_schema_version": run["source"].get("schema_version"),
        "original_run_id": run["source"].get("run_id"), "run_json_sha256": run["source"]["run_json_sha256"],
        "historical_adapter": run["source"].get("historical_adapter"), "historical_model": run["source"].get("historical_model"),
        "migration_note": "Historical provider settings are not executable in this Codex-native package.",
    }
    files.update({
        prefix + "SKILL.md": skill.encode(), prefix + "PROMPT_GUIDE.md": guide_index.encode(),
        prefix + "PROMPT_GUIDE.en.md": guide_en.encode(), prefix + "PROMPT_GUIDE.zh-CN.md": guide_zh.encode(),
        prefix + "references/manifest.json": (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "references/reference_manifest.json": (json.dumps(reference_manifest, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "references/source_run_summary.json": (json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "scripts/validate_prompt_pack.py": (plugin_root() / "assets" / "templates" / "validate_prompt_pack.py").read_bytes(),
    })
    content = _zip_bytes(files); sha = hashlib.sha256(content).hexdigest()
    output_dir = run_root / "exports"; output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{slug}-legacy-run-codex-skill-private.zip"; path.write_bytes(content)
    path.with_suffix(".zip.sha256").write_text(f"{sha}  {path.name}\n", encoding="utf-8")
    return path, sha


def import_apsal_package(
    source: Path, *, project_root: Path, home: Path | None = None,
) -> dict[str, Any]:
    """Take over a legacy run package and turn it into a Codex-native resumable run."""
    project_root = project_root.expanduser().resolve(); home = (home or apsal_home()).expanduser().resolve()
    init_workspace(project_root, home)
    legacy, files, origin, source_sha = _read_apsal_run_bundle(source)
    legacy_jobs = legacy.get("jobs")
    if not isinstance(legacy_jobs, list) or not 1 <= len(legacy_jobs) <= 24:
        raise ValidationError("APSAL run must contain 1 to 24 Jobs")
    shot_ids = [str(item.get("shot_id", "")) for item in legacy_jobs if isinstance(item, dict)]
    if len(shot_ids) != len(legacy_jobs) or len(set(shot_ids)) != len(shot_ids) or any(not SAFE_COMPONENT.fullmatch(item) for item in shot_ids):
        raise ValidationError("APSAL run has invalid or duplicate shot IDs")
    run_id = f"RUN-IMPORT-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8].upper()}"
    run_root = _run_dir(project_root, run_id)
    for relative in ("prompts", "outputs", "qa", "references", "exports"): _mkdir_private(run_root / relative)
    jobs = []
    for item in legacy_jobs:
        shot_id = str(item["shot_id"])
        positive_name = f"prompts/{shot_id}.prompt.txt"; negative_name = f"prompts/{shot_id}.negative.txt"
        positive_data = files.get(positive_name)
        if positive_data is None: raise ValidationError(f"APSAL package is missing {positive_name}")
        try: positive = positive_data.decode("utf-8").strip(); negative = files.get(negative_name, b"").decode("utf-8").strip()
        except UnicodeDecodeError as exc: raise ValidationError(f"Prompt is not UTF-8: {shot_id}") from exc
        if not positive: raise ValidationError(f"APSAL Prompt is empty: {shot_id}")
        full = positive + ("\n\nNegative constraints:\n" + negative if negative else "")
        (run_root / positive_name).write_text(positive + "\n", encoding="utf-8")
        (run_root / negative_name).write_text(negative + "\n", encoding="utf-8")
        (run_root / f"prompts/{shot_id}.full.txt").write_text(full + "\n", encoding="utf-8")
        jobs.append({
            "shot_id": shot_id, "status": "pending", "prompt_digest": hashlib.sha256(full.encode()).hexdigest(),
            "reference_ids": [str(value) for value in item.get("reference_ids", [])],
            "attempts": [], "output": None, "error": None, "model_visual_qa": "pending", "human_visual_qa": "pending",
        })
    legacy_manifest = legacy.get("reference_manifest") if isinstance(legacy.get("reference_manifest"), dict) else {"references": []}
    resolved, missing, warnings = [], [], []
    for raw in legacy_manifest.get("references", []):
        if not isinstance(raw, dict): continue
        item = json.loads(json.dumps(raw)); reference_id = str(item.get("reference_id", ""))
        if not SAFE_COMPONENT.fullmatch(reference_id): raise ValidationError("legacy reference has an invalid reference ID")
        conflicts = _import_reference_conflicts(item); warnings.extend(f"{reference_id}: {value}" for value in conflicts)
        candidate = _legacy_reference_candidate(item, files, home)
        if candidate is None:
            missing.append({"reference_id": reference_id, "sha256": item.get("original_sha256") or item.get("sha256"), "original_filename": item.get("original_filename"), "reason": "not_in_package_or_local_vault"})
            resolved.append({key: value for key, value in item.items() if key not in {"path", "source_path", "original_path", "vault_uri"}} | {"status": "missing"})
            continue
        data, suffix, recovered_from = candidate
        _sanitize_reference_bytes(data, suffix)
        target = run_root / "references" / f"{reference_id}{suffix}"
        target.write_bytes(data)
        resolved.append({key: value for key, value in item.items() if key not in {"path", "source_path", "original_path", "vault_uri"}} | {
            "status": "resolved", "local_path": str(target), "recovered_from": recovered_from,
        })
    for job in jobs:
        if job["reference_ids"]: continue
        job["reference_ids"] = [
            str(item["reference_id"]) for item in resolved
            if "*" in item.get("applies_to", []) or job["shot_id"] in item.get("applies_to", [])
        ]
    legacy_output = legacy.get("output_contract") if isinstance(legacy.get("output_contract"), dict) else {}
    theme = legacy.get("theme") if isinstance(legacy.get("theme"), dict) else {}
    sanitized_theme = {key: value for key, value in theme.items() if key != "path"}
    run = {
        "schema_version": "0.9.0", "run_id": run_id, "session_id": f"SESSION-IMPORT-{uuid.uuid4().hex[:12].upper()}",
        "source_kind": "legacy_run_import", "mode": "generate", "status": "partial" if missing else "generating",
        "theme": sanitized_theme, "dna": legacy.get("dna", []), "engine_version": ENGINE_VERSION,
        "adapter": "codex-imagegen", "model": "not_reported", "parameters": "not_reported",
        "output_contract": codex_delivery_contract(legacy_output, len(jobs)),
        "generation_surface": "codex_imagegen", "direct_api_calls": False, "api_key_required": False,
        "returned_dimensions_guaranteed": False,
        "rendering_contract": legacy.get("rendering_contract", {"status": "not_declared_legacy"}),
        "reference_manifest": {"schema_version": "0.9.0", "distribution": "private_only", "redistribution_allowed": False, "references": resolved},
        "missing_references": missing, "migration_warnings": sorted(set(warnings)), "jobs": jobs, "resume_count": 0,
        "created_at": _utc_now(), "updated_at": _utc_now(),
        "source": {"origin": origin, "run_json_sha256": source_sha, "run_id": legacy.get("run_id"), "schema_version": legacy.get("schema_version"), "historical_adapter": legacy.get("adapter", "not_reported"), "historical_model": legacy.get("model", "not_reported")},
        "lineage_note": "Legacy provider settings were preserved as history only. Codex directly generates one image per Job from the migrated Prompts and restored references.",
    }
    _write_run(run, project_root)
    if not missing:
        package, sha = _imported_prompt_package(run, run_root)
        run["prompt_package"] = {"path": str(package), "sha256": sha, "distribution": "private_only"}
        _write_run(run, project_root)
    result = {
        "run": run, "ready_for_codex": not missing, "missing_references": missing,
        "message": "Ready for Codex. Generate SHOT_01 directly; no API runner is needed." if not missing else "Attach only the listed missing reference images; APSAL already recovered all Prompts and will not follow obsolete absolute paths.",
    }
    if not missing: result["next_job"] = get_next_codex_job(run_id, project_root=project_root, home=home)
    return result


def bind_import_reference(
    run_id: str, reference_id: str, source: Path, *, project_root: Path,
) -> dict[str, Any]:
    """Restore one missing imported reference and finish the Codex package when complete."""
    project_root = project_root.expanduser().resolve(); run = load_generation_run(run_id, project_root)
    if run.get("source_kind") != "legacy_run_import": raise ValidationError("reference binding is only for imported legacy runs")
    record = next((item for item in run.get("reference_manifest", {}).get("references", []) if item.get("reference_id") == reference_id), None)
    if not record: raise ValidationError(f"unknown imported reference: {reference_id}")
    expected = str(record.get("original_sha256") or record.get("sha256") or "")
    source = source.expanduser().resolve()
    if not source.is_file(): raise ValidationError(f"reference image not found: {source}")
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected: raise ValidationError(f"reference SHA-256 mismatch: {reference_id}")
    _image_dimensions(data)
    target = _run_dir(project_root, run_id) / "references" / f"{reference_id}{source.suffix.lower()}"
    target.write_bytes(data); record.update({"status": "resolved", "local_path": str(target), "recovered_from": "creator_reattached"})
    run["missing_references"] = [item for item in run.get("missing_references", []) if item.get("reference_id") != reference_id]
    run["status"] = "partial" if run["missing_references"] else "generating"
    if not run["missing_references"]:
        package, sha = _imported_prompt_package(run, _run_dir(project_root, run_id))
        run["prompt_package"] = {"path": str(package), "sha256": sha, "distribution": "private_only"}
    _write_run(run, project_root)
    result = {"run": run, "ready_for_codex": not run["missing_references"], "missing_references": run["missing_references"]}
    if not run["missing_references"]: result["next_job"] = get_next_codex_job(run_id, project_root=project_root)
    return result


def get_next_codex_job(
    run_id: str, *, project_root: Path, home: Path | None = None,
) -> dict[str, Any]:
    """Return the next exact Codex image-generation call; never call a provider."""
    project_root = project_root.expanduser().resolve(); home = (home or apsal_home()).resolve()
    run = load_generation_run(run_id, project_root)
    if run.get("mode") != "generate": raise ValidationError("only generate-mode runs have a next Codex Job")
    if run.get("generation_surface") != "codex_imagegen" or run.get("direct_api_calls") is not False:
        raise ValidationError("this is not a Codex-native generation run")
    pending_visual = next((job for job in run["jobs"] if job.get("status") == "succeeded" and job.get("model_visual_qa") == "pending"), None)
    if pending_visual and run.get("rendering_contract", {}).get("medium") == "live_action_photography":
        raise ValidationError(f"record Codex visual QA for {pending_visual['shot_id']} before continuing")
    job = next((item for item in run["jobs"] if item.get("status") in {"pending", "failed"}), None)
    if not job:
        return {"run_id": run_id, "status": run.get("status"), "next_job": None, "message": "No pending Jobs remain."}
    if run.get("source_kind") == "legacy_run_import":
        run_root = _run_dir(project_root, run_id)
        positive = (
            "Generate the finished photographic image itself. Do not show code, JSON, a terminal, a programming interface, a Prompt sheet, or an explanation inside the image. "
            + (run_root / "prompts" / f"{job['shot_id']}.prompt.txt").read_text(encoding="utf-8").strip()
        )
        negative = (run_root / "prompts" / f"{job['shot_id']}.negative.txt").read_text(encoding="utf-8").strip()
        reference_records = {item["reference_id"]: item for item in run.get("reference_manifest", {}).get("references", [])}
        relevant_missing = [
            reference_id for reference_id in job.get("reference_ids", [])
            if reference_id not in reference_records or reference_records[reference_id].get("status") != "resolved"
        ]
        if relevant_missing:
            raise ValidationError(f"reattach missing reference images before {job['shot_id']}: {relevant_missing}")
        reference_paths = [
            Path(reference_records[reference_id]["local_path"])
            for reference_id in job.get("reference_ids", []) if reference_id in reference_records
        ]
        policy_lines = []
        for reference_id in job.get("reference_ids", []):
            record = reference_records.get(reference_id, {})
            allowed = "; ".join(str(item) for item in record.get("allowed_uses", [])) or "only the declared reference purpose"
            forbidden = "; ".join(str(item) for item in record.get("forbidden_uses", [])) or "none additionally declared"
            policy_lines.append(f"Reference {reference_id}: allowed — {allowed}; forbidden — {forbidden}. Forbidden uses take precedence.")
        policy_instruction = (" Reference policy: " + " ".join(policy_lines)) if policy_lines else ""
    else:
        session, _ = load_design_session(run["session_id"], project_root)
        theme_root = Path(session["theme_artifact"]["path"]); compiled = load_json(theme_root / "compiled" / "image.json")
        shot = next(item for item in compiled["shots"] if item["shot_id"] == job["shot_id"])
        positive, negative = shot["positive_prompt"], shot["negative_prompt"]
        local_manifest_path = theme_root / "references" / "reference_manifest.json"
        local_manifest = load_json(local_manifest_path) if local_manifest_path.is_file() else {"references": []}
        reference_records = {item["reference_id"]: item for item in local_manifest.get("references", [])}
        reference_paths = [
            _vault_reference_path(reference_records[reference_id]["vault_uri"], home)
            for reference_id in job.get("reference_ids", []) if reference_id in reference_records and reference_records[reference_id].get("vault_uri")
        ]
        policy_instruction = ""
    job_index = run["jobs"].index(job); previous = run["jobs"][job_index - 1] if job_index > 0 else None
    previous_path = Path(previous.get("output", {}).get("path", "")) if previous and isinstance(previous.get("output"), dict) else None
    local_identity_anchor = bool(previous_path and previous_path.is_file())
    recent_identity_anchor = bool(previous and previous.get("status") == "succeeded" and not local_identity_anchor and not reference_paths)
    anchor_instruction = ""
    if local_identity_anchor or recent_identity_anchor:
        anchor_instruction = (
            " Use the immediately previous accepted APSAL image only to preserve the fictional adult identity and facial continuity; "
            "do not inherit its pose, action, hands, gaze, face direction, expression, camera, background, composition, makeup, hair, wardrobe, focal length, or lighting."
        )
    if local_identity_anchor and previous_path is not None: reference_paths.append(previous_path)
    prompt = positive + policy_instruction + anchor_instruction + (" Negative constraints: " + negative if negative else "")
    tool_arguments: dict[str, Any] = {"prompt": prompt}
    if reference_paths: tool_arguments["referenced_image_paths"] = [str(path) for path in reference_paths]
    elif recent_identity_anchor: tool_arguments["num_last_images_to_include"] = 1
    return {
        "run_id": run_id, "shot_id": job["shot_id"], "job_position": job_index + 1,
        "job_count": len(run["jobs"]), "prompt": prompt, "prompt_digest": hashlib.sha256(prompt.encode()).hexdigest(),
        "negative_prompt": negative, "reference_ids": job.get("reference_ids", []),
        "reference_paths": [str(path) for path in reference_paths],
        "identity_anchor": "local_previous_output" if local_identity_anchor else "recent_previous_image" if recent_identity_anchor else "none",
        "codex_tool": "built_in_image_generation", "codex_tool_arguments": tool_arguments,
        "direct_api_calls": False, "api_key_required": False,
        "requested_output": run.get("output_contract", {}), "returned_dimensions_guaranteed": False,
        "after_generation": "Emit the generated image and stop. On the creator's next 'continue', record only metadata actually available, perform Codex visual QA, then request the next Job.",
    }


def record_generation_result(
    run_id: str, shot_id: str, status: str, *, project_root: Path, output_path: Path | None = None,
    artifact_uri: str | None = None, provider_metadata: dict[str, Any] | None = None, error: str | None = None,
) -> dict[str, Any]:
    """Record one Codex-managed result, preserving successful Jobs across retries."""
    if status not in {"succeeded", "failed"}: raise ValidationError("generation status must be succeeded or failed")
    project_root = project_root.expanduser().resolve(); run = load_generation_run(run_id, project_root)
    job = next((item for item in run["jobs"] if item["shot_id"] == shot_id), None)
    if not job: raise ValidationError(f"unknown shot in run: {shot_id}")
    if job["status"] == "succeeded": raise ValidationError(f"successful output is immutable: {shot_id}")
    attempt = {
        "attempt": len(job["attempts"]) + 1, "status": status, "recorded_at": _utc_now(),
        "provider_metadata": provider_metadata if provider_metadata is not None else "not_reported",
        "generation_surface": run.get("generation_surface", "legacy_provider"),
    }
    if status == "failed":
        message = (error or "provider_error_not_reported").strip()
        attempt["error"] = message; job["error"] = message
    else:
        if output_path is None and not artifact_uri:
            raise ValidationError("successful generation requires an output path or artifact URI")
        if run.get("returned_dimensions_guaranteed") is True and run.get("output_contract", {}).get("provider_native") is True and output_path is None:
            raise ValidationError("provider-native output requires a local file for format and dimension validation")
        output: dict[str, Any] = {"artifact_uri": artifact_uri or "not_reported", "sha256": "not_reported"}
        if output_path is not None:
            source = output_path.expanduser().resolve()
            if not source.is_file(): raise ValidationError(f"generated output not found: {source}")
            data = source.read_bytes()
            actual_format = _image_format(data)
            validation_contract = dict(run.get("output_contract", {}))
            if run.get("generation_surface") == "codex_imagegen":
                # A local Codex result gives us concrete bytes to inspect even though
                # the requested delivery size is not a provider-native guarantee.
                dimensions = _image_dimensions(data)
            else:
                dimensions = _validate_output_image(data, validation_contract)
            suffix = source.suffix.lower() if re.fullmatch(r"\.[a-z0-9]{1,8}", source.suffix.lower()) else ".bin"
            target = _run_dir(project_root, run_id) / "outputs" / f"{shot_id}{suffix}"
            if target.exists(): raise ValidationError(f"output already exists: {target.name}")
            shutil.copyfile(source, target)
            output.update({
                "path": str(target), "sha256": hashlib.sha256(data).hexdigest(),
                "size": target.stat().st_size, "format": actual_format,
            })
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
    warning = _advisory_library_reconcile(project_root)
    if warning:
        run["library_warning"] = warning
        _write_run(run, project_root)
    else:
        run.pop("library_warning", None)
    if run.get("source_kind") != "legacy_run_import":
        session, theme = load_design_session(run["session_id"], project_root)
        session["state"] = run["status"]; _write_session(session, theme, project_root)
    return run


def _image_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        return struct.unpack(">II", data[16:24])
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP": return _webp_dimensions(data)
    if data[:2] == b"\xff\xd8":
        offset = 2
        start_of_frame = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
        while offset + 4 <= len(data):
            if data[offset] != 0xFF: offset += 1; continue
            marker = data[offset + 1]; offset += 2
            if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7: continue
            if offset + 2 > len(data): break
            length = int.from_bytes(data[offset:offset + 2], "big")
            if length < 2 or offset + length > len(data): break
            if marker in start_of_frame and length >= 7:
                height = int.from_bytes(data[offset + 3:offset + 5], "big")
                width = int.from_bytes(data[offset + 5:offset + 7], "big")
                return width, height
            offset += length
    raise ValidationError("generated output has an unsupported or invalid image header")


def _image_format(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"): return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP": return "webp"
    if data[:2] == b"\xff\xd8": return "jpeg"
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
    warning = _advisory_library_reconcile(project_root)
    if warning:
        run["library_warning"] = warning
        _write_run(run, project_root)
    else:
        run.pop("library_warning", None)
    if run.get("source_kind") != "legacy_run_import":
        session, theme = load_design_session(run["session_id"], project_root)
        session["state"] = run["status"]; _write_session(session, theme, project_root)
    return run


def execute_generation_run(
    run_id: str, *, project_root: Path, home: Path | None = None, max_retries: int = 2,
    max_jobs: int | None = None, adapter_callable: Any | None = None, visual_qa_callable: Any | None = None,
) -> dict[str, Any]:
    """Compatibility guard: Studio no longer performs provider/API execution."""
    raise ValidationError("direct provider execution was removed in APSAL Studio 0.8; call get_next_codex_job and let Codex use its built-in image generation")
