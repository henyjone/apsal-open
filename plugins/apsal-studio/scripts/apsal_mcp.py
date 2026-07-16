#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

from apsal_engine import (
    ValidationError, bind_import_reference, commit_element_layer, commit_session_stage, dna_card, finalize_design_session,
    get_next_codex_job, load_design_session, project_root_from, record_generation_result,
    import_apsal_package,
    record_model_visual_qa, search_registry, start_design_session, start_generation_run,
    present_element_layer, recommend_dna, recommend_layer_dna, suggest_discovery_metadata, confirm_discovery_metadata,
    resolve_dna_memory_offer, record_dna_feedback, export_dna_pack, install_dna_pack,
)

UI_URI = "ui://apsal/dna-cards.html"
UI_PATH = Path(__file__).resolve().parents[1] / "assets" / "ui" / "dna-cards.html"
ELEMENT_UI_URI = "ui://apsal/element-cards.html"
ELEMENT_UI_PATH = Path(__file__).resolve().parents[1] / "assets" / "ui" / "element-cards.html"


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


REF_SCHEMA = _schema({
    "namespace": {"type": "string"}, "id": {"type": "string"}, "type": {"type": "string"},
    "version": {"type": "string"}, "content_digest": {"type": "string"},
}, ["namespace", "id", "type", "version"])

