# Executed by apsal_engine/__init__.py into that module. Not an importable submodule.
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

def normalize_interface_language(value: str | None) -> str:
    """Normalize an explicit creator-facing locale without guessing a host locale."""
    raw = str(value or "auto").strip().casefold().replace("_", "-")
    if raw in {"", "auto"}: return "auto"
    if raw in {"zh", "zh-cn", "zh-hans", "chinese", "中文", "简体中文"}: return "zh-CN"
    if raw in {"en", "en-us", "en-gb", "english", "英文", "英语"}: return "en"
    raise ValidationError("language must be auto, zh-CN, or en")


def resolve_interface_language(text: str, requested: str | None = "auto") -> dict[str, Any]:
    """Resolve UI language from an explicit choice or the current creator message.

    This intentionally does not inspect an operating-system locale: local MCP plugins
    are not guaranteed to receive one from every Codex surface.
    """
    explicit = normalize_interface_language(requested)
    if explicit != "auto":
        return {"code": explicit, "status": "confirmed", "source": "creator_explicit", "supported": list(SUPPORTED_INTERFACE_LANGUAGES)}
    value = str(text or "").strip()
    if re.search(r"(?:please\s+)?(?:reply|respond|continue|use|switch)\s+(?:in|to)\s+english\b", value, re.I) or re.search(r"(?:请)?(?:用|使用|切换到)(?:英文|英语)(?:回答|交流|界面)?", value):
        return {"code": "en", "status": "confirmed", "source": "message_explicit", "supported": list(SUPPORTED_INTERFACE_LANGUAGES)}
    if re.search(r"(?:please\s+)?(?:reply|respond|continue|use|switch)\s+(?:in|to)\s+(?:simplified\s+)?chinese\b", value, re.I) or re.search(r"(?:请)?(?:用|使用|切换到)(?:中文|简体中文)(?:回答|交流|界面)?", value):
        return {"code": "zh-CN", "status": "confirmed", "source": "message_explicit", "supported": list(SUPPORTED_INTERFACE_LANGUAGES)}
    cjk_count = len(re.findall(r"[\u3400-\u9fff]", value))
    latin_words = len(re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)*", value))
    detected: str | None = None
    if cjk_count >= 2 and cjk_count >= latin_words: detected = "zh-CN"
    elif latin_words >= 2 and latin_words > cjk_count: detected = "en"
    return {
        "code": detected, "status": "confirmed" if detected else "pending",
        "source": "message_detected" if detected else "ambiguous",
        "supported": list(SUPPORTED_INTERFACE_LANGUAGES),
    }


def session_interface_language(session: dict[str, Any]) -> dict[str, Any]:
    """Read the persisted language contract, with a compatible legacy fallback."""
    value = session.get("language")
    if isinstance(value, dict) and value.get("status") in {"confirmed", "pending"}:
        return value
    inferred = resolve_interface_language(str(session.get("brief", "")))
    if inferred["status"] == "pending":
        inferred = {"code": "en", "status": "confirmed", "source": "legacy_fallback", "supported": list(SUPPORTED_INTERFACE_LANGUAGES)}
    return inferred


ZH_UI_LABELS = {
    "layers": {
        "direction": "创作命题与情绪", "worldbuilding": "人物与世界陈设", "narrative": "事件与叙事序列",
        "image": "摄影与成像语言", "delivery": "执行与验证",
    },
    "stages": {
        "character": "人物", "world": "世界", "scene": "场景", "photo": "摄影",
        "direction": "创作命题与情绪", "worldbuilding": "人物与世界陈设", "narrative": "事件与叙事序列",
        "image": "摄影与成像语言", "delivery": "执行与验证",
    },
    "types": {
        "character": "人物资源", "style": "摄影风格资源", "environment": "环境资源", "lighting": "灯光资源",
        "composition": "构图资源", "shot": "镜头资源", "qa": "质量检查资源",
    },
    "scopes": {"project": "当前项目", "personal": "我的资源库", "extension": "社区扩展库", "official": "官方资源库"},
    "status": {"proposed": "待确认", "confirmed": "已确认", "pending": "待处理"},
    "source": {
        "proposed_from_brief": "根据创作描述提出", "derived_from_dna": "根据已选资源推导",
        "system_policy": "根据执行规则设定", "creator_confirmed": "创作者已确认",
        "automatic_default": "全自动方案",
    },
    "qa": {
        "visual_qa_pending": "等待视觉检查", "static_validated": "结构检查通过",
        "visual_qa_passed": "视觉检查通过", "not_applicable_semantic_card": "语义卡检查完成",
    },
    "value_keys": {
        "theme_statement": "主题命题", "subject_matter": "画面主体", "central_tension": "核心张力",
        "set_strategy": "套片组织策略", "scene_strategy": "场景组织方式", "scene_count": "场景数量",
        "scene_chapters": "场景章节", "styling_strategy": "妆造组织方式", "look_count": "妆造数量",
        "look_chapters": "妆造章节", "transition_rule": "切换规则", "pose_strategy": "动作与姿态策略",
        "pose_states": "动作与姿态计划", "chapter_plan": "章节计划", "variation_axes": "变化维度",
        "continuity_axes": "保持维度", "focal_length_strategy": "焦段组织方式", "focal_length_plan": "焦段计划",
        "perspective_plan": "透视目的", "variation_checks": "变化检查", "continuity_checks": "连续性检查",
        "primary_tone": "主情绪", "secondary_tones": "辅助情绪", "undertone": "潜在情绪", "valence": "情绪倾向",
        "arousal": "唤醒程度", "expression": "表达强度", "energy": "运动能量", "tension": "张力状态", "arc": "情绪弧线",
        "start": "开始", "turn": "转折", "end": "结束", "identity": "人物身份", "representation": "呈现媒介",
        "presence": "人物气质", "styling_versatility": "妆造适配", "variable_styling_traits": "可变妆造项",
        "identity_locks": "身份锁定", "space": "空间", "time": "时间", "materials": "材质", "physical_rules": "物理规则",
        "continuity": "连续性", "wardrobe": "服装", "grooming": "妆发", "props": "道具", "ownership_policy": "道具归属",
        "inciting_action": "起始动作", "state_changes": "状态变化", "consequences": "后续结果", "strategy": "序列策略",
        "rhythm": "节奏", "progression": "推进阶段", "shot_count": "镜头数量", "viewpoint": "观看视点", "coverage": "镜头覆盖",
        "framing_language": "景别语言", "lens_language": "镜头语言", "composition": "构图关系", "source": "光源",
        "direction": "方向", "quality": "光线质感", "contrast": "反差", "time_phase": "时间阶段",
        "photographic_genre": "摄影类型", "visual_rhetoric": "视觉修辞", "texture": "质感", "realism": "真实感",
        "palette": "色彩组合", "temperature": "色温", "saturation": "饱和度", "contrast_curve": "影调曲线", "grain": "颗粒",
        "sharpness": "锐度", "dynamic_range": "动态范围", "skin_tone_policy": "肤色规则", "one_job_one_image": "单镜单图",
        "output_count": "输出数量", "aspect_ratio": "画面比例", "size": "请求尺寸", "format": "文件形式",
        "required_checks": "必查项目", "reject_if": "拒绝条件", "human_visual_qa": "人工视觉检查",
        "scene_plan": "九镜场景方案", "makeup_plan": "九镜妆容方案", "hair_plan": "九镜发型方案",
        "wardrobe_plan": "九镜服装方案", "face_orientation_plan": "九镜面部朝向", "body_orientation_plan": "九镜身体朝向",
        "composition_plan": "九镜构图方案", "lighting_plan": "九镜灯光方案",
    },
}

