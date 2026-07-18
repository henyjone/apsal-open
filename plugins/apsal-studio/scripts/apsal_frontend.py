#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def descriptor_path() -> Path:
    override = os.environ.get("APSAL_FRONTEND_DESCRIPTOR")
    return Path(override).expanduser().resolve() if override else Path.home() / ".apsal" / "frontend-link.json"


def _descriptor() -> dict[str, Any] | None:
    path = descriptor_path()
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or value.get("schema_version") != "0.1.0":
        return None
    if not value.get("base_url") or not value.get("token"):
        return None
    try:
        parsed = urllib.parse.urlsplit(str(value["base_url"]))
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        return None
    return value


def _request(path: str, *, payload: dict[str, Any] | None = None, timeout: float = 1.5) -> dict[str, Any]:
    descriptor = _descriptor()
    if descriptor is None:
        return {
            "connected": False,
            "status": "unconfigured",
            "code": "frontend_not_linked",
            "message": "APSAL Studio Codex linkage is not configured or is currently disabled.",
        }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    if data is not None and len(data) > 1024 * 1024:
        raise ValueError("APSAL Studio bridge request exceeds the 1 MiB limit")
    request = urllib.request.Request(
        str(descriptor["base_url"]).rstrip("/") + path,
        data=data,
        method="POST" if payload is not None else "GET",
        headers={
            "Authorization": f"Bearer {descriptor['token']}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            value = json.loads(exc.read().decode("utf-8"))
        except (OSError, json.JSONDecodeError):
            value = {"error": {"code": "frontend_http_error", "message": str(exc)}}
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return {
            "connected": False,
            "status": "offline",
            "code": "frontend_unreachable",
            "message": str(exc),
        }
    return value if isinstance(value, dict) else {"connected": False, "status": "invalid_response"}


def frontend_status() -> dict[str, Any]:
    return _request("/v1/status", timeout=0.4)


def frontend_call(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = _request("/v1/rpc", payload={"method": method, "params": params or {}})
    if response.get("error"):
        error = response["error"]
        raise RuntimeError(error.get("message") if isinstance(error, dict) else str(error))
    if "result" in response:
        return response["result"]
    return response


def frontend_is_connected() -> bool:
    return frontend_status().get("connected") is True


def studio_executable() -> Path | None:
    if sys.platform != "darwin":
        return None
    bundle = Path("/Applications/APSAL Studio.app")
    executable = bundle / "Contents" / "MacOS" / "APSAL Studio"
    return executable.resolve() if executable.is_file() else None


def _same_project(status: dict[str, Any], project_root: Path) -> bool:
    if status.get("connected") is not True or not status.get("project_root"):
        return False
    try:
        return Path(str(status["project_root"])).expanduser().resolve() == project_root
    except OSError:
        return False


def launch_frontend(project_root: str | Path, *, timeout: float = 8.0) -> dict[str, Any]:
    root = Path(project_root).expanduser().resolve()
    if not (root / ".apsal" / "project.json").is_file():
        return {
            "connected": False,
            "status": "project_required",
            "code": "frontend_project_required",
            "message": "Start or resume the APSAL project before opening APSAL Studio.",
            "project_root": str(root),
        }

    current = frontend_status()
    if _same_project(current, root):
        return {**current, "code": "frontend_connected", "launched": False}

    executable = studio_executable()
    if executable is None:
        return {
            "connected": False,
            "status": "not_installed",
            "code": "frontend_app_not_found",
            "message": "APSAL Studio.app is not installed in /Applications.",
            "project_root": str(root),
        }

    try:
        subprocess.Popen(
            [str(executable), "--project-root", str(root), "--codex-link"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
    except OSError as exc:
        return {
            "connected": False,
            "status": "launch_failed",
            "code": "frontend_launch_failed",
            "message": str(exc),
            "project_root": str(root),
        }

    deadline = time.monotonic() + max(0.1, timeout)
    last = current
    while time.monotonic() < deadline:
        time.sleep(0.1)
        last = frontend_status()
        if _same_project(last, root):
            return {**last, "code": "frontend_connected", "launched": True}
    return {
        **last,
        "connected": False,
        "status": "launch_timeout",
        "code": "frontend_launch_timeout",
        "message": "APSAL Studio opened but did not authenticate the requested project in time.",
        "project_root": str(root),
        "launched": True,
    }
