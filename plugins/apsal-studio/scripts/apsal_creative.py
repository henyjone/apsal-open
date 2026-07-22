#!/usr/bin/env python3
"""APSAL 0.16 local-first project library, reference analysis, and sharing.

The project files under ``.apsal`` remain authoritative.  The SQLite library is
only a rebuildable cross-project projection inspired by MOSA's local archive
model.  No image-analysis or image-generation provider is called here: Codex
receives explicit jobs and records structured results through the protocol.
"""
from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import tempfile
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path
from typing import Any

import apsal_engine as engine


CREATIVE_PROJECT_SCHEMA_VERSION = "0.1.0"
ANALYSIS_SCHEMA_VERSION = "0.1.0"
LIBRARY_SCHEMA_VERSION = "0.1.0"
SHARE_SCHEMA_VERSION = "0.1.0"
X_MAX_IMAGE_BYTES = 5 * 1024 * 1024
PROJECT_KINDS = {"root", "fork", "imported"}
SHARE_PLATFORMS = {"x", "xiaohongshu"}
ANALYSIS_ROLES = tuple(role for layer in engine.CREATIVE_LAYERS for role in engine.LAYER_ROLES[layer])


def _project_file(project_root: Path) -> Path:
    return project_root.expanduser().resolve() / ".apsal" / "project.json"


def _references_file(project_root: Path) -> Path:
    return project_root.expanduser().resolve() / ".apsal" / "references.json"


def _analysis_root(project_root: Path) -> Path:
    return project_root.expanduser().resolve() / ".apsal" / "analysis"


def _share_root(project_root: Path) -> Path:
    return project_root.expanduser().resolve() / ".apsal" / "share"


def _exports_root(project_root: Path) -> Path:
    return project_root.expanduser().resolve() / ".apsal" / "exports"


def _library_root(home: Path | None = None) -> Path:
    return (home or engine.apsal_home()).expanduser().resolve() / "library"


def _read_project(project_root: Path) -> dict[str, Any]:
    path = _project_file(project_root)
    if not path.is_file():
        raise engine.ValidationError("APSAL project is not initialized")
    return engine.load_json(path)


def _write_project(project_root: Path, value: dict[str, Any]) -> None:
    value["updated_at"] = engine._utc_now()
    engine._write_private_json(value, _project_file(project_root))


def _default_lineage() -> dict[str, Any]:
    return {
        "parent_project_id": None,
        "origin_project_id": None,
        "source_asset_ids": [],
        "fork_type": None,
        "parent_snapshot_digest": None,
    }