ZH_UI_TERMS = {
    "quiet_joy": "安静的喜悦", "tenderness": "温柔", "serenity": "宁静", "hope": "希望", "nostalgia": "怀旧",
    "melancholy": "忧郁", "sorrow": "悲伤", "tension": "紧张", "mystery": "神秘", "solemnity": "庄重", "contemplative": "沉思",
    "anticipation": "期待", "intimacy": "亲密", "relief": "释然", "longing": "向往", "hesitation": "犹疑", "loneliness": "孤独",
    "loss": "失落", "unease": "不安", "awe": "敬畏", "none": "无", "positive": "正向", "negative": "负向", "mixed": "复合",
    "neutral": "中性", "low": "低", "medium": "中", "high": "高", "restrained": "克制", "clear": "清晰", "intense": "强烈",
    "still": "静止", "slow": "缓慢", "flowing": "流动", "urgent": "急促", "stable": "稳定", "suspended": "悬置",
    "rising": "上升", "released": "释放", "arrival": "进入", "attention": "凝视", "stillness": "静止", "distance": "疏离",
    "approach": "靠近", "uncertainty": "不确定", "opening": "打开", "possibility": "可能", "encounter": "相遇", "memory": "回忆",
    "aftertaste": "余韵", "quiet": "沉静", "absence": "缺席", "resistance": "抗拒", "recognition": "确认", "acceptance": "接受",
    "warning": "预兆", "escalation": "升级", "suspension": "悬停", "trace": "线索", "revelation": "显现", "unresolved": "未决",
    "preparation": "准备", "ritual": "仪式", "observation": "观察", "decision": "决定", "release": "释放",
    "one stable fictional adult identity": "一个稳定的虚构成年人物身份",
    "one poised fictional East Asian adult female protagonist": "一位气质鲜明的虚构东亚成年女主角",
    "one poised fictional East Asian adult male protagonist": "一位气质鲜明的虚构东亚成年男主角",
    "real adult human in live-action photography": "真人成年人的实拍摄影呈现",
    "poised, distinctive, and camera-confident": "气质鲜明、从容，并具有稳定的镜头表现力",
    "supports classical, contemporary, editorial, and ceremonial styling without identity substitution": "能够适配古典、当代、编辑与仪式感妆造，同时不发生身份替换",
    "makeup": "妆容", "hairstyle": "发型", "wardrobe": "服装", "era styling": "时代造型",
    "face geometry": "面部结构", "age band": "年龄区间", "skin characteristics": "皮肤特征", "hair": "发型",
    "hair color and hairline": "发色与发际线", "body proportions": "身体比例",
    "one coherent live-action photographic world": "一个连贯的真人摄影世界",
    "the visible situation must reveal a change rather than a decorative pose": "画面必须揭示真实变化，而不是停留在装饰性摆姿",
    "one coherent physical location": "一个连续统一的真实空间", "one continuous time phase": "一个连续的时间阶段",
    "photographically plausible materials": "符合摄影真实感的材质", "consistent geometry": "一致的空间几何", "gravity": "重力",
    "reflection": "反射关系", "material response": "材质受光反应", "location": "地点", "weather": "天气", "object placement": "物体位置",
    "one locked wardrobe look unless a declared event changes it": "一套锁定服装，除非事件明确改变", "consistent across the sequence": "整组保持一致",
    "every prop has one declared owner, location and state": "每件道具都有明确的归属、位置与状态",
    "one observable action initiates the sequence": "以一个可观察动作启动序列", "each major action leaves a visible consequence": "每个关键动作都留下可见结果",
    "later Jobs inherit the changed state": "后续镜头继承已经发生的状态变化", "distinct functional progression": "具有不同职能的递进序列",
    "measured progression with no duplicate shot function": "克制推进，镜头职能不重复", "one coherent physical camera position per Job": "每个镜头只有一个连贯机位",
    "physically plausible perspective without arbitrary lens drift": "透视符合物理规律，镜头语言不随意漂移",
    "one motivated key source with declared practical or ambient support": "一个有动机的主光源，并由明确的环境光辅助",
    "consistent with the world": "与世界设定一致", "physically plausible softness and falloff": "软硬与衰减符合物理规律",
    "motivated by the emotional direction": "由情绪方向决定", "continuous unless the sequence declares a transition": "除非序列明确转场，否则时间保持连续",
    "direction, shadow and exposure remain traceable": "方向、阴影与曝光关系可以追溯", "restrained live-action editorial photography": "克制的真人编辑摄影",
    "world-led rather than effect-led": "由世界关系主导，而非由效果主导", "photographic material detail": "摄影材质细节", "live-action photographic realism": "真人实拍摄影真实感",
    "world-derived base colors": "来自世界材质的基础色", "one restrained accent": "一个克制的强调色", "motivated by light and emotional arc": "由光线与情绪弧线决定",
    "controlled": "受控", "preserve skin and material latitude": "保留肤色与材质层次", "subtle photographic grain": "轻微摄影颗粒",
    "natural detail without synthetic oversharpening": "自然细节，不做人工过度锐化", "retain highlight and shadow information": "保留高光与暗部信息",
    "natural and stable across all Jobs": "全部镜头中的肤色自然且稳定", "not_guaranteed": "不保证具体像素", "png_requested": "请求无损图片文件",
    "high_requested": "请求高质量", "pending until evidence": "等待生成结果后检查",
    "identity": "身份", "live-action medium": "真人摄影媒介", "anatomy and hands": "人体结构与手部", "world geometry": "空间几何",
    "prop ownership": "道具归属", "lighting": "灯光", "color": "色彩", "shot intent": "镜头意图", "rights": "权利信息",
    "illustrated person": "插画人物", "identity drift": "身份漂移", "anatomy failure": "人体结构错误", "prop duplication": "道具重复",
    "contradictory light": "光线矛盾", "collage or text": "拼图或文字", "creator intent": "创作者意图", "rights provenance": "权利来源",
    "subject identity": "人物身份", "stable identity": "稳定身份", "adult age": "成年年龄", "natural anatomy": "自然人体结构",
    "distinctive personal presence": "鲜明而稳定的人物气质", "facial presence and styling compatibility": "面部气质与妆造适配",
    "physical causality": "物理因果", "wardrobe continuity": "服装连续性", "material continuity": "材质连续性", "world physics": "世界物理规则",
    "event consequences": "事件后果", "shot order": "镜头顺序", "required action visibility": "关键动作可见", "skin tone": "肤色", "time continuity": "时间连续性",
    "live-action human medium": "真人实拍媒介", "world material response": "世界材质反应", "light motivation": "光线动机", "material distinctions": "材质区分",
    "unique output filename": "唯一输出文件名", "no grid": "不生成网格", "no text": "不生成文字", "no watermark": "不生成水印",
    "successful outputs are immutable": "已成功结果不可覆盖", "True": "是", "False": "否",
    "chaptered_variation": "章节式丰富变化", "continuous_narrative": "连续叙事",
    "three related sub-scenes inside one coherent photographic world": "同一摄影世界中的三个关联场景",
    "nine distinct scene designs inside one coherent photographic theme": "同一摄影主题中的九个不同场景设计",
    "nine declared scene-light states inside one coherent emotional arc": "统一情绪弧线中的九种场景与灯光状态",
    "one core scene with continuous physical state": "一个保持物理连续的核心场景",
    "threshold_space": "第一章：入口与空间建立", "relation_space": "第二章：关系与事件发展",
    "resolution_space": "第三章：转折与情绪完成", "single_core_scene": "同一核心场景",
    "three coordinated looks, one locked per chapter": "三套相互协调的妆造，每章锁定一套",
    "nine coordinated per-Job wardrobes; facial identity remains unchanged": "九套逐镜协调服装，人物面部身份不变",
    "nine distinct makeup and hair designs; facial identity remains unchanged": "九套不同妆发，人物面部身份不变",
    "one confirmed look locked across the continuous event": "一套已确认妆造贯穿连续事件",
    "three related grooming states, one locked per chapter": "三种相互关联的妆发状态，每章锁定一种",
    "one grooming state continuous across the event": "一种妆发状态贯穿连续事件",
    "look_a_foundation": "第一章：基础妆造", "look_b_development": "第二章：发展妆造",
    "look_c_resolution": "第三章：完成妆造", "look_a_continuous": "同一套连续妆造",
    "look changes only at a declared chapter boundary; identity never changes": "只在已声明的章节边界切换妆造；人物身份始终不变",
    "look changes only when an observable event causes it": "只有可观察事件明确导致时才改变妆造",
    "nine distinct action-led body states with declared hands, gaze and weight": "九种由行动驱动的身体状态，并明确手部、视线与重心",
    "nine causally connected action states inside one continuous event": "同一连续事件中的九种因果相连动作状态",
    "arrival_observation": "进入并观察", "crossing_turn": "行进中转身", "first_contact": "第一次接触",
    "threshold_transition": "跨越场景边界", "prop_interaction": "与叙事道具互动", "contained_reaction": "克制的内在反应",
    "changed_stance": "关系改变后的站姿", "tactile_detail": "手部触感细节", "resolved_presence": "完成情绪后的稳定状态",
    "three chapters of three Jobs": "三章，每章三个独立镜头任务", "one continuous event across nine Jobs": "一个事件连续推进九个独立镜头任务",
    "scene": "场景", "styling": "妆造", "action": "动作", "pose": "姿态", "framing": "景别", "focal length": "焦段",
    "identity": "身份", "world grammar": "世界规则", "photographic medium": "摄影媒介", "color system": "色彩体系",
    "functional multi-focal coverage by shot purpose": "按照镜头职能使用多种焦段",
    "coherent focal family with functional variation": "在统一镜头体系中按职能变化焦段",
    "28 mm environmental wide": "约二十八毫米环境广角", "35 mm full-action perspective": "约三十五毫米全身动作视角",
    "50 mm natural medium perspective": "约五十毫米自然中景", "85 mm emotional close portrait": "约八十五毫米情绪近景",
    "105 mm hand or prop detail": "约一百零五毫米手部或道具细节",
    "environment establishes spatial relation": "环境焦段建立空间关系", "full frame makes body action legible": "全身视角让身体行动清楚可见",
    "medium frame balances subject and world": "中景平衡人物与世界", "close frame reveals restrained emotion": "近景揭示克制情绪",
    "detail frame proves touch, material and consequence": "细节镜头证明触感、材质与事件结果",
    "three scenes are visibly distinct but belong to one world": "三个场景可明确区分，但属于同一世界",
    "three looks are visibly distinct and identity remains stable": "三套妆造可明确区分，人物身份保持稳定",
    "nine scenes are visibly distinct and identity remains stable": "九个场景均可明确区分，人物身份保持稳定",
    "nine looks are visibly distinct and facial identity remains stable": "九套妆造均可明确区分，人物面部身份保持稳定",
    "all nine body states and shot functions are distinct": "九种身体状态和镜头职能均不重复",
    "single scene, look and event state remain continuous": "同一场景、妆造与事件状态保持连续",
    "identity, live-action medium, world physics and color grammar remain coherent": "人物身份、真人摄影媒介、世界物理与色彩体系保持连贯",
}

