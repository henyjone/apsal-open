# Part of apsal_engine. __init__.py executes this file in the package namespace.
from __future__ import annotations

import hashlib
import html
import datetime as dt
import importlib.util
import io
import json
import os
import re
import shutil
import struct
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path
from typing import Any

def validate_protocol_package(root: Path) -> list[str]:
    """Validate the publishable APSAL Open Protocol boundary of an extracted package."""
    errors: list[str] = []
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return ["package: missing manifest.json"]
    try:
        manifest = load_json(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"package: invalid manifest.json: {exc}"]
    required = ("protocol", "protocol_version", "id", "version", "parent_version", "changed_fields", "change_summary", "license", "rights", "modules", "sequence", "jobs", "checksums", "output", "qa_status")
    for key in required:
        if key not in manifest: errors.append(f"manifest: missing {key}")
    if manifest.get("protocol") != "apsal-open": errors.append("manifest: protocol must be apsal-open")
    for key in ("protocol_version", "version"):
        if not SEMVER.fullmatch(str(manifest.get(key, ""))): errors.append(f"manifest: invalid {key}")
    if manifest.get("protocol_version") in {"0.3.0", "0.4.0"} and manifest.get("semantic_contract_version") != SEMANTIC_CONTRACT_VERSION:
        errors.append("manifest: Protocol 0.3/0.4 requires semantic_contract_version 0.3.0")
    if not manifest.get("changed_fields"): errors.append("manifest: changed_fields cannot be empty")
    licenses = manifest.get("license", {})
    if not licenses.get("code") or not licenses.get("content"): errors.append("manifest: code and content licenses are required")
    rights = manifest.get("rights", {})
    for key in ("status", "attribution", "reference_media", "ai_disclosure"):
        if key not in rights: errors.append(f"manifest rights: missing {key}")
    if rights.get("status") not in {"original_open_content", "authorized_open_content"}:
        errors.append("manifest rights: content is not approved for open redistribution")
    if rights.get("reference_media") not in {"none", "separately_licensed"}:
        errors.append("manifest rights: reference_media must be none or separately_licensed")
    modules = manifest.get("modules", {})
    if not isinstance(modules, dict): errors.append("manifest: modules must be an object"); modules = {}
    missing = set(PROTOCOL_TYPES[:11]) - set(modules)
    if missing: errors.append(f"manifest: missing module roles {sorted(missing)}")
    jobs = manifest.get("jobs", [])
    if not isinstance(jobs, list) or not 1 <= len(jobs) <= 24: errors.append("manifest: jobs must contain 1-24 paths"); jobs = []
    listed = list(modules.values()) + ([manifest.get("sequence")] if manifest.get("sequence") else []) + jobs
    checksums = manifest.get("checksums", {})
    filenames: set[str] = set()
    for rel in listed:
        if not isinstance(rel, str): errors.append("manifest: package path must be a string"); continue
        candidate = (root / rel).resolve()
        try: candidate.relative_to(root.resolve())
        except ValueError: errors.append(f"package: path escapes root: {rel}"); continue
        if not candidate.is_file(): errors.append(f"package: missing file {rel}"); continue
        actual = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if checksums.get(rel) != actual: errors.append(f"package: checksum mismatch for {rel}")
        try: value = load_json(candidate)
        except (OSError, ValueError, json.JSONDecodeError) as exc: errors.append(f"package: invalid JSON {rel}: {exc}"); continue
        kind = "job" if rel in jobs else "sequence" if rel == manifest.get("sequence") else next((k for k,v in modules.items() if v == rel), "")
        for key in ("schema_version", "namespace", "id", "type", "version", "parent_version", "changed_fields", "change_summary", "dependencies", "rights", "qa_status", "payload"):
            if key not in value: errors.append(f"{rel}: missing {key}")
        if value.get("type") != kind: errors.append(f"{rel}: type must be {kind}")
        if not SEMVER.fullmatch(str(value.get("version", ""))): errors.append(f"{rel}: invalid semantic version")
        if value.get("schema_version") == "1.1.0":
            errors.extend(validate_semantic_contract(value.get("semantics"), f"{rel}.semantics"))
        module_rights = value.get("rights", {})
        if not module_rights.get("license") or not module_rights.get("attribution"): errors.append(f"{rel}: incomplete rights")
        if value.get("qa_status") == "visual_qa_passed" and not value.get("visual_qa_evidence"): errors.append(f"{rel}: visual QA evidence required")
        if kind == "job":
            output = value.get("payload", {}).get("output", {})
            if output.get("independent_image") is not True: errors.append(f"{rel}: job must output one independent image")
            filename = output.get("filename")
            if not filename: errors.append(f"{rel}: output filename required")
            elif filename in filenames: errors.append(f"{rel}: duplicate output filename {filename}")
            filenames.add(filename)
    output = manifest.get("output", {})
    if output.get("one_job_one_image") is not True: errors.append("manifest: one_job_one_image must be true")
    if output.get("count") != len(jobs): errors.append("manifest: output count does not match jobs")
    if manifest.get("qa_status") == "visual_qa_passed" and not manifest.get("visual_qa_evidence"):
        errors.append("manifest: visual_qa_passed requires evidence")
    return errors


