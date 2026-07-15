#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READMES = (ROOT / "README.md", ROOT / "README.zh-CN.md")
REQUIRED = ("APSAL", "apsal-studio", "releases/latest", "APSAL_OPEN_PROTOCOL.md", "validate-package")


def main() -> int:
    errors: list[str] = []
    plugin_manifest = (ROOT / "plugins/apsal-studio/.codex-plugin/plugin.json").read_text(encoding="utf-8")
    version = re.search(r'"version"\s*:\s*"([^"]+)"', plugin_manifest).group(1)
    for readme in READMES:
        text = readme.read_text(encoding="utf-8")
        for token in REQUIRED:
            if token not in text:
                errors.append(f"{readme.name}: missing {token}")
        for target in re.findall(r'(?<!\!)\[[^]]+\]\(([^)]+)\)', text):
            if target.startswith(("http://", "https://", "#")):
                continue
            path = target.split("#", 1)[0]
            if path and not (ROOT / path).exists():
                errors.append(f"{readme.name}: broken local link {target}")
    if f'"version": "{version}"' not in plugin_manifest:
        errors.append("plugin manifest version is unreadable")
    for asset in (ROOT / "assets/brand/apsal-readme-banner.jpg", ROOT / "assets/brand/apsal-social-preview.jpg"):
        if not asset.is_file():
            errors.append(f"missing brand asset {asset.relative_to(ROOT)}")
        elif asset.stat().st_size >= 1_000_000:
            errors.append(f"brand asset exceeds 1 MB: {asset.relative_to(ROOT)}")
    if errors:
        print("\n".join(errors)); return 1
    print(f"homepage checks passed for APSAL Studio {version}")
    return 0


if __name__ == "__main__": raise SystemExit(main())