ZH_ROLE_COPY = {
    "content": ("把创作描述整理为一个具体、可被摄影表达的命题。", ["所有镜头都围绕同一创作命题。", "物体与行动共同服务于核心表达。"], ["创作者意图", "权利来源"], ["无需解释文字也能理解主题。"]),
    "emotion": ("把整体情绪转化为可观察的行为和九镜情绪弧线。", ["主情绪、潜在情绪和表达强度在画面中可见。", "情绪随镜头序列逐步推进。"], ["人物身份", "情绪通过视线、呼吸、动作和距离呈现"], ["不依赖情绪标签也能看出情绪。", "最后一镜完成预设情绪弧线。"]),
    "subject": ("定义谁存在于画面中，以及哪些身份特征不能漂移。", ["全部镜头都能识别为同一位气质鲜明的真实成年主角。", "人物可以适配多种妆发与服装，但换造型不能变成换脸。"], ["稳定身份", "成年年龄", "自然人体结构", "人物的核心气质"], ["全部输出中的人物身份保持连续。", "妆造变化增强人物表达，不得遮盖或替换其身份特征。"]),
    "world": ("构建一个具有持续空间、材质和物理规则的世界。", ["建筑、入口、窗户、反射和物体位置保持物理一致。"], ["空间几何", "物理因果"], ["每个镜头都能被推断为属于同一世界。"]),
    "look": ("把服装、妆发和道具归属定义为世界状态，而不是装饰。", ["服装与妆发保持连续。", "每件道具都有稳定归属，只能通过事件改变状态。"], ["服装连续性", "道具归属", "材质连续性"], ["道具不能无故重复、漂浮或改变归属。"]),
    "event": ("先让可观察事件改变世界状态，再设计人物姿态。", ["动作在物理上清楚可见，并在后续镜头留下结果。"], ["人物身份", "世界物理规则", "道具归属"], ["每个动作都改变或揭示状态，而不是空洞摆姿。"]),
    "sequence": ("把多个观看视点组织成时间、节奏和叙事推进。", ["全部镜头形成可读的递进关系，且职能各不相同。", "信息、距离、动作和情绪随序列发展。"], ["事件后果", "世界连续性", "镜头顺序"], ["不能有两个镜头重复相同叙事职能。"]),
    "camera": ("为每个独立镜头选择必要的观看视点与摄影覆盖。", ["每个镜头都有明确动机的视点和不同构图。"], ["空间几何", "关键动作可见"], ["景别与透视符合镜头职能。"]),
    "light": ("用物理一致的光线让时间、深度、材质和情绪变得可见。", ["光线方向、阴影、衰减和反射属于同一物理系统。"], ["肤色", "空间几何", "时间连续性"], ["不能出现矛盾阴影或无动机的灯光变化。"]),
    "style": ("定义可观察的摄影修辞，不用艺术家姓名代替风格设计。", ["画面呈现有意图、质感连贯的真实摄影语言。"], ["真人实拍媒介", "世界材质反应"], ["风格不能压过身份、物理规律、事件和相机逻辑。"]),
    "color_post": ("把色彩与后期组织为肤色、服装、道具、空间、情绪和时间之间的关系。", ["整组的色彩、肤色、饱和度、反差与颗粒关系保持连贯。"], ["自然肤色", "光线动机", "材质区分"], ["整体滤镜不能破坏肤色、材质和时间关系。"]),
    "job": ("把每个视点冻结为一个独立、可复现的生成任务。", ["每个任务只生成一张可独立使用的图片。"], ["唯一输出文件名", "不生成网格", "不生成文字", "不生成水印"], ["每个任务必须只产生一张独立成图。"]),
    "quality_control": ("定义接受或拒绝每个镜头及整组作品的证据。", ["每个镜头都有模型视觉检查，并保留独立的人工视觉检查。"], ["权利来源", "已成功结果不可覆盖"], ["任何必查项失败都必须拒绝；结构检查不能冒充视觉质量检查。"]),
}


