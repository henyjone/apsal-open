#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRERELEASE_TAG = "v0.16.0-beta.1"
CURRENT_DOCS = (
    "README.md",
    "README.zh-CN.md",
    "docs/README.md",
    "docs/USAGE_GUIDE.md",
    "docs/USAGE_GUIDE.zh-CN.md",
    "docs/UPGRADE_GUIDE_0.16.0.md",
    "docs/UPGRADE_GUIDE_0.16.0.zh-CN.md",
    "docs/releases/0.16.0.md",
    "apps/apsal-studio/README.md",
    "plugins/apsal-studio/PRIVACY.md",
    "plugins/apsal-studio/skills/apsal-theme-creator/SKILL.md",
    "plugins/apsal-studio/skills/apsal-theme-creator/references/INTERACTION.md",
    "plugins/apsal-studio/skills/apsal-theme-creator/references/FORMAT.md",
    "protocol/APSAL_OPEN_PROTOCOL.md",
    "protocol/RFC-0012-CREATIVE-PROJECT-LIBRARY-ANALYSIS-AND-SHARING.md",
)
PINNED_INSTALL_DOCS = (
    "README.md",
    "README.zh-CN.md",
    "docs/USAGE_GUIDE.md",
    "docs/USAGE_GUIDE.zh-CN.md",
    "docs/UPGRADE_GUIDE_0.16.0.md",
    "docs/UPGRADE_GUIDE_0.16.0.zh-CN.md",
    "docs/releases/0.16.0.md",
)
EXPECTED_VERSIONS = {
    "protocol": "0.4.0",
    "project_protocol": "0.16.0",
    "reference_engine": "0.16.0",
    "plugin": "0.16.0",
    "studio_frontend": "0.3.0",
    "semantic_contract": "0.3.0",
    "creative_library": "0.1.0",
    "reference_analysis": "0.1.0",
    "share": "0.1.0",
}
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def local_link_errors(relative: str, text: str) -> list[str]:
    errors: list[str] = []
    source = ROOT / relative
    for raw_target in LINK.findall(text):
        target = raw_target.strip().strip("<>").split("#", 1)[0]
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        target = target.split(" ", 1)[0]
        if not (source.parent / target).resolve().exists():
            errors.append(f"{relative}: broken local link {raw_target}")
    return errors


def main() -> int:
    errors: list[str] = []
    for relative in CURRENT_DOCS:
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing current documentation: {relative}")
            continue
        text = path.read_text(encoding="utf-8")
        errors.extend(local_link_errors(relative, text))
        if text.startswith("# APSAL Studio 0.15"):
            errors.append(f"{relative}: current document still advertises APSAL Studio 0.15")

    for relative in PINNED_INSTALL_DOCS:
        path = ROOT / relative
        if path.is_file() and PRERELEASE_TAG not in path.read_text(encoding="utf-8"):
            errors.append(f"{relative}: missing pinned prerelease tag {PRERELEASE_TAG}")

    version_map = json.loads((ROOT / "manifest/CURRENT_VERSION_MAP.json").read_text(encoding="utf-8"))
    for key, expected in EXPECTED_VERSIONS.items():
        actual = version_map.get(key, {}).get("version")
        if actual != expected:
            errors.append(f"manifest/CURRENT_VERSION_MAP.json: {key} is {actual!r}, expected {expected!r}")

    plugin = json.loads((ROOT / "plugins/apsal-studio/.codex-plugin/plugin.json").read_text(encoding="utf-8"))
    studio = json.loads((ROOT / "apps/apsal-studio/package.json").read_text(encoding="utf-8"))
    if plugin.get("version") != "0.16.0":
        errors.append("plugin manifest version must be 0.16.0")
    if studio.get("version") != "0.3.0":
        errors.append("Studio package version must be 0.3.0")

    if errors:
        print("\n".join(errors))
        return 1
    print(f"documentation checks passed for APSAL {PRERELEASE_TAG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
