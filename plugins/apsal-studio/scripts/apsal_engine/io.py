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

def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def plugin_root() -> Path:
    # Package facade is scripts/apsal_engine/__init__.py. parents[2] is the
    # plugin root, the same directory the former scripts/apsal_engine.py
    # module reached with parents[1].
    return Path(__file__).resolve().parents[2]


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


def _atomic_write_bytes(path: Path, data: bytes, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _atomic_write_text(path: Path, value: str, mode: int | None = None) -> None:
    _atomic_write_bytes(path, value.encode("utf-8"), mode)


def write_canonical_json(value: dict[str, Any], path: Path) -> None:
    _atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def load_semantic_registry() -> dict[str, Any]:
    return load_json(plugin_root() / "assets" / "semantics" / "registry.json")


def load_recommendation_registry() -> dict[str, Any]:
    return load_json(plugin_root() / "assets" / "semantics" / "recommendation.json")


def load_creative_layers() -> dict[str, Any]:
    return load_json(plugin_root() / "assets" / "semantics" / "creative-layers.json")


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
    for relative in ("registry", "extensions", "usage", "vault", "vault/sha256", "cache", "library", "library/objects"):
        _mkdir_private(_inside(home, home / relative))
    workspace = project_root / ".apsal"
    _mkdir_private(workspace)
    for relative in ("drafts", "registry", "themes", "runs", "analysis", "share", "exports", "cache"):
        _mkdir_private(_inside(workspace, workspace / relative))
    project_file = workspace / "project.json"
    if not project_file.exists():
        _write_private_json({
            "schema_version": "0.7.0", "project_id": f"PROJECT-{uuid.uuid4().hex[:12].upper()}",
            "project_kind": "root", "lineage": {"parent_project_id": None, "origin_project_id": None,
            "source_asset_ids": [], "fork_type": None, "parent_snapshot_digest": None},
            "created_at": _utc_now(), "storage": "local_first",
        }, project_file)
    ignore = workspace / ".gitignore"
    if not ignore.exists():
        ignore.write_text("drafts/\nruns/\nanalysis/\nshare/\nexports/\ncache/\nvault/\nstudio/\n", encoding="utf-8")
    return {"project_root": str(project_root), "workspace": str(workspace), "apsal_home": str(home)}