def _contains_latin(value: str) -> bool:
    return bool(re.search(r"[A-Za-z]", value))


def _zh_creator_text(value: str) -> str:
    """Keep a Chinese brief useful while removing English tokens from Chinese cards."""
    text = str(value)
    replacements = (
        (r"\bAPSAL\b", "元素摄影协议"), (r"\bAI\b", "人工智能"), (r"\bDNA\b", "元素资源"),
        (r"\bJSON\b|\bYAML\b", "结构化文件"), (r"\bSkill\b", "技能包"), (r"\bPrompt\b", "提示词"),
        (r"\bCodex\b", "创作助手"), (r"\b4K\b", "超高清"),
    )
    for pattern, replacement in replacements: text = re.sub(pattern, replacement, text, flags=re.I)
    if re.search(r"[\u3400-\u9fff]", text): text = re.sub(r"[A-Za-z][A-Za-z0-9_.+-]*", "相关创作概念", text)
    return text


def _zh_ui_value(value: Any) -> Any:
    if isinstance(value, bool): return "是" if value else "否"
    if isinstance(value, list): return [_zh_ui_value(item) for item in value]
    if isinstance(value, dict): return {ZH_UI_LABELS["value_keys"].get(str(key), str(key)): _zh_ui_value(item) for key, item in value.items()}
    if not isinstance(value, str): return value
    if value in ZH_UI_TERMS: return ZH_UI_TERMS[value]
    if "→" in value:
        return " → ".join(str(_zh_ui_value(item.strip())) for item in value.split("→"))
    if re.fullmatch(r"[0-9]+ distinct viewpoints", value): return value.split()[0] + " 个不同视点"
    if re.fullmatch(r"[0-9]+", value) or not _contains_latin(value): return value
    if re.search(r"[\u3400-\u9fff]", value): return _zh_creator_text(value)
    return "已按当前创作方案设置"


