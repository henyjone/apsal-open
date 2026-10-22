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

def new_theme(
    theme_id: str, name: str, shot_count: int = 9, *, native_4k: bool = True,
    live_action: bool = True,
) -> dict[str, Any]:
    if not SAFE_ID.fullmatch(theme_id):
        raise ValidationError("theme id must match ^[A-Z][A-Z0-9-]*$")
    if not 1 <= shot_count <= 24:
        raise ValidationError("shot count must be between 1 and 24")
    assets = load_catalog()["assets"]
    refs = [asset_ref(next(a for a in assets if a["type"] == category)) for category in CATEGORIES]
    framings = ("environment", "full", "medium", "close-up", "detail")
    shots = []
    for i in range(1, shot_count + 1):
        shots.append({
            "shot_id": f"SHOT_{i:02d}", "title": f"Scene {i}",
            "narrative_purpose": "Describe the unique story function of this frame.",
            "framing": framings[(i - 1) % len(framings)],
            "action": "Describe an observable action before the pose.",
            "hands": "Describe both hands or state that they are naturally outside frame.",
            "gaze": "Describe gaze direction and motivation.",
            "composition": "Describe subject placement, depth, foreground and background.",
            "continuity": {"identity": "locked", "wardrobe": "LOOK_A", "phase": f"PHASE_{((i - 1) * 3 // shot_count) + 1}"},
            "output_filename": f"{theme_id.lower()}_{i:02d}.{'png' if native_4k else 'jpg'}",
        })
    output = {"count": shot_count, "aspect_ratio": "2:3", "independent_images": True,
              "forbid": ["collage", "grid", "contact sheet", "text", "logo", "watermark"]}
    if native_4k: output.update(NATIVE_4K_OUTPUT)
    theme = {
        "schema_version": "1.0.0", "id": theme_id, "version": "1.0.0", "name": name,
        "parent_version": None, "changed_fields": ["initial_version"],
        "change_summary": "Initial original APSAL Open theme.", "dna": refs,
        "output": output,
        "shots": shots,
        "rights": {"license": "CC-BY-4.0", "status": "original_open_content", "attribution": "APSAL Open contributors"},
        "qa_status": "visual_qa_pending",
    }
    if live_action: theme["rendering_contract"] = live_action_rendering_contract()
    return theme


def _statement(statement_id: str, en: str, zh: str) -> dict[str, str]:
    return {"id": statement_id, "en": en, "zh": zh}


def _role_contract(role: str, role_value: dict[str, Any], tag: str) -> dict[str, Any]:
    return {
        "purpose": {"en": role_value["question_en"], "zh": role_value["question_zh"]},
        "affects": [f"{role}.output"],
        "must_preserve": ["subject.identity", "rights.provenance"],
        "may_vary": [f"{role}.declared_variables"],
        "expected_effects": [_statement(f"{role}.coherent", f"The {role} decision is observable and coherent.", f"{role_value['zh']}决定可观察且保持连贯。")],
        "qa_expectations": [_statement(f"{role}.intent", f"The output matches the declared {role} purpose.", f"输出符合已声明的{role_value['zh']}目的。")],
        "semantic_tags": [tag],
        "priority": role_value["priority"],
    }


def _generic_field_intent(field_name: str, field: dict[str, Any]) -> dict[str, Any]:
    return {
        "purpose": {"en": field["en"], "zh": field["zh"]},
        "affects": field["affects"],
        "expected_effects": [_statement(f"{field_name}.observable", f"The declared {field_name} is visually observable.", f"已声明的{field_name}在画面中可观察。")],
        "qa_expectations": [
            _statement(item, item.replace("_", " ").capitalize() + ".", item.replace("_", " ") + "。")
            for item in field["qa"]
        ],
    }


def new_semantic_theme(
    theme_id: str, name: str, shot_count: int = 9, *, native_4k: bool = True,
    live_action: bool = True,
) -> dict[str, Any]:
    """Create a Protocol 0.3 authoring theme with complete generic semantics."""
    theme = new_theme(theme_id, name, shot_count, native_4k=native_4k, live_action=live_action)
    registry = load_semantic_registry()
    theme["schema_version"] = "1.1.0"
    theme["semantic_contract_version"] = SEMANTIC_CONTRACT_VERSION
    theme["protocol_mapping"] = registry["dna_to_protocol"]
    theme["semantics"] = {
        "purpose": {"en": "Define a coherent photographic world before selecting its viewpoints.", "zh": "在选择摄影视点之前，定义一个连贯的摄影世界。"},
        "affects": ["element_semantics", "shots", "output"],
        "must_preserve": ["subject.identity", "world.geometry", "rights.provenance"],
        "may_vary": ["job.viewpoint", "event.action", "camera.framing"],
        "expected_effects": [_statement("theme.world_coherence", "All Jobs remain inferably inside one world.", "所有 Job 均可被推断为处于同一世界。")],
        "qa_expectations": [_statement("theme.distinct_jobs", "Every Job has a distinct narrative function and one output.", "每个 Job 都有不同叙事职能并只输出一张图。")],
        "semantic_tags": ["sequence.function.progression", "job.output.independent"],
        "priority": 95,
    }
    tags_by_role = {
        role: next(item["id"] for item in registry["tags"] if role in item["roles"])
        for role in PROTOCOL_TYPES
    }
    theme["element_semantics"] = {
        role: _role_contract(role, registry["roles"][role], tags_by_role[role]) for role in PROTOCOL_TYPES
    }
    for shot in theme["shots"]:
        shot["intent"] = {
            "purpose": {"en": shot["narrative_purpose"], "zh": "定义本镜独立且不可替代的叙事职能。"},
            "affects": ["event", "camera", "sequence", "job"],
            "must_preserve": ["subject.identity", "world.geometry", "look.wardrobe"],
            "may_vary": ["camera.framing", "event.action", "emotion.external_expression"],
            "expected_effects": [_statement("shot.distinct", "This frame adds information not duplicated by another Job.", "本镜增加其他 Job 未重复的信息。")],
            "qa_expectations": [_statement("shot.intent", "The narrative purpose is visually legible without explanatory text.", "无需解释文字即可看出本镜叙事目的。")],
            "semantic_tags": ["job.output.independent", "camera.viewpoint.single"],
            "priority": 82,
        }
        shot["field_intents"] = {
            field_name: _generic_field_intent(field_name, registry["fields"][f"shots.*.{field_name}"])
            for field_name in CREATIVE_FIELDS
        }
    return theme


