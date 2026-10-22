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

try:
    from apsal_yaml import YamlError, dumps as dump_yaml, loads as load_yaml_text
except ModuleNotFoundError:  # Supports direct importlib loading in tests and embedders.
    _yaml_spec = importlib.util.spec_from_file_location("apsal_yaml", Path(__file__).resolve().parent.parent / "apsal_yaml.py")
    if _yaml_spec is None or _yaml_spec.loader is None:
        raise
    _yaml_module = importlib.util.module_from_spec(_yaml_spec)
    sys.modules[_yaml_spec.name] = _yaml_module
    _yaml_spec.loader.exec_module(_yaml_module)
    YamlError = _yaml_module.YamlError
    dump_yaml = _yaml_module.dumps
    load_yaml_text = _yaml_module.loads

# Sibling modules execute in this module's globals. Every historical name,
# public and private, stays on apsal_engine, and a patch of apsal_engine.X
# is the binding internal calls read.
_ENGINE_PARTS = (
    "constants",
    "locale",
    "io",
    "registry",
    "theme",
    "compile",
    "session",
    "runs",
    "packages",
)
_namespace = globals()
_package_dir = Path(__file__).resolve().parent
for _part in _ENGINE_PARTS:
    _path = _package_dir / f"{_part}.py"
    exec(compile(_path.read_text(encoding="utf-8"), str(_path), "exec"), _namespace)
del _ENGINE_PARTS, _namespace, _package_dir, _part, _path
