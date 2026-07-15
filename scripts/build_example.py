#!/usr/bin/env python3
"""Validate, but never rewrite, the preserved and semantic Quiet Window examples."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "plugins/apsal-studio/scripts/apsal_engine.py"
spec = importlib.util.spec_from_file_location("apsal_engine", ENGINE)
engine = importlib.util.module_from_spec(spec); spec.loader.exec_module(engine)


def main() -> int:
    legacy = engine.load_document(ROOT / "examples/quiet-window/theme.json")
    semantic = engine.load_document(ROOT / "examples/quiet-window/theme.apsal.yaml")
    errors = [*engine.validate_theme(legacy), *engine.validate_theme(semantic)]
    if semantic.get("parent_version") != legacy.get("version"):
        errors.append("semantic pilot parent_version does not match preserved 1.0.0")
    unchanged = ("id", "name", "dna", "output")
    for key in unchanged:
        if semantic.get(key) != legacy.get(key): errors.append(f"semantic pilot changed protected field {key}")
    for before, after in zip(legacy.get("shots", []), semantic.get("shots", [])):
        for key in ("shot_id", "title", "narrative_purpose", "framing", "action", "hands", "gaze", "composition", "continuity", "output_filename"):
            if before.get(key) != after.get(key): errors.append(f"semantic pilot changed generation intent at {before.get('shot_id')}.{key}")
    if errors:
        print("\n".join(errors)); return 1
    subprocess.run([sys.executable, str(ROOT / "scripts/migrate_quiet_window_1_1.py"), "--check"], check=True)
    print("Quiet Window 1.0.0 preserved; 1.1.0 semantics and derivatives are reproducible")
    return 0


if __name__ == "__main__": raise SystemExit(main())
