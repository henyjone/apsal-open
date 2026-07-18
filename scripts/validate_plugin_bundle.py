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
STUDIO_ICON = ROOT / "apps" / "apsal-studio" / "src" / "assets" / "apsal-icon.png"


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
    for key in ("displayName", "shortDescription", "longDescription", "developerName", "category", "capabilities", "defaultPrompt", "composerIcon", "logo"):
        if not interface.get(key): errors.append(f"plugin interface: missing {key}")
    prompts = interface.get("defaultPrompt", [])
    if not isinstance(prompts, list) or not 1 <= len(prompts) <= 3 or any(not isinstance(item, str) or len(item) > 128 for item in prompts):
        errors.append("plugin interface: defaultPrompt must contain 1-3 strings of at most 128 characters")
    for key in ("skills", "mcpServers"):
        value = manifest.get(key)
        if isinstance(value, str) and not (PLUGIN / value).exists(): errors.append(f"plugin manifest: missing path {value}")
    for key in ("websiteURL", "privacyPolicyURL"):
        if interface.get(key) and not interface[key].startswith("https://"): errors.append(f"plugin interface: {key} must use https")
    if interface.get("composerIcon") != interface.get("logo"):
        errors.append("plugin interface: composerIcon and logo must use the same APSAL Studio icon")
    for key in ("composerIcon", "logo"):
        value = interface.get(key)
        path = PLUGIN / value if isinstance(value, str) else None
        if path is not None and not path.is_file():
            errors.append(f"plugin interface: missing {key} path {value}")
        elif path is not None and STUDIO_ICON.is_file() and path.read_bytes() != STUDIO_ICON.read_bytes():
            errors.append(f"plugin interface: {key} must be byte-identical to the APSAL Studio icon")

    mcp_config = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))
    server = mcp_config.get("mcpServers", {}).get("apsal-studio", {})
    if server.get("command") != "python3" or server.get("args") != ["./scripts/apsal_mcp.py"] or server.get("cwd") != ".":
        errors.append("MCP config: expected bundled dependency-free stdio server")

    skill = PLUGIN / "skills" / "apsal-theme-creator" / "SKILL.md"
    text = skill.read_text(encoding="utf-8") if skill.is_file() else ""
    if not text.startswith("---\nname: apsal-theme-creator\n"): errors.append("Skill: invalid or missing frontmatter")
    if "references/INTERACTION.md" not in text: errors.append("Skill: missing interaction reference link")
    if not (skill.parent / "references" / "INTERACTION.md").is_file(): errors.append("Skill: missing interaction reference")
    if "references/LANGUAGE.md" not in text: errors.append("Skill: missing bilingual language policy link")
    if not (skill.parent / "references" / "LANGUAGE.md").is_file(): errors.append("Skill: missing bilingual language policy")

    requests = (
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "resources/list", "params": {}},
        {"jsonrpc": "2.0", "id": 4, "method": "resources/read", "params": {"uri": "ui://apsal/dna-cards.html"}},
        {"jsonrpc": "2.0", "id": 5, "method": "resources/read", "params": {"uri": "ui://apsal/element-cards.html"}},
    )
    process = subprocess.run([sys.executable, "scripts/apsal_mcp.py"], cwd=PLUGIN, input="".join(json.dumps(item) + "\n" for item in requests), text=True, capture_output=True)
    if process.returncode:
        errors.append(f"MCP smoke test failed: {process.stderr.strip()}")
    else:
        try: responses = [json.loads(line) for line in process.stdout.splitlines()]
        except json.JSONDecodeError as exc: errors.append(f"MCP smoke test returned invalid JSON: {exc}"); responses = []
        if len(responses) != 5: errors.append("MCP smoke test: expected five responses")
        elif responses[0].get("result", {}).get("serverInfo", {}).get("version") != manifest.get("version"): errors.append("MCP smoke test: server and manifest versions differ")
        elif len(responses[1].get("result", {}).get("tools", [])) != 28: errors.append("MCP smoke test: expected twenty-eight tools")
        elif not {"set_session_language", "recommend_dna", "recommend_layer_dna", "present_element_layer", "commit_element_layer", "suggest_dna_tags", "resolve_dna_memory", "record_dna_feedback", "export_dna_pack", "install_dna_pack", "start_generation_run", "get_next_codex_job", "import_apsal_package", "bind_import_reference", "apsal_frontend_status", "apsal_frontend_get_project", "apsal_frontend_preview_changes", "apsal_frontend_apply_preview", "apsal_frontend_reject_preview", "apsal_frontend_undo_operation", "apsal_frontend_focus_elements"}.issubset({tool.get("name") for tool in responses[1].get("result", {}).get("tools", [])}):
            errors.append("MCP smoke test: 0.15 authoring, frontend linkage, Prompt delivery, Codex generation, memory, or exchange tools missing")
        elif "execute_generation_run" in {tool.get("name") for tool in responses[1].get("result", {}).get("tools", [])}:
            errors.append("MCP smoke test: direct provider execution must not be exposed")
        elif len(responses[2].get("result", {}).get("resources", [])) != 2:
            errors.append("MCP smoke test: expected DNA and element-card resources")
        elif "元素资源库" not in responses[3].get("result", {}).get("contents", [{}])[0].get("text", ""):
            errors.append("MCP smoke test: DNA card UI resource missing")
        elif not all(token in responses[3].get("result", {}).get("contents", [{}])[0].get("text", "") for token in ("--celadon-strong", "card.type_label", "card.reference_label", "card.display_reasons")):
            errors.append("MCP smoke test: DNA card localization or highlight hierarchy missing")
        elif "<img" in responses[3].get("result", {}).get("contents", [{}])[0].get("text", ""):
            errors.append("MCP smoke test: DNA selection UI must be text-only")
        elif "元素设计" not in responses[4].get("result", {}).get("contents", [{}])[0].get("text", ""):
            errors.append("MCP smoke test: bilingual thirteen-element card UI resource missing")
        elif not all(token in responses[4].get("result", {}).get("contents", [{}])[0].get("text", "") for token in ("--accent-strong", "card.role_label", "card.display_recommendation", "card.display_rationale", "card.display_options", "add(optionHost,\"button\",\"option\"", "card.display_values", "card.display_qa_expectations", "output.layer_label")):
            errors.append("MCP smoke test: element card proposal content, localization, or highlight hierarchy missing")
        elif not all(token in responses[4].get("result", {}).get("contents", [{}])[0].get("text", "") for token in ("#stage-previews", "preview.data_uri", "preview.generation_input")):
            errors.append("MCP smoke test: five-stage semantic thumbnail strip missing")

    if errors:
        print("\n".join(errors))
        return 1
    print(f"APSAL Studio {manifest['version']} plugin validated: manifest, Skill, 28 MCP tools, text-only DNA cards and bilingual stage thumbnails")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
