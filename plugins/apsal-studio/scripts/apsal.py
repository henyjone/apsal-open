#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from apsal_engine import (
    COMPILE_TARGETS, ValidationError, YamlError, check_sync, compile_theme,
    commit_session_stage, dump_yaml, explain_theme_path, finalize_design_session,
    init_workspace, load_catalog, load_design_session, load_document,
    load_generation_run, load_layered_registry, new_semantic_theme, new_theme,
    pack_theme, project_root_from, promote_registry_asset, registry_assets,
    search_registry, start_design_session, start_generation_run,
    validate_protocol_package, validate_theme, write_canonical_json,
)


def _root(value: Path | None) -> Path:
    return project_root_from(value or Path.cwd())


def _ref_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--id", required=True)
    parser.add_argument("--type", required=True)
    parser.add_argument("--version", required=True)


def _ref_from_args(args: argparse.Namespace) -> dict[str, str]:
    return {key: getattr(args, key) for key in ("namespace", "id", "type", "version")}


def main() -> int:
    parser = argparse.ArgumentParser(prog="apsal", description="APSAL Open offline engine")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("catalog")
    init = sub.add_parser("init"); init.add_argument("--project", type=Path, default=Path.cwd()); init.add_argument("--home", type=Path)
    new = sub.add_parser("new"); new.add_argument("--id", required=True); new.add_argument("--name", required=True); new.add_argument("--shots", type=int, default=9); new.add_argument("-o", "--output", type=Path, required=True)
    validate = sub.add_parser("validate"); validate.add_argument("theme", type=Path)
    validate_package = sub.add_parser("validate-package"); validate_package.add_argument("package", type=Path)
    normalize = sub.add_parser("normalize"); normalize.add_argument("theme", type=Path); normalize.add_argument("-o", "--output", type=Path, required=True)
    explain = sub.add_parser("explain"); explain.add_argument("theme", type=Path); explain.add_argument("--path", required=True)
    compile_cmd = sub.add_parser("compile"); compile_cmd.add_argument("theme", type=Path); compile_cmd.add_argument("--target", choices=COMPILE_TARGETS, default="image"); compile_cmd.add_argument("-o", "--output", type=Path, required=True)
    sync = sub.add_parser("check-sync"); sync.add_argument("package", type=Path)
    pack = sub.add_parser("pack"); pack.add_argument("theme", type=Path); pack.add_argument("-o", "--output", type=Path, required=True)
    registry = sub.add_parser("registry"); registry.add_argument("--project", type=Path, default=Path.cwd()); registry.add_argument("--home", type=Path)
    registry_sub = registry.add_subparsers(dest="registry_command", required=True)
    registry_sub.add_parser("list")
    search = registry_sub.add_parser("search"); search.add_argument("query", nargs="?", default=""); search.add_argument("--stage", choices=("character", "world", "scene", "photo")); search.add_argument("--limit", type=int, default=12)
    show = registry_sub.add_parser("show"); _ref_args(show)
    promote = registry_sub.add_parser("promote"); _ref_args(promote)
    session = sub.add_parser("session"); session.add_argument("--project", type=Path, default=Path.cwd()); session.add_argument("--home", type=Path)
    session_sub = session.add_subparsers(dest="session_command", required=True)
    start = session_sub.add_parser("start"); start.add_argument("brief"); start.add_argument("--id"); start.add_argument("--name"); start.add_argument("--shots", type=int, default=9)
    show_session = session_sub.add_parser("show"); show_session.add_argument("session_id")
    apply = session_sub.add_parser("apply"); apply.add_argument("session_id"); apply.add_argument("--stage", required=True, choices=("character", "world", "scene", "photo")); apply.add_argument("--selection", type=Path, required=True)
    finalize = session_sub.add_parser("finalize"); finalize.add_argument("session_id")
    run = sub.add_parser("run"); run.add_argument("--project", type=Path, default=Path.cwd()); run.add_argument("--home", type=Path); run.add_argument("--session", required=True); run.add_argument("--mode", choices=("generate", "prompts", "skill"), default="generate"); run.add_argument("--confirm", action="store_true"); run.add_argument("--adapter", default="codex-imagegen"); run.add_argument("--model", default="not_reported"); run.add_argument("--resume")
    run_show = sub.add_parser("run-show"); run_show.add_argument("run_id"); run_show.add_argument("--project", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        if args.command == "catalog":
            for item in load_catalog()["assets"]: print(f"{item['type']:12} {item['namespace']}/{item['id']}@{item['version']} — {item['change_summary']}")
        elif args.command == "init":
            print(json.dumps(init_workspace(args.project, args.home), ensure_ascii=False, indent=2))
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
        elif args.command == "registry":
            project = _root(args.project)
            if args.registry_command in {"list", "search"}:
                records = load_layered_registry(project, args.home) if args.registry_command == "list" else search_registry(project, args.query, args.stage, args.home, args.limit)
                for number, record in enumerate(records, 1):
                    asset = record["asset"]
                    print(f"{number:2}. [{record['scope']}] {asset['type']:12} {asset['namespace']}/{asset['id']}@{asset['version']} — {asset['change_summary']}")
            elif args.registry_command == "show":
                ref = _ref_from_args(args); match = next((asset for asset in registry_assets(project, args.home) if all(asset[key] == value for key, value in ref.items())), None)
                if not match: raise ValidationError("DNA reference not found")
                print(json.dumps(match, ensure_ascii=False, indent=2))
            elif args.registry_command == "promote":
                print(json.dumps(promote_registry_asset(_ref_from_args(args), project_root=project, home=args.home), ensure_ascii=False, indent=2))
        elif args.command == "session":
            project = _root(args.project)
            if args.session_command == "start":
                value = start_design_session(args.brief, project_root=project, home=args.home, theme_id=args.id, name=args.name, shot_count=args.shots)
            elif args.session_command == "show":
                value, _ = load_design_session(args.session_id, project)
            elif args.session_command == "apply":
                selection = json.loads(args.selection.read_text(encoding="utf-8"))
                value = commit_session_stage(args.session_id, args.stage, selection.get("refs", []), project_root=project, home=args.home, shots=selection.get("shots"), reference_path=Path(selection["reference_path"]) if selection.get("reference_path") else None, draft_assets=selection.get("draft_assets"))
            else:
                value = finalize_design_session(args.session_id, project_root=project, home=args.home)
            print(json.dumps(value, ensure_ascii=False, indent=2))
        elif args.command == "run":
            project = _root(args.project)
            value = start_generation_run(args.session, project_root=project, home=args.home, confirmed=args.confirm, mode=args.mode, adapter=args.adapter, model=args.model, resume_run_id=args.resume)
            print(json.dumps(value, ensure_ascii=False, indent=2))
        elif args.command == "run-show":
            print(json.dumps(load_generation_run(args.run_id, _root(args.project)), ensure_ascii=False, indent=2))
    except (ValidationError, YamlError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}"); return 2
    return 0


if __name__ == "__main__": raise SystemExit(main())