def _display_value(role: str, key: str, value: Any, locale: str) -> Any:
    """Give intentionally empty proposal fields a useful creator-facing meaning."""
    if value == []:
        empty = {
            ("emotion", "secondary_tones"): ("暂不叠加辅助情绪；创作描述出现第二种情绪时再加入", "No secondary tone unless the brief introduces one"),
            ("look", "props"): ("先不添加装饰性道具；确认事件后只配置有叙事作用和明确归属的道具", "No decorative prop yet; add only story-motivated props with clear ownership after the event is confirmed"),
        }.get((role, key), ("当前无需额外项目", "No additional item is needed now"))
        return empty[0] if locale == "zh-CN" else empty[1]
    return _zh_ui_value(value) if locale == "zh-CN" else value


def element_attribute_display(role: str, key: str, value: Any, locale: str) -> tuple[str, Any]:
    """Return one localized Studio attribute without changing its canonical key or value."""
    label = ZH_UI_LABELS["value_keys"].get(key, "创作参数") if locale == "zh-CN" else key
    return label, _display_value(role, key, value, locale)


def _decision_set_strategy(role: str, values: dict[str, Any]) -> str | None:
    for key in ("set_strategy", "scene_strategy", "styling_strategy"):
        if values.get(key) in SET_STRATEGIES: return values[key]
    if values.get("chapter_plan") == "three chapters of three Jobs": return "chaptered_variation"
    if values.get("chapter_plan") == "one continuous event across nine Jobs": return "continuous_narrative"
    if values.get("focal_length_strategy") == "functional multi-focal coverage by shot purpose": return "chaptered_variation"
    if values.get("focal_length_strategy") == "coherent focal family with functional variation": return "continuous_narrative"
    if values.get("pose_strategy") == "nine distinct action-led body states with declared hands, gaze and weight": return "chaptered_variation"
    if values.get("pose_strategy") == "nine causally connected action states inside one continuous event": return "continuous_narrative"
    variation_checks = values.get("variation_checks", [])
    if "three scenes are visibly distinct but belong to one world" in variation_checks: return "chaptered_variation"
    if "nine scenes, nine looks, nine poses, nine gaze and face directions, nine compositions, nine focal lengths and nine lighting designs are distinct" in variation_checks: return "chaptered_variation"
    if "single scene, look and event state remain continuous" in values.get("continuity_checks", []): return "continuous_narrative"
    return None


