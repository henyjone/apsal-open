#!/usr/bin/env python3
"""Generate bilingual monograph reference tables from the semantic registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "plugins/apsal-studio/assets/semantics/registry.json"
OUT = ROOT / "docs/monograph/reference"


def outputs() -> dict[Path, str]:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    field_lines = [
        "# APSAL Semantic Field Reference / APSAL 语义字段参考", "",
        "> Generated from the normative semantic registry. Do not edit by hand. / 由规范语义注册表生成，请勿手工编辑。", "",
        "| Path | Role | English meaning | 中文含义 | Affects | Compile | QA |",
        "|---|---|---|---|---|---|---|",
    ]
    for path, value in registry["fields"].items():
        field_lines.append(f"| `{path}` | `{value['role']}` | {value['en']} | {value['zh']} | {'<br>'.join(f'`{x}`' for x in value['affects'])} | `{value['compile_stage']}` | {'<br>'.join(f'`{x}`' for x in value['qa'])} |")

    term_lines = [
        "# APSAL Bilingual Semantic Terms / APSAL 双语语义术语", "",
        "> Generated from the normative semantic registry. Interpretive aesthetic relations explain method; they are not machine parameters.", "",
        "## Thirteen roles / 十三类角色", "",
        "| ID | English | 中文 | Core question | 核心问题 | 中国视觉思想关联 |",
        "|---|---|---|---|---|---|",
    ]
    for role, value in registry["roles"].items():
        term_lines.append(f"| `{role}` | {value['en']} | {value['zh']} | {value['question_en']} | {value['question_zh']} | {value['aesthetic_relation_zh']} |")
    term_lines += ["", "## Controlled tags / 受控标签", "", "| Tag | English | 中文 | Valid roles |", "|---|---|---|---|"]
    for tag in registry["tags"]:
        term_lines.append(f"| `{tag['id']}` | {tag['en']} | {tag['zh']} | {', '.join(f'`{x}`' for x in tag['roles'])} |")
    return {
        OUT / "SEMANTIC_FIELD_REFERENCE.md": "\n".join(field_lines) + "\n",
        OUT / "BILINGUAL_TERMS.md": "\n".join(term_lines) + "\n",
    }


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--check", action="store_true"); args = parser.parse_args()
    errors = []
    for path, content in outputs().items():
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                errors.append(f"out of date: {path.relative_to(ROOT)}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content, encoding="utf-8")
    if errors:
        print("\n".join(errors)); return 1
    print("semantic documentation is synchronized")
    return 0


if __name__ == "__main__": raise SystemExit(main())
