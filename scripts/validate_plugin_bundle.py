#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "apsal-studio"
MANIFEST = PLUGIN / ".codex-plugin" / "plugin.json"


def main() -> int:
    errors: list[str] = []
    try: manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"plugin manifest unreadable: {exc}")
        return 1
    required = ("name", "version", "description", "author", "skills", "mcpServers", "interface")
    for key in required:
        if not manifest.get(key): errors.append(f"plugin manifest: missing {key}")
    if manifest.get("name") != "apsal-studio": errors.append("plugin manifest: name must be apsal-studio")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", str(manifest.get("version", ""))): errors.append("plugin manifest: invalid semantic version")
    interface = manifest.get("interface", {})
    for key in ("displayName", "shortDescription", "longDescription", "developerName", "category", "capabilities", "defaultPrompt"):
        if not interface.get(key): errors.append(f"plugin interface: missing {key}")
    prompts = interface.get("defaultPrompt", [])
    if not isinstance(prompts, list) or not 1 <= len(prompts) <= 3 or any(not isinstance(item, str) or len(item) > 128 for item in prompts):
        errors.append("plugin interface: defaultPrompt must contain 1-3 strings of at most 128 characters")
    for key in ("skills", "mcpServers"):
        value = manifest.get(key)
        if isinstance(value, str) and not (PLUGIN / value).exists(): errors.append(f"plugin manifest: missing path {value}")
    for key in ("websiteURL", "privacyPolicyURL"):
        if interface.get(key) and not interface[key].startswith("https://"): errors.append(f"plugin interface: {key} must use https")

    mcp_config = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))
    server = mcp_config.get("mcpServers", {}).get("apsal-studio", {})
    if server.get("command") != "python3" or server.get("args") != ["./scripts/apsal_mcp.py"] or server.get("cwd") != ".":
        errors.append("MCP config: expected bundled dependency-free stdio server")

    skill = PLUGIN / "skills" / "apsal-theme-creator" / "SKILL.md"
    text = skill.read_text(encoding="utf-8") if skill.is_file() else ""
    if not text.startswith("---\nname: apsal-theme-creator\n"): errors.append("Skill: invalid or missing frontmatter")
    if "references/INTERACTION.md" not in text: errors.append("Skill: missing interaction reference link")
    if not (skill.parent / "references" / "INTERACTION.md").is_file(): errors.append("Skill: missing interaction reference")

    requests = (
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "resources/list", "params": {}},
        {"jsonrpc": "2.0", "id": 4, "method": "resources/read", "params": {"uri": "ui://apsal/dna-cards.html"}},
    )
    process = subprocess.run([sys.executable, "scripts/apsal_mcp.py"], cwd=PLUGIN, input="".join(json.dumps(item) + "\n" for item in requests), text=True, capture_output=True)
    if process.returncode:
        errors.append(f"MCP smoke test failed: {process.stderr.strip()}")
    else:
        try: responses = [json.loads(line) for line in process.stdout.splitlines()]
        except json.JSONDecodeError as exc: errors.append(f"MCP smoke test returned invalid JSON: {exc}"); responses = []
        if len(responses) != 4: errors.append("MCP smoke test: expected four responses")
        elif len(responses[1].get("result", {}).get("tools", [])) != 9: errors.append("MCP smoke test: expected nine tools")
        elif "APSAL DNA Registry" not in responses[3].get("result", {}).get("contents", [{}])[0].get("text", ""):
            errors.append("MCP smoke test: DNA card UI resource missing")

    if errors:
        print("\n".join(errors))
        return 1
    print(f"APSAL Studio {manifest['version']} plugin validated: manifest, Skill, 9 MCP tools, card resource")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