def _element_proposal_copy(role: str, decision: dict[str, Any], brief: str, locale: str) -> tuple[str, str, list[str]]:
    """Create complete card copy from the actual proposed values, not placeholders."""
    values = decision.get("values", {})
    set_strategy = _decision_set_strategy(role, values)
    chaptered = set_strategy == "chaptered_variation"
    if locale == "zh-CN":
        v = lambda key: str(_display_value(role, key, values.get(key), locale))
        identity = values.get("identity")
        protagonist_zh = "东亚成年男主角" if identity == "one poised fictional East Asian adult male protagonist" else "东亚成年女主角" if identity == "one poised fictional East Asian adult female protagonist" else "虚构成年主角"
        subject_proposal_zh = f"建议默认采用一位气质鲜明、从容且镜头表现力稳定的{protagonist_zh}。人物应能自然适配古典、当代、编辑与仪式感等多种妆发和服装；每次换造型仍必须被识别为同一个人。" if values.get("styling_versatility") else "建议保留当前虚构成年人物身份基线及其既有身份锁；如需新增气质与多妆造适配能力，应建立新的主题或人物资源版本。"
        subject_rationale_zh = "多妆造适配扩大人物资源的复用范围；锁定面部结构、成年年龄、肤质、发色发际线和身体比例，可以防止适配变成换脸。" if values.get("styling_versatility") else "旧会话保持原生成意图，避免插件升级后静默改变已经建立的人物设计。"
        copy = {
            "content": (f"建议把“{_zh_creator_text(brief)}”凝练为一套统一的摄影命题，并默认采用“{'章节式丰富变化' if chaptered else '连续叙事'}”。{'九张图仍分成三章，但九个场景、九套妆造、九种动作姿态、九种眼神与面部朝向、九种构图、九个焦段和九套灯光逐镜不同，只锁定同一个人物面部身份。' if chaptered else '九张图在同一核心场景和同一套妆造中推进一个连续事件，动作、视点与焦段按叙事职能变化。'}", "先确定套片怎样变化，后续场景、妆造、姿态和相机设计才不会在“丰富”与“连续”之间互相冲突。", ["章节式丰富变化（推荐）", "连续叙事"]),
            "emotion": (f"建议以“{v('primary_tone')}”为主情绪，以“{v('undertone')}”为潜在线索；情绪从“{_zh_ui_value(values.get('arc', {}).get('start', ''))}”推进到“{_zh_ui_value(values.get('arc', {}).get('turn', ''))}”，最后落在“{_zh_ui_value(values.get('arc', {}).get('end', ''))}”。", "把情绪拆成强度、能量、张力和进程，可以让九张照片形成变化，而不是九次相同表情。", ["更克制含蓄", "更明朗外放", "加入第二种复合情绪"]),
            "subject": (subject_proposal_zh, subject_rationale_zh, ["古典含蓄妆造", "当代编辑妆造", "礼服与仪式感妆造"] if values.get("styling_versatility") else ["保持现有身份", "建立兼容新版本", "补充明确身份参考"]),
            "world": (("建议逐镜设计九个不同场景，每个场景都有独立空间、材质、景深与物理光线；九镜通过统一主题与真人摄影规则关联，不要求重复同一背景。" if chaptered else "建议锁定一个核心场景，让空间几何、时间、材质、天气、物体位置和事件结果在九个镜头中连续成立。"), "逐镜声明场景才能避免只换姿势不换画面；连续模式则以物理状态的可追溯性建立真实感。", (["强化九场景差异", "调整九镜场景顺序", "保留统一主题线索"] if chaptered else ["强化同一空间连续", "增加同场景内的观看区域", "让物体状态变化更明显"])),
            "look": (("建议逐镜设计九套不同的妆容、发型与服装，并让每套妆造服务于该镜场景和动作；只锁定面部结构、五官、成年年龄、肤质与身体比例，不能换脸。" if chaptered else "建议锁定一套与人物、事件和世界相符的妆发服装贯穿九镜；只有可观察事件明确导致时才允许改变。"), "把妆造明确写入每镜提示词，可以得到真正的九套变化，同时把身份锁与造型变化分开。", (["调整九套妆造关系", "强化逐镜妆造差异", "只保留面部身份锁"] if chaptered else ["保持一套连续妆造", "强化妆造与事件关系", "增加一件推动事件的主道具"])),
            "event": (("建议为九个镜头安排九种不重复的行动与身体状态，逐镜明确重心、手部职责、视线动机、面部朝向和动作结果。" if chaptered else "建议在同一连续事件中安排九种因果相连的行动状态，姿态可以变化，但必须继承前一镜已经发生的结果。"), "先定义行动、手部、视线、面朝与重心，再形成姿态，可以避免九张图只是换背景重复摆拍。", ["更明显的身体运动", "更克制的微动作", "强化手部与道具关系"]),
            "sequence": ((f"建议把{v('shot_count')}个镜头组织成三章，每章三镜；但每一镜的场景、妆发服装、动作姿态、眼神面朝、构图、焦段与灯光都必须不同，仅保持人物面部身份一致。" if chaptered else f"建议把{v('shot_count')}个镜头组织成同一事件的连续推进；场景和妆造保持一致，动作、视点、景别与焦段按镜头职能变化。"), "先声明哪些维度应该变化、哪些必须保持，才能同时获得丰富性和整组一致性。", (["调整三章节奏", "强化章间转折", "让第三章更开放"] if chaptered else ["强化连续因果", "放慢事件节奏", "增加最终余韵"])),
            "camera": (("建议九镜使用九个不同焦段：约二十四、二十八、三十五、四十、五十、六十五、八十五、一百零五和一百三十五毫米；每镜同时声明独立构图与透视目的。" if chaptered else "建议在统一镜头体系中按职能变化焦段：场景、动作、中景、情绪近景与必要细节各自采用可信透视，同时避免无理由跳变。"), "焦段不是装饰数字；每一次变化都必须改变观看距离、空间关系或信息重点。", ["强化环境与空间", "强化人物与动作", "强化情绪与细节"]),
            "light": (("建议九镜分别使用九套有物理来源的灯光设计，并逐镜声明光源、方向、软硬、反差与衰减。" if chaptered else "建议建立一个有物理来源的主光，并让方向、阴影、衰减、曝光和反射在整组中可追溯。"), "可信光线同时解释时间、空间深度、材质和情绪；逐镜不同不等于随机打光。", ["柔和自然光", "更具方向性的戏剧光", "具有时间递进的光线变化"]),
            "style": ("建议采用克制的真人编辑摄影语言，让真实材质、人物状态和世界关系主导画面，风格效果保持在身份与物理规律之后。", "先保证人物和世界可信，再使用摄影修辞，能避免作品被滤镜、插画感或人工质感吞没。", ["更纪实自然", "更精致编辑", "更具电影叙事感"]),
            "color_post": ("建议从肤色、服装、道具和空间材质中建立基础色，只设置一个克制强调色；保留高光暗部、真实肤色与自然细节。", "关系化调色比统一套滤镜更能维持人物身份、材质差异、时间变化和整组连续性。", ["降低饱和度", "强化冷暖关系", "增加轻微胶片质感"]),
            "job": (f"建议冻结为{v('output_count')}个独立镜头任务，每个任务只生成一张{v('aspect_ratio')}成图，并保留唯一文件名和完整提示词。", "单镜单图便于失败重试、身份检查、版本追踪和后续独立使用。", ["现在逐张生成", "只保存完整提示词", "导出可安装技能包"]),
            "quality_control": (("建议逐项检查九个场景、九套妆造、九种姿态动作、九种眼神面朝、九种构图、九个焦段和九套灯光均不重复；只允许人物面部身份、成年年龄、身体比例与真人摄影媒介保持一致。" if chaptered else "建议检查同一场景、同一妆造和连续事件状态是否保持，同时确认九种动作状态与镜头职能没有重复。"), "丰富性与身份一致性是两组不同证据，必须分别验收；结构检查也不能冒充生成结果已经通过视觉检查。", ["变化维度检查", "身份一致性检查", "人工最终验收"]),
        }
        return copy[role]
    identity = values.get("identity")
    protagonist_en = "East Asian adult male protagonist" if identity == "one poised fictional East Asian adult male protagonist" else "East Asian adult female protagonist" if identity == "one poised fictional East Asian adult female protagonist" else "fictional adult protagonist"
    subject_proposal_en = f"Default to a poised, distinctive {protagonist_en} with stable camera presence. The protagonist should support classical, contemporary, editorial, and ceremonial makeup, hair, and wardrobe while remaining unmistakably the same person." if values.get("styling_versatility") else "Preserve the existing fictional adult identity and its current locks. Create a new theme or Character DNA version before adding a new presence and styling-versatility contract."
    subject_rationale_en = "Styling versatility improves reuse; fixed facial geometry, adult age, skin, hair color and hairline, and proportions prevent styling from becoming identity substitution." if values.get("styling_versatility") else "A legacy session keeps its original generation intent instead of silently changing when the plugin is upgraded."
    copy = {
        "content": (f"Build one photographic proposition from “{brief}” and use {'Chaptered Variation' if chaptered else 'Continuous Narrative'} as the set strategy. " + ("Keep three narrative chapters, but make all nine scenes, looks, actions, poses, gazes, face orientations, compositions, focal lengths and lighting designs different; preserve only the same facial identity and real adult person." if chaptered else "Carry one continuous event through the same core scene and confirmed look while action, viewpoint, framing, and focal length vary by narrative function."), "Choosing the set strategy first prevents scene, styling, pose, and camera decisions from contradicting each other about richness versus continuity.", ["Chaptered Variation (recommended)", "Continuous Narrative"]),
        "emotion": (f"Use {values.get('primary_tone')} as the primary tone and {values.get('undertone')} as the undertone, progressing from {values.get('arc', {}).get('start')} through {values.get('arc', {}).get('turn')} to {values.get('arc', {}).get('end')}.", "Separating intensity, energy, tension, and progression prevents nine repeated facial expressions.", ["More restrained", "More openly expressive", "Add a secondary emotional tone"]),
        "subject": (subject_proposal_en, subject_rationale_en, ["Classical restrained styling", "Contemporary editorial styling", "Ceremonial formal styling"] if values.get("styling_versatility") else ["Keep the current identity", "Create a compatible new version", "Add an explicit identity reference"]),
        "world": (("Design nine distinct scenes, each with its own space, materials, depth and physical light, while one photographic theme and the same adult facial identity bind the set." if chaptered else "Lock one core scene whose geometry, time, materials, object positions, and event consequences remain continuous across all nine viewpoints."), "A declared scene plan prevents nine prompts from becoming the same background with different poses.", (["Increase nine-scene contrast", "Reorder the nine scenes", "Strengthen the shared theme clue"] if chaptered else ["Strengthen single-space continuity", "Use more zones inside the same scene", "Make object-state changes clearer"])),
        "look": (("Design nine distinct makeup, hair and wardrobe combinations, one for each Job. Preserve face geometry, facial features, adult age, natural skin identity and body proportions; styling must never become a different person." if chaptered else "Lock one theme-appropriate wardrobe and grooming state across the continuous event; change it only when an observable event causes the change."), "Writing the complete look into every Prompt separates styling variation from facial identity continuity.", (["Adjust the relation among nine looks", "Strengthen per-Job styling contrast", "Preserve facial identity only"] if chaptered else ["Keep one continuous look", "Strengthen styling-event relation", "Add one event-driving hero prop"])),
        "event": (("Plan nine distinct action-led body states. Declare weight, hand function, gaze motivation, face orientation and consequence for every Job." if chaptered else "Plan nine causally connected action states inside one continuous event, inheriting the result of every preceding action."), "Action, hands, gaze, face direction and weight create meaningful pose variety instead of repeated posing against new backgrounds.", ["More full-body motion", "More restrained micro-actions", "Stronger hand-and-prop relation"]),
        "sequence": ((f"Organize {values.get('shot_count')} Jobs as three chapters of three, but require a distinct scene, makeup, hair, wardrobe, action, pose, gaze, face orientation, composition, focal length and lighting design for every Job; preserve the same facial identity." if chaptered else f"Organize {values.get('shot_count')} Jobs as one continuous event; preserve scene and look while viewpoint, action, framing, and focal length vary by function."), "Declaring both variation axes and identity locks produces richness without changing the person.", (["Adjust the three-chapter rhythm", "Strengthen chapter transitions", "Open the final chapter"] if chaptered else ["Strengthen continuous causality", "Slow the event rhythm", "Add a longer final aftertaste"])),
        "camera": (("Use nine distinct focal lengths—about 24, 28, 35, 40, 50, 65, 85, 105 and 135 mm—and pair every one with a different composition and observable perspective purpose." if chaptered else "Use a coherent focal family with functional variation for environment, action, medium relation, emotional close portrait, and necessary detail."), "A focal length is not a decorative number; each change must serve viewpoint, spatial relation, or information priority.", ["More environment and space", "More subject and action", "More emotion and detail"]),
        "light": (("Use nine distinct physically motivated lighting designs and declare source, direction, quality, contrast and falloff for every Job." if chaptered else "Use one physically motivated key source whose direction, shadow, falloff, exposure, and reflections remain traceable."), "Different lighting must still remain physically credible and serve the scene rather than becoming random effects.", ["Soft natural light", "More directional dramatic light", "Time-progressive light"]),
        "style": ("Use restrained live-action editorial photography led by real materials, subject state, and world relations; keep stylistic effects subordinate to identity and physics.", "Securing human and world credibility first prevents filters or synthetic rendering from overwhelming the photograph.", ["More documentary", "More polished editorial", "More cinematic narrative"]),
        "color_post": ("Derive base colors from skin, wardrobe, props, and world materials; use one restrained accent while retaining natural skin, highlight and shadow latitude, and photographic detail.", "Relational grading preserves identity, material differences, time, and set continuity better than a global filter.", ["Lower saturation", "Stronger warm-cool relation", "Subtle film texture"]),
        "job": (f"Freeze {values.get('output_count')} independent {values.get('aspect_ratio')} Jobs, one image per Job, each with a unique filename and complete Prompt.", "Independent Jobs support retry, QA, lineage, and standalone use.", ["Generate one by one now", "Save complete Prompts only", "Export an installable Skill package"]),
        "quality_control": (("Verify that nine scenes, nine looks, nine actions and poses, nine gaze and face directions, nine compositions, nine focal lengths and nine lighting designs are all distinct; only facial identity, adult age, body proportions and live-action medium remain fixed." if chaptered else "Check that one scene, one look, and continuous event state persist while nine body states and shot functions remain distinct."), "Variation evidence and identity evidence are separate acceptance groups; static validation never proves photographic quality.", ["Variation review", "Identity review", "Final human acceptance"]),
    }
    return copy[role]