def _english_statements(contract: dict[str, Any], key: str) -> list[str]:
    return [item["en"] for item in contract.get(key, []) if isinstance(item, dict) and item.get("en")]


def _confirmed_element_prompt(theme: dict[str, Any]) -> str:
    decisions = theme.get("element_decisions")
    if not isinstance(decisions, dict): return ""
    parts = []
    for role in PROTOCOL_TYPES:
        if role == "quality_control": continue
        observable = decisions.get(role, {}).get("observable", [])
        if observable: parts.append(f"{role.upper().replace('_', ' ')}: {'; '.join(observable)}")
    strategy = theme.get("set_strategy")
    strategy_prefix = f"APSAL SET STRATEGY — {strategy}. " if strategy in SET_STRATEGIES else ""
    return strategy_prefix + ("APSAL CONFIRMED ELEMENT DESIGN — " + " | ".join(parts) + ". " if parts else "")


def _shot_reference_policy(theme: dict[str, Any], shot_id: str) -> tuple[list[str], str]:
    """Compile executable per-Job reference rules without exposing private paths."""
    relevant = [
        ref for ref in theme.get("references", [])
        if "*" in ref.get("applies_to", []) or shot_id in ref.get("applies_to", [])
    ]
    reference_ids = [str(ref["reference_id"]) for ref in relevant]
    rules = []
    for ref in relevant:
        ref_id = str(ref["reference_id"]); uses = set(ref.get("uses", []))
        allowed = "; ".join(str(item) for item in ref.get("allowed_uses", [])) or "only the declared reference purpose"
        forbidden = "; ".join(str(item) for item in ref.get("forbidden_uses", [])) or "none additionally declared"
        if uses == {"identity"}:
            rules.append(
                f"Reference {ref_id} is an identity-only facial anchor: preserve the same adult face geometry, facial features, age and natural skin identity, "
                "but do not inherit its pose, action, hands, gaze, face direction, expression, scene, composition, makeup, hair, wardrobe, lens, lighting or background."
            )
        else:
            rules.append(f"Reference {ref_id}: allowed — {allowed}; forbidden — {forbidden}; forbidden uses take precedence.")
    return reference_ids, (" REFERENCE INPUT POLICY — " + " ".join(rules)) if rules else ""


