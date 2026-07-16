#!/usr/bin/env python3
"""Execute one APSAL theme Skill as sequential GPT Image 2 Jobs.

The API key is read only from OPENAI_API_KEY and is never persisted.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import mimetypes
import os
import shutil
import struct
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "references"
ASSETS = ROOT / "assets" / "references"
DEFAULT_RUN = ROOT / "run"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise RuntimeError(f"{path}: expected an object")
    return value


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def png_size(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise RuntimeError("provider output is not a valid PNG header")
    return struct.unpack(">II", data[16:24])


def validate_bundle() -> tuple[dict, dict, dict, dict[str, Path]]:
    compiled = read_json(REFERENCES / "compiled.json")
    theme = read_json(REFERENCES / "theme.json")
    manifest = read_json(REFERENCES / "reference_manifest.json")
    rendering = read_json(REFERENCES / "rendering_contract.json")
    claimed = manifest.pop("reference_manifest_digest", None)
    if claimed != digest(manifest): raise RuntimeError("reference manifest digest mismatch")
    manifest["reference_manifest_digest"] = claimed
    paths = {}
    for item in manifest.get("references", []):
        path = ROOT / item["packaged_file"]
        if not path.is_file(): raise RuntimeError(f"missing reference image: {item['reference_id']}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["packaged_sha256"]:
            raise RuntimeError(f"packaged reference digest mismatch: {item['reference_id']}")
        paths[item["reference_id"]] = path
    if theme.get("output", {}).get("provider_native") is True:
        expected = {"aspect_ratio": "9:16", "size": "2160x3840", "quality": "high", "format": "png"}
        for key, value in expected.items():
            if theme["output"].get(key) != value: raise RuntimeError(f"invalid native 4K output contract: {key}")
    return compiled, theme, rendering, paths


def multipart(fields: dict[str, str], images: list[Path]) -> tuple[bytes, str]:
    boundary = "apsal-" + uuid.uuid4().hex
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    for image in images:
        mime = mimetypes.guess_type(image.name)[0] or "application/octet-stream"
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"image[]\"; filename=\"{image.name}\"\r\nContent-Type: {mime}\r\n\r\n".encode())
        body.extend(image.read_bytes()); body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def request_image(api_key: str, request: dict, images: list[Path]) -> tuple[bytes, dict]:
    endpoint = "https://api.openai.com/v1/images/edits" if images else "https://api.openai.com/v1/images/generations"
    fields = {key: str(request[key]) for key in ("model", "prompt", "size", "quality", "output_format", "n")}
    if images:
        payload, content_type = multipart(fields, images)
    else:
        payload = json.dumps(fields).encode(); content_type = "application/json"
    http_request = urllib.request.Request(endpoint, data=payload, method="POST", headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": content_type,
    })
    try:
        with urllib.request.urlopen(http_request, timeout=600) as response:
            raw = response.read(); request_id = response.headers.get("x-request-id", "not_reported")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"OpenAI Image API HTTP {exc.code}: {detail}") from exc
    value = json.loads(raw)
    try: data = base64.b64decode(value["data"][0]["b64_json"], validate=True)
    except Exception as exc: raise RuntimeError("OpenAI Image API response did not contain image data") from exc
    return data, {"request_id": request_id, "endpoint": "edits" if images else "generations", "reported": value.get("usage", "not_reported")}


def load_state(run_dir: Path, compiled: dict, theme: dict) -> dict:
    path = run_dir / "run.json"
    if path.is_file(): return read_json(path)
    jobs = [{"shot_id": shot["shot_id"], "status": "pending", "attempts": [], "output": None, "model_visual_qa": "pending", "human_visual_qa": "pending"} for shot in compiled["shots"]]
    skill_manifest = read_json(REFERENCES / "manifest.json")
    created_at = utc_now()
    return {
        "schema_version": "0.5.0", "theme_id": theme["id"], "theme_version": theme["version"],
        "theme_digest": digest(theme), "compiled_digest": compiled.get("compiled_digest", "not_reported"),
        "dna": theme.get("dna", []), "engine_version": skill_manifest.get("engine_version", "not_reported"),
        "adapter": "openai-image-api", "model": "gpt-image-2",
        "parameters": {"size": theme["output"].get("size", "not_reported"), "quality": theme["output"].get("quality", "not_reported"), "output_format": theme["output"].get("format", "not_reported"), "n": 1},
        "output_contract": theme["output"], "reference_manifest_digest": skill_manifest.get("reference_manifest_digest", "not_reported"),
        "generation_confirmed": False, "jobs": jobs, "created_at": created_at, "updated_at": created_at,
    }


def save_state(run_dir: Path, state: dict) -> None:
    jobs = state.get("jobs", [])
    if jobs and all(job.get("status") == "succeeded" and job.get("model_visual_qa") in {"pass", "passed"} for job in jobs):
        state["status"] = "completed"
    elif any(job.get("status") == "failed" for job in jobs):
        state["status"] = "partial"
    else:
        state["status"] = "generating"
    state["updated_at"] = utc_now()
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record_model_qa(run_dir: Path, state: dict, shot_id: str, status: str, finding: str) -> None:
    job = next((item for item in state["jobs"] if item["shot_id"] == shot_id), None)
    if not job or not job.get("output"): raise RuntimeError(f"no generated output to review for {shot_id}")
    job["model_visual_qa"] = status; job["model_visual_qa_finding"] = finding or "not_reported"; job["model_visual_qa_at"] = utc_now()
    if status == "fail":
        source = Path(job["output"]["path"]); rejected = run_dir / "qa" / "rejected"
        rejected.mkdir(parents=True, exist_ok=True)
        target = rejected / f"{shot_id.lower()}-attempt-{len(job['attempts'])}.png"
        if source.is_file(): shutil.move(source, target)
        job["output"] = None; job["status"] = "failed"; job["error"] = "model_visual_qa_failed"
    save_state(run_dir, state)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an APSAL set as independent GPT Image 2 Jobs")
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--shot")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm", action="store_true", help="Confirm one paid/remote generation run")
    parser.add_argument("--model-qa-shot")
    parser.add_argument("--model-qa-status", choices=("pass", "fail"))
    parser.add_argument("--finding", default="")
    args = parser.parse_args()
    compiled, theme, rendering, reference_paths = validate_bundle()
    run_dir = args.run_dir.resolve(); (run_dir / "outputs").mkdir(parents=True, exist_ok=True)
    state = load_state(run_dir, compiled, theme)
    if args.model_qa_shot:
        if not args.model_qa_status: parser.error("--model-qa-status is required")
        record_model_qa(run_dir, state, args.model_qa_shot, args.model_qa_status, args.finding)
        return 0
    if args.confirm and not args.dry_run:
        state["generation_confirmed"] = True
        state.setdefault("generation_confirmed_at", utc_now()); save_state(run_dir, state)
    if not args.dry_run and state.get("generation_confirmed") is not True:
        raise RuntimeError("explicit --confirm is required once before paid or remote generation")
    pending_review = next((job for job in state["jobs"] if job.get("status") == "succeeded" and job.get("model_visual_qa") == "pending"), None)
    if not args.dry_run and pending_review and rendering.get("medium") == "live_action_photography":
        raise RuntimeError(f"record model visual QA for {pending_review['shot_id']} before continuing")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not args.dry_run and not api_key: raise RuntimeError("OPENAI_API_KEY is required; use --dry-run to validate without provider calls")
    shots = [shot for shot in compiled["shots"] if not args.shot or shot["shot_id"] == args.shot]
    if args.shot and not shots: raise RuntimeError(f"unknown shot: {args.shot}")
    request_log = []
    for shot in shots:
        job = next(item for item in state["jobs"] if item["shot_id"] == shot["shot_id"])
        if job["status"] == "succeeded": continue
        selected = [reference_paths[item] for item in shot.get("reference_ids", [])]
        identity_anchor = run_dir / "outputs" / "shot_01.png"
        anchor_instruction = ""
        if shot["shot_id"] != "SHOT_01" and identity_anchor.is_file():
            selected.append(identity_anchor)
            anchor_instruction = " Use the SHOT_01 image only to preserve the fictional adult identity and facial continuity; do not inherit its pose, camera, background, wardrobe, action, or composition."
        prompt = shot["positive_prompt"] + anchor_instruction + " Negative constraints: " + shot["negative_prompt"]
        prompts_dir = run_dir / "prompts"; prompts_dir.mkdir(parents=True, exist_ok=True)
        (prompts_dir / f"{shot['shot_id']}.prompt.txt").write_text(prompt + "\n", encoding="utf-8")
        runtime_reference_ids = [*shot.get("reference_ids", [])]
        if identity_anchor.is_file() and shot["shot_id"] != "SHOT_01": runtime_reference_ids.append("RUNTIME_IDENTITY_ANCHOR_SHOT_01")
        request = {"model": "gpt-image-2", "prompt": prompt, "size": theme["output"].get("size", "auto"), "quality": theme["output"].get("quality", "high"), "output_format": theme["output"].get("format", "png"), "n": 1, "reference_ids": shot.get("reference_ids", []), "runtime_reference_ids": runtime_reference_ids, "identity_anchor": identity_anchor.is_file() and shot["shot_id"] != "SHOT_01"}
        request_log.append({key: value for key, value in request.items() if key != "prompt"} | {"prompt_digest": hashlib.sha256(prompt.encode()).hexdigest()})
        if args.dry_run: continue
        for attempt_number in range(1, 4):
            attempt = {"attempt": len(job["attempts"]) + 1, "request": request_log[-1]}
            try:
                data, provider = request_image(api_key, request, selected)
                width, height = png_size(data)
                if theme["output"].get("provider_native") is True and (width, height) != (2160, 3840):
                    raise RuntimeError(f"provider output dimensions {width}x{height}, expected 2160x3840")
                output = run_dir / "outputs" / f"{shot['shot_id'].lower()}.png"
                if output.exists(): raise RuntimeError(f"successful output already exists: {output.name}")
                output.write_bytes(data)
                attempt.update({"status": "succeeded", "provider": provider, "sha256": hashlib.sha256(data).hexdigest()})
                job.update({"status": "succeeded", "output": {"path": str(output), "sha256": attempt["sha256"], "width": width, "height": height}, "error": None, "model_visual_qa": "pending", "human_visual_qa": "pending"})
                job["attempts"].append(attempt); save_state(run_dir, state); break
            except Exception as exc:
                attempt.update({"status": "failed", "error": str(exc)}); job["attempts"].append(attempt); job["status"] = "failed"; job["error"] = str(exc); save_state(run_dir, state)
                if attempt_number == 3: break
                time.sleep(1)
        if job["status"] == "succeeded" and rendering.get("medium") == "live_action_photography": break
    if args.dry_run:
        (run_dir / "requests.dry-run.json").write_text(json.dumps(request_log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    save_state(run_dir, state)
    return 0 if all(job["status"] in {"succeeded", "pending"} for job in state["jobs"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