_NINE_SHOT_VARIATION_PLAN = (
    {
        "title": "Chapter One — Arrival", "narrative_purpose": "Establish arrival and the governing spatial relation.",
        "scene_design": "A quiet threshold with layered foreground screens, a visible entry path, and distant spatial evidence.",
        "framing": "environmental portrait", "focal_length": "24 mm environmental wide", "perspective_intent": "environment establishes spatial relation",
        "action": "The protagonist enters the threshold and pauses to read the space.",
        "hands": "One hand settles a garment edge while the other remains naturally relaxed and fully legible.",
        "gaze": "The gaze searches beyond the near foreground toward an upper-left spatial clue.",
        "face_orientation": "Three-quarter face turned left, chin level, with both eyes naturally legible.",
        "body_orientation": "Weight on the rear foot, torso opened diagonally toward the threshold.",
        "expression": "Reserved curiosity before recognition.",
        "composition": "Use foreground depth, the threshold, and a smaller human figure to establish the world without diminishing presence.",
        "makeup": "Sheer skin, softly defined brows, and a muted natural lip.",
        "hair": "Loose natural hair with one side tucked behind the ear.",
        "wardrobe": "A fluid light-toned base layer with a long clean vertical silhouette.",
        "lighting": "Broad dawn window light from camera left with soft ambient fill and long gentle falloff.",
        "pose_state": "arrival_observation",
    },
    {
        "title": "Chapter One — Crossing", "narrative_purpose": "Reveal full-body movement and the first active choice.",
        "scene_design": "A long passage crossed by repeating structural lines and a clear lateral travel path.",
        "framing": "full-length action portrait", "focal_length": "28 mm full-action perspective", "perspective_intent": "full frame makes body action legible",
        "action": "The protagonist crosses the frame and turns through the movement rather than stopping to pose.",
        "hands": "Both hands have different natural functions that follow balance and garment movement.",
        "gaze": "The gaze leads toward the right-hand direction of travel.",
        "face_orientation": "Clean right profile carried by the turn, chin slightly forward.",
        "body_orientation": "Mid-stride lateral profile with the leading shoulder and opposite hip counter-rotated.",
        "expression": "Purposeful concentration during movement.",
        "composition": "Keep the complete body, floor contact, travel direction, and usable negative space inside the vertical frame.",
        "makeup": "Brushed brows, restrained liner, and a cool rose lip.",
        "hair": "Low moving ponytail with controlled flyaways.",
        "wardrobe": "A structured travel look with cropped outer layer and fluid lower movement.",
        "lighting": "Narrow reflected raking light from camera right that articulates stride and fabric edges.",
        "pose_state": "crossing_turn",
    },
    {
        "title": "Chapter One — Contact", "narrative_purpose": "Show the first observable contact with the world.",
        "scene_design": "A tactile alcove centered on one meaningful surface and a small object with visible material response.",
        "framing": "medium-full contact portrait", "focal_length": "35 mm contact perspective", "perspective_intent": "near-normal wide coverage connects face, hand and material",
        "action": "The protagonist makes first contact with a meaningful surface or object and registers its response.",
        "hands": "The active hand touches one declared object; the supporting hand remains anatomically clear and non-duplicated.",
        "gaze": "The gaze drops to the active hand and contact point.",
        "face_orientation": "Downward three-quarter face turned right toward the active hand.",
        "body_orientation": "Forward hinge from the hips with weight settled evenly and shoulders relaxed.",
        "expression": "Quiet tactile surprise.",
        "composition": "Balance face, active hand, object, and enough background evidence to complete the first chapter.",
        "makeup": "Soft taupe eye, natural lashes, and a warm muted lip.",
        "hair": "Half-up hair exposing the cheek and working-hand sightline.",
        "wardrobe": "Textured linen layers with visible cuff and tactile weave.",
        "lighting": "Soft overhead skylight with a low frontal bounce that preserves skin and hand detail.",
        "pose_state": "first_contact",
    },
    {
        "title": "Chapter Two — Transition", "narrative_purpose": "Make the transition visible through movement, space, and styling.",
        "scene_design": "A luminous doorway between darker and brighter zones with a visible change of spatial direction.",
        "framing": "full-length transition portrait", "focal_length": "40 mm transition perspective", "perspective_intent": "moderate wide perspective keeps the threshold and full body readable",
        "action": "The protagonist crosses into a new scene with a changed direction of travel.",
        "hands": "One hand interacts with the boundary while the other supports the body's change of direction.",
        "gaze": "The gaze enters the brighter new space before the body fully follows.",
        "face_orientation": "Over-shoulder face turned left, eyes entering the brighter zone first.",
        "body_orientation": "Torso twisting across the threshold with weight transferring to the front foot.",
        "expression": "Alert anticipation at the boundary.",
        "composition": "Use the boundary line and full figure to distinguish the new scene while preserving the theme grammar.",
        "makeup": "Graphic but thin liner, softly sculpted cheek, and a neutral satin lip.",
        "hair": "Swept-back hair with a clean exposed neckline.",
        "wardrobe": "A layered transitional coat over a narrow tonal silhouette.",
        "lighting": "Motivated doorway backlight with a restrained rim and darker ambient foreground exposure.",
        "pose_state": "threshold_transition",
    },
    {
        "title": "Chapter Two — Development", "narrative_purpose": "Develop the event through a deliberate prop or material interaction.",
        "scene_design": "A focused work surface with one narrative prop, its prior state, and room for a visible changed state.",
        "framing": "relational medium portrait", "focal_length": "50 mm natural medium perspective", "perspective_intent": "medium frame balances subject and world",
        "action": "The protagonist changes the state of one narrative prop and leaves a visible consequence.",
        "hands": "Both hands participate in one physically plausible task without hiding ownership or object state.",
        "gaze": "The gaze moves between the prop and its visible consequence, never toward the camera.",
        "face_orientation": "Three-quarter face turned right and lowered toward the changed prop state.",
        "body_orientation": "Square to the work surface with one shoulder subtly advanced.",
        "expression": "Focused intent while completing a precise task.",
        "composition": "Create a readable triangle among face, hands, and the changed prop state.",
        "makeup": "Satin eyelid, defined upper lashes, and a deeper terracotta lip.",
        "hair": "Compact low knot with a precise side part.",
        "wardrobe": "A tailored work look with controlled sleeves and one functional fastening detail.",
        "lighting": "Warm practical task light from below eye level balanced by a cooler room fill.",
        "pose_state": "prop_interaction",
    },
    {
        "title": "Chapter Two — Interior Response", "narrative_purpose": "Translate the consequence into a restrained internal response.",
        "scene_design": "A quiet recess separated from the prior work surface by depth, shadow, and one residual continuity cue.",
        "framing": "tight emotional medium portrait", "focal_length": "65 mm intimate medium perspective", "perspective_intent": "compressed medium distance reads breath, shoulders and restrained emotion",
        "action": "The body settles after the action while breath, shoulders, and facial attention reveal the consequence.",
        "hands": "Hands remain naturally placed at the edge of frame or explicitly outside it; no unexplained gesture is introduced.",
        "gaze": "The gaze shifts off-frame lower left toward an implication beyond the prior prop.",
        "face_orientation": "Near-frontal face with chin lowered and eyes moving off-frame lower left.",
        "body_orientation": "Torso almost frontal with shoulders dropping after the completed action.",
        "expression": "Contained realization held in breath and eyelids.",
        "composition": "Use optical separation and controlled negative space to make the internal turn visible.",
        "makeup": "Barely powdered skin, softened eye definition, and a desaturated nude lip.",
        "hair": "Soft side part with one loose strand crossing the temple.",
        "wardrobe": "A quiet monochrome knit with softened shoulder structure.",
        "lighting": "Cool diffused side light through a translucent surface with low-contrast shadow detail.",
        "pose_state": "contained_reaction",
    },
    {
        "title": "Chapter Three — Changed Relation", "narrative_purpose": "Show a visibly changed relation between protagonist and world.",
        "scene_design": "An open final chamber with one distant consequence marker and a new stable axis between person and world.",
        "framing": "compressed environmental portrait", "focal_length": "85 mm compressed environmental perspective", "perspective_intent": "compressed layers make the changed person-world relation explicit",
        "action": "The protagonist enters the final relation with a changed stance and a clear new decision.",
        "hands": "The hands settle into an asymmetrical but purposeful state that supports the changed stance.",
        "gaze": "The gaze holds on an upper-right consequence marker established by the event.",
        "face_orientation": "Left profile with chin slightly raised toward the distant consequence.",
        "body_orientation": "Stable contrapposto facing away from camera while the head returns into profile.",
        "expression": "Resolved decision without overt performance.",
        "composition": "Place the figure and the final spatial clue in a stable relation that differs from the opening.",
        "makeup": "Defined lip, controlled cheek plane, and restrained luminous eyelid.",
        "hair": "Braided crown with a clean sculptural contour.",
        "wardrobe": "A sculptural formal silhouette with one asymmetric architectural line.",
        "lighting": "Low-angle reflected glow from the scene marker with a subtle opposite-edge separation.",
        "pose_state": "changed_stance",
    },
    {
        "title": "Chapter Three — Evidence", "narrative_purpose": "Prove the tactile consequence through one necessary detail.",
        "scene_design": "A close material field where hand, surface, and the transformed detail are the dominant evidence.",
        "framing": "hand and material detail", "focal_length": "105 mm hand or prop detail", "perspective_intent": "detail frame proves touch, material and consequence",
        "action": "A precise hand action reveals texture, ownership, and the final changed state.",
        "hands": "Only anatomically necessary fingers and the declared object are visible; contact and pressure are physically credible.",
        "gaze": "Attention drops vertically toward the precise hand action in the foreground.",
        "face_orientation": "Soft half-profile face remains defocused in the upper background, angled down toward the hand.",
        "body_orientation": "Only the necessary shoulder-to-hand diagonal enters frame, with no decorative pose.",
        "expression": "Quiet precision implied by the softened background face.",
        "composition": "Isolate hand, material, and consequence with shallow optical depth while retaining one identity cue.",
        "makeup": "Controlled polished nails and a faint metallic eye accent visible only in the defocused face cue.",
        "hair": "Smooth tucked hair that does not compete with the hand detail.",
        "wardrobe": "A precise sleeve and one restrained jewelry detail framing the hand action.",
        "lighting": "Tight specular detail light across texture with flagged spill and a soft facial background glow.",
        "pose_state": "tactile_detail",
    },
    {
        "title": "Chapter Three — Resolution", "narrative_purpose": "Resolve the emotional arc with a final changed human presence.",
        "scene_design": "A simplified closing field with calm negative space and one distant trace of the completed journey.",
        "framing": "resolved close portrait", "focal_length": "135 mm resolved close portrait", "perspective_intent": "long portrait compression isolates the final emotional state",
        "action": "The protagonist holds a calm final state shaped by what has happened, without returning to the opening pose.",
        "hands": "Visible hands rest in a simple resolved position; otherwise they remain naturally outside frame.",
        "gaze": "The final gaze rests just beyond the lens and repeats no earlier direction.",
        "face_orientation": "Almost frontal face turned a few degrees right, eyes resting just beyond the lens.",
        "body_orientation": "Upright frontal stillness with balanced shoulders and released weight.",
        "expression": "Calm release with a trace of the preceding experience.",
        "composition": "Use a stable close portrait, preserved optical realism, and final negative space to close the set.",
        "makeup": "Luminous skin, finely defined lashes, and a clear ceremonial rose lip.",
        "hair": "Polished high knot with a minimal clean silhouette.",
        "wardrobe": "A resolved ceremonial look with a quiet neckline and controlled reflective detail.",
        "lighting": "Large feathered frontal beauty light with gentle wrap, a low fill ratio, and a clean eye light.",
        "pose_state": "resolved_presence",
    },
)


