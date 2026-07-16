#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

from apsal_engine import (
    ValidationError, commit_session_stage, dna_card, finalize_design_session,
    execute_generation_run, load_design_session, project_root_from, record_generation_result,
    record_model_visual_qa, search_registry, start_design_session, start_generation_run,
)

UI_URI = "ui://apsal/dna-cards.html"
UI_PATH = Path(__file__).resolve().parents[1] / "assets" / "ui" / "dna-cards.html"


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
        "name": "present_dna_cards", "description": "Present selectable DNA preview cards with an equivalent numbered-text fallback.",
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
        "name": "finalize_theme", "description": "Freeze the four confirmed stages into local YAML, canonical JSON, compiled targets and per-shot prompts.",
        "inputSchema": _schema({"session_id": {"type": "string"}, "project_root": {"type": "string"}}, ["session_id"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "start_generation_run", "description": "Create or resume one-Job-one-image work; generate mode requires explicit user confirmation.",
        "inputSchema": _schema({"session_id": {"type": "string"}, "project_root": {"type": "string"}, "confirmed": {"type": "boolean"}, "mode": {"enum": ["generate", "prompts", "skill"]}, "adapter": {"type": "string"}, "model": {"type": "string"}, "parameters": {"type": "object"}, "resume_run_id": {"type": "string"}}, ["session_id", "mode"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "execute_generation_run", "description": "Execute native 4K GPT Image 2 Jobs sequentially; one call defaults to one Job so Codex can visually review it before continuing.",
        "inputSchema": _schema({"run_id": {"type": "string"}, "project_root": {"type": "string"}, "max_jobs": {"type": "integer", "minimum": 1, "maximum": 24}, "max_retries": {"type": "integer", "minimum": 0, "maximum": 5}}, ["run_id"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True},
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
    return {
        "session_id": session["session_id"], "state": session["state"], "brief": session["brief"],
        "shot_count": session["shot_count"], "stages": session["stages"],
        "theme_artifact": session.get("theme_artifact"), "invalidations": session.get("invalidations", []),
        "reference_count": len(session.get("private_references", [])),
    }


def _tool_start(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("session_id"):
        session, _ = load_design_session(arguments["session_id"], _root(arguments))
        return {**_summary(session), "next_action": f"Resume at {session['state']}; present only the pending or invalidated stage."}
    if not arguments.get("brief"): raise ValidationError("brief is required when starting a new session")
    session = start_design_session(arguments["brief"], project_root=_root(arguments), theme_id=arguments.get("theme_id"), name=arguments.get("name"), shot_count=arguments.get("shot_count", 9))
    return {**_summary(session), "next_action": "Present Character DNA cards and ask the user to choose or revise the identity."}


def _records(arguments: dict[str, Any]) -> list[dict[str, Any]]:
    return search_registry(_root(arguments), arguments.get("query", ""), arguments.get("stage"), limit=arguments.get("limit", 12))


def _tool_search(arguments: dict[str, Any]) -> dict[str, Any]:
    records = _records(arguments)
    return {"count": len(records), "results": [{"scope": item["scope"], "asset": item["asset"], "preview_metadata": item["preview"]} for item in records]}


def _tool_cards(arguments: dict[str, Any]) -> dict[str, Any]:
    cards = [dna_card(item) for item in _records(arguments)]
    return {"stage": arguments["stage"], "cards": cards, "count": len(cards)}


def _tool_commit(arguments: dict[str, Any]) -> dict[str, Any]:
    session = commit_session_stage(arguments["session_id"], arguments["stage"], arguments.get("refs", []), project_root=_root(arguments), shots=arguments.get("shots"), reference_path=Path(arguments["reference_path"]) if arguments.get("reference_path") else None, reference_bindings=arguments.get("reference_bindings"), draft_assets=arguments.get("draft_assets"))
    return _summary(session)


def _tool_finalize(arguments: dict[str, Any]) -> dict[str, Any]:
    return _summary(finalize_design_session(arguments["session_id"], project_root=_root(arguments)))


def _tool_run(arguments: dict[str, Any]) -> dict[str, Any]:
    run = start_generation_run(arguments["session_id"], project_root=_root(arguments), confirmed=arguments.get("confirmed", False), mode=arguments["mode"], adapter=arguments.get("adapter", "openai-image-api"), model=arguments.get("model", "gpt-image-2"), parameters=arguments.get("parameters"), resume_run_id=arguments.get("resume_run_id"))
    return run


def _tool_execute(arguments: dict[str, Any]) -> dict[str, Any]:
    return execute_generation_run(arguments["run_id"], project_root=_root(arguments), max_jobs=arguments.get("max_jobs", 1), max_retries=arguments.get("max_retries", 2))


def _tool_model_qa(arguments: dict[str, Any]) -> dict[str, Any]:
    return record_model_visual_qa(arguments["run_id"], arguments["shot_id"], arguments["status"], project_root=_root(arguments), findings=arguments.get("findings"))


def _tool_record(arguments: dict[str, Any]) -> dict[str, Any]:
    return record_generation_result(arguments["run_id"], arguments["shot_id"], arguments["status"], project_root=_root(arguments), output_path=Path(arguments["output_path"]) if arguments.get("output_path") else None, artifact_uri=arguments.get("artifact_uri"), provider_metadata=arguments.get("provider_metadata"), error=arguments.get("error"))


HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "start_design_session": _tool_start, "search_dna": _tool_search,
    "present_dna_cards": _tool_cards, "commit_stage": _tool_commit,
    "finalize_theme": _tool_finalize, "start_generation_run": _tool_run,
    "execute_generation_run": _tool_execute, "record_model_visual_qa": _tool_model_qa,
    "record_generation_result": _tool_record,
}


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name not in HANDLERS: raise ValidationError(f"unknown MCP tool: {name}")
    value = HANDLERS[name](arguments)
    if name == "present_dna_cards":
        lines = [f"APSAL {value['stage']} DNA choices (text fallback):"]
        for number, card in enumerate(value["cards"], 1):
            ref = card["ref"]
            attributes = "; ".join(card["core_attributes"])
            lines.append(f"{number}. [{card['scope']}] {card['title']} v{card['version']} — {card['summary']} — {attributes} — {card['rights']['license']} / {card['rights']['attribution']} — {card['qa_status']} — digest {ref['content_digest']}")
        text = "\n".join(lines)
    else:
        text = json.dumps(value, ensure_ascii=False, indent=2)
    result = {"content": [{"type": "text", "text": text}], "structuredContent": value, "isError": False}
    if name == "present_dna_cards": result["_meta"] = {"openai/outputTemplate": UI_URI}
    return result


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    method, request_id = message.get("method"), message.get("id")
    if request_id is None: return None
    if method == "initialize":
        params = message.get("params", {})
        result = {"protocolVersion": params.get("protocolVersion", "2025-06-18"), "capabilities": {"tools": {}, "resources": {}}, "serverInfo": {"name": "apsal-studio", "version": "0.5.0"}}
    elif method == "tools/list": result = {"tools": TOOLS}
    elif method == "resources/list": result = {"resources": [{"uri": UI_URI, "name": "APSAL DNA Cards", "mimeType": "text/html;profile=mcp-app"}]}
    elif method == "resources/read":
        if message.get("params", {}).get("uri") != UI_URI: raise ValidationError("unknown MCP resource")
        result = {"contents": [{"uri": UI_URI, "mimeType": "text/html;profile=mcp-app", "text": UI_PATH.read_text(encoding="utf-8")}]}
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