TOOLS = [
    {
        "name": "start_design_session", "description": "Start a new APSAL design from one natural-language brief, or resume an existing local session.",
        "inputSchema": _schema({"brief": {"type": "string"}, "session_id": {"type": "string"}, "project_root": {"type": "string"}, "theme_id": {"type": "string"}, "name": {"type": "string"}, "shot_count": {"type": "integer", "minimum": 1, "maximum": 24}}, []),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "search_dna", "description": "Search project, personal and official DNA in that precedence order.",
        "inputSchema": _schema({"project_root": {"type": "string"}, "query": {"type": "string"}, "stage": {"enum": ["character", "world", "scene", "photo"]}, "limit": {"type": "integer", "minimum": 1, "maximum": 50}}, []),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "recommend_dna", "description": "Recommend stage-compatible DNA from the scene brief with controlled tags, explainable scoring, upstream compatibility, QA, rights, and private usage memory.",
        "inputSchema": _schema({"brief": {"type": "string"}, "stage": {"enum": ["character", "world", "scene", "photo"]}, "session_id": {"type": "string"}, "project_root": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 12}}, ["brief", "stage"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "_meta": {"openai/outputTemplate": UI_URI, "ui/resourceUri": UI_URI},
    },
    {
        "name": "recommend_layer_dna", "description": "Recommend explained DNA choices for every Registry type required by one of the five creative layers.",
        "inputSchema": _schema({"brief": {"type": "string"}, "layer": {"enum": ["direction", "worldbuilding", "narrative", "image", "delivery"]}, "session_id": {"type": "string"}, "project_root": {"type": "string"}, "limit_per_type": {"type": "integer", "minimum": 1, "maximum": 6}}, ["brief", "layer"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "_meta": {"openai/outputTemplate": UI_URI, "ui/resourceUri": UI_URI},
    },
    {
        "name": "present_element_layer", "description": "Present the creator-facing text cards for one of five layers, exposing every relevant APSAL protocol element, proposed value, source, observable effect and QA expectation.",
        "inputSchema": _schema({"session_id": {"type": "string"}, "layer": {"enum": ["direction", "worldbuilding", "narrative", "image", "delivery"]}, "project_root": {"type": "string"}}, ["session_id", "layer"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "_meta": {"openai/outputTemplate": ELEMENT_UI_URI, "ui/resourceUri": ELEMENT_UI_URI},
    },
    {
        "name": "suggest_dna_tags", "description": "Suggest controlled semantic tags and scene facets for a new or revised DNA before the creator confirms it.",
        "inputSchema": _schema({"asset": {"type": "object"}, "brief": {"type": "string"}, "confirmed": {"type": "boolean"}}, ["asset"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "present_dna_cards", "description": "Present compact selectable DNA text cards with an equivalent numbered-text fallback.",
        "inputSchema": _schema({"project_root": {"type": "string"}, "query": {"type": "string"}, "stage": {"enum": ["character", "world", "scene", "photo"]}, "limit": {"type": "integer", "minimum": 1, "maximum": 12}}, ["stage"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "_meta": {"openai/outputTemplate": UI_URI, "ui/resourceUri": UI_URI},
    },
    {
        "name": "commit_stage", "description": "Confirm one DNA stage and invalidate affected downstream selections when an upstream choice changes.",
        "inputSchema": _schema({"session_id": {"type": "string"}, "stage": {"enum": ["character", "world", "scene", "photo"]}, "refs": {"type": "array", "items": REF_SCHEMA}, "draft_assets": {"type": "array", "items": {"type": "object"}}, "project_root": {"type": "string"}, "shots": {"type": "array", "items": {"type": "object"}}, "reference_path": {"type": "string"}, "reference_bindings": {"type": "array", "items": {"type": "object"}}}, ["session_id", "stage"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "commit_element_layer", "description": "Confirm one of five creative layers, its complete subset of thirteen element decisions and the exact DNA references required by that layer.",
        "inputSchema": _schema({"session_id": {"type": "string"}, "layer": {"enum": ["direction", "worldbuilding", "narrative", "image", "delivery"]}, "decisions": {"type": "object"}, "refs": {"type": "array", "items": REF_SCHEMA}, "draft_assets": {"type": "array", "items": {"type": "object"}}, "project_root": {"type": "string"}, "shots": {"type": "array", "items": {"type": "object"}}, "reference_path": {"type": "string"}, "reference_bindings": {"type": "array", "items": {"type": "object"}}}, ["session_id", "layer"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "resolve_dna_memory", "description": "Resolve the post-confirmation offer to save new/revised project DNA to My DNA, keep it project-only, or decide later.",
        "inputSchema": _schema({"session_id": {"type": "string"}, "offer_id": {"type": "string"}, "action": {"enum": ["save_personal", "project_only", "not_now"]}, "project_root": {"type": "string"}}, ["session_id", "offer_id", "action"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "record_dna_feedback", "description": "Record accepted, rejected, successful, or failed DNA usage as private recommendation memory without saving the raw brief.",
        "inputSchema": _schema({"ref": REF_SCHEMA, "outcome": {"enum": ["accepted", "rejected", "successful", "failed"]}, "context": {"type": "string"}, "note": {"type": "string"}, "project_root": {"type": "string"}}, ["ref", "outcome"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "export_dna_pack", "description": "Export selected rights-cleared, tagged DNA and previews as a deterministic standalone Extension Pack for GitHub sharing.",
        "inputSchema": _schema({"refs": {"type": "array", "items": REF_SCHEMA, "minItems": 1}, "pack_id": {"type": "string"}, "namespace": {"type": "string"}, "version": {"type": "string"}, "name": {"type": "string"}, "description": {"type": "string"}, "output_dir": {"type": "string"}, "distribution": {"enum": ["auto", "private_only", "public"]}, "project_root": {"type": "string"}}, ["refs", "pack_id", "namespace", "version", "name", "description", "output_dir"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "install_dna_pack", "description": "Validate and install a local ZIP or pinned public GitHub Release DNA Pack as a read-only extension Registry layer.",
        "inputSchema": _schema({"source": {"type": "string"}, "project_root": {"type": "string"}}, ["source"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True},
    },
    {
        "name": "finalize_theme", "description": "Freeze five confirmed creative layers and all thirteen protocol elements into local YAML, canonical JSON, compiled targets and per-shot prompts; legacy four-stage sessions remain readable.",
        "inputSchema": _schema({"session_id": {"type": "string"}, "project_root": {"type": "string"}}, ["session_id"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "import_apsal_package", "description": "Open an attached legacy APSAL run directory or ZIP, recover its Prompts and references by SHA-256, remove executable provider assumptions, and prepare the first Codex image Job plus a private Prompt/Skill package.",
        "inputSchema": _schema({"source": {"type": "string"}, "project_root": {"type": "string"}}, ["source"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "bind_import_reference", "description": "Attach one reference image that a legacy APSAL package omitted, verify its declared SHA-256, and complete the Codex-ready private Prompt/Skill package when all references are restored.",
        "inputSchema": _schema({"run_id": {"type": "string"}, "reference_id": {"type": "string"}, "source": {"type": "string"}, "project_root": {"type": "string"}}, ["run_id", "reference_id", "source"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "start_generation_run", "description": "Prepare or resume one-Job-one-image work for Codex built-in image generation; no image API or API key is used.",
        "inputSchema": _schema({"session_id": {"type": "string"}, "project_root": {"type": "string"}, "confirmed": {"type": "boolean"}, "mode": {"enum": ["generate", "prompts", "skill"]}, "resume_run_id": {"type": "string"}}, ["session_id", "mode"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "get_next_codex_job", "description": "Return the next exact Prompt and reference arguments for Codex built-in image generation without making a provider or HTTP call.",
        "inputSchema": _schema({"run_id": {"type": "string"}, "project_root": {"type": "string"}}, ["run_id"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "record_model_visual_qa", "description": "Record Codex visual review separately from pending human QA; failed medium checks archive the candidate and reopen the Job for retry.",
        "inputSchema": _schema({"run_id": {"type": "string"}, "shot_id": {"type": "string"}, "status": {"enum": ["passed", "failed"]}, "findings": {"type": "array", "items": {"type": "string"}}, "project_root": {"type": "string"}}, ["run_id", "shot_id", "status"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "record_generation_result", "description": "Record one successful or failed image Job with exact local lineage and retry state.",
        "inputSchema": _schema({"run_id": {"type": "string"}, "shot_id": {"type": "string"}, "status": {"enum": ["succeeded", "failed"]}, "project_root": {"type": "string"}, "output_path": {"type": "string"}, "artifact_uri": {"type": "string"}, "provider_metadata": {"type": "object"}, "error": {"type": "string"}}, ["run_id", "shot_id", "status"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
]


def _root(arguments: dict[str, Any]) -> Path:
    return project_root_from(Path(arguments.get("project_root") or Path.cwd()))


def _summary(session: dict[str, Any]) -> dict[str, Any]:
    value = {
        "session_id": session["session_id"], "state": session["state"], "brief": session["brief"],
        "shot_count": session["shot_count"],
        "theme_artifact": session.get("theme_artifact"), "invalidations": session.get("invalidations", []),
        "reference_count": len(session.get("private_references", [])),
        "memory_offers": session.get("memory_offers", []),
    }
    if session.get("schema_version") == "0.7.0":
        value.update({"interaction_model": session["interaction_model"], "layers": session["layers"],
                      "confirmed_element_count": sum(len(item["roles"]) for item in session["layers"].values() if item["status"] == "confirmed")})
    else: value["stages"] = session["stages"]
    return value


def _tool_start(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("session_id"):
        session, _ = load_design_session(arguments["session_id"], _root(arguments))
        return {**_summary(session), "next_action": f"Resume at {session['state']}; present only the pending or invalidated layer."}
    if not arguments.get("brief"): raise ValidationError("brief is required when starting a new session")
    session = start_design_session(arguments["brief"], project_root=_root(arguments), theme_id=arguments.get("theme_id"), name=arguments.get("name"), shot_count=arguments.get("shot_count", 9))
    return {**_summary(session), "next_action": "Present Direction and Emotion element cards, then confirm the first of five creative layers."}


def _records(arguments: dict[str, Any]) -> list[dict[str, Any]]:
    return search_registry(_root(arguments), arguments.get("query", ""), arguments.get("stage"), limit=arguments.get("limit", 12))


def _tool_search(arguments: dict[str, Any]) -> dict[str, Any]:
    records = _records(arguments)
    return {"count": len(records), "results": [{"scope": item["scope"], "asset": item["asset"], "preview_metadata": item["preview"]} for item in records]}


def _tool_recommend(arguments: dict[str, Any]) -> dict[str, Any]:
    value = recommend_dna(arguments["brief"], arguments["stage"], project_root=_root(arguments), session_id=arguments.get("session_id"), limit=arguments.get("limit", 6))
    recommendations = []
    for item in value["recommendations"]:
        card = dna_card(item["record"]); card.update({key: item[key] for key in ("score", "reasons", "matched_tags", "matched_facets", "discovery")})
        recommendations.append(card)
    return {**value, "recommendations": recommendations}


def _tool_layer_recommend(arguments: dict[str, Any]) -> dict[str, Any]:
    value = recommend_layer_dna(arguments["brief"], arguments["layer"], project_root=_root(arguments), session_id=arguments.get("session_id"), limit_per_type=arguments.get("limit_per_type", 3))
    by_type = {}; cards = []
    for asset_type, items in value["by_type"].items():
        converted = []
        for item in items:
            card = dna_card(item["record"]); card.update({key: item[key] for key in ("score", "reasons", "matched_tags", "matched_facets", "discovery")})
            converted.append(card); cards.append(card)
        by_type[asset_type] = converted
    return {**value, "by_type": by_type, "cards": cards, "stage": arguments["layer"]}


def _tool_element_layer(arguments: dict[str, Any]) -> dict[str, Any]:
    return present_element_layer(arguments["session_id"], arguments["layer"], project_root=_root(arguments))


def _tool_suggest(arguments: dict[str, Any]) -> dict[str, Any]:
    value = suggest_discovery_metadata(arguments["asset"], arguments.get("brief", ""))
    return confirm_discovery_metadata(value) if arguments.get("confirmed") is True else value


def _tool_cards(arguments: dict[str, Any]) -> dict[str, Any]:
    cards = [dna_card(item) for item in _records(arguments)]
    return {"stage": arguments["stage"], "cards": cards, "count": len(cards)}


def _tool_commit(arguments: dict[str, Any]) -> dict[str, Any]:
    session = commit_session_stage(arguments["session_id"], arguments["stage"], arguments.get("refs", []), project_root=_root(arguments), shots=arguments.get("shots"), reference_path=Path(arguments["reference_path"]) if arguments.get("reference_path") else None, reference_bindings=arguments.get("reference_bindings"), draft_assets=arguments.get("draft_assets"))
    return _summary(session)


def _tool_commit_layer(arguments: dict[str, Any]) -> dict[str, Any]:
    session = commit_element_layer(arguments["session_id"], arguments["layer"], arguments.get("refs", []), project_root=_root(arguments), decisions=arguments.get("decisions"), shots=arguments.get("shots"), reference_path=Path(arguments["reference_path"]) if arguments.get("reference_path") else None, reference_bindings=arguments.get("reference_bindings"), draft_assets=arguments.get("draft_assets"))
    return _summary(session)


def _tool_memory(arguments: dict[str, Any]) -> dict[str, Any]:
    return resolve_dna_memory_offer(arguments["session_id"], arguments["offer_id"], arguments["action"], project_root=_root(arguments))


def _tool_feedback(arguments: dict[str, Any]) -> dict[str, Any]:
    return record_dna_feedback(arguments["ref"], arguments["outcome"], project_root=_root(arguments), context=arguments.get("context", ""), note=arguments.get("note", ""))


def _tool_export(arguments: dict[str, Any]) -> dict[str, Any]:
    path, sha = export_dna_pack(arguments["refs"], pack_id=arguments["pack_id"], namespace=arguments["namespace"], version=arguments["version"], name=arguments["name"], description=arguments["description"], project_root=_root(arguments), output_dir=Path(arguments["output_dir"]), distribution=arguments.get("distribution", "auto"))
    return {"path": str(path), "sha256": sha}


def _tool_install(arguments: dict[str, Any]) -> dict[str, Any]:
    return install_dna_pack(arguments["source"], project_root=_root(arguments))


def _tool_finalize(arguments: dict[str, Any]) -> dict[str, Any]:
    return _summary(finalize_design_session(arguments["session_id"], project_root=_root(arguments)))


def _tool_import_package(arguments: dict[str, Any]) -> dict[str, Any]:
    return import_apsal_package(Path(arguments["source"]), project_root=_root(arguments))


def _tool_bind_import_reference(arguments: dict[str, Any]) -> dict[str, Any]:
    return bind_import_reference(arguments["run_id"], arguments["reference_id"], Path(arguments["source"]), project_root=_root(arguments))


def _tool_run(arguments: dict[str, Any]) -> dict[str, Any]:
    run = start_generation_run(arguments["session_id"], project_root=_root(arguments), confirmed=arguments.get("confirmed", False), mode=arguments["mode"], resume_run_id=arguments.get("resume_run_id"))
    return run


def _tool_next_codex_job(arguments: dict[str, Any]) -> dict[str, Any]:
    return get_next_codex_job(arguments["run_id"], project_root=_root(arguments))


def _tool_model_qa(arguments: dict[str, Any]) -> dict[str, Any]:
    return record_model_visual_qa(arguments["run_id"], arguments["shot_id"], arguments["status"], project_root=_root(arguments), findings=arguments.get("findings"))


def _tool_record(arguments: dict[str, Any]) -> dict[str, Any]:
    return record_generation_result(arguments["run_id"], arguments["shot_id"], arguments["status"], project_root=_root(arguments), output_path=Path(arguments["output_path"]) if arguments.get("output_path") else None, artifact_uri=arguments.get("artifact_uri"), provider_metadata=arguments.get("provider_metadata"), error=arguments.get("error"))


HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "start_design_session": _tool_start, "search_dna": _tool_search,
    "recommend_dna": _tool_recommend, "recommend_layer_dna": _tool_layer_recommend,
    "present_element_layer": _tool_element_layer, "suggest_dna_tags": _tool_suggest,
    "present_dna_cards": _tool_cards, "commit_stage": _tool_commit, "commit_element_layer": _tool_commit_layer,
    "resolve_dna_memory": _tool_memory, "record_dna_feedback": _tool_feedback,
    "export_dna_pack": _tool_export, "install_dna_pack": _tool_install,
    "finalize_theme": _tool_finalize, "import_apsal_package": _tool_import_package,
    "bind_import_reference": _tool_bind_import_reference, "start_generation_run": _tool_run,
    "get_next_codex_job": _tool_next_codex_job, "record_model_visual_qa": _tool_model_qa,
    "record_generation_result": _tool_record,
}


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name not in HANDLERS: raise ValidationError(f"unknown MCP tool: {name}")
    value = HANDLERS[name](arguments)
    if name in {"present_dna_cards", "recommend_dna", "recommend_layer_dna"}:
        cards = value["cards"] if name in {"present_dna_cards", "recommend_layer_dna"} else value["recommendations"]
        lines = [f"APSAL {value['stage']} DNA choices (text fallback):"]
        for number, card in enumerate(cards, 1):
            ref = card["ref"]
            attributes = "; ".join(card["core_attributes"])
            reason = f" — Why: {'; '.join(card.get('reasons', []))}" if card.get("reasons") else ""
            lines.append(f"{number}. [{card['scope']}] {card['title']} v{card['version']} — {card['summary']} — {attributes} — {card['rights']['license']} / {card['rights']['attribution']} — {card['qa_status']} — digest {ref['content_digest']}{reason}")
        text = "\n".join(lines)
    elif name == "present_element_layer":
        lines = [f"APSAL layer: {value['title']} / {value['title_en']}"]
        for card in value["cards"]:
            lines.append(f"- {card['title']} / {card['title_en']} [{card['source']}]: {card['intent']} Values: {json.dumps(card['values'], ensure_ascii=False)} Observable: {'; '.join(card['observable'])}")
        text = "\n".join(lines)
    else:
        text = json.dumps(value, ensure_ascii=False, indent=2)
    result = {"content": [{"type": "text", "text": text}], "structuredContent": value, "isError": False}
    if name in {"present_dna_cards", "recommend_dna", "recommend_layer_dna"}: result["_meta"] = {"openai/outputTemplate": UI_URI}
    if name == "present_element_layer": result["_meta"] = {"openai/outputTemplate": ELEMENT_UI_URI}
    return result


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    method, request_id = message.get("method"), message.get("id")
    if request_id is None: return None
    if method == "initialize":
        params = message.get("params", {})
        result = {"protocolVersion": params.get("protocolVersion", "2025-06-18"), "capabilities": {"tools": {}, "resources": {}}, "serverInfo": {"name": "apsal-studio", "version": "0.9.0"}}
    elif method == "tools/list": result = {"tools": TOOLS}
    elif method == "resources/list": result = {"resources": [
        {"uri": UI_URI, "name": "APSAL DNA Text Cards", "mimeType": "text/html;profile=mcp-app"},
        {"uri": ELEMENT_UI_URI, "name": "APSAL Element Text Cards", "mimeType": "text/html;profile=mcp-app"},
    ]}
    elif method == "resources/read":
        uri = message.get("params", {}).get("uri")
        path = UI_PATH if uri == UI_URI else ELEMENT_UI_PATH if uri == ELEMENT_UI_URI else None
        if path is None: raise ValidationError("unknown MCP resource")
        result = {"contents": [{"uri": uri, "mimeType": "text/html;profile=mcp-app", "text": path.read_text(encoding="utf-8")}]}
    elif method == "tools/call":
        params = message.get("params", {}); result = call_tool(params.get("name", ""), params.get("arguments", {}))
    else: raise ValidationError(f"unsupported MCP method: {method}")
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def main() -> int:
    for line in sys.stdin:
        try:
            message = json.loads(line); response = handle(message)
            if response is not None: print(json.dumps(response, ensure_ascii=False), flush=True)
        except Exception as exc:
            request_id = message.get("id") if isinstance(locals().get("message"), dict) else None
            print(json.dumps({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": str(exc)}}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
