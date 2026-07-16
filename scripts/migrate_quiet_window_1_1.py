#!/usr/bin/env python3
"""Reproducible compatible migration for Quiet Window 1.0.0 -> 1.1.0."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "plugins/apsal-studio/scripts/apsal_engine.py"
spec = importlib.util.spec_from_file_location("apsal_engine", ENGINE)
engine = importlib.util.module_from_spec(spec); spec.loader.exec_module(engine)

EXAMPLE = ROOT / "examples/quiet-window"
SOURCE = EXAMPLE / "theme.apsal.yaml"
CANONICAL = EXAMPLE / "theme.apsal.json"
OUTPUTS = {target: EXAMPLE / f"compiled.{target}.json" for target in engine.COMPILE_TARGETS}


def statement(statement_id: str, en: str, zh: str) -> dict[str, str]:
    return {"id": statement_id, "en": en, "zh": zh}


def contract(*, en: str, zh: str, affects: list[str], preserve: list[str], vary: list[str],
             effect: tuple[str, str, str], qa: tuple[str, str, str], tags: list[str], priority: int) -> dict:
    return {
        "purpose": {"en": en, "zh": zh}, "affects": affects,
        "must_preserve": preserve, "may_vary": vary,
        "expected_effects": [statement(*effect)], "qa_expectations": [statement(*qa)],
        "semantic_tags": tags, "priority": priority,
    }


def field_intent(field: str, shot: dict, field_def: dict) -> dict:
    values = {
        "framing": shot["framing"], "action": shot["action"], "hands": shot["hands"],
        "gaze": shot["gaze"], "composition": shot["composition"],
    }
    value = values[field]
    return {
        "purpose": {
            "en": f"Use {field}='{value}' to serve this Job's narrative purpose: {shot['narrative_purpose']}",
            "zh": f"使用 {field}='{value}' 服务本 Job 的叙事目的，而不是作为孤立的形式标签。",
        },
        "affects": field_def["affects"],
        "expected_effects": [statement(
            f"{field}.observable", f"The declared {field} is observable and supports the action.",
            f"已声明的 {field} 在画面中可观察，并服务于动作。",
        )],
        "qa_expectations": [statement(
            field_def["qa"][0], field_def["qa"][0].replace("_", " ").capitalize() + ".",
            field_def["qa"][0].replace("_", " ") + "。",
        )],
    }


def build() -> dict:
    legacy = engine.load_json(EXAMPLE / "theme.json")
    theme = engine.new_semantic_theme(legacy["id"], legacy["name"], len(legacy["shots"]), native_4k=False, live_action=False)
    theme.update({
        "version": "1.1.0", "parent_version": "1.0.0",
        "changed_fields": ["schema_version", "semantics", "protocol_mapping", "element_semantics", "shots[*].intent", "shots[*].field_intents"],
        "change_summary": "Compatible Semantic Contract 0.3 authoring metadata; photographic generation intent and seven DNA dependencies remain unchanged.",
        "rights": legacy["rights"], "qa_status": "visual_qa_pending",
    })
    for target, source in zip(theme["shots"], legacy["shots"]):
        target.update(source)

    common_preserve = ["subject.identity", "world.geometry", "look.wardrobe", "rights.provenance"]
    role_specs = {
        "subject": contract(en="Keep one fictional adult recognizable across all nine viewpoints.", zh="让同一虚构成年人物在九次观看中保持可识别身份。", affects=["job.identity", "emotion.expression", "quality_control.identity"], preserve=["subject.adult_age", "subject.facial_geometry", "subject.hair"], vary=["subject.gaze", "subject.expression", "subject.pose"], effect=("subject.same_person", "Every frame reads as the same adult person.", "每一镜均可识别为同一成年人物。"), qa=("subject.identity_evidence", "Compare face, age and proportions across all Jobs.", "跨全部 Job 比较面部、年龄与比例。"), tags=["subject.identity.locked"], priority=100),
        "world": contract(en="Make the quiet window room a persistent reality rather than a replaceable backdrop.", zh="让安静的窗边房间成为持续现实，而不是可随意替换的背景。", affects=["camera.viewpoint", "light.direction", "event.path", "sequence.continuity"], preserve=["world.window.east", "world.table.position", "world.room.geometry"], vary=["world.visible_area", "world.curtain_motion", "world.light_phase"], effect=("world.inferable", "Different framings still imply one room.", "不同景别仍能推断为同一房间。"), qa=("world.geometry_evidence", "Window, floor, table and movement path remain physically compatible.", "窗户、地面、桌子与行动路径保持物理兼容。"), tags=["world.space.coherent"], priority=90),
        "style": contract(en="Use restrained editorial photography without overriding identity, event or material truth.", zh="采用克制的编辑摄影语言，但不得压过身份、事件或材质真实。", affects=["camera.composition", "color_post.rendering", "light.contrast"], preserve=["subject.realistic_skin", "world.believable_materials", "content.quiet_tone"], vary=["style.grain", "style.depth", "style.negative_space"], effect=("style.coherent", "The set shares a restrained tactile editorial character.", "整组保持克制、可触的编辑摄影气质。"), qa=("style.no_gloss", "Reject CGI gloss, beauty-filter skin and decorative excess.", "拒绝 CGI 光泽、美颜皮肤与装饰过量。"), tags=["style.editorial.restrained"], priority=50),
        "look": contract(en="Keep LOOK_A and the blank cream paper physically owned by the subject.", zh="保持 LOOK_A，并让米白信纸始终具有明确的主体归属。", affects=["subject.silhouette", "event.hand_action", "sequence.prop_state"], preserve=["look.wardrobe.LOOK_A", "look.paper.owner"], vary=["look.fabric_motion", "look.paper.orientation"], effect=("look.continuous", "Wardrobe and paper remain continuous while their state changes naturally.", "服装与信纸保持连续，同时状态自然变化。"), qa=("look.ownership", "The paper never floats, duplicates or changes owner.", "信纸不得漂浮、复制或改变归属。"), tags=["look.wardrobe.locked", "world.prop.ownership"], priority=88),
        "emotion": contract(en="Externalize a quiet unresolved decision through gaze, breath and action rather than labels.", zh="通过视线、呼吸和动作外化安静而未决的决定，而不是直接贴情绪标签。", affects=["subject.gaze", "event.tempo", "camera.distance"], preserve=["emotion.restrained_range", "content.unspoken_decision"], vary=["emotion.intensity", "emotion.external_expression"], effect=("emotion.observable", "Emotion is inferred from behavior, not theatrical posing.", "情绪由行为推断，而非戏剧化摆姿。"), qa=("emotion.motivated", "Expression and gaze follow the current event phase.", "表情与视线符合当前事件阶段。"), tags=["emotion.expression.restrained"], priority=75),
        "event": contract(en="Turn the blank paper from an active object of reading into a closed object after decision.", zh="让空白信纸从正在阅读的对象转变为决定之后被关闭的对象。", affects=["world.paper_state", "look.hands", "sequence.phase"], preserve=["event.paper.owner", "event.causal_order"], vary=["event.action", "event.tempo"], effect=("event.transition", "Paper orientation and hand action make state changes legible.", "信纸方向与手部动作使状态变化清楚可见。"), qa=("event.causality", "Each action follows the prior state and leaves a usable next state.", "每个动作承接前一状态，并留下可供下一镜继承的状态。"), tags=["event.state.transition", "world.prop.ownership"], priority=82),
        "camera": contract(en="Use one coherent viewpoint per Job and varied distances across the sequence.", zh="每个 Job 使用一个连贯视点，并在序列中改变观看距离。", affects=["world.visible_information", "emotion.viewer_distance", "content.emphasis"], preserve=["camera.single_viewpoint", "world.perspective"], vary=["camera.framing", "camera.height", "camera.distance"], effect=("camera.youguan", "Nine single viewpoints form a deliberate movement through the world.", "九个单一视点形成对世界的有意游观。"), qa=("camera.distinct", "Framings are distinct without breaking room geometry.", "景别彼此不同，但不破坏房间几何。"), tags=["camera.viewpoint.single"], priority=70),
        "light": contract(en="Let one east-facing source progress from cool arrival to warm afterglow.", zh="让同一东向光源从冷静进入阶段推进到温暖余晖。", affects=["world.time", "subject.visibility", "sequence.phase"], preserve=["light.source.east_window", "light.shadow_direction"], vary=["light.temperature", "light.intensity", "light.falloff"], effect=("light.time", "Light phase makes narrative time perceptible.", "光线阶段让叙事时间可以被感知。"), qa=("light.physical", "Reject contradictory shadows, multiple suns and clipped highlights.", "拒绝矛盾阴影、多重太阳和高光溢出。"), tags=["light.direction.consistent"], priority=70),
        "color_post": contract(en="Keep natural separation and tactile grain subordinate to world and skin.", zh="让自然色彩分离与触感颗粒服从世界和肤质。", affects=["style.materiality", "light.phase", "subject.skin"], preserve=["color.skin_natural", "color.world_palette"], vary=["color.warmth_by_phase", "color.grain"], effect=("color.relational", "Color changes with light phase without becoming a preset filter.", "色彩随光线阶段变化，但不退化为预设滤镜。"), qa=("color.no_drift", "Skin and room materials do not drift between Jobs.", "肤色与房间材质不得跨 Job 漂移。"), tags=["color.palette.natural"], priority=65),
        "quality_control": contract(en="Separate static validity from evidence-based human visual QA.", zh="严格区分静态合法性与基于证据的人工视觉 QA。", affects=["subject", "world", "look", "event", "camera", "light", "job"], preserve=["qa.honest_status", "rights.disclosure"], vary=["qa.evidence_links"], effect=("qa.actionable", "Every semantic purpose has an observable acceptance check.", "每个语义目的都有可观察的验收检查。"), qa=("qa.no_false_pass", "Do not claim visual pass without linked generated-image evidence.", "没有关联生成图证据时不得声称视觉通过。"), tags=["qa.identity", "qa.anatomy", "qa.continuity", "qa.no_text"], priority=100),
        "content": contract(en="Express an unspoken decision through world and action instead of written explanation.", zh="通过世界与行动表达未说出口的决定，而不依赖文字解释。", affects=["event.paper_state", "emotion.restraint", "sequence.resolution"], preserve=["content.no_text", "content.quiet_decision"], vary=["content.viewer_interpretation"], effect=("content.felt", "The decision is felt through the paper sequence and final breath.", "决定通过信纸序列与最后呼吸被感知。"), qa=("content.no_caption", "The story remains legible without generated captions or typography.", "故事无需生成字幕或排版文字仍可理解。"), tags=["content.theme.decision"], priority=80),
        "sequence": contract(en="Move from arrival through encounter and decision to an unresolved afterword.", zh="从进入、接触、决定推进到未完全封闭的余韵。", affects=["event.order", "camera.coverage", "light.phase", "emotion.intensity"], preserve=["sequence.causal_order", "sequence.unique_functions"], vary=["sequence.viewpoint", "sequence.distance"], effect=("sequence.progression", "Each Job adds a new function rather than repeating a pose.", "每个 Job 增加新职能，而不是重复姿势。"), qa=("sequence.coverage", "Removing any Job creates a clear information or rhythm loss.", "移除任一 Job 都会造成明确的信息或节奏损失。"), tags=["sequence.function.progression", "qa.continuity"], priority=85),
        "job": contract(en="Make each shot one complete, independently usable act of looking.", zh="让每一镜成为完整且可独立使用的一次观看。", affects=["camera", "event", "output.filename", "quality_control"], preserve=["job.one_image", "job.unique_filename", "subject.identity"], vary=["job.viewpoint", "job.action"], effect=("job.independent", "Every Job produces one finished photograph with a unique role.", "每个 Job 产生一张具有独特职能的完成照片。"), qa=("job.output", "Reject grids, collages, storyboards, text, logos and watermarks.", "拒绝网格、拼图、故事板、文字、标志和水印。"), tags=["job.output.independent", "camera.viewpoint.single"], priority=82),
    }
    theme["element_semantics"] = role_specs

    shot_effects = [
        ("arrival", "Establish room geometry and solitary arrival.", "建立房间几何与独自进入。"),
        ("window_figure", "Reveal identity and silhouette in relation to the window.", "揭示人物身份、轮廓及其与窗户的关系。"),
        ("unfolding", "Begin the paper event with physically legible hands.", "以物理清楚的手部动作启动信纸事件。"),
        ("before_reading", "Suspend action and move attention toward inner decision.", "暂停动作，并把注意力转向内在决定。"),
        ("paper_detail", "Make texture, touch and prop ownership observable.", "让材质、触觉与道具归属变得可观察。"),
        ("light_turns", "Show time changing the subject's attention.", "表现时间变化如何改变人物注意方向。"),
        ("crossing", "Use movement through the room to begin resolution.", "通过穿越房间的动作启动解决阶段。"),
        ("decision", "Turn the paper face down as the visible consequence of decision.", "把信纸翻面作为决定的可见后果。"),
        ("afterword", "Close with breath and unresolved emotional remainder.", "以呼吸和未完全解决的情绪余韵收束。"),
    ]
    field_defs = engine.load_semantic_registry()["fields"]
    for shot, (effect_id, effect_en, effect_zh) in zip(theme["shots"], shot_effects):
        shot["intent"] = contract(
            en=shot["narrative_purpose"], zh=effect_zh,
            affects=["event", "camera", "sequence", "job"], preserve=common_preserve,
            vary=["camera.framing", "event.action", "emotion.external_expression"],
            effect=(effect_id, effect_en, effect_zh),
            qa=(f"{effect_id}.legible", f"The intended function '{effect_en}' is visible without explanatory text.", f"无需解释文字即可看出“{effect_zh}”这一职能。"),
            tags=["job.output.independent", "camera.viewpoint.single", "sequence.function.progression"], priority=82,
        )
        shot["field_intents"] = {
            field: field_intent(field, shot, field_defs[f"shots.*.{field}"])
            for field in engine.CREATIVE_FIELDS
        }
    return theme


def rendered() -> dict[Path, str]:
    theme = build()
    return {
        SOURCE: engine.dump_yaml(theme),
        CANONICAL: json.dumps(theme, ensure_ascii=False, indent=2) + "\n",
        **{path: json.dumps(engine.compile_theme(theme, target), ensure_ascii=False, indent=2) + "\n" for target, path in OUTPUTS.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--check", action="store_true"); args = parser.parse_args()
    errors = []
    for path, content in rendered().items():
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                errors.append(f"out of date: {path.relative_to(ROOT)}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content, encoding="utf-8")
    if errors:
        print("\n".join(errors)); return 1
    print("Quiet Window Semantic Contract 1.1.0 is reproducible")
    return 0


if __name__ == "__main__": raise SystemExit(main())
