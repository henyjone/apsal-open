#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from apsal_engine import (
    COMPILE_TARGETS, ValidationError, YamlError, check_sync, compile_theme,
    dump_yaml, explain_theme_path, load_catalog, load_document, new_semantic_theme,
    new_theme, pack_theme, validate_protocol_package, validate_theme,
    write_canonical_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(prog="apsal", description="APSAL Open offline engine")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("catalog")
    new = sub.add_parser("new"); new.add_argument("--id", required=True); new.add_argument("--name", required=True); new.add_argument("--shots", type=int, default=9); new.add_argument("-o", "--output", type=Path, required=True)
    validate = sub.add_parser("validate"); validate.add_argument("theme", type=Path)
    validate_package = sub.add_parser("validate-package"); validate_package.add_argument("package", type=Path)
    normalize = sub.add_parser("normalize"); normalize.add_argument("theme", type=Path); normalize.add_argument("-o", "--output", type=Path, required=True)
    explain = sub.add_parser("explain"); explain.add_argument("theme", type=Path); explain.add_argument("--path", required=True)
    compile_cmd = sub.add_parser("compile"); compile_cmd.add_argument("theme", type=Path); compile_cmd.add_argument("--target", choices=COMPILE_TARGETS, default="image"); compile_cmd.add_argument("-o", "--output", type=Path, required=True)
    sync = sub.add_parser("check-sync"); sync.add_argument("package", type=Path)
    pack = sub.add_parser("pack"); pack.add_argument("theme", type=Path); pack.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "catalog":
            for item in load_catalog()["assets"]: print(f"{item['type']:12} {item['namespace']}/{item['id']}@{item['version']} — {item['change_summary']}")
        elif args.command == "new":
            semantic = args.output.name.lower().endswith((".yaml", ".yml"))
            value = new_semantic_theme(args.id, args.name, args.shots) if semantic else new_theme(args.id, args.name, args.shots)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(dump_yaml(value) if semantic else json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); print(args.output)
        elif args.command == "validate":
            errors = validate_theme(load_document(args.theme));
            if errors: print("\n".join(errors)); return 1
            print("valid: static structure, lineage, rights, DNA locks, shots, and output rules")
        elif args.command == "validate-package":
            errors = validate_protocol_package(args.package)
            if errors: print("\n".join(errors)); return 1
            print("valid APSAL Open Protocol package: structure, lineage, rights, checksums, modules, jobs, and output rules")
        elif args.command == "normalize":
            value = load_document(args.theme); errors = validate_theme(value)
            if errors: print("\n".join(errors)); return 1
            write_canonical_json(value, args.output); print(args.output)
        elif args.command == "explain":
            print(json.dumps(explain_theme_path(load_document(args.theme), args.path), ensure_ascii=False, indent=2))
        elif args.command == "compile":
            value = compile_theme(load_document(args.theme), args.target); write_canonical_json(value, args.output); print(args.output)
        elif args.command == "check-sync":
            errors = check_sync(args.package)
            if errors: print("\n".join(errors)); return 1
            print("in sync: authoring YAML and canonical JSON are semantically identical")
        elif args.command == "pack":
            source_yaml = args.theme.read_bytes() if args.theme.name.lower().endswith((".yaml", ".yml")) else None
            path, sha = pack_theme(load_document(args.theme), args.output, source_yaml); print(f"{path}\nsha256 {sha}")
    except (ValidationError, YamlError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}"); return 2
    return 0


if __name__ == "__main__": raise SystemExit(main())