def infer_set_strategy(brief: str) -> str:
    """Choose a new-session default while preserving an explicit continuity request."""
    if re.search(r"(?:连续叙事|同一场景|同一妆造|保持场景|保持造型|一镜到底|连续事件|continuous narrative|single scene|same look)", brief, re.I):
        return "continuous_narrative"
    return DEFAULT_SET_STRATEGY


def _strategy_counts(strategy: str, shot_count: int) -> tuple[int, int]:
    if strategy == "continuous_narrative": return 1, 1
    return shot_count, shot_count


def apply_set_strategy(theme: dict[str, Any], strategy: str) -> dict[str, Any]:
    """Materialize one controlled-variation policy into per-shot scene, look, optics and body-state plans."""
    if strategy not in SET_STRATEGIES: raise ValidationError(f"set strategy must be one of {list(SET_STRATEGIES)}")
    shots = theme.get("shots", []); shot_count = len(shots)
    if not shots: raise ValidationError("set strategy requires at least one shot")
    theme["set_strategy"] = strategy
    scene_count, look_count = _strategy_counts(strategy, shot_count)
    for index, shot in enumerate(shots):
        template = _NINE_SHOT_VARIATION_PLAN[index] if index < len(_NINE_SHOT_VARIATION_PLAN) else {
            "title": f"Extended Viewpoint {index + 1}",
            "narrative_purpose": f"Add a unique extended viewpoint and event consequence for Job {index + 1}.",
            "framing": ("environmental portrait", "full-length action portrait", "natural medium portrait", "emotional close portrait", "hand and material detail")[index % 5],
            "focal_length": ("28 mm environmental wide", "35 mm full-action perspective", "50 mm natural medium perspective", "85 mm emotional close portrait", "105 mm hand or prop detail")[index % 5],
            "perspective_intent": ("environment establishes spatial relation", "full frame makes body action legible", "medium frame balances subject and world", "close frame reveals restrained emotion", "detail frame proves touch, material and consequence")[index % 5],
            "action": f"Perform one observable, non-repeated action state for extended Job {index + 1}.",
            "hands": "Declare both hands according to the action and keep anatomy physically plausible.",
            "gaze": "Use a motivated gaze direction not duplicated by the preceding Job.",
            "face_orientation": f"Use one face orientation unique to extended Job {index + 1}.",
            "body_orientation": f"Use one action-led body orientation unique to extended Job {index + 1}.",
            "expression": f"Use one restrained expression state unique to extended Job {index + 1}.",
            "composition": "Create one distinct vertical composition while preserving the established world grammar.",
            "scene_design": f"Create one distinct scene design for extended Job {index + 1} inside the theme grammar.",
            "makeup": f"Use one identity-safe makeup design unique to extended Job {index + 1}.",
            "hair": f"Use one identity-safe hairstyle unique to extended Job {index + 1}.",
            "wardrobe": f"Use one coordinated wardrobe design unique to extended Job {index + 1}.",
            "lighting": f"Use one physically motivated lighting design unique to extended Job {index + 1}.",
            "pose_state": f"extended_action_state_{index + 1}",
        }
        if strategy == "continuous_narrative":
            scene_index = look_index = 0
            act_index = min((index * 3) // shot_count, 2)
            title = template["title"].replace("Chapter One", "Continuous Act One").replace("Chapter Two", "Continuous Act Two").replace("Chapter Three", "Continuous Act Three")
            narrative_purpose = template["narrative_purpose"].replace("first sub-scene", "continuous scene").replace("second sub-scene", "continuous scene").replace("final sub-scene", "continuous scene").replace("chapter boundary", "event transition")
        else:
            scene_index = index
            look_index = index
            act_index = min((index * 3) // shot_count, 2)
            title = template["title"]
            narrative_purpose = template["narrative_purpose"]
        scene_id = f"SCENE_{chr(65 + scene_index)}"; look_id = f"LOOK_{chr(65 + look_index)}"
        shot.update({
            "title": title, "narrative_purpose": narrative_purpose, "framing": template["framing"],
            "action": template["action"], "hands": template["hands"], "gaze": template["gaze"],
            "composition": template["composition"], "focal_length": template["focal_length"],
            "perspective_intent": template["perspective_intent"], "pose_state": template["pose_state"],
            "scene_design": template["scene_design"] if strategy == "chaptered_variation" else "One continuous core scene; preserve geometry while changing only occupied zone and event state.",
            "face_orientation": template["face_orientation"], "body_orientation": template["body_orientation"],
            "expression": template["expression"],
            "makeup": template["makeup"] if strategy == "chaptered_variation" else "One continuous identity-safe makeup state across the event.",
            "hair": template["hair"] if strategy == "chaptered_variation" else "One continuous hairstyle across the event.",
            "wardrobe": template["wardrobe"] if strategy == "chaptered_variation" else "One continuous wardrobe state across the event.",
            "lighting": template["lighting"],
            "chapter": f"ACT_{act_index + 1}" if strategy == "continuous_narrative" else f"CHAPTER_{chr(65 + act_index)}",
            "continuity": {
                "identity": "locked", "scene": scene_id, "wardrobe": look_id,
                "phase": f"PHASE_{act_index + 1}", "set_strategy": strategy,
            },
        })
        if isinstance(shot.get("intent"), dict):
            shot["intent"]["purpose"] = {"en": narrative_purpose, "zh": "定义本镜在套片章节或连续事件中的独立叙事职能。"}
            shot["intent"]["must_preserve"] = ["subject.identity", "world.physics", f"world.{scene_id}", f"look.{look_id}"]
            shot["intent"]["may_vary"] = ["camera.framing", "camera.focal_length", "event.action", "subject.pose_state"]
    return theme


def _mood_profile(brief: str) -> dict[str, Any]:
    registry = load_creative_layers(); folded = brief.casefold()
    profiles = registry["mood_profiles"]
    matches: list[tuple[int, int, dict[str, Any]]] = []
    for order, profile in enumerate(profiles):
        positions = [folded.find(term.casefold()) for term in profile["terms"] if folded.find(term.casefold()) >= 0]
        if positions: matches.append((min(positions), order, profile))
    matches.sort(key=lambda item: (item[0], item[1]))
    primary = matches[0][2] if matches else profiles[-1]
    result = json.loads(json.dumps(primary))
    secondary = []
    for _, _, profile in matches[1:]:
        if profile["id"] != primary["id"] and profile["id"] not in secondary: secondary.append(profile["id"])
    result["secondary_tones"] = secondary
    matched_valences = {item[2]["valence"] for item in matches}
    if "positive" in matched_valences and "negative" in matched_valences: result["valence"] = "mixed"
    return result


def _decision(
    role: str, layer: str, intent: str, values: dict[str, Any], observable: list[str],
    must_preserve: list[str], qa_expectations: list[str], *, source: str = "proposed_from_brief",
    basis: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "role": role, "layer": layer, "status": "proposed", "source": source,
        "intent": intent, "values": values, "observable": observable,
        "must_preserve": must_preserve, "qa_expectations": qa_expectations,
        "basis": basis or ["natural_language_brief"], "dna_refs": [],
    }


def propose_element_decisions(brief: str, theme: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Create a deterministic, editable proposal covering all thirteen protocol roles."""
    strategy = theme.get("set_strategy") or infer_set_strategy(brief)
    if strategy not in SET_STRATEGIES: raise ValidationError(f"set strategy must be one of {list(SET_STRATEGIES)}")
    if theme.get("set_strategy") != strategy: apply_set_strategy(theme, strategy)
    mood = _mood_profile(brief); output = theme["output"]; count = len(theme["shots"])
    arc = dict(mood["arc"])
    scene_count, look_count = _strategy_counts(strategy, count)
    scene_chapters = [str(shot["continuity"]["scene"]) for shot in theme["shots"]] if strategy == "chaptered_variation" else ["single_core_scene"]
    look_chapters = [str(shot["continuity"]["wardrobe"]) for shot in theme["shots"]] if strategy == "chaptered_variation" else ["look_a_continuous"]
    pose_states = [str(shot["pose_state"]) for shot in theme["shots"]]
    focal_plan = [str(shot["focal_length"]) for shot in theme["shots"]]
    perspective_plan = [str(shot["perspective_intent"]) for shot in theme["shots"]]
    scene_plan = [str(shot["scene_design"]) for shot in theme["shots"]]
    makeup_plan = [str(shot["makeup"]) for shot in theme["shots"]]
    hair_plan = [str(shot["hair"]) for shot in theme["shots"]]
    wardrobe_plan = [str(shot["wardrobe"]) for shot in theme["shots"]]
    face_orientation_plan = [str(shot["face_orientation"]) for shot in theme["shots"]]
    body_orientation_plan = [str(shot["body_orientation"]) for shot in theme["shots"]]
    composition_plan = [str(shot["composition"]) for shot in theme["shots"]]
    lighting_plan = [str(shot["lighting"]) for shot in theme["shots"]]
    explicit_male = bool(re.search(r"(?:男主角|男性|男士|男人|男模|\bmale\b|\bman\b)", brief, re.I))
    protagonist = "one poised fictional East Asian adult male protagonist" if explicit_male else "one poised fictional East Asian adult female protagonist"
    return {
        "content": _decision("content", "direction", f"Turn the creator brief into one concrete photographic proposition: {brief}", {
            "theme_statement": brief, "subject_matter": "one coherent live-action photographic world",
            "central_tension": "the visible situation must reveal a change rather than a decorative pose",
            "set_strategy": strategy,
        }, [f"Every frame remains recognizably about: {brief}", "Objects and actions support one central proposition."],
            ["creator intent", "rights provenance"], ["The theme remains legible without explanatory text."]),
        "emotion": _decision("emotion", "direction", "Translate the overall emotional direction into observable behavior and a nine-shot arc.", {
            "primary_tone": mood["id"], "secondary_tones": mood["secondary_tones"], "undertone": mood["undertone"], "valence": mood["valence"],
            "arousal": mood["arousal"], "expression": mood["expression"], "energy": mood["energy"],
            "tension": mood["tension"], "arc": arc,
        }, [f"Primary tone: {mood['id']}; undertone: {mood['undertone']}.",
            f"Emotional progression: {arc['start']} → {arc['turn']} → {arc['end']}.",
            f"Expression is {mood['expression']}; energy is {mood['energy']}; tension is {mood['tension']}."],
            ["subject identity", "emotion must be shown through gaze, breath, gesture and distance"],
            ["The declared tone is observable without relying on a facial-expression label.", "The final frame completes the declared emotional arc."]),
        "subject": _decision("subject", "worldbuilding", "Define a poised protagonist whose identity stays stable while makeup, hair, wardrobe, and period styling can vary deliberately.", {
            "identity": protagonist, "representation": "real adult human in live-action photography",
            "presence": "poised, distinctive, and camera-confident",
            "styling_versatility": "supports classical, contemporary, editorial, and ceremonial styling without identity substitution",
            "variable_styling_traits": ["makeup", "hairstyle", "hair finish", "wardrobe", "era styling"],
            "identity_locks": ["face geometry", "facial features", "age band", "skin characteristics", "body proportions"],
        }, [
            "The same poised real adult protagonist remains identifiable across every Job.",
            "Makeup, hairstyle, wardrobe, and period styling may change deliberately without face substitution or identity drift.",
        ], ["stable identity", "adult age", "natural anatomy", "distinctive personal presence"], [
            "Identity remains continuous in all outputs.",
            "Every styling choice complements the protagonist without obscuring or replacing identity-defining features.",
        ]),
        "world": _decision("world", "worldbuilding", "Construct one coherent physical world with persistent spatial and material rules.", {
            "space": "nine distinct scene designs inside one coherent photographic theme" if strategy == "chaptered_variation" else "one core scene with continuous physical state",
            "time": "nine declared scene-light states inside one coherent emotional arc" if strategy == "chaptered_variation" else "one continuous time phase", "materials": ["photographically plausible materials"],
            "physical_rules": ["consistent geometry", "gravity", "reflection", "material response"],
            "continuity": ["identity", "photographic realism", "theme grammar", "prop ownership"],
            "scene_strategy": strategy, "scene_count": scene_count, "scene_chapters": scene_chapters, "scene_plan": scene_plan,
        }, [
            "Each scene has its own architecture, depth, material evidence and physical light.",
            "Nine scene designs are visibly distinct while sharing one photographic theme grammar." if strategy == "chaptered_variation" else "One core scene preserves geometry, object state and time across the continuous event.",
        ], ["subject identity", "physical causality", "photographic realism"], [
            "Every Job has a distinct scene purpose and physically plausible environment.",
            "nine scenes are visibly distinct and identity remains stable" if strategy == "chaptered_variation" else "single scene, look and event state remain continuous",
        ]),
        "look": _decision("look", "worldbuilding", "Define wardrobe, grooming and prop ownership as world state rather than decoration.", {
            "wardrobe": "nine coordinated per-Job wardrobes; facial identity remains unchanged" if strategy == "chaptered_variation" else "one confirmed look locked across the continuous event",
            "grooming": "nine distinct makeup and hair designs; facial identity remains unchanged" if strategy == "chaptered_variation" else "one grooming state continuous across the event",
            "props": [], "ownership_policy": "every prop has one declared owner, location and state",
            "styling_strategy": strategy, "look_count": look_count, "look_chapters": look_chapters,
            "makeup_plan": makeup_plan, "hair_plan": hair_plan, "wardrobe_plan": wardrobe_plan,
            "transition_rule": "every Job has a declared coordinated look; face geometry and identity never change" if strategy == "chaptered_variation" else "look changes only when an observable event causes it",
        }, [
            "Every Job has distinct makeup, hair and wardrobe while the same face remains unmistakable." if strategy == "chaptered_variation" else "Wardrobe and grooming remain continuous across the event.",
            "Every visible prop has stable ownership and changes state only through an event.",
        ], ["facial identity", "prop ownership", "material plausibility"], [
            "No prop duplicates, floats or changes owner without cause.",
            "nine looks are visibly distinct and facial identity remains stable" if strategy == "chaptered_variation" else "single scene, look and event state remain continuous",
        ]),
        "event": _decision("event", "narrative", "Make an observable event change world state before designing poses.", {
            "inciting_action": "one observable action initiates the sequence", "state_changes": ["each major action leaves a visible consequence"],
            "consequences": ["later Jobs inherit the changed state"],
            "pose_strategy": "nine distinct action-led body states with declared hands, gaze and weight" if strategy == "chaptered_variation" else "nine causally connected action states inside one continuous event",
            "pose_states": pose_states, "face_orientation_plan": face_orientation_plan, "body_orientation_plan": body_orientation_plan,
        }, ["Actions are physically legible and leave consequences visible in later frames.", "All body states differ in action, hand function, gaze or weight distribution."],
            ["subject identity", "world physics", "prop ownership"], ["Every action changes or reveals state rather than serving as an empty pose.", "all nine body states and shot functions are distinct"]),
        "sequence": _decision("sequence", "narrative", "Organize multiple viewpoints into time, rhythm and narrative progression.", {
            "strategy": "establish → approach → trigger → develop → interiorize → reveal → turn → release → resolve" if count == 9 else "distinct functional progression",
            "rhythm": "measured progression with no duplicate shot function", "progression": list(arc.values()), "shot_count": count,
            "chapter_plan": "three chapters of three Jobs" if strategy == "chaptered_variation" and count == 9 else "one continuous event across nine Jobs" if strategy == "continuous_narrative" and count == 9 else "distinct functional progression",
            "variation_axes": ["scene", "makeup", "hair", "wardrobe", "action", "pose", "gaze", "face orientation", "composition", "focal length", "lighting"] if strategy == "chaptered_variation" else ["action", "pose", "gaze", "face orientation", "composition", "focal length", "lighting"],
            "continuity_axes": ["facial identity", "adult age", "body proportions", "photographic medium"] if strategy == "chaptered_variation" else ["identity", "scene", "styling", "world grammar", "photographic medium", "color system"],
        }, [f"The {count} Jobs form a readable progression with distinct functions.", "Information, distance, action and emotion evolve across the sequence.",
            "The set uses three visually distinct chapters without becoming nine unrelated images." if strategy == "chaptered_variation" else "The same scene and look carry one causally continuous event."],
            ["event consequences", "world continuity", "shot order"], ["No two Jobs repeat the same narrative function."]),
        "camera": _decision("camera", "image", "Choose necessary viewpoints and photographic coverage for each independent Job.", {
            "viewpoint": "one coherent physical camera position per Job", "coverage": f"{count} distinct viewpoints",
            "framing_language": "environment, full, medium, close and detail frames used by narrative need",
            "lens_language": "physically plausible perspective without arbitrary lens drift",
            "composition": "subject, depth, foreground, background and negative space form one relation system",
            "focal_length_strategy": "functional multi-focal coverage by shot purpose" if strategy == "chaptered_variation" else "coherent focal family with functional variation",
            "focal_length_plan": focal_plan, "perspective_plan": perspective_plan, "composition_plan": composition_plan,
        }, ["Every Job has one motivated viewpoint and visibly distinct composition.", "Focal length changes only when shot function and perspective require it."],
            ["world geometry", "required action visibility"], ["Framing and perspective match the declared shot function."]),
        "light": _decision("light", "image", "Make time, depth, material and emotion visible through physically coherent light.", {
            "source": "one motivated key source with declared practical or ambient support", "direction": "consistent with the world",
            "quality": "physically plausible softness and falloff", "contrast": "motivated by the emotional direction",
            "time_phase": "continuous unless the sequence declares a transition", "continuity": "direction, shadow and exposure remain traceable",
            "lighting_plan": lighting_plan,
        }, ["Light direction, shadow, falloff and reflections agree with one physical setup."],
            ["skin tone", "world geometry", "time continuity"], ["No contradictory shadows or unmotivated lighting changes appear."]),
        "style": _decision("style", "image", "Define observable photographic rhetoric without using an artist name as a shortcut.", {
            "photographic_genre": "restrained live-action editorial photography", "visual_rhetoric": "world-led rather than effect-led",
            "texture": "photographic material detail", "realism": "live-action photographic realism",
        }, ["The image reads as intentional photography with coherent texture and visual rhetoric."],
            ["live-action human medium", "world material response"], ["Style never overrides identity, physics, event or camera logic."]),
        "color_post": _decision("color_post", "image", "Organize color and rendering as relationships among skin, wardrobe, props, space, mood and time.", {
            "palette": ["world-derived base colors", "one restrained accent"], "temperature": "motivated by light and emotional arc",
            "saturation": "controlled", "contrast_curve": "preserve skin and material latitude", "grain": "subtle photographic grain",
            "sharpness": "natural detail without synthetic oversharpening", "dynamic_range": "retain highlight and shadow information",
            "skin_tone_policy": "natural and stable across all Jobs",
        }, ["Palette, skin tone, saturation, contrast and grain remain relationally coherent across the set."],
            ["natural skin tone", "light motivation", "material distinctions"], ["No global filter destroys skin, material or time relationships."]),
        "job": _decision("job", "delivery", "Freeze each viewpoint as one independent, reproducible generation Job.", {
            "one_job_one_image": True, "output_count": output["count"], "aspect_ratio": output["aspect_ratio"],
            "size": output.get("size", "not_reported"), "format": output.get("format", "not_reported"),
        }, [f"Produce {output['count']} independent {output['aspect_ratio']} images, exactly one image per Job."],
            ["unique output filename", "no grid", "no text", "no watermark"], ["Each Job produces exactly one independently usable image."],
            source="system_policy", basis=["output_contract"]),
        "quality_control": _decision("quality_control", "delivery", "Define evidence that accepts or rejects each Job and the complete set.", {
            "required_checks": ["identity", "facial presence and styling compatibility", "live-action medium", "anatomy and hands", "world geometry", "prop ownership", "lighting", "color", "continuity", "shot intent", "rights"],
            "reject_if": ["illustrated person", "identity drift", "anatomy failure", "prop duplication", "contradictory light", "collage or text"],
            "human_visual_qa": "pending until evidence",
            "variation_checks": ["nine scenes, nine looks, nine poses, nine gaze and face directions, nine compositions, nine focal lengths and nine lighting designs are distinct"] if strategy == "chaptered_variation" else ["all nine body states and shot functions are distinct"],
            "continuity_checks": ["facial identity, adult age, body proportions and live-action medium remain coherent"] if strategy == "chaptered_variation" else ["single scene, look and event state remain continuous", "identity, live-action medium, world physics and color grammar remain coherent"],
        }, ["Every Job carries model visual QA and separate pending human visual QA."],
            ["rights provenance", "successful outputs are immutable"], ["A failed required check rejects the Job; static validation never claims visual quality."],
            source="system_policy", basis=["protocol_quality_policy"]),
    }


def validate_element_decisions(decisions: Any, *, require_confirmed: bool = True) -> list[str]:
    errors: list[str] = []; spec = load_creative_layers(); required_values = spec["required_values"]
    if not isinstance(decisions, dict) or set(decisions) != set(PROTOCOL_TYPES):
        return ["element decisions must contain exactly the thirteen protocol roles"]
    emotion_taxonomy = spec["emotion_taxonomy"]
    list_fields = {
        "emotion": {"secondary_tones"}, "subject": {"identity_locks"},
        "world": {"materials", "physical_rules", "continuity"}, "look": {"props"},
        "event": {"state_changes", "consequences"}, "sequence": {"progression"},
        "color_post": {"palette"}, "quality_control": {"required_checks", "reject_if"},
    }
    non_string_fields = {"emotion": {"arc", "secondary_tones"}, "subject": {"identity_locks"},
                         "world": {"materials", "physical_rules", "continuity"}, "look": {"props"},
                         "event": {"state_changes", "consequences"}, "sequence": {"progression", "shot_count"},
                         "color_post": {"palette"}, "job": {"one_job_one_image", "output_count"},
                         "quality_control": {"required_checks", "reject_if"}}
    for role in PROTOCOL_TYPES:
        decision = decisions.get(role); label = f"element_decisions.{role}"
        if not isinstance(decision, dict): errors.append(f"{label}: must be an object"); continue
        expected_layer = next(layer for layer, roles in LAYER_ROLES.items() if role in roles)
        if decision.get("role") != role or decision.get("layer") != expected_layer: errors.append(f"{label}: role or layer mismatch")
        if decision.get("status") not in {"proposed", "confirmed"}: errors.append(f"{label}: invalid status")
        if require_confirmed and decision.get("status") != "confirmed": errors.append(f"{label}: confirmation is required")
        if decision.get("source") not in {"proposed_from_brief", "derived_from_dna", "system_policy", "creator_confirmed", "automatic_default"}: errors.append(f"{label}: invalid source")
        if not isinstance(decision.get("intent"), str) or not decision["intent"].strip(): errors.append(f"{label}: intent is required")
        values = decision.get("values")
        if not isinstance(values, dict): errors.append(f"{label}: values must be an object"); values = {}
        missing = set(required_values[role]) - set(values)
        if missing: errors.append(f"{label}: missing values {sorted(missing)}")
        for field in list_fields.get(role, set()):
            value = values.get(field)
            allow_empty = (role, field) in {("emotion", "secondary_tones"), ("look", "props")}
            if not isinstance(value, list) or (not value and not allow_empty) or any(not isinstance(item, str) or not item.strip() for item in value):
                errors.append(f"{label}.values.{field}: must be {'a' if allow_empty else 'a non-empty'} string array")
        for field in set(required_values[role]) - non_string_fields.get(role, set()):
            if not isinstance(values.get(field), str) or not values[field].strip(): errors.append(f"{label}.values.{field}: non-empty text is required")
        for field in ("observable", "must_preserve", "qa_expectations", "basis"):
            items = decision.get(field)
            if not isinstance(items, list) or not items or any(not isinstance(item, str) or not item.strip() for item in items): errors.append(f"{label}.{field}: must be a non-empty string array")
        if not isinstance(decision.get("dna_refs", []), list): errors.append(f"{label}.dna_refs: must be an array")
    emotion = decisions.get("emotion", {}).get("values", {}) if isinstance(decisions.get("emotion"), dict) else {}
    for field in ("primary_tone", "undertone", "valence", "arousal", "expression", "energy", "tension"):
        allowed_key = "primary_tones" if field == "primary_tone" else "undertones" if field == "undertone" else field
        if emotion.get(field) not in emotion_taxonomy[allowed_key]: errors.append(f"element_decisions.emotion.values.{field}: unknown controlled value")
    secondary = emotion.get("secondary_tones")
    if not isinstance(secondary, list) or len(secondary) != len(set(secondary)) or any(value not in emotion_taxonomy["primary_tones"] or value == emotion.get("primary_tone") for value in secondary):
        errors.append("element_decisions.emotion.values.secondary_tones: requires unique controlled tones different from primary_tone")
    arc = emotion.get("arc")
    if not isinstance(arc, dict) or set(arc) != {"start", "turn", "end"} or any(not str(value).strip() for value in arc.values()): errors.append("element_decisions.emotion.values.arc: requires start, turn and end")
    sequence = decisions.get("sequence", {}).get("values", {}) if isinstance(decisions.get("sequence"), dict) else {}
    if not isinstance(sequence.get("shot_count"), int) or isinstance(sequence.get("shot_count"), bool) or sequence.get("shot_count", 0) < 1: errors.append("element_decisions.sequence.values.shot_count: positive integer required")
    content = decisions.get("content", {}).get("values", {}) if isinstance(decisions.get("content"), dict) else {}
    set_strategy = content.get("set_strategy")
    if set_strategy is not None:
        if set_strategy not in SET_STRATEGIES: errors.append("element_decisions.content.values.set_strategy: unknown controlled value")
        world = decisions.get("world", {}).get("values", {}) if isinstance(decisions.get("world"), dict) else {}
        look = decisions.get("look", {}).get("values", {}) if isinstance(decisions.get("look"), dict) else {}
        event = decisions.get("event", {}).get("values", {}) if isinstance(decisions.get("event"), dict) else {}
        camera = decisions.get("camera", {}).get("values", {}) if isinstance(decisions.get("camera"), dict) else {}
        quality = decisions.get("quality_control", {}).get("values", {}) if isinstance(decisions.get("quality_control"), dict) else {}
        expected_count = sequence.get("shot_count") if isinstance(sequence.get("shot_count"), int) else 0
        light = decisions.get("light", {}).get("values", {}) if isinstance(decisions.get("light"), dict) else {}
        per_job_lists = (
            ("world", world, "scene_plan"), ("look", look, "makeup_plan"),
            ("look", look, "hair_plan"), ("look", look, "wardrobe_plan"),
            ("event", event, "pose_states"), ("event", event, "face_orientation_plan"),
            ("event", event, "body_orientation_plan"),
            ("camera", camera, "focal_length_plan"), ("camera", camera, "perspective_plan"),
            ("camera", camera, "composition_plan"), ("light", light, "lighting_plan"),
        )
        planned_lists = (("world", world, "scene_chapters"), ("look", look, "look_chapters"), *per_job_lists)
        for role, values, field in (*planned_lists, ("sequence", sequence, "variation_axes"), ("sequence", sequence, "continuity_axes"), ("quality_control", quality, "variation_checks"), ("quality_control", quality, "continuity_checks")):
            value = values.get(field)
            if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item.strip() for item in value):
                errors.append(f"element_decisions.{role}.values.{field}: must be a non-empty string array")
        if expected_count:
            for role, values, field in per_job_lists:
                if len(values.get(field, [])) != expected_count:
                    errors.append(f"element_decisions.{role}.values.{field}: must contain one entry per Job")
            if set_strategy == "chaptered_variation":
                for role, values, field in planned_lists:
                    items = values.get(field, [])
                    if len(items) != len(set(items)):
                        errors.append(f"element_decisions.{role}.values.{field}: chaptered variation requires unique entries")
        for role, values, field in (("world", world, "scene_count"), ("look", look, "look_count")):
            if not isinstance(values.get(field), int) or isinstance(values.get(field), bool) or values.get(field, 0) < 1: errors.append(f"element_decisions.{role}.values.{field}: positive integer required")
        if set_strategy == "continuous_narrative" and (world.get("scene_count") != 1 or look.get("look_count") != 1):
            errors.append("element_decisions: continuous_narrative requires one scene and one look")
        if set_strategy == "chaptered_variation" and expected_count and (world.get("scene_count") != expected_count or look.get("look_count") != expected_count):
            errors.append("element_decisions: chaptered_variation requires one distinct scene and look per Job")
    job = decisions.get("job", {}).get("values", {}) if isinstance(decisions.get("job"), dict) else {}
    if job.get("one_job_one_image") is not True: errors.append("element_decisions.job.values.one_job_one_image: must remain true")
    if not isinstance(job.get("output_count"), int) or isinstance(job.get("output_count"), bool) or job.get("output_count", 0) < 1: errors.append("element_decisions.job.values.output_count: positive integer required")
    quality = decisions.get("quality_control", {}).get("values", {}) if isinstance(decisions.get("quality_control"), dict) else {}
    if quality.get("human_visual_qa") in {"passed", "visual_qa_passed"}: errors.append("element_decisions.quality_control.values.human_visual_qa: cannot pass without evidence")
    return errors


def validate_catalog() -> list[str]:
    errors: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    categories: set[str] = set()
    for pos, asset in enumerate(load_catalog().get("assets", []), 1):
        label = f"catalog asset {pos}"
        for key in ("namespace", "id", "type", "version", "parent_version", "changed_fields", "change_summary", "prompt_fragment", "negative_fragment", "rights", "qa_status"):
            if key not in asset:
                errors.append(f"{label}: missing {key}")
        if asset.get("type") not in CATEGORIES:
            errors.append(f"{label}: unsupported type")
        else:
            categories.add(asset["type"])
        if not SEMVER.fullmatch(str(asset.get("version", ""))):
            errors.append(f"{label}: invalid semantic version")
        key = (str(asset.get("namespace")), str(asset.get("id")), str(asset.get("version")))
        if key in seen:
            errors.append(f"{label}: duplicate ID/version")
        seen.add(key)
        rights = asset.get("rights", {})
        if rights.get("status") != "original_open_content" or rights.get("license") != "CC-BY-4.0":
            errors.append(f"{label}: not approved for the starter catalog")
        if rights.get("reference_images_included") is not False:
            errors.append(f"{label}: reference images must not be bundled")
    missing = set(CATEGORIES) - categories
    if missing:
        errors.append(f"catalog: missing categories {sorted(missing)}")
    return errors


def validate_creative_layers() -> list[str]:
    """Keep the five creator layers synchronized with all protocol and DNA roles."""
    errors: list[str] = []
    try:
        spec = load_creative_layers()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"creative layers: unreadable: {exc}"]
    layers = spec.get("layers", [])
    ids = [item.get("id") for item in layers if isinstance(item, dict)]
    if ids != list(CREATIVE_LAYERS):
        errors.append("creative layers: order or IDs do not match the five-layer engine contract")
    declared_roles: list[str] = []
    declared_types: list[str] = []
    for item in layers:
        if not isinstance(item, dict):
            errors.append("creative layers: every layer must be an object"); continue
        layer = item.get("id")
        if layer not in CREATIVE_LAYERS: continue
        if item.get("roles") != list(LAYER_ROLES[layer]): errors.append(f"creative layers.{layer}: role mapping mismatch")
        if item.get("dna_types") != list(LAYER_TYPES[layer]): errors.append(f"creative layers.{layer}: DNA mapping mismatch")
        if not str(item.get("zh", "")).strip() or not str(item.get("en", "")).strip(): errors.append(f"creative layers.{layer}: bilingual titles are required")
        declared_roles.extend(item.get("roles", [])); declared_types.extend(item.get("dna_types", []))
    if len(declared_roles) != len(set(declared_roles)) or set(declared_roles) != set(PROTOCOL_TYPES):
        errors.append("creative layers: the thirteen protocol roles must each appear exactly once")
    if len(declared_types) != len(set(declared_types)) or set(declared_types) != set(CATEGORIES):
        errors.append("creative layers: the seven Registry DNA types must each appear exactly once")
    required_values = spec.get("required_values", {})
    if set(required_values) != set(PROTOCOL_TYPES) or any(not isinstance(value, list) or not value for value in required_values.values()):
        errors.append("creative layers: every protocol role requires a non-empty value contract")
    strategies = spec.get("set_strategies", [])
    strategy_ids = [item.get("id") for item in strategies if isinstance(item, dict)]
    if strategy_ids != list(SET_STRATEGIES): errors.append("creative layers: set strategy IDs or order mismatch")
    if sum(item.get("default") is True for item in strategies if isinstance(item, dict)) != 1 or not any(item.get("id") == DEFAULT_SET_STRATEGY and item.get("default") is True for item in strategies if isinstance(item, dict)):
        errors.append("creative layers: exactly one matching default set strategy is required")
    for item in strategies:
        if not isinstance(item, dict): errors.append("creative layers: every set strategy must be an object"); continue
        if not str(item.get("zh", "")).strip() or not str(item.get("en", "")).strip(): errors.append(f"creative layers.set_strategies.{item.get('id')}: bilingual titles are required")
        for field in ("variation_axes", "continuity_axes"):
            values = item.get(field)
            if not isinstance(values, list) or not values or any(not isinstance(value, str) or not value for value in values): errors.append(f"creative layers.set_strategies.{item.get('id')}.{field}: non-empty string array required")
    taxonomy = spec.get("emotion_taxonomy", {})
    for key in ("primary_tones", "undertones", "valence", "arousal", "expression", "energy", "tension"):
        values = taxonomy.get(key)
        if not isinstance(values, list) or not values or len(values) != len(set(values)): errors.append(f"creative layers.emotion_taxonomy.{key}: non-empty unique values required")
    profiles = spec.get("mood_profiles", [])
    profile_ids = [item.get("id") for item in profiles if isinstance(item, dict)]
    if set(profile_ids) != set(taxonomy.get("primary_tones", [])): errors.append("creative layers: mood profiles must cover every primary tone")
    for profile in profiles:
        if not isinstance(profile, dict): continue
        for field in ("undertone", "valence", "arousal", "expression", "energy", "tension"):
            allowed = taxonomy.get("undertones" if field == "undertone" else field, [])
            if profile.get(field) not in allowed: errors.append(f"creative layers.mood_profiles.{profile.get('id')}.{field}: unknown value")
        arc = profile.get("arc")
        if not isinstance(arc, dict) or set(arc) != {"start", "turn", "end"}: errors.append(f"creative layers.mood_profiles.{profile.get('id')}: complete emotional arc required")
    return errors


def validate_semantic_registry() -> list[str]:
    errors: list[str] = []
    try:
        registry = load_semantic_registry()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"semantic registry: unreadable: {exc}"]
    if registry.get("semantic_contract_version") != SEMANTIC_CONTRACT_VERSION:
        errors.append("semantic registry: contract version mismatch")
    roles = registry.get("roles", {})
    if set(roles) != set(PROTOCOL_TYPES):
        errors.append("semantic registry: roles must contain exactly the thirteen protocol types")
    tags = registry.get("tags", [])
    ids = [item.get("id") for item in tags if isinstance(item, dict)]
    if len(ids) != len(set(ids)):
        errors.append("semantic registry: duplicate tag id")
    for item in tags:
        if not isinstance(item, dict):
            errors.append("semantic registry: tag must be an object"); continue
        for key in ("id", "en", "zh", "roles"):
            if not item.get(key): errors.append(f"semantic registry tag: missing {key}")
        unknown_roles = set(item.get("roles", [])) - set(PROTOCOL_TYPES)
        if unknown_roles: errors.append(f"semantic registry tag {item.get('id')}: unknown roles {sorted(unknown_roles)}")
    mappings = registry.get("dna_to_protocol", {})
    if set(mappings) != set(CATEGORIES):
        errors.append("semantic registry: DNA mapping must contain all seven catalog categories")
    covered = {role for values in mappings.values() for role in values}
    if covered != set(PROTOCOL_TYPES):
        errors.append("semantic registry: DNA mapping must cover all thirteen protocol roles")
    fields = registry.get("fields", {})
    for name in CREATIVE_FIELDS:
        field = fields.get(f"shots.*.{name}", {})
        for key in ("en", "zh", "role", "affects", "compile_stage", "qa"):
            if not field.get(key): errors.append(f"semantic registry field {name}: missing {key}")
    errors.extend(validate_creative_layers())
    return errors


def _localized(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, dict) or not str(value.get("en", "")).strip() or not str(value.get("zh", "")).strip():
        errors.append(f"{label}: must contain non-empty en and zh text")


def _semantic_statements(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{label}: must be a non-empty array"); return
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            errors.append(f"{label}: statement must be an object"); continue
        statement_id = item.get("id")
        if not statement_id or statement_id in seen:
            errors.append(f"{label}: statement ids must be present and unique")
        seen.add(str(statement_id))
        _localized(item, f"{label}.{statement_id or '?'}", errors)


def validate_semantic_contract(value: Any, label: str, *, field_level: bool = False) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{label}: semantic contract must be an object"]
    required = ("purpose", "affects", "expected_effects", "qa_expectations") if field_level else (
        "purpose", "affects", "must_preserve", "may_vary", "expected_effects",
        "qa_expectations", "semantic_tags", "priority",
    )
    for key in required:
        if key not in value: errors.append(f"{label}: missing {key}")
    _localized(value.get("purpose"), f"{label}.purpose", errors)
    for key in ("affects",) if field_level else ("affects", "must_preserve", "may_vary"):
        items = value.get(key)
        if not isinstance(items, list) or not items or any(not isinstance(item, str) or not item for item in items):
            errors.append(f"{label}.{key}: must be a non-empty string array")
    _semantic_statements(value.get("expected_effects"), f"{label}.expected_effects", errors)
    _semantic_statements(value.get("qa_expectations"), f"{label}.qa_expectations", errors)
    if not field_level:
        tags = value.get("semantic_tags")
        if not isinstance(tags, list) or not tags:
            errors.append(f"{label}.semantic_tags: must be a non-empty array")
        else:
            unknown = set(tags) - allowed_semantic_tags()
            if unknown: errors.append(f"{label}.semantic_tags: unknown tags {sorted(unknown)}")
        priority = value.get("priority")
        if not isinstance(priority, int) or isinstance(priority, bool) or not 0 <= priority <= 100:
            errors.append(f"{label}.priority: must be an integer from 0 through 100")
    return errors


def validate_semantic_theme(theme: dict[str, Any]) -> list[str]:
    errors = validate_semantic_registry()
    if theme.get("semantic_contract_version") != SEMANTIC_CONTRACT_VERSION:
        errors.append("theme: semantic_contract_version must be 0.3.0")
    errors.extend(validate_semantic_contract(theme.get("semantics"), "theme.semantics"))
    mappings = theme.get("protocol_mapping")
    expected_mapping = load_semantic_registry().get("dna_to_protocol", {}) if not errors or (plugin_root() / "assets/semantics/registry.json").exists() else {}
    if mappings != expected_mapping:
        errors.append("theme: protocol_mapping must match the registered seven-to-thirteen role mapping")
    role_semantics = theme.get("element_semantics")
    if not isinstance(role_semantics, dict) or set(role_semantics) != set(PROTOCOL_TYPES):
        errors.append("theme: element_semantics must contain exactly the thirteen protocol roles")
    else:
        for role in PROTOCOL_TYPES:
            errors.extend(validate_semantic_contract(role_semantics[role], f"theme.element_semantics.{role}"))
            valid_for_role = {item["id"] for item in load_semantic_registry()["tags"] if role in item["roles"]}
            invalid = set(role_semantics[role].get("semantic_tags", [])) - valid_for_role
            if invalid: errors.append(f"theme.element_semantics.{role}: tags not valid for role {sorted(invalid)}")
    for shot in theme.get("shots", []):
        shot_id = shot.get("shot_id", "?")
        errors.extend(validate_semantic_contract(shot.get("intent"), f"shot {shot_id}.intent"))
        field_intents = shot.get("field_intents")
        if not isinstance(field_intents, dict):
            errors.append(f"shot {shot_id}: field_intents must be an object"); continue
        for field in CREATIVE_FIELDS:
            errors.extend(validate_semantic_contract(field_intents.get(field), f"shot {shot_id}.field_intents.{field}", field_level=True))
    return errors


def validate_rendering_contract(value: Any) -> list[str]:
    if not isinstance(value, dict): return ["rendering_contract: must be an object"]
    errors: list[str] = []
    if value.get("medium") != "live_action_photography": errors.append("rendering_contract: medium must be live_action_photography")
    if value.get("subject_representation") != "real_adult_human": errors.append("rendering_contract: subject_representation must be real_adult_human")
    if value.get("environment_style_may_be_handmade") is not True: errors.append("rendering_contract: handmade environment allowance must be explicit")
    preserve = value.get("must_preserve")
    required_preserve = set(live_action_rendering_contract()["must_preserve"])
    if not isinstance(preserve, list) or not required_preserve.issubset(set(preserve)):
        errors.append("rendering_contract: live-action preservation rules are incomplete")
    forbidden = value.get("forbid")
    if not isinstance(forbidden, list) or not set(LIVE_ACTION_FORBID).issubset(set(forbidden)):
        errors.append("rendering_contract: illustrated/CGI human prohibitions are incomplete")
    if value.get("priority") != 100: errors.append("rendering_contract: priority must be 100")
    instruction = value.get("instruction", {})
    if not instruction.get("en") or not instruction.get("zh"): errors.append("rendering_contract: bilingual instruction is required")
    return errors


def validate_reference_metadata(references: Any, theme: dict[str, Any] | None = None) -> list[str]:
    if references is None: return []
    if not isinstance(references, list): return ["references: must be an array"]
    errors: list[str] = []; ids: set[str] = set(); digests: set[str] = set()
    shot_ids = {shot.get("shot_id") for shot in (theme or {}).get("shots", [])}
    for pos, ref in enumerate(references, 1):
        label = f"reference {pos}"
        if not isinstance(ref, dict): errors.append(f"{label}: must be an object"); continue
        ref_id = str(ref.get("reference_id", ""))
        if not SAFE_ASSET_ID.fullmatch(ref_id): errors.append(f"{label}: invalid reference_id")
        if ref_id in ids: errors.append(f"{label}: duplicate reference_id {ref_id}")
        ids.add(ref_id)
        sha = str(ref.get("original_sha256", ""))
        if not re.fullmatch(r"[a-f0-9]{64}", sha): errors.append(f"{label}: invalid original_sha256")
        if sha in digests: errors.append(f"{label}: duplicate original_sha256")
        digests.add(sha)
        filename = ref.get("original_filename")
        if not isinstance(filename, str) or not filename or Path(filename).name != filename:
            errors.append(f"{label}: original_filename must be one safe filename")
        uses_value = ref.get("uses"); uses = set(uses_value) if isinstance(uses_value, list) else set()
        if not isinstance(uses_value, list) or not uses or uses - REFERENCE_USES:
            errors.append(f"{label}: uses must be selected from {sorted(REFERENCE_USES)}")
        for key in ("allowed_uses", "forbidden_uses", "applies_to"):
            value = ref.get(key)
            if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item for item in value):
                errors.append(f"{label}: {key} must be a non-empty string array")
        applies_value = ref.get("applies_to"); applies = set(applies_value) if isinstance(applies_value, list) else set()
        if theme is not None:
            unknown_shots = applies - shot_ids - {"*"}
            if unknown_shots: errors.append(f"{label}: unknown Jobs {sorted(unknown_shots)}")
        elif any(item != "*" and not re.fullmatch(r"SHOT_[0-9]{2,3}", item) for item in applies):
            errors.append(f"{label}: applies_to contains an invalid Job ID")
        rights_value = ref.get("rights"); rights = rights_value if isinstance(rights_value, dict) else {}
        if not isinstance(rights_value, dict): errors.append(f"{label}: rights must be an object")
        for key in ("copyright_status", "portrait_rights", "attribution", "redistribution_allowed"):
            if key not in rights: errors.append(f"{label}: missing rights.{key}")
        for key in ("copyright_status", "portrait_rights", "attribution"):
            if key in rights and (not isinstance(rights[key], str) or not rights[key].strip()):
                errors.append(f"{label}: rights.{key} must be a non-empty string")
        if "redistribution_allowed" in rights and not isinstance(rights["redistribution_allowed"], bool):
            errors.append(f"{label}: rights.redistribution_allowed must be boolean")
        forbidden_value = ref.get("forbidden_uses"); forbidden = set(forbidden_value) if isinstance(forbidden_value, list) else set()
        if "identity" not in uses and "identity" not in forbidden:
            errors.append(f"{label}: non-identity reference must explicitly forbid identity use")
    analysis_value = (theme or {}).get("reference_analysis", {}); analysis = analysis_value if isinstance(analysis_value, dict) else {}
    expected = {item.get("sha256") for item in analysis.get("references", []) if isinstance(item, dict)}
    actual = {item.get("original_sha256") for item in references if isinstance(item, dict)}
    if expected and expected != actual: errors.append("references: digests must match reference_analysis exactly")
    if analysis.get("identity_usage") == "none" and any("identity" in ref.get("uses", []) for ref in references if isinstance(ref, dict)):
        errors.append("references: identity usage conflicts with reference_analysis.identity_usage=none")
    anchor = (theme or {}).get("core_visual_anchor_reference_id")
    if anchor is not None and anchor not in ids:
        errors.append("references: core_visual_anchor_reference_id must resolve to a declared reference")
    return errors


def _reference_rights_allow_public(ref: dict[str, Any]) -> bool:
    rights = ref.get("rights", {})
    if not isinstance(rights, dict) or rights.get("redistribution_allowed") is not True:
        return False
    unresolved = ("unverified", "unknown", "unresolved", "pending", "private_only")
    for key in ("copyright_status", "portrait_rights"):
        value = str(rights.get(key, "")).lower()
        if not value or any(token in value for token in unresolved): return False
    return bool(str(rights.get("attribution", "")).strip())


def validate_theme(theme: dict[str, Any], assets: list[dict[str, Any]] | None = None) -> list[str]:
    errors = validate_catalog() if assets is None else []
    for key in ("schema_version", "id", "version", "name", "parent_version", "changed_fields", "change_summary", "dna", "output", "shots", "rights", "qa_status"):
        if key not in theme:
            errors.append(f"theme: missing {key}")
    if theme.get("schema_version") not in {"1.0.0", "1.1.0"}: errors.append("theme: unsupported schema_version")
    if not SAFE_ID.fullmatch(str(theme.get("id", ""))): errors.append("theme: invalid id")
    if not SEMVER.fullmatch(str(theme.get("version", ""))): errors.append("theme: invalid semantic version")
    refs = theme.get("dna", [])
    if not isinstance(refs, list):
        errors.append("theme: dna must be an array"); refs = []
    index = _asset_index(assets)
    ref_types: set[str] = set()
    for ref in refs:
        if not isinstance(ref, dict): errors.append("theme: invalid DNA reference"); continue
        key = tuple(ref.get(k, "") for k in ("namespace", "id", "type", "version"))
        asset = index.get(key)
        if not asset: errors.append(f"theme: unresolved DNA reference {key}"); continue
        ref_types.add(ref["type"])
        if ref.get("content_digest") != digest(asset): errors.append(f"theme: DNA digest mismatch for {ref['id']}")
    missing = set(CATEGORIES) - ref_types
    if missing: errors.append(f"theme: missing DNA categories {sorted(missing)}")
    shots = theme.get("shots", [])
    if not isinstance(shots, list) or not 1 <= len(shots) <= 24:
        errors.append("theme: shots must contain 1-24 entries"); shots = []
    output = theme.get("output", {})
    if output.get("count") != len(shots): errors.append("theme: output count does not match shots")
    if output.get("independent_images") is not True: errors.append("theme: outputs must be independent images")
    if output.get("provider_native") is True:
        expected_output = NATIVE_4K_OUTPUT
        for key, expected in expected_output.items():
            if output.get(key) != expected: errors.append(f"theme: native 4K output {key} must be {expected}")
    if output.get("generation_surface") == "codex_imagegen":
        for key, expected in CODEX_IMAGEGEN_OUTPUT.items():
            if output.get(key) != expected: errors.append(f"theme: Codex image output {key} must be {expected}")
    required = ("shot_id", "title", "narrative_purpose", "framing", "action", "hands", "gaze", "composition", "continuity", "output_filename")
    ids, filenames = set(), set()
    for shot in shots:
        for key in required:
            if not shot.get(key): errors.append(f"shot: missing {key}")
        if shot.get("shot_id") in ids: errors.append(f"shot: duplicate id {shot.get('shot_id')}")
        if shot.get("output_filename") in filenames: errors.append(f"shot: duplicate filename {shot.get('output_filename')}")
        ids.add(shot.get("shot_id")); filenames.add(shot.get("output_filename"))
    set_strategy = theme.get("set_strategy")
    if set_strategy is not None:
        if set_strategy not in SET_STRATEGIES: errors.append("theme: unknown set_strategy")
        variation_fields = (
            "scene_design", "pose_state", "action", "hands", "gaze", "face_orientation",
            "body_orientation", "expression", "composition", "makeup", "hair", "wardrobe",
            "focal_length", "perspective_intent", "lighting",
        )
        for shot in shots:
            for key in ("chapter", *variation_fields):
                if not str(shot.get(key, "")).strip(): errors.append(f"shot {shot.get('shot_id')}: set strategy requires {key}")
            if shot.get("continuity", {}).get("set_strategy") != set_strategy: errors.append(f"shot {shot.get('shot_id')}: continuity set strategy mismatch")
        pose_states = [shot.get("pose_state") for shot in shots]
        if len(pose_states) != len(set(pose_states)): errors.append("theme: every Job requires a distinct action-led pose_state")
        scenes = {shot.get("continuity", {}).get("scene") for shot in shots}
        looks = {shot.get("continuity", {}).get("wardrobe") for shot in shots}
        if set_strategy == "continuous_narrative" and (scenes != {"SCENE_A"} or looks != {"LOOK_A"}): errors.append("theme: continuous_narrative requires one scene and one look")
        if set_strategy == "chaptered_variation":
            if len(scenes) != len(shots) or len(looks) != len(shots):
                errors.append("theme: chaptered_variation requires one distinct scene and look per Job")
            for field in variation_fields:
                values = [str(shot.get(field, "")).strip().casefold() for shot in shots]
                if len(values) != len(set(values)):
                    errors.append(f"theme: chaptered_variation requires distinct {field} for every Job")
        decision_strategy = theme.get("element_decisions", {}).get("content", {}).get("values", {}).get("set_strategy")
        if decision_strategy is not None and decision_strategy != set_strategy: errors.append("theme: set_strategy conflicts with Content decision")
    rights = theme.get("rights", {})
    if rights.get("status") != "original_open_content": errors.append("theme: rights status must be original_open_content")
    if theme.get("qa_status") == "visual_qa_passed" and not theme.get("visual_qa_evidence"):
        errors.append("theme: visual_qa_passed requires evidence")
    if "rendering_contract" in theme: errors.extend(validate_rendering_contract(theme["rendering_contract"]))
    if "references" in theme:
        errors.extend(validate_reference_metadata(theme["references"], theme))
        if any(not _reference_rights_allow_public(ref) for ref in theme.get("references", []) if isinstance(ref, dict)):
            if theme.get("distribution") != "private_only": errors.append("theme: unredistributable references require distribution=private_only")
    if theme.get("schema_version") == "1.1.0":
        if theme.get("parent_version"):
            if theme.get("version") == theme.get("parent_version"):
                errors.append("theme: child version must differ from parent_version")
            if not {"semantics", "element_semantics", "shots[*].intent", "protocol_mapping"}.issubset(set(theme.get("changed_fields", []))):
                errors.append("theme: semantic extension changed_fields are incomplete")
        elif "initial_version" not in theme.get("changed_fields", []):
            errors.append("theme: new semantic asset without a parent must declare initial_version")
        errors.extend(validate_semantic_theme(theme))
    if "element_decisions" in theme:
        errors.extend(validate_element_decisions(theme["element_decisions"], require_confirmed=True))
    return errors
