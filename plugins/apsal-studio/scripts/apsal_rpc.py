#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from typing import Any

from apsal_engine import ENGINE_VERSION, ValidationError
from apsal_protocol import PROTOCOL_VERSION, handle_domain_method


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    request_id = message.get("id")
    if request_id is None:
        return None
    method = message.get("method")
    params = message.get("params") or {}
    if method == "initialize":
        result = {
            "name": "apsal-protocol-engine",
            "engine_version": ENGINE_VERSION,
            "protocol_version": PROTOCOL_VERSION,
            "transport": "stdio-jsonrpc",
        }
    elif method == "ping":
        result = {"ok": True, "engine_version": ENGINE_VERSION, "protocol_version": PROTOCOL_VERSION}
    else:
        result = handle_domain_method(str(method), params)
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def main() -> int:
    for line in sys.stdin:
        request_id = None
        try:
            message = json.loads(line)
            request_id = message.get("id") if isinstance(message, dict) else None
            if not isinstance(message, dict):
                raise ValidationError("JSON-RPC message must be an object")
            response = handle(message)
            if response is not None:
                print(json.dumps(response, ensure_ascii=False), flush=True)
        except Exception as exc:
            print(
                json.dumps(
                    {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": str(exc)}},
                    ensure_ascii=False,
                ),
                flush=True,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
