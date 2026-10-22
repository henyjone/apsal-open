#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import tomllib
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
SKIP_LINK_PARTS = {".git", "node_modules", "dist", ".build", "release"}
CONST_TEMPLATE = r"^(?:export\s+const\s+)?{name}\s*=\s*['\"]([^'\"]+)['\"]"


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


def assignment(name: str, text: str) -> str | None:
    found = re.search(CONST_TEMPLATE.replace("{name}", re.escape(name)), text, re.M)
    return found.group(1) if found else None


def main() -> int:
    errors: list[str] = []
    for relative in CURRENT_DOCS:
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing current documentation: {relative}")
            continue
        text = path.read_text(encoding="utf-8")
        if text.startswith("# APSAL Studio 0.15"):
            errors.append(f"{relative}: current document still advertises APSAL Studio 0.15")

    for path in sorted(ROOT.rglob("*.md")):
        if any(part in SKIP_LINK_PARTS for part in path.parts):
            continue
        relative = str(path.relative_to(ROOT))
        errors.extend(local_link_errors(relative, path.read_text(encoding="utf-8")))

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
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    engine_dir = ROOT / "plugins/apsal-studio/scripts/apsal_engine"
    if not engine_dir.is_dir():
        errors.append("plugins/apsal-studio/scripts/apsal_engine package is missing")
        engine_text = ""
    else:
        engine_text = "\n".join(path.read_text(encoding="utf-8") for path in sorted(engine_dir.glob("*.py")))
    protocol_text = (ROOT / "plugins/apsal-studio/scripts/apsal_protocol.py").read_text(encoding="utf-8")
    creative_text = (ROOT / "plugins/apsal-studio/scripts/apsal_creative.py").read_text(encoding="utf-8")
    electron_text = (ROOT / "apps/apsal-studio/electron/apsal-protocol.mjs").read_text(encoding="utf-8")
    app_text = (ROOT / "apps/apsal-studio/src/App.tsx").read_text(encoding="utf-8")
    engine_version = version_map["reference_engine"]["version"]
    protocol_version = version_map["protocol"]["version"]
    project_version = version_map["project_protocol"]["version"]
    studio_version = version_map["studio_frontend"]["version"]
    semantic_version = version_map["semantic_contract"]["version"]

    def expect(label: str, actual: str | None, expected: str) -> None:
        if actual != expected:
            errors.append(f"{label} is {actual!r}, expected {expected!r}")

    expect("plugin manifest version", plugin.get("version"), engine_version)
    expect("Studio package version", studio.get("version"), studio_version)
    expect("pyproject version", pyproject.get("project", {}).get("version"), engine_version)
    expect("ENGINE_VERSION", assignment("ENGINE_VERSION", engine_text), engine_version)
    expect("OPEN_PROTOCOL_VERSION", assignment("OPEN_PROTOCOL_VERSION", engine_text), protocol_version)
    expect("SEMANTIC_CONTRACT_VERSION", assignment("SEMANTIC_CONTRACT_VERSION", engine_text), semantic_version)
    expect("PROTOCOL_VERSION", assignment("PROTOCOL_VERSION", protocol_text), project_version)
    expect("CREATIVE_PROJECT_SCHEMA_VERSION", assignment("CREATIVE_PROJECT_SCHEMA_VERSION", creative_text), version_map["creative_library"]["version"])
    expect("ANALYSIS_SCHEMA_VERSION", assignment("ANALYSIS_SCHEMA_VERSION", creative_text), version_map["reference_analysis"]["version"])
    expect("SHARE_SCHEMA_VERSION", assignment("SHARE_SCHEMA_VERSION", creative_text), version_map["share"]["version"])
    expect("APSAL_PROTOCOL_VERSION", assignment("APSAL_PROTOCOL_VERSION", electron_text), project_version)
    expect("APSAL_ENGINE_VERSION", assignment("APSAL_ENGINE_VERSION", electron_text), engine_version)
    if version_map["project_protocol"].get("engine_version") != engine_version:
        errors.append("project_protocol.engine_version must match reference_engine.version")
    if version_map["project_protocol"].get("studio_version") != studio_version:
        errors.append("project_protocol.studio_version must match studio_frontend.version")
    if f"APSAL Studio {studio_version}" not in app_text or f"{studio_version} / {engine_version}" not in app_text:
        errors.append("Studio shell version labels must match the Studio and Engine versions")
    protocol_note = (ROOT / "plugins/apsal-studio/assets/protocol/README.md").read_text(encoding="utf-8")
    # Label and version must occur together. Studio Desktop and the Semantic
    # Contract can share a version number, so a bare "0.3.0" must not satisfy both.
    for label, version in (
        ("Open Protocol", protocol_version),
        ("Reference engine and Codex plugin", engine_version),
        ("Semantic Contract", semantic_version),
        ("APSAL Studio Desktop", studio_version),
    ):
        needle = f"{label}: `{version}`"
        if needle not in protocol_note:
            errors.append(f"plugin protocol note must contain {needle}")
    if re.search(r"\[[^\]]*\]\(\.\./", protocol_note):
        errors.append("plugin protocol note must not use a relative link; the release ZIP does not contain the repository tree")
    canonical_protocol = "https://github.com/henyjone/apsal-open/blob/main/protocol/APSAL_OPEN_PROTOCOL.md"
    if canonical_protocol not in protocol_note:
        errors.append("plugin protocol note must link to the canonical protocol with an absolute GitHub URL")
    status_anchor = "engine-016-per-job-scene-and-look"
    rfc9 = (ROOT / "protocol/RFC-0009-CONTROLLED-VARIATION-SET-STRATEGY.md").read_text(encoding="utf-8")
    if f'id="{status_anchor}"' not in rfc9 or "one distinct scene and one distinct look" not in rfc9:
        errors.append("RFC-0009 must keep its Engine 0.16 per-Job scene and look status note")
    if "three chapters of three Jobs" not in rfc9:
        errors.append("RFC-0009 must keep the 0.13 three-chapter table")
    for relative in (
        "protocol/RFC-0005-FIVE-LAYER-THIRTEEN-ELEMENT-AUTHORING.md",
        "docs/README.md",
    ):
        if f"#{status_anchor}" not in (ROOT / relative).read_text(encoding="utf-8"):
            errors.append(f"{relative}: must point at the RFC-0009 Engine 0.16 status note")

    tracked_dist = subprocess.run(
        ["git", "ls-files", "dist"], cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.strip()
    if tracked_dist:
        errors.append("tracked build output under dist/; release ZIPs are CI artifacts:\n" + tracked_dist)

    if errors:
        print("\n".join(errors))
        return 1
    print(f"documentation checks passed for APSAL {PRERELEASE_TAG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
