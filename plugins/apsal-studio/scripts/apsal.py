#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from apsal_engine import ValidationError, compile_theme, load_catalog, load_json, new_theme, pack_theme, validate_protocol_package, validate_theme


def main() -> int:
    parser = argparse.ArgumentParser(prog="apsal", description="APSAL Open offline engine")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("catalog")
    new = sub.add_parser("new"); new.add_argument("--id", required=True); new.add_argument("--name", required=True); new.add_argument("--shots", type=int, default=9); new.add_argument("-o", "--output", type=Path, required=True)
    validate = sub.add_parser("validate"); validate.add_argument("theme", type=Path)
    validate_package = sub.add_parser("validate-package"); validate_package.add_argument("package", type=Path)
    compile_cmd = sub.add_parser("compile"); compile_cmd.add_argument("theme", type=Path); compile_cmd.add_argument("-o", "--output", type=Path, required=True)
    pack = sub.add_parser("pack"); pack.add_argument("theme", type=Path); pack.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "catalog":
            for item in load_catalog()["assets"]: print(f"{item['type']:12} {item['namespace']}/{item['id']}@{item['version']} — {item['change_summary']}")
        elif args.command == "new":
            args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(new_theme(args.id, args.name, args.shots), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); print(args.output)
        elif args.command == "validate":
            errors = validate_theme(load_json(args.theme));
            if errors: print("\n".join(errors)); return 1
            print("valid: static structure, lineage, rights, DNA locks, shots, and output rules")
        elif args.command == "validate-package":
            errors = validate_protocol_package(args.package)
            if errors: print("\n".join(errors)); return 1
            print("valid APSAL Open Protocol package: structure, lineage, rights, checksums, modules, jobs, and output rules")
        elif args.command == "compile":
            value = compile_theme(load_json(args.theme)); args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); print(args.output)
        elif args.command == "pack":
            path, sha = pack_theme(load_json(args.theme), args.output); print(f"{path}\nsha256 {sha}")
    except (ValidationError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}"); return 2
    return 0


if __name__ == "__main__": raise SystemExit(main())