def _compile_image(theme: dict[str, Any], assets: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(assets, key=lambda a: CATEGORIES.index(a["type"]))
    shared = ", ".join(a["prompt_fragment"] for a in ordered)
    negative = ", ".join(a["negative_fragment"] for a in ordered)
    element_prefix = _confirmed_element_prompt(theme)
    quality_values = theme.get("element_decisions", {}).get("quality_control", {}).get("values", {})
    reject_if = quality_values.get("reject_if", []) if isinstance(quality_values, dict) else []
    if reject_if: negative = f"{', '.join(str(item) for item in reject_if)}, {negative}"
    rendering = theme.get("rendering_contract")
    medium_prefix = ""
    if rendering:
        medium_prefix = (
            "MEDIUM CONTRACT — LIVE-ACTION PHOTOGRAPHY. Create a photograph of a real adult human captured by a physical camera, "
            "with natural skin texture, plausible anatomy, optical depth of field, physically plausible light, and photographic material response. "
            "The set and props may use hand-drawn, crayon, or handmade textures; the adult subject must never become an illustration, anime figure, "
            "painting, 3D-rendered person, mannequin, doll, wax figure, or clay character. "
        )
        negative = f"{', '.join(rendering['forbid'])}, illustrated person, cartoon human, synthetic 3D human, {negative}"
    compiled = []
    for shot in theme["shots"]:
        observable = _english_statements(shot.get("intent", {}), "expected_effects")
        observable_text = f" Observable results: {'; '.join(observable)}." if observable else ""
        instruction = (
            f"Create exactly one independent finished vertical photograph for {shot['shot_id']} ({shot['title']}). "
            f"Narrative purpose: {shot['narrative_purpose']}. Scene design: {shot.get('scene_design', 'use the declared world')}. "
            f"Framing: {shot['framing']}. Action: {shot['action']}. Body orientation and weight: {shot.get('body_orientation', 'action-led and physically grounded')}. "
            f"Hands: {shot['hands']}. Gaze: {shot['gaze']}. Face orientation: {shot.get('face_orientation', 'motivated by the event')}. "
            f"Expression: {shot.get('expression', 'restrained and event-motivated')}. Composition: {shot['composition']}. "
            f"Makeup: {shot.get('makeup', 'identity-safe and declared by the look')}. Hair: {shot.get('hair', 'identity-safe and declared by the look')}. "
            f"Wardrobe: {shot.get('wardrobe', 'declared by the look')}. Lighting: {shot.get('lighting', 'physically motivated by the scene')}. "
            f"Optics: {shot.get('focal_length', 'declared by camera design')}; perspective purpose: {shot.get('perspective_intent', 'match the shot function')}. "
            f"Body state: {shot.get('pose_state', 'action-led and non-repeated')}. Set chapter: {shot.get('chapter', 'not_declared')}. "
            f"Continuity: {canonical_json(shot['continuity'])}. Output file: {shot['output_filename']}."
            f"{observable_text}"
        )
        reference_ids, reference_policy = _shot_reference_policy(theme, shot["shot_id"])
        positive = f"{medium_prefix}{element_prefix}{shared}, {instruction}{reference_policy}"
        compiled.append({"shot_id": shot["shot_id"], "title": shot["title"], "positive_prompt": positive,
                         "negative_prompt": negative, "reference_ids": reference_ids,
                         "prompt_digest": digest({"positive": positive, "negative": negative, "references": reference_ids})})
    return {"target": "image", "rendering_contract": rendering, "output_contract": theme.get("output"), "shots": compiled}


def _compile_design(theme: dict[str, Any], assets: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "target": "design",
        "semantic_contract_version": theme.get("semantic_contract_version"),
        "priority_order": [
            "identity_and_rights", "world_physics_and_continuity", "event_and_shot_function",
            "camera_light_and_color", "style_rhetoric",
        ],
        "theme_semantics": theme.get("semantics"),
        "rendering_contract": theme.get("rendering_contract"),
        "reference_summary": [{"reference_id": ref["reference_id"], "uses": ref["uses"], "applies_to": ref["applies_to"]} for ref in theme.get("references", [])],
        "output_contract": theme.get("output"),
        "protocol_mapping": theme.get("protocol_mapping"),
        "element_semantics": theme.get("element_semantics"),
        "interaction_model": theme.get("interaction_model", "legacy_four_stage"),
        "creative_layers": load_creative_layers()["layers"] if theme.get("element_decisions") else None,
        "element_decisions": theme.get("element_decisions"),
        "dna": [{"id": asset["id"], "type": asset["type"], "version": asset["version"]} for asset in assets],
        "shots": [
            {
                "shot_id": shot["shot_id"], "title": shot["title"],
                "narrative_purpose": shot["narrative_purpose"], "framing": shot["framing"],
                "action": shot["action"], "hands": shot["hands"], "gaze": shot["gaze"],
                "composition": shot["composition"], "focal_length": shot.get("focal_length"),
                "perspective_intent": shot.get("perspective_intent"), "pose_state": shot.get("pose_state"),
                "chapter": shot.get("chapter"), "continuity": shot["continuity"],
                "intent": shot.get("intent"), "field_intents": shot.get("field_intents"),
                "output_filename": shot["output_filename"],
            } for shot in theme["shots"]
        ],
    }


def _compile_qa(theme: dict[str, Any]) -> dict[str, Any]:
    global_checks = []
    for role in PROTOCOL_TYPES:
        decision = theme.get("element_decisions", {}).get(role, {})
        for position, expectation in enumerate(decision.get("qa_expectations", []), 1):
            global_checks.append({
                "id": f"element.{role}.{position:02d}", "en": expectation, "zh": expectation,
                "scope": "theme", "source": f"element_decisions.{role}",
            })
    strategy_quality = theme.get("element_decisions", {}).get("quality_control", {}).get("values", {})
    if isinstance(strategy_quality, dict):
        for group in ("variation_checks", "continuity_checks"):
            for position, expectation in enumerate(strategy_quality.get(group, []), 1):
                global_checks.append({
                    "id": f"set_strategy.{group}.{position:02d}", "en": expectation,
                    "zh": str(_zh_ui_value(expectation)), "scope": "set", "source": f"set_strategy.quality_control.values.{group}",
                })
    quality = theme.get("element_semantics", {}).get("quality_control", {})
    for item in quality.get("qa_expectations", []):
        global_checks.append({"id": item["id"], "en": item["en"], "zh": item["zh"], "scope": "theme"})
    if theme.get("rendering_contract"):
        global_checks.extend([
            {"id": "medium.live_action", "en": "The adult subject is unmistakably a real human in live-action photography, while handmade styling remains confined to set and props.", "zh": "成年人物明确呈现为真人实拍摄影；手绘和手工风格仅作用于布景与道具。", "scope": "theme"},
            {"id": "medium.skin_eyes_hands", "en": "Skin pores, both eyes when visible, and all visible hands are anatomically and photographically plausible.", "zh": "可见皮肤毛孔、双眼与手部在解剖和摄影表现上均可信。", "scope": "theme"},
            {"id": "medium.optics_light", "en": "Depth of field, light falloff, shadows and material response behave like physical photography rather than illustration or CGI.", "zh": "景深、光线衰减、阴影与材质响应符合物理摄影，而非插画或 CGI。", "scope": "theme"},
        ])
    shots = []
    for shot in theme["shots"]:
        checks: list[dict[str, Any]] = []
        seen: set[str] = set()
        sources = [("intent", shot.get("intent", {}))] + [
            (field, shot.get("field_intents", {}).get(field, {})) for field in CREATIVE_FIELDS
        ]
        for source, contract in sources:
            for item in contract.get("qa_expectations", []):
                check_id = f"{source}.{item['id']}"
                if check_id in seen: continue
                seen.add(check_id)
                checks.append({"id": check_id, "en": item["en"], "zh": item["zh"], "source": source})
        checks.extend([
            {"id": "continuity.identity", "en": "The same fictional adult identity is preserved.", "zh": "保持同一虚构成年人物身份。", "source": "continuity"},
            {"id": "variation.pose_state", "en": f"The declared body state {shot.get('pose_state', 'for this Job')} is visibly distinct and action-led.", "zh": "本镜声明的身体状态清楚可见、由行动驱动，并且不与其他镜头重复。", "source": "set_strategy"},
            {"id": "camera.focal_purpose", "en": f"The declared {shot.get('focal_length', 'focal perspective')} serves this Job's perspective purpose without artificial optical distortion.", "zh": "本镜焦段服务于已声明的观看目的，不产生无理由的人工透视变形。", "source": "set_strategy"},
            {"id": "continuity.scene_look", "en": "The scene and look match the declared chapter or continuous-event lock.", "zh": "场景与妆造符合本章锁定或连续事件锁定。", "source": "set_strategy"},
            {"id": "output.independent", "en": "The output is one independent finished image with no text or grid.", "zh": "输出为一张无文字、无拼图的独立完成图。", "source": "output"},
        ])
        if theme.get("rendering_contract"):
            checks.append({"id": "medium.real_adult_human", "en": "This Job depicts a real adult human in live-action photography, not an illustrated, painted, doll-like, wax, clay or 3D-rendered person.", "zh": "本 Job 呈现真人成年人的实拍摄影，而非插画、绘画、玩偶、蜡像、黏土或 3D 人物。", "source": "rendering_contract"})
        shots.append({"shot_id": shot["shot_id"], "title": shot["title"], "output_filename": shot["output_filename"], "checks": checks})
    return {"target": "qa", "model_visual_qa": "required_before_delivery", "human_visual_qa": "pending_until_evidence", "global_checks": global_checks, "shots": shots}


def compile_theme(
    theme: dict[str, Any], target: str = "image", assets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if target not in COMPILE_TARGETS:
        raise ValidationError(f"compile target must be one of {', '.join(COMPILE_TARGETS)}")
    errors = validate_theme(theme, assets)
    if errors: raise ValidationError("\n".join(errors))
    index = _asset_index(assets)
    selected = [index[tuple(ref[k] for k in ("namespace", "id", "type", "version"))] for ref in theme["dna"]]
    payload = _compile_image(theme, selected) if target == "image" else _compile_design(theme, selected) if target == "design" else _compile_qa(theme)
    result = {"engine_version": ENGINE_VERSION, "theme_id": theme["id"], "theme_version": theme["version"],
              "theme_digest": digest(theme), **payload}
    result["compiled_digest"] = digest(result)
    return result