def configure_project(
    project_root: Path,
    *,
    name: str,
    project_kind: str = "root",
    lineage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if project_kind not in PROJECT_KINDS:
        raise engine.ValidationError(f"project_kind must be one of {sorted(PROJECT_KINDS)}")
    clean_name = str(name or "").strip()
    if not clean_name:
        raise engine.ValidationError("project name is required")
    manifest = _read_project(project_root)
    manifest.update({
        "name": clean_name[:160],
        "project_kind": project_kind,
        "lineage": {**_default_lineage(), **(lineage or {})},
        "creative_project_schema_version": CREATIVE_PROJECT_SCHEMA_VERSION,
    })
    _write_project(project_root, manifest)
    return manifest


def load_project_references(project_root: Path) -> dict[str, Any]:
    path = _references_file(project_root)
    if not path.is_file():
        return {
            "schema_version": CREATIVE_PROJECT_SCHEMA_VERSION,
            "project_id": _read_project(project_root).get("project_id"),
            "references": [],
            "created_at": engine._utc_now(),
            "updated_at": engine._utc_now(),
        }
    value = engine.load_json(path)
    if not isinstance(value.get("references"), list):
        raise engine.ValidationError("project references must be a list")
    return value


def _rights_status(rights: dict[str, Any], uses: list[str]) -> str:
    copyright_status = str(rights.get("copyright_status", "")).strip()
    if copyright_status in {"", "user_provided_unverified", "unknown", "pending"}:
        return "rights_pending"
    if rights.get("ai_modification_allowed") is not True:
        return "ai_modification_not_allowed"
    if "identity" in uses and not (
        rights.get("identity_use_allowed") is True
        and str(rights.get("portrait_rights", "")).strip() in {"confirmed", "owned", "licensed"}
    ):
        return "identity_not_authorized"
    return "confirmed"


def _validate_rights(rights: Any, uses: list[str]) -> dict[str, Any]:
    if not isinstance(rights, dict):
        raise engine.ValidationError("each reference requires a rights object")
    required = {"copyright_status", "portrait_rights", "redistribution_allowed", "ai_modification_allowed"}
    missing = sorted(key for key in required if key not in rights)
    if missing:
        raise engine.ValidationError(f"reference rights are missing: {missing}")
    if not isinstance(rights.get("redistribution_allowed"), bool) or not isinstance(rights.get("ai_modification_allowed"), bool):
        raise engine.ValidationError("reference redistribution and AI-modification rights must be explicit booleans")
    status = _rights_status(rights, uses)
    if status == "identity_not_authorized":
        raise engine.ValidationError("identity use requires explicit portrait and identity authorization")
    return {**rights, "rights_status": status}


def _reference_binding(record: dict[str, Any], *, home: Path | None = None) -> dict[str, Any]:
    path = engine._vault_reference_path(record["vault_uri"], home)
    return {
        "path": str(path),
        "reference_id": record["reference_id"],
        "uses": record.get("uses", []),
        "allowed_uses": record.get("allowed_uses", []),
        "forbidden_uses": record.get("forbidden_uses", []),
        "applies_to": record.get("applies_to", ["*"]),
        "rights": record.get("rights", {}),
        "expected_sha256": record.get("sha256"),
        "core_visual_anchor": "identity" in record.get("uses", []),
    }


def create_reference_project(
    project_root: Path,
    *,
    name: str,
    references: list[dict[str, Any]],
    home: Path | None = None,
) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    if not references or len(references) > 24:
        raise engine.ValidationError("a reference project requires 1-24 images")
    manifest = configure_project(root, name=name, project_kind="root")
    stored: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(references, 1):
        if not isinstance(item, dict) or not item.get("path"):
            raise engine.ValidationError("each reference requires a local path")
        uses = [str(value) for value in item.get("uses", ["style", "world", "composition"])]
        if not uses or set(uses) - engine.REFERENCE_USES:
            raise engine.ValidationError(f"reference uses must be selected from {sorted(engine.REFERENCE_USES)}")
        rights = _validate_rights(item.get("rights"), uses)
        stored_item = engine.store_private_reference(
            Path(str(item["path"])),
            home=home,
            reference_id=item.get("reference_id"),
            uses=uses,
            allowed_uses=item.get("allowed_uses"),
            forbidden_uses=item.get("forbidden_uses"),
            applies_to=item.get("applies_to"),
            rights={key: value for key, value in rights.items() if key != "rights_status"},
            expected_sha256=item.get("expected_sha256"),
        )
        if stored_item["sha256"] in seen:
            continue
        seen.add(stored_item["sha256"])
        stored.append({
            **stored_item,
            "order": index,
            "role": str(item.get("role") or "unassigned"),
            "rights_status": rights["rights_status"],
            "identity_lock_allowed": "identity" in uses and rights.get("identity_use_allowed") is True,
        })
    value = {
        "schema_version": CREATIVE_PROJECT_SCHEMA_VERSION,
        "project_id": manifest["project_id"],
        "reference_count": len(stored),
        "references": stored,
        "created_at": engine._utc_now(),
        "updated_at": engine._utc_now(),
    }
    engine._write_private_json(value, _references_file(root))
    reconcile_library(root, home=home)
    return {"project_root": str(root), "project": manifest, "references": value}


def fork_project(
    parent_root: Path,
    target_root: Path,
    *,
    name: str,
    fork_type: str,
    source_asset_ids: list[str] | None = None,
    home: Path | None = None,
) -> dict[str, Any]:
    parent_root = parent_root.expanduser().resolve()
    target_root = target_root.expanduser().resolve()
    parent = _read_project(parent_root)
    target = _read_project(target_root)
    lineage = {
        "parent_project_id": parent["project_id"],
        "origin_project_id": parent.get("lineage", {}).get("origin_project_id") or parent["project_id"],
        "source_asset_ids": list(dict.fromkeys(source_asset_ids or [])),
        "fork_type": str(fork_type or "creative_expansion")[:80],
        "parent_snapshot_digest": engine.digest({
            "project": parent,
            "references": load_project_references(parent_root),
            "analysis": list_analysis(parent_root),
        }),
    }
    target = configure_project(target_root, name=name, project_kind="fork", lineage=lineage)
    if parent.get("active_session_id"):
        target["active_session_id"] = parent["active_session_id"]
        _write_project(target_root, target)
    references = load_project_references(parent_root)
    references = {**references, "project_id": target["project_id"], "forked_from": parent["project_id"], "updated_at": engine._utc_now()}
    engine._write_private_json(references, _references_file(target_root))
    for relative in ("analysis", "drafts", "themes", "registry"):
        source = parent_root / ".apsal" / relative
        destination = target_root / ".apsal" / relative
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
    reconcile_library(parent_root, home=home)
    reconcile_library(target_root, home=home)
    return {"project_root": str(target_root), "project": target, "lineage": lineage}


def _analysis_file(project_root: Path, analysis_id: str) -> Path:
    safe = engine._safe_part(analysis_id, "analysis id")
    return engine._inside(_analysis_root(project_root), _analysis_root(project_root) / f"{safe}.json")


def list_analysis(project_root: Path) -> list[dict[str, Any]]:
    root = _analysis_root(project_root)
    if not root.is_dir():
        return []
    return [engine.load_json(path) for path in sorted(root.glob("ANALYSIS-*.json"))]


def load_analysis(project_root: Path, analysis_id: str) -> dict[str, Any]:
    path = _analysis_file(project_root, analysis_id)
    if not path.is_file():
        raise engine.ValidationError(f"unknown analysis: {analysis_id}")
    return engine.load_json(path)


def _write_analysis(project_root: Path, value: dict[str, Any]) -> None:
    value["updated_at"] = engine._utc_now()
    engine._write_private_json(value, _analysis_file(project_root, value["analysis_id"]))


def start_analysis(project_root: Path) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    references = load_project_references(root).get("references", [])
    if not references:
        raise engine.ValidationError("analysis requires imported project references")
    pending = [item["reference_id"] for item in references if item.get("rights_status") != "confirmed"]
    if pending:
        raise engine.ValidationError(f"confirm reference rights before analysis: {pending}")
    analysis_id = f"ANALYSIS-{uuid.uuid4().hex[:12].upper()}"
    jobs = [{
        "job_id": f"IMAGE-{item['reference_id']}",
        "kind": "image",
        "reference_ids": [item["reference_id"]],
        "status": "pending",
        "attempts": [],
        "result": None,
    } for item in references]
    jobs.append({
        "job_id": "SET-SYNTHESIS",
        "kind": "synthesis",
        "reference_ids": [item["reference_id"] for item in references],
        "status": "blocked",
        "attempts": [],
        "result": None,
    })
    value = {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "analysis_id": analysis_id,
        "project_id": _read_project(root)["project_id"],
        "status": "analyzing",
        "jobs": jobs,
        "created_at": engine._utc_now(),
        "updated_at": engine._utc_now(),
    }
    _write_analysis(root, value)
    return value


def _image_analysis_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["observed", "inferred", "reference_roles", "locks", "variables", "risks", "uncertainties", "elements"],
        "properties": {
            "observed": {"type": "array", "items": {"type": "string"}},
            "inferred": {"type": "array", "items": {"type": "string"}},
            "reference_roles": {"type": "array", "items": {"type": "string"}},
            "locks": {"type": "array", "items": {"type": "string"}},
            "variables": {"type": "array", "items": {"type": "string"}},
            "risks": {"type": "array", "items": {"type": "string"}},
            "uncertainties": {"type": "array", "items": {"type": "string"}},
            "elements": {
                "type": "object",
                "required": list(ANALYSIS_ROLES),
                "properties": {role: {"type": "object"} for role in ANALYSIS_ROLES},
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
    }


def _synthesis_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["common_visual_dna", "conflicts", "complements", "recommended_directions", "element_decisions"],
        "properties": {
            "common_visual_dna": {"type": "array", "items": {"type": "string"}},
            "conflicts": {"type": "array", "items": {"type": "string"}},
            "complements": {"type": "array", "items": {"type": "string"}},
            "recommended_directions": {"type": "array", "items": {"type": "string"}},
            "element_decisions": {
                "type": "object",
                "required": list(ANALYSIS_ROLES),
                "properties": {role: {"type": "object"} for role in ANALYSIS_ROLES},
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
    }


def _analysis_reference_map(project_root: Path) -> dict[str, dict[str, Any]]:
    return {item["reference_id"]: item for item in load_project_references(project_root).get("references", [])}


def next_analysis_job(project_root: Path, analysis_id: str) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    analysis = load_analysis(root, analysis_id)
    image_jobs = [job for job in analysis["jobs"] if job["kind"] == "image"]
    synthesis = next(job for job in analysis["jobs"] if job["kind"] == "synthesis")
    if all(job["status"] == "succeeded" for job in image_jobs) and synthesis["status"] == "blocked":
        synthesis["status"] = "pending"
        _write_analysis(root, analysis)
    job = next((item for item in analysis["jobs"] if item["status"] == "pending"), None)
    if job is None:
        job = next((item for item in analysis["jobs"] if item["status"] == "failed"), None)
    if job is None:
        return {"analysis_id": analysis_id, "status": analysis["status"], "job": None}
    references = _analysis_reference_map(root)
    reference_paths = [str(engine._vault_reference_path(references[item]["vault_uri"])) for item in job["reference_ids"]]
    if job["kind"] == "image":
        identity_allowed = all(references[item].get("identity_lock_allowed") is True for item in job["reference_ids"])
        instruction = (
            "Analyze only observable photographic evidence and separate observations from inference. "
            "Do not identify a person or infer sensitive traits. "
            + ("Identity continuity may be described only as authorized visual attributes. " if identity_allowed else "Do not describe or preserve identity-specific facial traits. ")
            + "Return every APSAL five-layer/thirteen-element role in the supplied JSON schema."
        )
        schema = _image_analysis_schema()
        context = None
    else:
        instruction = "Synthesize the completed per-image analyses into one APSAL visual DNA without reading new media. Return the supplied JSON schema."
        schema = _synthesis_schema()
        context = [{"job_id": item["job_id"], "result": item["result"]} for item in image_jobs]
    return {
        "analysis_id": analysis_id,
        "job_id": job["job_id"],
        "kind": job["kind"],
        "reference_ids": job["reference_ids"],
        "referenced_image_paths": reference_paths if job["kind"] == "image" else [],
        "instruction": instruction,
        "result_schema": schema,
        "context": context,
        "codex_tool": "multimodal_analysis" if job["kind"] == "image" else "structured_synthesis",
        "direct_api_calls": False,
        "attempt_count": len(job.get("attempts", [])),
        "last_error": job.get("error"),
    }


def _require_string_lists(value: dict[str, Any], fields: list[str]) -> None:
    for field in fields:
        if not isinstance(value.get(field), list) or any(not isinstance(item, str) for item in value[field]):
            raise engine.ValidationError(f"analysis result {field} must be a string list")


def _validate_analysis_result(kind: str, result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise engine.ValidationError("analysis result must be an object")
    if kind == "image":
        fields = ["observed", "inferred", "reference_roles", "locks", "variables", "risks", "uncertainties"]
        expected = {*fields, "elements"}
        _require_string_lists(result, fields)
        elements = result.get("elements")
    else:
        fields = ["common_visual_dna", "conflicts", "complements", "recommended_directions"]
        expected = {*fields, "element_decisions"}
        _require_string_lists(result, fields)
        elements = result.get("element_decisions")
    if set(result) != expected:
        raise engine.ValidationError("analysis result must match the supplied strict schema")
    if not isinstance(elements, dict) or set(elements) != set(ANALYSIS_ROLES):
        raise engine.ValidationError("analysis result must cover all thirteen APSAL roles")
    if any(not isinstance(elements[role], dict) for role in ANALYSIS_ROLES):
        raise engine.ValidationError("each APSAL role analysis must be an object")
    return json.loads(json.dumps(result))


def record_analysis(
    project_root: Path,
    analysis_id: str,
    job_id: str,
    *,
    status: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    if status not in {"succeeded", "failed"}:
        raise engine.ValidationError("analysis status must be succeeded or failed")
    root = project_root.expanduser().resolve()
    analysis = load_analysis(root, analysis_id)
    job = next((item for item in analysis["jobs"] if item["job_id"] == job_id), None)
    if job is None:
        raise engine.ValidationError(f"unknown analysis job: {job_id}")
    if job["status"] == "succeeded":
        if status == "succeeded" and result is not None and engine.digest(result) == engine.digest(job["result"]):
            return analysis
        raise engine.ValidationError("successful analysis results are immutable")
    attempt: dict[str, Any] = {"status": status, "recorded_at": engine._utc_now()}
    if status == "succeeded":
        validated = _validate_analysis_result(job["kind"], result)
        job["result"] = validated
        attempt["result_digest"] = engine.digest(validated)
        job["error"] = None
    else:
        message = str(error or "analysis_error_not_reported").strip()
        job["error"] = message
        attempt["error"] = message
    job["attempts"].append(attempt)
    job["status"] = status
    image_jobs = [item for item in analysis["jobs"] if item["kind"] == "image"]
    synthesis = next(item for item in analysis["jobs"] if item["kind"] == "synthesis")
    if all(item["status"] == "succeeded" for item in image_jobs) and synthesis["status"] == "blocked":
        synthesis["status"] = "pending"
    if synthesis["status"] == "succeeded":
        analysis["status"] = "completed"
        analysis["synthesis"] = synthesis["result"]
    elif any(item["status"] == "failed" for item in analysis["jobs"]):
        analysis["status"] = "partial"
    else:
        analysis["status"] = "analyzing"
    _write_analysis(root, analysis)
    reconcile_library(root)
    return analysis


def analysis_status(project_root: Path, analysis_id: str) -> dict[str, Any]:
    return load_analysis(project_root, analysis_id)


def build_design_from_analysis(
    project_root: Path,
    analysis_id: str,
    *,
    shot_count: int = 9,
    language: str = "zh-CN",
    theme_id: str | None = None,
    home: Path | None = None,
) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    analysis = load_analysis(root, analysis_id)
    if analysis.get("status") != "completed" or not isinstance(analysis.get("synthesis"), dict):
        raise engine.ValidationError("complete reference analysis before building an APSAL design")
    references = load_project_references(root).get("references", [])
    pending = [item["reference_id"] for item in references if item.get("rights_status") != "confirmed"]
    if pending:
        raise engine.ValidationError(f"confirm reference rights before automatic design: {pending}")
    synthesis = analysis["synthesis"]
    brief = "；".join(synthesis.get("recommended_directions") or synthesis.get("common_visual_dna") or ["参考图驱动的 APSAL 摄影主题"])
    bindings = [_reference_binding(item, home=home) for item in references]
    identity = [item for item in bindings if "identity" in item.get("uses", [])]
    for item in bindings:
        item["core_visual_anchor"] = bool(identity and item["reference_id"] == identity[0]["reference_id"])
    session = engine.start_design_session(
        brief,
        project_root=root,
        theme_id=theme_id,
        name=_read_project(root).get("name") or brief[:80],
        shot_count=shot_count,
        home=home,
        language=language,
        authoring_mode="automatic",
        reference_bindings=bindings,
    )
    analysis["design_session_id"] = session["session_id"]
    analysis["design_theme_id"] = session.get("theme_artifact", {}).get("theme_id") if session.get("theme_artifact") else theme_id
    _write_analysis(root, analysis)
    reconcile_library(root, home=home)
    return session


def _library_connection(home: Path | None = None) -> sqlite3.Connection:
    root = _library_root(home)
    engine._mkdir_private(root)
    engine._mkdir_private(root / "objects")
    connection = sqlite3.connect(root / "library.sqlite3")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS projects (
          project_id TEXT PRIMARY KEY,
          project_root TEXT NOT NULL UNIQUE,
          name TEXT NOT NULL,
          project_kind TEXT NOT NULL,
          parent_project_id TEXT,
          origin_project_id TEXT,
          stage TEXT NOT NULL,
          reference_count INTEGER NOT NULL DEFAULT 0,
          output_count INTEGER NOT NULL DEFAULT 0,
          cover_path TEXT,
          tags_json TEXT NOT NULL DEFAULT '[]',
          favorite INTEGER NOT NULL DEFAULT 0,
          archived INTEGER NOT NULL DEFAULT 0,
          analysis_text TEXT NOT NULL DEFAULT '',
          created_at TEXT,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS assets (
          asset_id TEXT PRIMARY KEY,
          sha256 TEXT NOT NULL,
          kind TEXT NOT NULL,
          path TEXT NOT NULL,
          archived_path TEXT,
          format TEXT,
          width INTEGER,
          height INTEGER,
          size INTEGER,
          rights_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS assets_sha_kind ON assets(sha256, kind);
        CREATE TABLE IF NOT EXISTS project_assets (
          project_id TEXT NOT NULL,
          asset_id TEXT NOT NULL,
          reference_id TEXT,
          run_id TEXT,
          shot_id TEXT,
          role TEXT,
          prompt_digest TEXT,
          qa_status TEXT,
          PRIMARY KEY(project_id, asset_id, reference_id, run_id, shot_id),
          FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE,
          FOREIGN KEY(asset_id) REFERENCES assets(asset_id) ON DELETE CASCADE
        );
        """
    )
    return connection


def _project_stage(project_root: Path, analyses: list[dict[str, Any]]) -> str:
    shares = list(_share_root(project_root).glob("SHARE-*.json")) if _share_root(project_root).is_dir() else []
    if any(engine.load_json(path).get("status") == "published" for path in shares):
        return "published"
    runs_root = project_root / ".apsal" / "runs"
    runs = [engine.load_json(path) for path in runs_root.glob("*/run.json")] if runs_root.is_dir() else []
    if any(run.get("status") == "completed" for run in runs):
        return "review_ready"
    if any(run.get("status") in {"generating", "partial"} for run in runs):
        return "generating"
    if any(item.get("design_session_id") for item in analyses):
        return "skill_ready"
    if any(item.get("status") == "completed" for item in analyses):
        return "design_ready"
    if analyses:
        return "analyzing"
    return "references_ready"


def _archive_generated_object(source: Path, sha: str, home: Path | None = None) -> Path:
    root = _library_root(home) / "objects" / sha[:2]
    engine._mkdir_private(root)
    suffix = source.suffix.lower() if re.fullmatch(r"\.[a-z0-9]{1,8}", source.suffix.lower()) else ".bin"
    target = root / f"{sha}{suffix}"
    if not target.exists():
        try:
            os.link(source, target)
        except OSError:
            shutil.copyfile(source, target)
        try:
            target.chmod(0o600)
        except OSError:
            pass
    return target


def _upsert_asset(
    connection: sqlite3.Connection,
    *,
    project_id: str,
    source: Path,
    kind: str,
    reference_id: str = "",
    run_id: str = "",
    shot_id: str = "",
    role: str = "",
    prompt_digest: str = "",
    qa_status: str = "",
    rights: dict[str, Any] | None = None,
    home: Path | None = None,
) -> tuple[str, str]:
    data = source.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    asset_id = f"ASSET-{kind.upper()}-{sha[:16].upper()}"
    width = height = None
    image_format = None
    try:
        image_format = engine._image_format(data)
        width, height = engine._image_dimensions(data)
    except engine.ValidationError:
        pass
    archived = _archive_generated_object(source, sha, home) if kind == "output" else source
    connection.execute(
        """INSERT INTO assets(asset_id, sha256, kind, path, archived_path, format, width, height, size, rights_json, created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(asset_id) DO UPDATE SET path=excluded.path, archived_path=excluded.archived_path,
             format=excluded.format, width=excluded.width, height=excluded.height, size=excluded.size,
             rights_json=excluded.rights_json""",
        (asset_id, sha, kind, str(source), str(archived), image_format, width, height, len(data),
         json.dumps(rights or {}, ensure_ascii=False), engine._utc_now()),
    )
    connection.execute(
        """INSERT INTO project_assets(project_id, asset_id, reference_id, run_id, shot_id, role, prompt_digest, qa_status)
           VALUES(?,?,?,?,?,?,?,?)
           ON CONFLICT(project_id, asset_id, reference_id, run_id, shot_id) DO UPDATE SET
             role=excluded.role, prompt_digest=excluded.prompt_digest, qa_status=excluded.qa_status""",
        (project_id, asset_id, reference_id, run_id, shot_id, role, prompt_digest, qa_status),
    )
    return asset_id, str(archived)


def reconcile_library(project_root: Path, *, home: Path | None = None) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    manifest = _read_project(root)
    project_id = str(manifest["project_id"])
    references = load_project_references(root).get("references", [])
    analyses = list_analysis(root)
    output_records: list[dict[str, Any]] = []
    runs_root = root / ".apsal" / "runs"
    if runs_root.is_dir():
        for run_path in sorted(runs_root.glob("*/run.json")):
            run = engine.load_json(run_path)
            for job in run.get("jobs", []):
                output = job.get("output") if isinstance(job.get("output"), dict) else None
                path = Path(str(output.get("path", ""))).expanduser() if output else None
                if job.get("status") == "succeeded" and path and path.is_file():
                    output_records.append({"run": run, "job": job, "path": path.resolve()})
    connection = _library_connection(home)
    try:
        previous = connection.execute("SELECT tags_json, favorite, archived FROM projects WHERE project_id=?", (project_id,)).fetchone()
        tags_json = previous["tags_json"] if previous else "[]"
        favorite = int(previous["favorite"]) if previous else 0
        archived = int(previous["archived"]) if previous else 0
        lineage = manifest.get("lineage") if isinstance(manifest.get("lineage"), dict) else {}
        analysis_text = json.dumps([item.get("synthesis") for item in analyses if item.get("synthesis")], ensure_ascii=False)
        connection.execute(
            """INSERT INTO projects(project_id, project_root, name, project_kind, parent_project_id, origin_project_id,
               stage, reference_count, output_count, cover_path, tags_json, favorite, archived, analysis_text, created_at, updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(project_id) DO UPDATE SET project_root=excluded.project_root, name=excluded.name,
                 project_kind=excluded.project_kind, parent_project_id=excluded.parent_project_id,
                 origin_project_id=excluded.origin_project_id, stage=excluded.stage,
                 reference_count=excluded.reference_count, output_count=excluded.output_count,
                 cover_path=excluded.cover_path, analysis_text=excluded.analysis_text, updated_at=excluded.updated_at""",
            (project_id, str(root), str(manifest.get("name") or root.name), str(manifest.get("project_kind") or "root"),
             lineage.get("parent_project_id"), lineage.get("origin_project_id"), _project_stage(root, analyses),
             len(references), len(output_records), None, tags_json, favorite, archived, analysis_text,
             manifest.get("created_at"), engine._utc_now()),
        )
        cover_path = None
        for item in references:
            try:
                path = engine._vault_reference_path(item["vault_uri"], home)
            except (KeyError, engine.ValidationError):
                continue
            _, archived_path = _upsert_asset(
                connection, project_id=project_id, source=path, kind="reference",
                reference_id=item.get("reference_id", ""), role=item.get("role", ""), rights=item.get("rights", {}), home=home,
            )
            cover_path = cover_path or archived_path
        for item in output_records:
            run, job, path = item["run"], item["job"], item["path"]
            qa_path = path.parent.parent / "qa" / f"{job['shot_id']}.json"
            qa = engine.load_json(qa_path) if qa_path.is_file() else {}
            _, archived_path = _upsert_asset(
                connection, project_id=project_id, source=path, kind="output",
                run_id=run.get("run_id", ""), shot_id=job.get("shot_id", ""),
                prompt_digest=job.get("prompt_digest", ""),
                qa_status=qa.get("model_visual_qa_status", job.get("model_visual_qa", "pending")), home=home,
            )
            cover_path = archived_path
        connection.execute("UPDATE projects SET cover_path=? WHERE project_id=?", (cover_path, project_id))
        connection.commit()
        return {
            "schema_version": LIBRARY_SCHEMA_VERSION,
            "project_id": project_id,
            "reference_count": len(references),
            "output_count": len(output_records),
            "cover_path": cover_path,
            "status": "reconciled",
        }
    finally:
        connection.close()


def library_status(*, home: Path | None = None) -> dict[str, Any]:
    connection = _library_connection(home)
    try:
        projects = connection.execute("SELECT COUNT(*) AS count FROM projects").fetchone()["count"]
        assets = connection.execute("SELECT COUNT(*) AS count FROM assets").fetchone()["count"]
        return {
            "schema_version": LIBRARY_SCHEMA_VERSION,
            "root": str(_library_root(home)),
            "project_count": projects,
            "asset_count": assets,
            "authoritative_source": ".apsal project directories",
        }
    finally:
        connection.close()


def _project_row(row: sqlite3.Row) -> dict[str, Any]:
    value = dict(row)
    value["tags"] = json.loads(value.pop("tags_json") or "[]")
    value["favorite"] = bool(value["favorite"])
    value["archived"] = bool(value["archived"])
    value.pop("analysis_text", None)
    return value


def library_list(
    *,
    query: str = "",
    archived: bool = False,
    favorite: bool | None = None,
    limit: int = 50,
    offset: int = 0,
    home: Path | None = None,
) -> dict[str, Any]:
    limit = min(max(int(limit), 1), 100)
    offset = max(int(offset), 0)
    clauses = ["archived=?"]
    values: list[Any] = [1 if archived else 0]
    if favorite is not None:
        clauses.append("favorite=?")
        values.append(1 if favorite else 0)
    text = str(query or "").strip()
    if text:
        clauses.append("(name LIKE ? OR tags_json LIKE ? OR analysis_text LIKE ? OR project_id LIKE ?)")
        token = f"%{text}%"
        values.extend([token, token, token, token])
    where = " AND ".join(clauses)
    connection = _library_connection(home)
    try:
        total = connection.execute(f"SELECT COUNT(*) AS count FROM projects WHERE {where}", values).fetchone()["count"]
        rows = connection.execute(
            f"SELECT * FROM projects WHERE {where} ORDER BY favorite DESC, updated_at DESC LIMIT ? OFFSET ?",
            [*values, limit, offset],
        ).fetchall()
        return {"schema_version": LIBRARY_SCHEMA_VERSION, "total": total, "offset": offset, "limit": limit,
                "projects": [_project_row(row) for row in rows]}
    finally:
        connection.close()


def library_get(project_id: str, *, home: Path | None = None) -> dict[str, Any]:
    connection = _library_connection(home)
    try:
        row = connection.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()
        if row is None:
            raise engine.ValidationError(f"unknown library project: {project_id}")
        assets = [dict(item) for item in connection.execute(
            """SELECT a.*, pa.reference_id, pa.run_id, pa.shot_id, pa.role, pa.prompt_digest, pa.qa_status
               FROM assets a JOIN project_assets pa ON pa.asset_id=a.asset_id WHERE pa.project_id=?
               ORDER BY a.kind, pa.run_id, pa.shot_id, pa.reference_id""", (project_id,)
        ).fetchall()]
        for item in assets:
            item["rights"] = json.loads(item.pop("rights_json") or "{}")
        project = _project_row(row)
        root = Path(project["project_root"])
        analyses = [{
            "analysis_id": item.get("analysis_id"),
            "status": item.get("status"),
            "job_count": len(item.get("jobs", [])),
            "completed_job_count": sum(job.get("status") == "succeeded" for job in item.get("jobs", [])),
            "design_session_id": item.get("design_session_id"),
            "updated_at": item.get("updated_at"),
        } for item in list_analysis(root)]
        shares = share_status(root).get("shares", [])
        share_summaries = [{
            "share_id": item.get("share_id"),
            "platform": item.get("content", {}).get("platform"),
            "status": item.get("status"),
            "publication": item.get("publication"),
            "updated_at": item.get("updated_at"),
        } for item in shares]
        return {
            "schema_version": LIBRARY_SCHEMA_VERSION,
            "project": project,
            "assets": assets,
            "analyses": analyses,
            "shares": share_summaries,
        }
    finally:
        connection.close()


def library_update(
    project_id: str,
    *,
    tags: list[str] | None = None,
    favorite: bool | None = None,
    display_name: str | None = None,
    home: Path | None = None,
) -> dict[str, Any]:
    connection = _library_connection(home)
    try:
        row = connection.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()
        if row is None:
            raise engine.ValidationError(f"unknown library project: {project_id}")
        updates: dict[str, Any] = {"updated_at": engine._utc_now()}
        if tags is not None:
            if any(not isinstance(item, str) or not item.strip() for item in tags) or len(tags) > 30:
                raise engine.ValidationError("library tags must be 1-30 non-empty strings")
            updates["tags_json"] = json.dumps(list(dict.fromkeys(item.strip()[:40] for item in tags)), ensure_ascii=False)
        if favorite is not None:
            updates["favorite"] = 1 if favorite else 0
        if display_name is not None:
            if not display_name.strip():
                raise engine.ValidationError("display name cannot be empty")
            updates["name"] = display_name.strip()[:160]
        assignments = ", ".join(f"{key}=?" for key in updates)
        connection.execute(f"UPDATE projects SET {assignments} WHERE project_id=?", [*updates.values(), project_id])
        connection.commit()
        updated = connection.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()
        return _project_row(updated)
    finally:
        connection.close()


def library_archive(project_id: str, archived: bool, *, home: Path | None = None) -> dict[str, Any]:
    connection = _library_connection(home)
    try:
        if connection.execute("SELECT 1 FROM projects WHERE project_id=?", (project_id,)).fetchone() is None:
            raise engine.ValidationError(f"unknown library project: {project_id}")
        connection.execute("UPDATE projects SET archived=?, updated_at=? WHERE project_id=?",
                           (1 if archived else 0, engine._utc_now(), project_id))
        connection.commit()
        return {"project_id": project_id, "archived": bool(archived), "source_files_deleted": False}
    finally:
        connection.close()


def library_lineage(project_id: str, *, home: Path | None = None) -> dict[str, Any]:
    connection = _library_connection(home)
    try:
        rows = {row["project_id"]: _project_row(row) for row in connection.execute("SELECT * FROM projects").fetchall()}
        if project_id not in rows:
            raise engine.ValidationError(f"unknown library project: {project_id}")
        ancestors = []
        current = rows[project_id]
        seen = {project_id}
        while current.get("parent_project_id") and current["parent_project_id"] in rows and current["parent_project_id"] not in seen:
            current = rows[current["parent_project_id"]]
            ancestors.append(current)
            seen.add(current["project_id"])
        descendants = [value for value in rows.values() if value.get("parent_project_id") == project_id]
        comparison = {"inherited": [], "modified": [], "added": [], "removed": [], "available": False}
        parent_id = rows[project_id].get("parent_project_id")
        if parent_id and parent_id in rows:
            def decisions(value: dict[str, Any]) -> dict[str, Any]:
                root = Path(value["project_root"])
                manifest = _read_project(root)
                session_id = manifest.get("active_session_id")
                if session_id:
                    try:
                        _session, theme = engine.load_design_session(str(session_id), root)
                        if isinstance(theme.get("element_decisions"), dict):
                            return theme["element_decisions"]
                    except (OSError, engine.ValidationError):
                        pass
                synthesis = _latest_synthesis(root)
                return synthesis.get("element_decisions", {}) if isinstance(synthesis.get("element_decisions"), dict) else {}

            parent_decisions = decisions(rows[parent_id])
            child_decisions = decisions(rows[project_id])
            for role in sorted(set(parent_decisions) | set(child_decisions)):
                parent_value = parent_decisions.get(role)
                child_value = child_decisions.get(role)
                if parent_value is None:
                    comparison["added"].append(role)
                elif child_value is None:
                    comparison["removed"].append(role)
                elif engine.digest(parent_value) == engine.digest(child_value):
                    comparison["inherited"].append(role)
                else:
                    comparison["modified"].append(role)
            comparison["available"] = bool(parent_decisions or child_decisions)
        return {"project": rows[project_id], "ancestors": ancestors, "children": descendants,
                "comparison": comparison}
    finally:
        connection.close()


def _public_rights_ready(references: list[dict[str, Any]]) -> None:
    pending = [item.get("reference_id") for item in references if item.get("rights_status") != "confirmed"]
    if pending:
        raise engine.ValidationError(f"public sharing requires confirmed reference rights: {pending}")
    blocked = [item.get("reference_id") for item in references if item.get("rights", {}).get("ai_modification_allowed") is not True]
    if blocked:
        raise engine.ValidationError(f"public sharing is blocked by AI-modification rights: {blocked}")


def _sanitize_public(value: Any, project_root: Path, home: Path | None = None) -> Any:
    blocked = [str(project_root.expanduser().resolve()), str((home or engine.apsal_home()).expanduser().resolve())]
    if isinstance(value, dict):
        return {
            key: _sanitize_public(item, project_root, home)
            for key, item in value.items()
            if key not in {"vault_uri", "path", "project_root", "automatic_reference_path"}
        }
    if isinstance(value, list):
        return [_sanitize_public(item, project_root, home) for item in value]
    if isinstance(value, str) and any(token and token in value for token in blocked):
        return "[local-path-removed]"
    return value


def _sanitize_public_theme_tree(theme_root: Path, project_root: Path, home: Path | None = None) -> None:
    """Remove private nested artifacts and scrub local paths from copied theme files."""
    for path in list(theme_root.rglob("*")):
        if path.is_dir() and (
            path.name == "exports"
            or (path.name == "references" and path.parent.name == "assets")
        ):
            shutil.rmtree(path)
    blocked = [
        str(project_root.expanduser().resolve()),
        str((home or engine.apsal_home()).expanduser().resolve()),
    ]
    for path in sorted(theme_root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() == ".json":
            try:
                engine.write_canonical_json(_sanitize_public(engine.load_json(path), project_root, home), path)
                continue
            except (json.JSONDecodeError, engine.ValidationError):
                pass
        if path.suffix.lower() in {".yaml", ".yml", ".txt", ".md"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            for token in blocked:
                if token:
                    text = text.replace(token, "[local-path-removed]")
            text = "\n".join(
                line for line in text.splitlines()
                if not re.match(r"^\s*(vault_uri|automatic_reference_path|local_path)\s*:", line)
            ) + "\n"
            path.write_text(text, encoding="utf-8")


def _write_public_skill(staging: Path, project: dict[str, Any], synthesis: dict[str, Any]) -> None:
    title = str(project.get("name") or project.get("project_id"))
    dna = synthesis.get("common_visual_dna") or []
    directions = synthesis.get("recommended_directions") or []
    body = f"""---
name: {re.sub(r'[^a-z0-9-]+', '-', title.lower()).strip('-') or 'apsal-shared-project'}
description: Recreate and extend the APSAL photography project {title} from its public, reference-free prompt package.
---

# {title}

This package was exported by APSAL Studio. Treat `project/themes/` as the
authoritative theme and use one independent Codex image-generation call per
shot prompt. Do not infer or reproduce any private reference image or real
person identity: original reference media and local paths are intentionally
absent from this public package.

## Visual DNA

{chr(10).join(f'- {item}' for item in dna) or '- Read the structured synthesis under `project/analysis/`.'}

## Recommended directions

{chr(10).join(f'- {item}' for item in directions) or '- Preserve the confirmed APSAL five-layer/thirteen-element design.'}

## Run

1. Read `project-package.json`, `references.json`, and `checksums.json`.
2. Inspect the theme, compiled prompts, negative constraints, and QA contract.
3. Generate exactly one image per shot, then record actual output and QA state.
4. Fork the imported project before changing direction; keep its lineage.

Built with APSAL Open: https://github.com/henyjone/apsal-open
"""
    (staging / "SKILL.md").write_text(body, encoding="utf-8")


def _latest_synthesis(project_root: Path) -> dict[str, Any]:
    completed = [item for item in list_analysis(project_root) if isinstance(item.get("synthesis"), dict)]
    return completed[-1]["synthesis"] if completed else {}


def _representative_outputs(project_root: Path, limit: int = 9) -> list[Path]:
    result: list[Path] = []
    runs = project_root / ".apsal" / "runs"
    if not runs.is_dir():
        return result
    for run_path in sorted(runs.glob("*/run.json"), reverse=True):
        run = engine.load_json(run_path)
        for job in run.get("jobs", []):
            output = job.get("output") if isinstance(job.get("output"), dict) else {}
            path = Path(str(output.get("path", ""))).expanduser()
            if job.get("status") == "succeeded" and path.is_file():
                result.append(path.resolve())
                if len(result) >= limit:
                    return result
    return result


def _share_page(project: dict[str, Any], synthesis: dict[str, Any], media_names: list[str]) -> str:
    title = html.escape(str(project.get("name") or project.get("project_id")))
    dna_values = synthesis.get("common_visual_dna", [])
    direction_values = synthesis.get("recommended_directions", [])
    dna = "".join(f"<li>{html.escape(str(item))}</li>" for item in dna_values)
    directions = "".join(f"<li>{html.escape(str(item))}</li>" for item in direction_values)
    media = "".join(f'<figure><img src="media/{html.escape(name)}" alt="APSAL project output" loading="lazy"></figure>' for name in media_names)
    story = html.escape(str((direction_values or dna_values or ["一个由参考图驱动、可追溯扩展的 APSAL 摄影项目。"])[0]))
    prompt_example = html.escape("；".join([
        *(str(item) for item in direction_values[:2]),
        *(f"视觉 DNA：{item}" for item in dna_values[:3]),
        "保持 APSAL 五层十三要素、参考边界与交付 QA 一致",
    ]))
    lineage = project.get("lineage") if isinstance(project.get("lineage"), dict) else {}
    lineage_items = "".join(
        f"<li><strong>{label}</strong> {html.escape(str(lineage.get(key)))}</li>"
        for key, label in (("parent_project_id", "父项目"), ("origin_project_id", "源项目"), ("fork_type", "扩展类型"))
        if lineage.get(key)
    ) or "<li>根项目</li>"
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · APSAL</title><style>
	body{{margin:0;background:#f4efe4;color:#231f18;font:16px/1.7 system-ui,-apple-system,'PingFang SC',sans-serif}}main{{max-width:1120px;margin:auto;padding:64px 28px}}header{{border-bottom:1px solid #b9aa8c;padding-bottom:30px}}.eyebrow{{letter-spacing:.18em;color:#8a5c24}}h1{{font:600 clamp(38px,7vw,76px)/1.05 Georgia,serif;margin:.2em 0}}.story{{max-width:760px;font-size:1.15rem}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin:36px 0}}figure{{margin:0;background:#ddd0b8;aspect-ratio:3/4;overflow:hidden}}img{{width:100%;height:100%;object-fit:cover}}section{{display:grid;grid-template-columns:1fr 1fr;gap:40px;margin:54px 0}}.prompt{{padding:20px;border-left:3px solid #8a5c24;background:#ece3d2;white-space:pre-wrap}}footer{{margin-top:70px;border-top:1px solid #b9aa8c;padding-top:24px}}@media(max-width:700px){{section{{grid-template-columns:1fr}}}}
	</style></head><body><main><header><div class="eyebrow">APSAL OPEN · SHARE PROJECT</div><h1>{title}</h1><p>项目 {html.escape(str(project.get('project_id')))} · 可复现的提示词、Skill 与创作谱系</p><p class="story">{story}</p></header><div class="grid">{media}</div><section><div><h2>共同视觉 DNA</h2><ul>{dna}</ul></div><div><h2>推荐扩展方向</h2><ul>{directions}</ul></div><div><h2>提示词示例</h2><p class="prompt">{prompt_example}</p></div><div><h2>项目谱系</h2><ul>{lineage_items}</ul></div><div><h2>使用说明</h2><ol><li>导入分享包并生成新的本地项目 ID。</li><li>检查版本、参考边界与 QA 标准。</li><li>通过 APSAL Engine 或 Studio 继续分叉与生成。</li></ol></div></section><footer>使用 <a href="https://github.com/henyjone/apsal-open">APSAL Open</a> 构建 · 参考图默认不包含在公开包中</footer></main></body></html>"""


def _zip_tree(source: Path, target: Path) -> str:
    files = sorted(path for path in source.rglob("*") if path.is_file())
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            info = zipfile.ZipInfo(str(path.relative_to(source)).replace(os.sep, "/"))
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    return hashlib.sha256(target.read_bytes()).hexdigest()


def export_project(
    project_root: Path,
    *,
    distribution: str,
    output_dir: Path,
    confirmed_public: bool = False,
    home: Path | None = None,
) -> dict[str, Any]:
    if distribution not in {"public", "private"}:
        raise engine.ValidationError("project export distribution must be public or private")
    root = project_root.expanduser().resolve()
    project = _read_project(root)
    reference_value = load_project_references(root)
    references = reference_value.get("references", [])
    if distribution == "public":
        _public_rights_ready(references)
        if confirmed_public is not True:
            raise engine.ValidationError("explicit public-release confirmation is required")
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    export_id = f"EXPORT-{uuid.uuid4().hex[:12].upper()}"
    with tempfile.TemporaryDirectory(prefix="apsal-project-export-") as temporary:
        staging = Path(temporary) / "apsal-project"
        staging.mkdir()
        project_dir = staging / "project"
        project_dir.mkdir()
        public_project = _sanitize_public(project, root, home)
        package_manifest = {
            "schema_version": CREATIVE_PROJECT_SCHEMA_VERSION,
            "export_id": export_id,
            "distribution": distribution,
            "source_project_id": project["project_id"],
            "project": public_project,
            "reference_count": len(references),
            "references_included": distribution == "private",
            "created_at": engine._utc_now(),
            "apsal_open": "https://github.com/henyjone/apsal-open",
        }
        engine.write_canonical_json(package_manifest, staging / "project-package.json")
        for relative in ("analysis", "themes"):
            source = root / ".apsal" / relative
            if source.is_dir():
                destination = project_dir / relative
                shutil.copytree(source, destination)
                if distribution == "public":
                    _sanitize_public_theme_tree(destination, root, home)
        media_root = staging / "media"
        media_root.mkdir()
        media_names: list[str] = []
        for index, source in enumerate(_representative_outputs(root), 1):
            name = f"output-{index:02d}{source.suffix.lower()}"
            shutil.copyfile(source, media_root / name)
            media_names.append(name)
        if distribution == "private":
            refs_root = staging / "references"
            refs_root.mkdir()
            packaged_refs = []
            for item in references:
                source = engine._vault_reference_path(item["vault_uri"], home)
                name = f"{item['reference_id']}{source.suffix.lower()}"
                shutil.copyfile(source, refs_root / name)
                packaged_refs.append({**_sanitize_public(item, root, home), "package_path": f"references/{name}"})
            engine.write_canonical_json({"schema_version": CREATIVE_PROJECT_SCHEMA_VERSION, "references": packaged_refs}, staging / "references.json")
        else:
            engine.write_canonical_json({
                "schema_version": CREATIVE_PROJECT_SCHEMA_VERSION,
                "references": [_sanitize_public(item, root, home) for item in references],
                "media_included": False,
            }, staging / "references.json")
        synthesis = _latest_synthesis(root)
        (staging / "index.html").write_text(_share_page(project, synthesis, media_names), encoding="utf-8")
        if distribution == "public":
            _write_public_skill(staging, project, synthesis)
        checksums = {
            str(path.relative_to(staging)).replace(os.sep, "/"): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(staging.rglob("*")) if path.is_file() and path.name != "checksums.json"
        }
        engine.write_canonical_json({"schema_version": "0.1.0", "sha256": checksums}, staging / "checksums.json")
        target = output_dir / f"{project['project_id']}-{distribution}.zip"
        sha = _zip_tree(staging, target)
    export_record = {
        "schema_version": CREATIVE_PROJECT_SCHEMA_VERSION,
        "export_id": export_id,
        "distribution": distribution,
        "path": str(target),
        "sha256": sha,
        "created_at": engine._utc_now(),
    }
    engine._write_private_json(export_record, _exports_root(root) / f"{export_id}.json")
    return export_record


def _safe_archive_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    total = 0
    for member in members:
        path = Path(member.filename)
        total += member.file_size
        if path.is_absolute() or ".." in path.parts or len(path.parts) > 12:
            raise engine.ValidationError(f"unsafe project package path: {member.filename}")
        if member.file_size > 50_000_000 or total > 500_000_000:
            raise engine.ValidationError("project package exceeds safe import limits")
    return members


def import_project(
    source: Path,
    target_root: Path,
    *,
    name: str | None = None,
    home: Path | None = None,
) -> dict[str, Any]:
    source = source.expanduser().resolve()
    target_root = target_root.expanduser().resolve()
    if not source.is_file():
        raise engine.ValidationError(f"project package not found: {source}")
    with tempfile.TemporaryDirectory(prefix="apsal-project-import-") as temporary:
        unpacked = Path(temporary)
        with zipfile.ZipFile(source) as archive:
            members = _safe_archive_members(archive)
            archive.extractall(unpacked, members=members)
        manifest_path = unpacked / "project-package.json"
        if not manifest_path.is_file():
            raise engine.ValidationError("project package manifest is missing")
        package = engine.load_json(manifest_path)
        source_project = package.get("project") if isinstance(package.get("project"), dict) else {}
        target = configure_project(
            target_root,
            name=name or source_project.get("name") or f"Imported {package.get('source_project_id', 'APSAL project')}",
            project_kind="imported",
            lineage={
                "origin_project_id": package.get("source_project_id"),
                "source_asset_ids": [],
                "fork_type": "project_import",
                "parent_snapshot_digest": hashlib.sha256(source.read_bytes()).hexdigest(),
            },
        )
        project_payload = unpacked / "project"
        for relative in ("analysis", "themes"):
            source_dir = project_payload / relative
            if source_dir.is_dir():
                shutil.copytree(source_dir, target_root / ".apsal" / relative, dirs_exist_ok=True)
        references_path = unpacked / "references.json"
        imported_refs = []
        if references_path.is_file():
            reference_manifest = engine.load_json(references_path)
            for item in reference_manifest.get("references", []):
                package_path = item.get("package_path")
                if package_path:
                    ref_path = (unpacked / package_path).resolve()
                    try:
                        ref_path.relative_to(unpacked.resolve())
                    except ValueError as exc:
                        raise engine.ValidationError("reference package path escapes import root") from exc
                    imported = engine.store_private_reference(
                        ref_path, home=home, reference_id=item.get("reference_id"), uses=item.get("uses"),
                        allowed_uses=item.get("allowed_uses"), forbidden_uses=item.get("forbidden_uses"),
                        applies_to=item.get("applies_to"), rights=item.get("rights"), expected_sha256=item.get("sha256"),
                    )
                    imported_refs.append({**imported, "role": item.get("role", "unassigned"),
                                          "rights_status": _rights_status(item.get("rights", {}), item.get("uses", [])),
                                          "identity_lock_allowed": False})
        engine._write_private_json({
            "schema_version": CREATIVE_PROJECT_SCHEMA_VERSION,
            "project_id": target["project_id"],
            "reference_count": len(imported_refs),
            "references": imported_refs,
            "created_at": engine._utc_now(),
            "updated_at": engine._utc_now(),
        }, _references_file(target_root))
    reconcile_library(target_root, home=home)
    return {"project_root": str(target_root), "project": target, "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}


def _share_file(project_root: Path, share_id: str) -> Path:
    safe = engine._safe_part(share_id, "share id")
    return engine._inside(_share_root(project_root), _share_root(project_root) / f"{safe}.json")


def load_share(project_root: Path, share_id: str) -> dict[str, Any]:
    path = _share_file(project_root, share_id)
    if not path.is_file():
        raise engine.ValidationError(f"unknown share draft: {share_id}")
    return engine.load_json(path)


def _write_share(project_root: Path, value: dict[str, Any]) -> None:
    value["updated_at"] = engine._utc_now()
    engine._write_private_json(value, _share_file(project_root, value["share_id"]))


def _default_share_copy(project_root: Path, platform: str) -> tuple[str, str, list[str]]:
    project = _read_project(project_root)
    synthesis = _latest_synthesis(project_root)
    title = str(project.get("name") or project["project_id"])
    directions = synthesis.get("recommended_directions") or synthesis.get("common_visual_dna") or []
    if platform == "x":
        text = f"{title} — 使用 APSAL Open 从参考图分析、构建 Prompt/Skill，并扩展为可追溯摄影项目。"
    else:
        text = f"{title}\n\n从多张参考图开始，按 APSAL 协议完成视觉分析、摄影语言构建、提示词与 Skill 打包。\n"
        if directions:
            text += "\n创作方向：\n" + "\n".join(f"- {item}" for item in directions[:5])
    return title, text, ["APSAL", "AI摄影", "摄影创作"]


def create_share_draft(
    project_root: Path,
    *,
    platform: str,
    title: str | None = None,
    text: str | None = None,
    hashtags: list[str] | None = None,
    image_paths: list[str] | None = None,
    project_url: str | None = None,
    account: str = "default",
) -> dict[str, Any]:
    if platform not in SHARE_PLATFORMS:
        raise engine.ValidationError(f"share platform must be one of {sorted(SHARE_PLATFORMS)}")
    root = project_root.expanduser().resolve()
    references = load_project_references(root).get("references", [])
    _public_rights_ready(references)
    default_title, default_text, default_tags = _default_share_copy(root, platform)
    selected = [Path(value).expanduser().resolve() for value in (image_paths or [str(path) for path in _representative_outputs(root, 9)])]
    if not selected:
        raise engine.ValidationError("share draft requires at least one generated project image")
    allowed_outputs = {path.resolve() for path in _representative_outputs(root, 100)}
    if any(path not in allowed_outputs for path in selected):
        raise engine.ValidationError("share images must be successful outputs from this APSAL project")
    if platform == "x" and len(selected) > 4:
        selected = selected[:4]
    assets = [{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in selected]
    content = {
        "platform": platform,
        "title": str(title or default_title).strip(),
        "text": str(text or default_text).strip(),
        "hashtags": list(dict.fromkeys((hashtags or default_tags))),
        "images": assets,
        "project_url": project_url or "https://github.com/henyjone/apsal-open",
        "made_with_ai": True,
        "account": account,
    }
    share_id = f"SHARE-{uuid.uuid4().hex[:12].upper()}"
    value = {
        "schema_version": SHARE_SCHEMA_VERSION,
        "share_id": share_id,
        "project_id": _read_project(root)["project_id"],
        "status": "draft",
        "content": content,
        "content_digest": engine.digest(content),
        "confirmation": None,
        "publication": None,
        "created_at": engine._utc_now(),
        "updated_at": engine._utc_now(),
    }
    _write_share(root, value)
    return value


def preview_share(project_root: Path, share_id: str) -> dict[str, Any]:
    value = load_share(project_root, share_id)
    return {
        "share_id": share_id,
        "status": value["status"],
        "content": value["content"],
        "content_digest": value["content_digest"],
        "confirmation_required": value.get("confirmation") is None,
    }


def confirm_share(project_root: Path, share_id: str, *, confirmed_public: bool) -> dict[str, Any]:
    if confirmed_public is not True:
        raise engine.ValidationError("explicit public-release confirmation is required")
    root = project_root.expanduser().resolve()
    value = load_share(root, share_id)
    _public_rights_ready(load_project_references(root).get("references", []))
    content_digest = engine.digest(value["content"])
    if content_digest != value["content_digest"]:
        raise engine.ValidationError("share draft changed; preview it again before confirmation")
    token = secrets.token_urlsafe(32)
    value["confirmation"] = {
        "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
        "content_digest": content_digest,
        "confirmed_at": engine._utc_now(),
    }
    value["status"] = "confirmed"
    _write_share(root, value)
    return {"share_id": share_id, "status": "confirmed", "confirmation_token": token, "content_digest": content_digest}


def _keychain_token(service: str, account: str) -> str | None:
    if sys_platform() != "darwin":
        return None
    result = subprocess.run(
        ["security", "find-generic-password", "-w", "-s", service, "-a", account],
        capture_output=True, text=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else None


def sys_platform() -> str:
    import sys
    return sys.platform


def _x_request(url: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "APSAL-Studio/0.3"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            value = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise engine.ValidationError(f"X API request failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise engine.ValidationError(f"X API request failed: {exc.reason}") from exc
    if not isinstance(value, dict):
        raise engine.ValidationError("X API returned an invalid response")
    return value


def _publish_x(content: dict[str, Any], token: str) -> dict[str, Any]:
    media_ids = []
    for item in content["images"][:4]:
        path = Path(item["path"])
        if not path.is_file():
            raise engine.ValidationError(f"X image does not exist: {path}")
        if path.stat().st_size > X_MAX_IMAGE_BYTES:
            raise engine.ValidationError("X images must be 5 MB or smaller")
        data = path.read_bytes()
        image_format = engine._image_format(data)
        media = _x_request("https://api.x.com/2/media/upload", token, {
            "media": base64.b64encode(data).decode("ascii"),
            "media_category": "tweet_image",
            "media_type": "image/jpeg" if image_format == "jpeg" else f"image/{image_format}",
            "shared": False,
        })
        media_id = (media.get("data") or {}).get("id")
        if not media_id:
            raise engine.ValidationError("X media upload did not return a media id")
        media_ids.append(str(media_id))
    tags = " ".join(f"#{str(item).lstrip('#')}" for item in content.get("hashtags", []))
    message = " ".join(part for part in [content.get("text", ""), tags, content.get("project_url", "")] if part).strip()
    response = _x_request("https://api.x.com/2/tweets", token, {
        "text": message,
        "media": {"media_ids": media_ids},
        "made_with_ai": True,
    })
    remote = response.get("data") or {}
    if not remote.get("id"):
        raise engine.ValidationError("X did not return a published post id")
    return {"remote_id": str(remote["id"]), "url": f"https://x.com/i/web/status/{remote['id']}"}


def _prepare_composer_handoff(project_root: Path, share_id: str, content: dict[str, Any]) -> dict[str, Any]:
    target = _share_root(project_root) / "handoff" / engine._safe_part(share_id, "share id")
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        target.chmod(0o700)
    except OSError:
        pass
    exported = []
    for index, item in enumerate(content.get("images", []), 1):
        source = Path(str(item.get("path", ""))).expanduser().resolve()
        if not source.is_file():
            raise engine.ValidationError(f"share image does not exist: {source}")
        destination = target / f"{index:02d}{source.suffix.lower()}"
        shutil.copyfile(source, destination)
        try:
            destination.chmod(0o600)
        except OSError:
            pass
        exported.append(str(destination))
    tags = " ".join(f"#{str(item).lstrip('#')}" for item in content.get("hashtags", []))
    parts = []
    if content.get("platform") == "xiaohongshu" and content.get("title"):
        parts.append(str(content["title"]))
    parts.extend(str(value) for value in (content.get("text"), tags, content.get("project_url")) if value)
    return {"copy_text": "\n\n".join(parts), "exported_images": exported, "export_directory": str(target)}


def publish_share(project_root: Path, share_id: str, *, confirmation_token: str) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    value = load_share(root, share_id)
    if value.get("status") in {"published", "awaiting_external_confirmation"}:
        return value
    confirmation = value.get("confirmation") if isinstance(value.get("confirmation"), dict) else None
    if not confirmation or not secrets.compare_digest(
        confirmation.get("token_sha256", ""), hashlib.sha256(str(confirmation_token).encode()).hexdigest()
    ):
        raise engine.ValidationError("valid share confirmation token is required")
    if confirmation.get("content_digest") != engine.digest(value["content"]):
        raise engine.ValidationError("share content changed after confirmation")
    platform = value["content"]["platform"]
    if platform == "xiaohongshu":
        handoff = _prepare_composer_handoff(root, share_id, value["content"])
        value["status"] = "awaiting_external_confirmation"
        value["publication"] = {
            "mode": "official_composer_handoff",
            "url": "https://creator.xiaohongshu.com/publish/publish",
            "images": value["content"]["images"],
            "title": value["content"]["title"],
            "text": value["content"]["text"],
            "hashtags": value["content"]["hashtags"],
            "published": False,
            **handoff,
        }
    else:
        token = _keychain_token("studio.apsal.x", value["content"].get("account", "default"))
        if not token:
            handoff = _prepare_composer_handoff(root, share_id, value["content"])
            value["status"] = "awaiting_external_confirmation"
            value["publication"] = {
                "mode": "official_composer_handoff",
                "url": "https://x.com/compose/post",
                "reason": "x_oauth_token_not_configured",
                "images": value["content"]["images"],
                "published": False,
                **handoff,
            }
        else:
            remote = _publish_x(value["content"], token)
            value["status"] = "published"
            value["publication"] = {**remote, "mode": "x_official_api", "published": True, "published_at": engine._utc_now()}
    _write_share(root, value)
    reconcile_library(root)
    return value


def share_status(project_root: Path, share_id: str | None = None) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    if share_id:
        return load_share(root, share_id)
    if not _share_root(root).is_dir():
        return {"schema_version": SHARE_SCHEMA_VERSION, "shares": []}
    return {"schema_version": SHARE_SCHEMA_VERSION,
            "shares": [engine.load_json(path) for path in sorted(_share_root(root).glob("SHARE-*.json"))]}


def migration_preview(source_root: Path, target_root: Path) -> dict[str, Any]:
    source_root = source_root.expanduser().resolve()
    target_root = target_root.expanduser().resolve()
    manifest = _read_project(source_root)
    if manifest.get("protocol_version") != "0.15.0" or manifest.get("engine_version") != "0.15.0":
        raise engine.ValidationError("only APSAL 0.15 projects can be copied into the 0.16 protocol")
    if target_root.exists() and any(target_root.iterdir()):
        raise engine.ValidationError("migration target directory must be empty")
    return {
        "source_project_root": str(source_root),
        "target_project_root": str(target_root),
        "source_project_id": manifest.get("project_id"),
        "source_protocol_version": "0.15.0",
        "target_protocol_version": "0.16.0",
        "mode": "copy_preserving_original",
        "confirmed": False,
    }


def migrate_project_copy(source_root: Path, target_root: Path, *, confirmed: bool) -> dict[str, Any]:
    if confirmed is not True:
        raise engine.ValidationError("explicit migration confirmation is required")
    preview = migration_preview(source_root, target_root)
    source_root = source_root.expanduser().resolve()
    target_root = target_root.expanduser().resolve()
    target_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_root / ".apsal", target_root / ".apsal")
    source_manifest = _read_project(source_root)
    target_manifest = _read_project(target_root)
    target_manifest.update({
        "schema_version": "0.16.0",
        "protocol_version": "0.16.0",
        "engine_version": "0.16.0",
        "project_id": f"PROJECT-{uuid.uuid4().hex[:12].upper()}",
        "project_kind": "imported",
        "lineage": {
            **_default_lineage(),
            "origin_project_id": source_manifest.get("project_id"),
            "fork_type": "protocol_copy_migration",
            "parent_snapshot_digest": engine.digest(source_manifest),
        },
        "creative_project_schema_version": CREATIVE_PROJECT_SCHEMA_VERSION,
        "migrated_from": {"project_id": source_manifest.get("project_id"), "protocol_version": "0.15.0"},
    })
    _write_project(target_root, target_manifest)
    reconcile_library(target_root)
    return {**preview, "confirmed": True, "project": target_manifest, "original_unchanged": True}