def _zh_element_presentation(role: str, decision: dict[str, Any], brief: str) -> dict[str, Any]:
    intent, observable, preserve, qa = ZH_ROLE_COPY[role]
    set_strategy = _decision_set_strategy(role, decision.get("values", {}))
    if set_strategy:
        chaptered = set_strategy == "chaptered_variation"
        strategy_copy = {
            "content": (
                ["整组采用章节式丰富变化：九镜逐镜改变场景、妆造、动作、眼神、面朝、构图、焦段与灯光，只锁人物面部身份。" if chaptered else "整组采用连续叙事，同一事件在九镜中持续推进。"],
                ["创作者意图", "人物身份", "真人摄影媒介"],
                ["套片组织策略能够在场景、妆造、动作和相机设计中一致执行。"],
            ),
            "world": (
                ["九个场景可明确区分，并共享同一摄影主题与真实物理规则。" if chaptered else "同一核心场景的几何、时间和物体状态持续成立。"],
                ["空间几何", "物理因果", "世界规则"],
                ["场景按章节变化但不成为无关背景。" if chaptered else "不能出现无原因的场景跳变。"],
            ),
            "look": (
                ["九套妆容、发型与服装逐镜不同，换造型不换脸。" if chaptered else "同一套妆造贯穿连续事件。", "每件道具都有稳定归属和状态。"],
                ["人物面部身份", "成年年龄", "身体比例", "道具归属"],
                ["九套妆造可区分且人物始终为同一人。" if chaptered else "妆造不得无原因漂移。"],
            ),
            "event": (
                ["九种行动与身体状态在重心、手部、视线、面部朝向或动作结果上各不相同。", "每个关键动作都具有明确视觉结果。"],
                ["人物身份", "世界物理规则", "道具归属"],
                ["不能用重复摆姿代替事件推进。"],
            ),
            "sequence": (
                ["三章各含三镜，但九镜的场景、妆造、姿态、眼神面朝、构图、焦段和灯光逐镜不同。" if chaptered else "九镜在同一场景和妆造中形成连续因果。", "信息、距离、动作与情绪持续推进。"],
                ["镜头顺序", "事件后果", "声明的变化维度与保持维度"],
                ["九个镜头不得重复同一叙事职能。"],
            ),
            "camera": (
                ["九镜分别使用九个不同焦段与九种不同构图。", "每次焦段变化都能解释观看距离或信息重点。"],
                ["空间几何", "关键动作可见", "自然透视"],
                ["焦段不能只是数字变化，必须在画面关系中可观察。"],
            ),
            "quality_control": (
                ["九个场景、九套妆造、九种动作姿态、九种眼神面朝、九种构图、九个焦段和九套灯光均有可观察差异。" if chaptered else "动作、姿态、景别与焦段有职能差异。", "同一人物面部身份、成年年龄、身体比例与真人媒介始终稳定。"],
                ["人物面部身份", "权利来源", "视觉检查证据"],
                ["变化性与连续性分别通过检查；人工最终检查仍须保留。"],
            ),
        }
        if role in strategy_copy: observable, preserve, qa = strategy_copy[role]
    if role == "subject" and not decision.get("values", {}).get("styling_versatility"):
        observable, preserve, qa = ["全部镜头都能识别为同一个真实成年人物。"], ["稳定身份", "成年年龄", "自然人体结构"], ["全部输出中的人物身份保持连续。"]
    values = dict(
        element_attribute_display(role, str(key), value, "zh-CN")
        for key, value in decision.get("values", {}).items()
    )
    recommendation, rationale, options = _element_proposal_copy(role, decision, brief, "zh-CN")
    return {
        "role_label": load_semantic_registry()["roles"][role]["zh"],
        "status_label": ZH_UI_LABELS["status"].get(decision.get("status"), "待确认"),
        "source_label": ZH_UI_LABELS["source"].get(decision.get("source"), "根据当前方案设定"),
        "display_recommendation": recommendation, "display_rationale": rationale, "display_options": options,
        "display_intent": intent, "display_values": values, "display_observable": observable,
        "display_must_preserve": preserve, "display_qa_expectations": qa,
    }


def element_display_projection(role: str, decision: dict[str, Any], brief: str, locale: str) -> dict[str, Any]:
    """Return localized, creator-facing element copy for cards and the Studio projection."""
    if locale == "zh-CN":
        return _zh_element_presentation(role, decision, brief)
    recommendation, rationale, options = _element_proposal_copy(role, decision, brief, "en")
    return {
        "role_label": role, "status_label": decision["status"], "source_label": decision["source"],
        "display_recommendation": recommendation, "display_rationale": rationale, "display_options": options,
        "display_intent": decision["intent"],
        "display_values": {
            key: element_attribute_display(role, key, value, "en")[1]
            for key, value in decision["values"].items()
        },
        "display_observable": decision["observable"], "display_must_preserve": decision["must_preserve"],
        "display_qa_expectations": decision["qa_expectations"],
    }
