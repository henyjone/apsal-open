from __future__ import annotations

import hashlib
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

try:
    from apsal_yaml import YamlError, dumps as dump_yaml, loads as load_yaml_text
except ModuleNotFoundError:  # Supports direct importlib loading in tests and embedders.
    _yaml_spec = importlib.util.spec_from_file_location("apsal_yaml", Path(__file__).with_name("apsal_yaml.py"))
    if _yaml_spec is None or _yaml_spec.loader is None:
        raise
    _yaml_module = importlib.util.module_from_spec(_yaml_spec)
    sys.modules[_yaml_spec.name] = _yaml_module
    _yaml_spec.loader.exec_module(_yaml_module)
    YamlError = _yaml_module.YamlError
    dump_yaml = _yaml_module.dumps
    load_yaml_text = _yaml_module.loads

ENGINE_VERSION = "0.12.0"
SEMANTIC_CONTRACT_VERSION = "0.3.0"
DNA_PACK_SCHEMA_VERSION = "0.6.0"
CATEGORIES = ("character", "style", "environment", "lighting", "composition", "shot", "qa")
PROTOCOL_TYPES = ("subject", "world", "style", "look", "emotion", "event", "camera", "light", "color_post", "quality_control", "content", "sequence", "job")
CREATIVE_FIELDS = ("framing", "action", "hands", "gaze", "composition")
COMPILE_TARGETS = ("design", "image", "qa")
INTERACTION_STAGES = ("character", "world", "scene", "photo")
STAGE_TYPES = {
    "character": ("character",),
    "world": ("environment",),
    "scene": ("composition", "shot"),
    "photo": ("style", "lighting"),
}
CREATIVE_LAYERS = ("direction", "worldbuilding", "narrative", "image", "delivery")
LAYER_ROLES = {
    "direction": ("content", "emotion"),
    "worldbuilding": ("subject", "world", "look"),
    "narrative": ("event", "sequence"),
    "image": ("camera", "light", "style", "color_post"),
    "delivery": ("job", "quality_control"),
}
LAYER_TYPES = {
    "direction": (),
    "worldbuilding": ("character", "environment"),
    "narrative": ("composition", "shot"),
    "image": ("style", "lighting"),
    "delivery": ("qa",),
}
SESSION_STATES = (
    "character_pending", "world_pending", "scene_pending", "photo_pending",
    "direction_pending", "worldbuilding_pending", "narrative_pending", "image_pending", "delivery_pending",
    "review_pending", "ready", "generating", "completed", "partial",
)
SUPPORTED_INTERFACE_LANGUAGES = ("zh-CN", "en")
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
SAFE_ID = re.compile(r"^[A-Z][A-Z0-9-]*$")
SAFE_ASSET_ID = re.compile(r"^[A-Z][A-Z0-9_]*$")
SAFE_NAMESPACE = re.compile(r"^[a-z][a-z0-9-]*$")
SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
REFERENCE_USES = {"style", "world", "prop", "wardrobe", "composition", "identity"}
LIVE_ACTION_FORBID = (
    "illustrated_human", "anime", "painting", "3d_rendered_person",
    "mannequin", "doll", "wax_figure", "clay_character",
)
NATIVE_4K_OUTPUT = {
    "aspect_ratio": "9:16", "size": "2160x3840", "quality": "high",
    "format": "png", "provider_native": True,
}
CODEX_IMAGEGEN_OUTPUT = {
    "aspect_ratio": "9:16", "requested_size": "2160x3840", "size": "not_guaranteed",
    "quality": "high_requested", "format": "png_requested", "provider_native": False,
    "generation_surface": "codex_imagegen",
}
DISCOVERY_FACETS = {
    "subject.age", "subject.presentation", "subject.temperament", "subject.identity_mode",
    "world.space", "world.feature", "world.cultural_language", "world.material",
    "lighting.source", "lighting.direction", "lighting.contrast", "lighting.time",
    "style.genre", "style.texture", "style.palette", "style.tempo",
    "narrative.mood", "narrative.function", "camera.coverage",
    "output.aspect_ratio", "output.medium",
}
DISCOVERY_FACET_PREFIXES = {
    "character": ("subject.", "output.medium"), "environment": ("world.",),
    "lighting": ("lighting.",), "style": ("style.", "output.medium"),
    "composition": ("camera.", "narrative.", "output.aspect_ratio"),
    "shot": ("narrative.", "camera."), "qa": ("output.",),
}
FEEDBACK_OUTCOMES = {"accepted", "rejected", "successful", "failed"}
DISCOVERY_STOPWORDS = {"and", "the", "with", "from", "into", "across", "every", "one", "without", "changing", "consistent", "original", "test"}


class ValidationError(ValueError):
    pass


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
    },
    "qa": {
        "visual_qa_pending": "等待视觉检查", "static_validated": "结构检查通过",
        "visual_qa_passed": "视觉检查通过", "not_applicable_semantic_card": "语义卡检查完成",
    },
    "value_keys": {
        "theme_statement": "主题命题", "subject_matter": "画面主体", "central_tension": "核心张力",
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


def _element_proposal_copy(role: str, decision: dict[str, Any], brief: str, locale: str) -> tuple[str, str, list[str]]:
    """Create complete card copy from the actual proposed values, not placeholders."""
    values = decision.get("values", {})
    if locale == "zh-CN":
        v = lambda key: str(_display_value(role, key, values.get(key), locale))
        identity = values.get("identity")
        protagonist_zh = "东亚成年男主角" if identity == "one poised fictional East Asian adult male protagonist" else "东亚成年女主角" if identity == "one poised fictional East Asian adult female protagonist" else "虚构成年主角"
        subject_proposal_zh = f"建议默认采用一位气质鲜明、从容且镜头表现力稳定的{protagonist_zh}。人物应能自然适配古典、当代、编辑与仪式感等多种妆发和服装；每次换造型仍必须被识别为同一个人。" if values.get("styling_versatility") else "建议保留当前虚构成年人物身份基线及其既有身份锁；如需新增气质与多妆造适配能力，应建立新的主题或人物资源版本。"
        subject_rationale_zh = "多妆造适配扩大人物资源的复用范围；锁定面部结构、成年年龄、肤质、发色发际线和身体比例，可以防止适配变成换脸。" if values.get("styling_versatility") else "旧会话保持原生成意图，避免插件升级后静默改变已经建立的人物设计。"
        copy = {
            "content": (f"建议把“{_zh_creator_text(brief)}”凝练为一套统一的摄影命题：九个镜头都围绕一次可见的变化展开，避免只有漂亮画面而没有关系。", "先锁定作品真正表达什么，人物、空间、物体和摄影语言才会朝同一方向工作。", ["强化人物内在选择", "强化空间关系", "强化物件线索"]),
            "emotion": (f"建议以“{v('primary_tone')}”为主情绪，以“{v('undertone')}”为潜在线索；情绪从“{_zh_ui_value(values.get('arc', {}).get('start', ''))}”推进到“{_zh_ui_value(values.get('arc', {}).get('turn', ''))}”，最后落在“{_zh_ui_value(values.get('arc', {}).get('end', ''))}”。", "把情绪拆成强度、能量、张力和进程，可以让九张照片形成变化，而不是九次相同表情。", ["更克制含蓄", "更明朗外放", "加入第二种复合情绪"]),
            "subject": (subject_proposal_zh, subject_rationale_zh, ["古典含蓄妆造", "当代编辑妆造", "礼服与仪式感妆造"] if values.get("styling_versatility") else ["保持现有身份", "建立兼容新版本", "补充明确身份参考"]),
            "world": ("建议先建立一个空间几何、时间、材质和物体位置都能持续成立的真实世界，再让九个镜头从不同位置观看它。", "稳定的世界让镜头变化看起来像同一现实中的连续观看，而不是九张互不相关的背景图。", ["强化室内空间层次", "强化室内外关系", "强化时间与天气变化"]),
            "look": ("建议为当前主题锁定一套与人物、事件和世界相符的妆发服装，并只保留有叙事作用、归属明确的道具。人物的多妆造能力用于未来主题或有因果依据的换装段落，不用于本组无理由漂移。", "把妆造和道具当作世界状态，能够同时保留人物复用能力与本组作品的连续性。", ["更简洁的妆造", "更强的时代特征", "增加一件推动事件的主道具"]),
            "event": ("建议用一个可见动作启动故事，并让每个关键动作都在空间、人物或道具上留下后续镜头可以继承的结果。", "先有事件后有姿态，人物才是在世界中行动，而不是在不同背景前重复摆拍。", ["人物主动触发", "环境变化触发", "道具状态触发"]),
            "sequence": (f"建议把{v('shot_count')}个镜头组织成“建立—靠近—触发—发展—内化—揭示—转折—释放—完成”的递进，每一镜承担不同职能。", "明确镜头职能和结果继承，可以减少重复景别、无意义动作与连续性漂移。", ["更舒缓的游观节奏", "更强的戏剧转折", "更开放的余韵结尾"]),
            "camera": ("建议根据每一镜的叙事任务选择机位、景别、透视与留白；环境、全身、中景、近景和细节只在真正需要时出现。", "相机不是套用镜头清单，而是决定观众在何处、以多远距离理解正在发生的事。", ["更亲近人物", "更强调环境", "更突出动作细节"]),
            "light": ("建议建立一个有物理来源的主光，并让方向、阴影、衰减、曝光和反射在整组中可追溯；反差随情绪推进，而不是随机改变。", "可信光线同时解释时间、空间深度、材质和情绪，是世界连续性的核心证据。", ["柔和自然光", "更具方向性的戏剧光", "具有时间递进的光线变化"]),
            "style": ("建议采用克制的真人编辑摄影语言，让真实材质、人物状态和世界关系主导画面，风格效果保持在身份与物理规律之后。", "先保证人物和世界可信，再使用摄影修辞，能避免作品被滤镜、插画感或人工质感吞没。", ["更纪实自然", "更精致编辑", "更具电影叙事感"]),
            "color_post": ("建议从肤色、服装、道具和空间材质中建立基础色，只设置一个克制强调色；保留高光暗部、真实肤色与自然细节。", "关系化调色比统一套滤镜更能维持人物身份、材质差异、时间变化和整组连续性。", ["降低饱和度", "强化冷暖关系", "增加轻微胶片质感"]),
            "job": (f"建议冻结为{v('output_count')}个独立镜头任务，每个任务只生成一张{v('aspect_ratio')}成图，并保留唯一文件名和完整提示词。", "单镜单图便于失败重试、身份检查、版本追踪和后续独立使用。", ["现在逐张生成", "只保存完整提示词", "导出可安装技能包"]),
            "quality_control": ("建议每张图都检查真人媒介、人物身份、气质与妆造适配、人体和手部、空间、道具、灯光、色彩、连续性及镜头职能；模型检查与人工检查分别记录。", "只有把拒绝条件写清楚，结构正确的提示词才不会被误当成视觉结果已经合格。", ["逐镜检查", "整组连续性检查", "人工最终验收"]),
        }
        return copy[role]
    identity = values.get("identity")
    protagonist_en = "East Asian adult male protagonist" if identity == "one poised fictional East Asian adult male protagonist" else "East Asian adult female protagonist" if identity == "one poised fictional East Asian adult female protagonist" else "fictional adult protagonist"
    subject_proposal_en = f"Default to a poised, distinctive {protagonist_en} with stable camera presence. The protagonist should support classical, contemporary, editorial, and ceremonial makeup, hair, and wardrobe while remaining unmistakably the same person." if values.get("styling_versatility") else "Preserve the existing fictional adult identity and its current locks. Create a new theme or Character DNA version before adding a new presence and styling-versatility contract."
    subject_rationale_en = "Styling versatility improves reuse; fixed facial geometry, adult age, skin, hair color and hairline, and proportions prevent styling from becoming identity substitution." if values.get("styling_versatility") else "A legacy session keeps its original generation intent instead of silently changing when the plugin is upgraded."
    copy = {
        "content": (f"Build one photographic proposition from “{brief}”: every shot should reveal one visible change rather than becoming an unrelated beautiful pose.", "A fixed proposition makes subject, world, objects, and photographic language work toward the same meaning.", ["Emphasize an inner decision", "Emphasize spatial relationships", "Emphasize an object clue"]),
        "emotion": (f"Use {values.get('primary_tone')} as the primary tone and {values.get('undertone')} as the undertone, progressing from {values.get('arc', {}).get('start')} through {values.get('arc', {}).get('turn')} to {values.get('arc', {}).get('end')}.", "Separating intensity, energy, tension, and progression prevents nine repeated facial expressions.", ["More restrained", "More openly expressive", "Add a secondary emotional tone"]),
        "subject": (subject_proposal_en, subject_rationale_en, ["Classical restrained styling", "Contemporary editorial styling", "Ceremonial formal styling"] if values.get("styling_versatility") else ["Keep the current identity", "Create a compatible new version", "Add an explicit identity reference"]),
        "world": ("Establish one physically coherent world whose geometry, time, materials, and object positions persist across every viewpoint.", "A stable world makes nine viewpoints feel like continuous observation rather than unrelated backgrounds.", ["Richer interior depth", "Stronger indoor-outdoor relation", "More visible time or weather progression"]),
        "look": ("Lock one theme-appropriate wardrobe, grooming, and prop state for this set. Use the protagonist's broader styling versatility across future themes or causally justified changes, never as unexplained drift.", "Treating styling and props as world state preserves both character reuse and sequence continuity.", ["Simpler styling", "Stronger period character", "One event-driving hero prop"]),
        "event": ("Start with one visible action and make every major action leave a consequence inherited by later shots.", "Event before pose makes the subject act inside a world instead of repeating poses against changing backgrounds.", ["Subject-triggered event", "Environment-triggered event", "Prop-state event"]),
        "sequence": (f"Organize {values.get('shot_count')} shots as establish, approach, trigger, develop, interiorize, reveal, turn, release, and resolve, with one distinct function per shot.", "Distinct functions and inherited consequences reduce repeated framing, empty action, and continuity drift.", ["Slower contemplative rhythm", "Stronger dramatic turn", "More open-ended resolution"]),
        "camera": ("Choose position, framing, perspective, and negative space from each shot's narrative need; use environmental, full, medium, close, and detail coverage only when motivated.", "The camera defines where the viewer stands and how much of the event and world can be understood.", ["Closer to the subject", "More environmental context", "More action detail"]),
        "light": ("Use one physically motivated key source whose direction, shadow, falloff, exposure, and reflections remain traceable; let contrast evolve with emotion, not randomly.", "Credible light is evidence for time, depth, material, emotion, and continuity.", ["Soft natural light", "More directional dramatic light", "Time-progressive light"]),
        "style": ("Use restrained live-action editorial photography led by real materials, subject state, and world relations; keep stylistic effects subordinate to identity and physics.", "Securing human and world credibility first prevents filters or synthetic rendering from overwhelming the photograph.", ["More documentary", "More polished editorial", "More cinematic narrative"]),
        "color_post": ("Derive base colors from skin, wardrobe, props, and world materials; use one restrained accent while retaining natural skin, highlight and shadow latitude, and photographic detail.", "Relational grading preserves identity, material differences, time, and set continuity better than a global filter.", ["Lower saturation", "Stronger warm-cool relation", "Subtle film texture"]),
        "job": (f"Freeze {values.get('output_count')} independent {values.get('aspect_ratio')} Jobs, one image per Job, each with a unique filename and complete Prompt.", "Independent Jobs support retry, QA, lineage, and standalone use.", ["Generate one by one now", "Save complete Prompts only", "Export an installable Skill package"]),
        "quality_control": ("Check live-action medium, identity, presence and styling fit, anatomy and hands, world, props, light, color, continuity, and shot function for every image; record model and human review separately.", "Explicit rejection rules prevent a structurally valid Prompt from being mistaken for a visually accepted result.", ["Per-shot review", "Set continuity review", "Final human acceptance"]),
    }
    return copy[role]


def _zh_element_presentation(role: str, decision: dict[str, Any], brief: str) -> dict[str, Any]:
    intent, observable, preserve, qa = ZH_ROLE_COPY[role]
    if role == "subject" and not decision.get("values", {}).get("styling_versatility"):
        observable, preserve, qa = ["全部镜头都能识别为同一个真实成年人物。"], ["稳定身份", "成年年龄", "自然人体结构"], ["全部输出中的人物身份保持连续。"]
    values = {
        ZH_UI_LABELS["value_keys"].get(str(key), "创作参数"): _display_value(role, str(key), value, "zh-CN")
        for key, value in decision.get("values", {}).items()
    }
    recommendation, rationale, options = _element_proposal_copy(role, decision, brief, "zh-CN")
    return {
        "role_label": load_semantic_registry()["roles"][role]["zh"],
        "status_label": ZH_UI_LABELS["status"].get(decision.get("status"), "待确认"),
        "source_label": ZH_UI_LABELS["source"].get(decision.get("source"), "根据当前方案设定"),
        "display_recommendation": recommendation, "display_rationale": rationale, "display_options": options,
        "display_intent": intent, "display_values": values, "display_observable": observable,
        "display_must_preserve": preserve, "display_qa_expectations": qa,
    }


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def plugin_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: expected a JSON object")
    return value


def load_document(path: Path) -> dict[str, Any]:
    """Load canonical JSON or safe authoring YAML into the same data model."""
    suffixes = path.name.lower()
    if suffixes.endswith((".yaml", ".yml")):
        value = load_yaml_text(path.read_text(encoding="utf-8"))
    elif suffixes.endswith(".json"):
        value = json.loads(path.read_text(encoding="utf-8"))
    else:
        raise ValidationError(f"{path}: expected .json, .yaml, or .yml")
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: expected an object at the document root")
    return value


def write_canonical_json(value: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_semantic_registry() -> dict[str, Any]:
    return load_json(plugin_root() / "assets" / "semantics" / "registry.json")


def load_recommendation_registry() -> dict[str, Any]:
    return load_json(plugin_root() / "assets" / "semantics" / "recommendation.json")


def load_creative_layers() -> dict[str, Any]:
    return load_json(plugin_root() / "assets" / "semantics" / "creative-layers.json")


def allowed_semantic_tags() -> set[str]:
    return {item["id"] for item in load_semantic_registry().get("tags", [])}


def load_catalog() -> dict[str, Any]:
    return load_json(plugin_root() / "assets" / "dna" / "catalog.json")


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def apsal_home() -> Path:
    """Return the user-owned APSAL data root without creating it."""
    configured = os.environ.get("APSAL_HOME")
    return Path(configured).expanduser().resolve() if configured else (Path.home() / ".apsal").resolve()


def _safe_part(value: str, label: str) -> str:
    if not SAFE_COMPONENT.fullmatch(value) or value in {".", ".."}:
        raise ValidationError(f"{label}: unsafe path component")
    return value


def _inside(root: Path, candidate: Path) -> Path:
    root = root.expanduser().resolve()
    candidate = candidate.expanduser().resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValidationError(f"path escapes APSAL root: {candidate}") from exc
    return candidate


def _write_private_json(value: dict[str, Any], path: Path) -> None:
    write_canonical_json(value, path)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _mkdir_private(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass


def project_root_from(start: Path | None = None) -> Path:
    """Discover an initialized APSAL project, otherwise use the supplied directory."""
    current = (start or Path.cwd()).expanduser().resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".apsal" / "project.json").is_file():
            return candidate
    return current


def init_workspace(project_root: Path, home: Path | None = None) -> dict[str, str]:
    """Initialize local-first APSAL storage. Existing files are never overwritten."""
    project_root = project_root.expanduser().resolve()
    home = (home or apsal_home()).expanduser().resolve()
    _mkdir_private(home)
    for relative in ("registry", "extensions", "usage", "vault", "vault/sha256", "cache"):
        _mkdir_private(_inside(home, home / relative))
    workspace = project_root / ".apsal"
    _mkdir_private(workspace)
    for relative in ("drafts", "registry", "themes", "runs", "cache"):
        _mkdir_private(_inside(workspace, workspace / relative))
    project_file = workspace / "project.json"
    if not project_file.exists():
        _write_private_json({
            "schema_version": "0.6.0", "project_id": f"PROJECT-{uuid.uuid4().hex[:12].upper()}",
            "created_at": _utc_now(), "storage": "local_first",
        }, project_file)
    ignore = workspace / ".gitignore"
    if not ignore.exists():
        ignore.write_text("drafts/\nruns/\ncache/\nvault/\n", encoding="utf-8")
    return {"project_root": str(project_root), "workspace": str(workspace), "apsal_home": str(home)}


def _asset_key(asset: dict[str, Any]) -> tuple[str, str, str, str]:
    return tuple(str(asset.get(key, "")) for key in ("namespace", "id", "type", "version"))  # type: ignore[return-value]


def _ref_label(key: tuple[str, str, str, str]) -> str:
    namespace, asset_id, asset_type, version = key
    return f"{namespace}/{asset_id}@{version} ({asset_type})"


def _official_preview_index() -> dict[tuple[str, str, str, str], dict[str, Any]]:
    path = plugin_root() / "assets" / "previews" / "catalog.json"
    if not path.is_file():
        return {}
    value = load_json(path)
    result: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for item in value.get("previews", []):
        ref = item.get("ref", {})
        result[tuple(str(ref.get(key, "")) for key in ("namespace", "id", "type", "version"))] = item
    return result


def _webp_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValidationError("preview image must be WebP")
    chunk = data[12:16]
    if chunk == b"VP8X":
        return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
    if chunk == b"VP8 ":
        marker = data.find(b"\x9d\x01\x2a", 20)
        if marker < 0 or marker + 7 > len(data):
            raise ValidationError("invalid VP8 preview")
        return struct.unpack_from("<H", data, marker + 3)[0] & 0x3FFF, struct.unpack_from("<H", data, marker + 5)[0] & 0x3FFF
    if chunk == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    raise ValidationError("unsupported WebP preview encoding")


def validate_preview_file(image: Path, metadata: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not image.is_file():
        return [f"preview: missing image {image}"]
    data = image.read_bytes()
    try:
        width, height = _webp_dimensions(data)
    except ValidationError as exc:
        return [f"preview {image.name}: {exc}"]
    if (width, height) != (768, 576):
        errors.append(f"preview {image.name}: expected 768x576, got {width}x{height}")
    if len(data) > 300_000:
        errors.append(f"preview {image.name}: exceeds 300 KB")
    actual = hashlib.sha256(data).hexdigest()
    if metadata.get("sha256") != actual:
        errors.append(f"preview {image.name}: SHA-256 mismatch")
    for key in ("license", "status", "attribution"):
        if not metadata.get("rights", {}).get(key):
            errors.append(f"preview {image.name}: missing rights.{key}")
    if not metadata.get("qa_status") or not metadata.get("visual_qa_status"):
        errors.append(f"preview {image.name}: QA status is required")
    if metadata.get("disclaimer") != "Design preview; not generated-image quality evidence.":
        errors.append(f"preview {image.name}: design-preview disclaimer is required")
    return errors


def validate_official_previews() -> list[str]:
    errors: list[str] = []
    assets = load_catalog().get("assets", [])
    previews = _official_preview_index()
    for asset in assets:
        key = _asset_key(asset)
        item = previews.get(key)
        if not item:
            errors.append(f"preview catalog: missing {_ref_label(key)}"); continue
        if item.get("ref", {}).get("content_digest") != digest(asset):
            errors.append(f"preview catalog: DNA digest mismatch for {_ref_label(key)}")
        image = plugin_root() / "assets" / "previews" / str(item.get("image", ""))
        errors.extend(validate_preview_file(image, item))
    extra = set(previews) - {_asset_key(asset) for asset in assets}
    if extra:
        errors.append(f"preview catalog: unknown references {[ _ref_label(key) for key in sorted(extra) ]}")
    return errors


def _registry_asset_dirs(project_root: Path, home: Path) -> list[tuple[str, Path]]:
    roots = [("project", project_root / ".apsal" / "registry"), ("personal", home / "registry")]
    extensions = home / "extensions"
    if extensions.is_dir():
        roots.extend(("extension", path) for path in sorted(extensions.glob("*/*/*/registry")) if path.is_dir())
    return roots


def _iter_registry_assets(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(path for path in root.rglob("asset.apsal.json") if path.is_file())


def validate_registry_asset(asset: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = (
        "schema_version", "namespace", "id", "type", "version", "status", "parent_version",
        "changed_fields", "change_summary", "prompt_fragment", "negative_fragment", "rights", "qa_status",
    )
    for key in required:
        if key not in asset: errors.append(f"DNA asset: missing {key}")
    if not SAFE_NAMESPACE.fullmatch(str(asset.get("namespace", ""))): errors.append("DNA asset: invalid namespace")
    if not SAFE_ASSET_ID.fullmatch(str(asset.get("id", ""))): errors.append("DNA asset: invalid id")
    if asset.get("type") not in CATEGORIES: errors.append("DNA asset: unsupported type")
    if not SEMVER.fullmatch(str(asset.get("version", ""))): errors.append("DNA asset: invalid version")
    if not isinstance(asset.get("changed_fields"), list) or not asset.get("changed_fields"):
        errors.append("DNA asset: changed_fields cannot be empty")
    rights = asset.get("rights", {})
    for key in ("license", "status", "attribution"):
        if not rights.get(key): errors.append(f"DNA asset: missing rights.{key}")
    if "discovery" in asset:
        errors.extend(validate_discovery_metadata(asset["discovery"]))
        semantic_registry = load_semantic_registry(); mapped_roles = set(semantic_registry.get("dna_to_protocol", {}).get(asset.get("type"), []))
        tag_roles = {item["id"]: set(item.get("roles", [])) for item in semantic_registry.get("tags", [])}
        incompatible = [tag for tag in asset["discovery"].get("semantic_tags", []) if not (tag_roles.get(tag, set()) & mapped_roles)] if isinstance(asset["discovery"], dict) else []
        if incompatible: errors.append(f"DNA discovery: tags incompatible with {asset.get('type')} DNA {sorted(incompatible)}")
        allowed_prefixes = DISCOVERY_FACET_PREFIXES.get(asset.get("type"), ())
        incompatible_facets = [key for key in asset["discovery"].get("facets", {}) if not any(key.startswith(prefix) for prefix in allowed_prefixes)] if isinstance(asset["discovery"], dict) and isinstance(asset["discovery"].get("facets"), dict) else []
        if incompatible_facets: errors.append(f"DNA discovery: facets incompatible with {asset.get('type')} DNA {sorted(incompatible_facets)}")
    return errors


def validate_discovery_metadata(value: Any) -> list[str]:
    if not isinstance(value, dict): return ["DNA discovery: must be an object"]
    errors: list[str] = []
    tags = value.get("semantic_tags")
    if not isinstance(tags, list) or not tags or any(not isinstance(tag, str) for tag in tags):
        errors.append("DNA discovery: semantic_tags must be a non-empty string array")
    else:
        if len(tags) != len(set(tags)): errors.append("DNA discovery: semantic_tags must be unique")
        unknown = set(tags) - allowed_semantic_tags()
        if unknown: errors.append(f"DNA discovery: unknown semantic_tags {sorted(unknown)}")
    facets = value.get("facets")
    if not isinstance(facets, dict):
        errors.append("DNA discovery: facets must be an object")
    else:
        unknown_facets = set(facets) - DISCOVERY_FACETS
        if unknown_facets: errors.append(f"DNA discovery: unknown facets {sorted(unknown_facets)}")
        for key, facet_value in facets.items():
            values = facet_value if isinstance(facet_value, list) else [facet_value]
            if not values or any(not isinstance(item, str) or not item.strip() for item in values):
                errors.append(f"DNA discovery: facet {key} must contain non-empty strings")
    keywords = value.get("keywords", [])
    if not isinstance(keywords, list) or len(keywords) > 32 or any(not isinstance(item, str) or not item.strip() for item in keywords):
        errors.append("DNA discovery: keywords must be an array of at most 32 non-empty strings")
    if value.get("source") not in {"auto", "creator_confirmed"}:
        errors.append("DNA discovery: source must be auto or creator_confirmed")
    return errors


def _detect_recommendation_context(text: str) -> dict[str, Any]:
    folded = text.casefold(); tags: set[str] = set(); facets: dict[str, set[str]] = {}; signals: list[str] = []
    for signal in load_recommendation_registry().get("signals", []):
        if any(str(term).casefold() in folded for term in signal.get("terms", [])):
            signals.append(signal["id"]); tags.update(signal.get("tags", []))
            for key, value in signal.get("facets", {}).items():
                facets.setdefault(key, set()).add(str(value))
    return {
        "signals": signals, "semantic_tags": sorted(tags),
        "facets": {key: sorted(values) if len(values) > 1 else next(iter(values)) for key, values in sorted(facets.items())},
    }


def suggest_discovery_metadata(asset: dict[str, Any], brief: str = "") -> dict[str, Any]:
    """Suggest deterministic controlled tags; creators confirm or edit before formal save."""
    text = " ".join(str(asset.get(key, "")) for key in ("id", "type", "change_summary", "prompt_fragment", "negative_fragment"))
    context = _detect_recommendation_context(f"{brief} {text}")
    defaults = load_recommendation_registry().get("default_tags", {}).get(asset.get("type"), [])
    semantic_registry = load_semantic_registry(); mapped_roles = set(semantic_registry.get("dna_to_protocol", {}).get(asset.get("type"), []))
    tag_roles = {item["id"]: set(item.get("roles", [])) for item in semantic_registry.get("tags", [])}
    tags = sorted(tag for tag in set(defaults) | set(context["semantic_tags"]) if tag_roles.get(tag, set()) & mapped_roles)
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", text.casefold())
    keywords = sorted(dict.fromkeys(word for word in words if word not in DISCOVERY_STOPWORDS))[:16]
    facet_prefixes = DISCOVERY_FACET_PREFIXES.get(asset.get("type"), ())
    facets = {key: value for key, value in context["facets"].items() if any(key.startswith(prefix) for prefix in facet_prefixes)}
    return {
        "schema_version": "0.6.0", "semantic_tags": tags, "facets": facets,
        "keywords": keywords, "source": "auto", "source_brief_digest": hashlib.sha256(brief.encode()).hexdigest() if brief else "not_reported",
    }


def confirm_discovery_metadata(value: dict[str, Any]) -> dict[str, Any]:
    confirmed = json.loads(json.dumps(value)); confirmed["source"] = "creator_confirmed"
    errors = validate_discovery_metadata(confirmed)
    if errors: raise ValidationError("\n".join(errors))
    return confirmed


def _registry_asset_path(root: Path, asset: dict[str, Any]) -> Path:
    namespace, asset_id, asset_type, version = _asset_key(asset)
    for value, label in ((namespace, "namespace"), (asset_id, "id"), (asset_type, "type"), (version, "version")):
        _safe_part(value, label)
    return _inside(root, root / namespace / asset_type / asset_id / version / "asset.apsal.json")


def _fallback_preview(asset_type: str) -> tuple[Path, dict[str, Any]]:
    asset = next((item for item in load_catalog()["assets"] if item["type"] == asset_type), None)
    if not asset:
        raise ValidationError(f"no official preview fallback for {asset_type}")
    item = _official_preview_index().get(_asset_key(asset))
    if not item:
        raise ValidationError(f"no official preview metadata for {asset_type}")
    return plugin_root() / "assets" / "previews" / item["image"], item


def save_registry_asset(
    asset: dict[str, Any], *, scope: str, project_root: Path, home: Path | None = None,
    preview_path: Path | None = None, preview_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Save an immutable DNA asset and a presentation-only preview sidecar."""
    errors = validate_registry_asset(asset)
    if errors: raise ValidationError("\n".join(errors))
    if scope not in {"project", "personal"}: raise ValidationError("registry scope must be project or personal")
    home = (home or apsal_home()).resolve(); project_root = project_root.resolve()
    init_workspace(project_root, home)
    root = project_root / ".apsal" / "registry" if scope == "project" else home / "registry"
    target = _registry_asset_path(root, asset)
    if target.exists():
        current = load_json(target)
        if digest(current) != digest(asset):
            raise ValidationError(f"immutable DNA conflict for {_ref_label(_asset_key(asset))}")
        return {"scope": scope, "path": str(target), "ref": asset_ref(current), "created": False}
    _mkdir_private(target.parent)
    _write_private_json(asset, target)
    source, fallback = (preview_path, preview_metadata) if preview_path else _fallback_preview(asset["type"])
    if source is None: raise ValidationError("preview source is required")
    source = source.resolve()
    metadata = dict(fallback or {})
    if preview_metadata:
        metadata.update(preview_metadata)
    image_data = source.read_bytes()
    preview_target = target.parent / "preview.webp"
    preview_target.write_bytes(image_data)
    metadata.update({
        "schema_version": "0.1.0", "image": "preview.webp", "sha256": hashlib.sha256(image_data).hexdigest(),
        "ref": asset_ref(asset), "kind": metadata.get("kind", "semantic_card"),
        "qa_status": metadata.get("qa_status", "static_validated"),
        "visual_qa_status": metadata.get("visual_qa_status", "not_applicable_semantic_card"),
        "disclaimer": "Design preview; not generated-image quality evidence.",
    })
    preview_errors = validate_preview_file(preview_target, metadata)
    if preview_errors:
        target.unlink(missing_ok=True); preview_target.unlink(missing_ok=True)
        raise ValidationError("\n".join(preview_errors))
    _write_private_json(metadata, target.parent / "preview.json")
    return {"scope": scope, "path": str(target), "ref": asset_ref(asset), "created": True}


def load_layered_registry(project_root: Path, home: Path | None = None) -> list[dict[str, Any]]:
    """Load project, personal and official assets with immutable collision checks."""
    project_root = project_root.resolve(); home = (home or apsal_home()).resolve()
    records: list[dict[str, Any]] = []
    previews = _official_preview_index()
    for scope, root in _registry_asset_dirs(project_root, home):
        for path in _iter_registry_assets(root):
            asset = load_json(path)
            errors = validate_registry_asset(asset)
            if errors: raise ValidationError(f"{path}: {'; '.join(errors)}")
            preview_path = path.parent / "preview.webp"; preview_meta_path = path.parent / "preview.json"
            if not preview_meta_path.is_file(): raise ValidationError(f"{path}: missing preview.json")
            metadata = load_json(preview_meta_path)
            preview_errors = validate_preview_file(preview_path, metadata)
            if preview_errors: raise ValidationError("\n".join(preview_errors))
            records.append({"scope": scope, "asset": asset, "asset_path": path, "preview_path": preview_path, "preview": metadata})
    for asset in load_catalog().get("assets", []):
        item = previews.get(_asset_key(asset))
        if not item: raise ValidationError(f"official DNA missing preview: {_ref_label(_asset_key(asset))}")
        preview_path = plugin_root() / "assets" / "previews" / item["image"]
        preview_errors = validate_preview_file(preview_path, item)
        if preview_errors: raise ValidationError("\n".join(preview_errors))
        records.append({
            "scope": "official", "asset": asset, "asset_path": plugin_root() / "assets" / "dna" / "catalog.json",
            "preview_path": preview_path, "preview": item,
        })
    chosen: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for record in records:
        key = _asset_key(record["asset"])
        if key in chosen:
            if digest(chosen[key]["asset"]) != digest(record["asset"]):
                raise ValidationError(f"registry digest conflict for {_ref_label(key)}")
            continue
        chosen[key] = record
    return list(chosen.values())


def registry_assets(project_root: Path, home: Path | None = None) -> list[dict[str, Any]]:
    return [record["asset"] for record in load_layered_registry(project_root, home)]


def search_registry(project_root: Path, query: str = "", stage: str | None = None, home: Path | None = None, limit: int = 12) -> list[dict[str, Any]]:
    if stage is not None and stage not in INTERACTION_STAGES:
        raise ValidationError(f"unknown interaction stage: {stage}")
    terms = [term.casefold() for term in query.split() if term]
    allowed = set(STAGE_TYPES[stage]) if stage else set(CATEGORIES)
    scored: list[tuple[int, int, dict[str, Any]]] = []
    scope_rank = {"project": 0, "personal": 1, "extension": 2, "official": 3}
    for record in load_layered_registry(project_root, home):
        asset = record["asset"]
        if asset["type"] not in allowed: continue
        haystack = (" ".join(str(asset.get(key, "")) for key in ("id", "type", "change_summary", "prompt_fragment")) + " " + canonical_json(asset.get("discovery", {}))).casefold()
        if terms and not all(term in haystack for term in terms): continue
        score = sum(haystack.count(term) for term in terms)
        scored.append((-score, scope_rank[record["scope"]], record))
    scored.sort(key=lambda item: (item[0], item[1], item[2]["asset"]["type"], item[2]["asset"]["id"]))
    return [record for _, _, record in scored[:max(1, min(limit, 50))]]


def _usage_events_path(home: Path) -> Path:
    return _inside(home, home / "usage" / "events.jsonl")


def _append_usage_event(event: dict[str, Any], home: Path) -> None:
    path = _usage_events_path(home); _mkdir_private(path.parent)
    value = {"schema_version": "0.6.0", "recorded_at": _utc_now(), **event}
    with path.open("a", encoding="utf-8") as stream: stream.write(canonical_json(value) + "\n")
    try: path.chmod(0o600)
    except OSError: pass


def _usage_weights(home: Path) -> dict[tuple[str, str, str, str], int]:
    path = _usage_events_path(home); weights: dict[tuple[str, str, str, str], int] = {}
    if not path.is_file(): return weights
    values = {"accepted": 2, "rejected": -6, "successful": 6, "failed": -3, "selected": 1, "remembered": 3}
    for line in path.read_text(encoding="utf-8").splitlines():
        try: event = json.loads(line)
        except json.JSONDecodeError: continue
        ref = event.get("ref", {}); key = tuple(str(ref.get(name, "")) for name in ("namespace", "id", "type", "version"))
        if all(key): weights[key] = weights.get(key, 0) + values.get(event.get("outcome"), 0)
    return weights


def record_dna_feedback(
    ref: dict[str, str], outcome: str, *, project_root: Path, home: Path | None = None,
    context: str = "", note: str = "",
) -> dict[str, Any]:
    if outcome not in FEEDBACK_OUTCOMES: raise ValidationError(f"feedback outcome must be one of {sorted(FEEDBACK_OUTCOMES)}")
    project_root = project_root.resolve(); home = (home or apsal_home()).resolve(); init_workspace(project_root, home)
    key = tuple(str(ref.get(name, "")) for name in ("namespace", "id", "type", "version"))
    record = next((item for item in load_layered_registry(project_root, home) if _asset_key(item["asset"]) == key), None)
    if not record: raise ValidationError(f"unresolved DNA reference {_ref_label(key)}")
    detected = _detect_recommendation_context(context)
    event = {
        "event": "dna_feedback", "outcome": outcome, "ref": asset_ref(record["asset"]),
        "context": detected, "context_digest": hashlib.sha256(context.encode()).hexdigest() if context else "not_reported",
        "note": note[:240],
    }
    _append_usage_event(event, home)
    return {"recorded": True, "outcome": outcome, "ref": event["ref"], "preference_weight": _usage_weights(home).get(key, 0)}


def recommend_dna(
    brief: str, stage: str, *, project_root: Path, home: Path | None = None,
    session_id: str | None = None, limit: int = 6, _asset_types: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Rank DNA for one scene stage and explain every recommendation."""
    if not brief.strip(): raise ValidationError("recommendation brief cannot be empty")
    if stage not in INTERACTION_STAGES and stage not in CREATIVE_LAYERS: raise ValidationError(f"unknown interaction stage: {stage}")
    project_root = project_root.resolve(); home = (home or apsal_home()).resolve()
    allowed_types = _asset_types or (STAGE_TYPES[stage] if stage in STAGE_TYPES else LAYER_TYPES[stage])
    context = _detect_recommendation_context(brief); context_tags = set(context["semantic_tags"])
    context_facets = {key: set(value if isinstance(value, list) else [value]) for key, value in context["facets"].items()}
    selected_refs: list[dict[str, str]] = []
    if session_id:
        session, _ = load_design_session(session_id, project_root)
        if session.get("schema_version") == "0.7.0" and stage in CREATIVE_LAYERS:
            for prior in CREATIVE_LAYERS[:CREATIVE_LAYERS.index(stage)]: selected_refs.extend(session["layers"][prior].get("selection", []))
        elif stage in INTERACTION_STAGES:
            for prior in INTERACTION_STAGES[:INTERACTION_STAGES.index(stage)]: selected_refs.extend(session["stages"][prior].get("selection", []))
    selected_keys = {tuple(str(ref.get(name, "")) for name in ("namespace", "id", "type", "version")) for ref in selected_refs}
    weights = _usage_weights(home); scope_bonus = {"project": 3, "personal": 2, "extension": 1, "official": 0}
    brief_terms = {term for term in re.findall(r"[a-z0-9-]{2,}", brief.casefold())}
    recommendations: list[tuple[int, int, str, dict[str, Any]]] = []
    for record in load_layered_registry(project_root, home):
        asset = record["asset"]
        if asset["type"] not in allowed_types: continue
        discovery = asset.get("discovery") or suggest_discovery_metadata(asset)
        tags = set(discovery.get("semantic_tags", [])); matched_tags = sorted(tags & context_tags)
        facets = discovery.get("facets", {}); matched_facets = []
        for key, wanted in context_facets.items():
            actual_value = facets.get(key); actual = set(actual_value if isinstance(actual_value, list) else [actual_value]) if actual_value is not None else set()
            if actual & wanted: matched_facets.append(key)
        text = " ".join(str(asset.get(key, "")) for key in ("id", "change_summary", "prompt_fragment")).casefold()
        matched_terms = sorted(term for term in brief_terms if term in text)
        key = _asset_key(asset); score = scope_bonus[record["scope"]] + len(matched_tags) * 8 + len(matched_facets) * 5 + len(matched_terms) * 2
        preference = max(-10, min(10, weights.get(key, 0))); score += preference
        reasons = []
        if matched_tags: reasons.append(f"semantic match: {', '.join(matched_tags)}")
        if matched_facets: reasons.append(f"scene facets: {', '.join(matched_facets)}")
        if matched_terms: reasons.append(f"brief terms: {', '.join(matched_terms[:5])}")
        dependencies = {tuple(str(dep.get(name, "")) for name in ("namespace", "id", "type", "version")) for dep in asset.get("dependencies", []) if isinstance(dep, dict)}
        if dependencies & selected_keys: score += 10; reasons.append("explicitly compatible with confirmed upstream DNA")
        if preference: reasons.append(f"personal usage memory: {preference:+d}")
        reasons.append(f"{record['scope']} Registry; {asset['qa_status']} QA; rights {asset['rights']['status']}")
        recommendations.append((-score, {"project": 0, "personal": 1, "extension": 2, "official": 3}[record["scope"]], asset["id"], {
            "score": score, "reasons": reasons, "matched_tags": matched_tags, "matched_facets": matched_facets,
            "record": record, "discovery": discovery,
        }))
    recommendations.sort(key=lambda item: item[:3]); selected = [item[3] for item in recommendations[:max(1, min(limit, 12))]]
    return {
        "stage": stage, "context": context, "selected_upstream_refs": selected_refs,
        "recommendations": selected, "count": len(selected),
        "ranking_policy": ["identity_rights_medium", "scene_intent", "dependency_compatibility", "photo_language", "personal_memory", "qa_scope"],
    }


def recommend_layer_dna(
    brief: str, layer: str, *, project_root: Path, home: Path | None = None,
    session_id: str | None = None, limit_per_type: int = 3,
) -> dict[str, Any]:
    """Recommend at least one explained candidate for every DNA type required by a creative layer."""
    if layer not in CREATIVE_LAYERS: raise ValidationError(f"unknown creative layer: {layer}")
    by_type: dict[str, list[dict[str, Any]]] = {}
    for asset_type in LAYER_TYPES[layer]:
        value = recommend_dna(brief, layer, project_root=project_root, home=home, session_id=session_id,
                              limit=limit_per_type, _asset_types=(asset_type,))
        by_type[asset_type] = value["recommendations"]
    return {
        "layer": layer, "required_types": list(LAYER_TYPES[layer]), "by_type": by_type,
        "count": sum(len(items) for items in by_type.values()),
        "ranking_policy": ["identity_rights_medium", "scene_intent", "dependency_compatibility", "photo_language", "personal_memory", "qa_scope"],
    }


ZH_OFFICIAL_DNA = {
    "OPEN_CHAR_ADULT_001": {
        "title": "稳定成年人物基线", "summary": "原创虚构成年人物身份基线。",
        "core": ["虚构东亚成年女性，年龄二十八至三十五岁", "自然面部结构与真实皮肤质感", "整组锁定年龄、发型和身体比例"],
    },
    "OPEN_STYLE_EDITORIAL_001": {
        "title": "克制的当代编辑摄影", "summary": "克制、真实并保留材质触感的当代编辑摄影风格。",
        "core": ["真实材质与轻微胶片颗粒", "受控反差和自然色彩分离", "避免过度修饰与人工光泽"],
    },
    "OPEN_ENV_WINDOW_001": {
        "title": "静谧窗边空间", "summary": "原创、连续且物理关系清楚的安静窗边环境。",
        "core": ["灰泥墙、东向高窗、浅色木地板与亚麻帘", "低矮木桌和稳定空间几何", "全部镜头属于同一房间"],
    },
    "OPEN_LIGHT_WINDOW_001": {
        "title": "三阶段自然窗光", "summary": "从冷调进入到温暖余晖的三阶段自然窗光。",
        "core": ["柔和定向窗光与可信衰减", "冷调进入、中性日间、温暖余晖", "每个阶段保持一致阴影方向"],
    },
    "OPEN_COMP_SEQUENCE_001": {
        "title": "均衡的多镜头覆盖", "summary": "兼顾叙事变化和画面呼吸的多镜头编辑摄影覆盖。",
        "core": ["环境、全身、中景、近景与细节有意变化", "主体分离清楚", "负空间服务叙事而非装饰"],
    },
    "OPEN_SHOT_NINE_001": {
        "title": "九镜独立成图基线", "summary": "九个镜头分别完成叙事职能，并各自输出一张独立成图。",
        "core": ["每镜都有不同叙事职能", "先设计可观察动作，再设计姿态", "不生成九宫格、拼图、文字或水印"],
    },
    "OPEN_QA_PORTRAIT_001": {
        "title": "人像套片质量检查", "summary": "覆盖身份、人体结构、连续性和输出规则的人像套片检查方案。",
        "core": ["检查身份、手部、人体结构和服装连续性", "检查道具归属、空间几何、反射和灯光方向", "检查镜头意图、非目标漂移及文字水印"],
    },
}


def _zh_rights_label(rights: dict[str, Any]) -> str:
    status = str(rights.get("status", ""))
    if status in {"original_open_content", "authorized_open_content"}: return "权利清晰的开放内容"
    if status == "private_user_content": return "仅限私人使用的内容"
    return "权利状态已记录"


def dna_card(record: dict[str, Any], locale: str = "en") -> dict[str, Any]:
    """Return the compact text-card projection used by conversational clients.

    Registry previews remain available for rights review and Extension Pack
    validation, but are deliberately excluded from interactive selection data.
    """
    asset = record["asset"]
    card = {
        "ref": asset_ref(asset), "scope": record["scope"], "title": asset["id"], "type": asset["type"],
        "summary": asset["change_summary"], "version": asset["version"], "locks": asset.get("locks", []),
        "core_attributes": asset.get("locks") or [asset["prompt_fragment"]],
        "rights": asset["rights"], "qa_status": asset["qa_status"],
    }
    if locale != "zh-CN":
        card.update({
            "type_label": asset["type"], "scope_label": record["scope"], "qa_status_label": asset["qa_status"],
            "reference_label": f"{asset['namespace']}/{asset['id']} · v{asset['version']} · {record['scope']}",
            "rights_label": f"{asset['rights'].get('license', '')} · {asset['rights'].get('attribution', '')}",
        })
        return card
    official = ZH_OFFICIAL_DNA.get(asset["id"])
    summary_text = str(asset.get("change_summary", ""))
    has_zh_summary = bool(re.search(r"[\u3400-\u9fff]", summary_text)) and not _contains_latin(summary_text)
    type_label = ZH_UI_LABELS["types"].get(asset["type"], "创作资源")
    card.update({
        "title": official["title"] if official else (asset["change_summary"] if has_zh_summary else "自定义" + type_label),
        "type_label": type_label, "scope_label": ZH_UI_LABELS["scopes"].get(record["scope"], "资源库"),
        "summary": official["summary"] if official else (asset["change_summary"] if has_zh_summary else "已按当前创作方案记录的可复用资源。"),
        "core_attributes": official["core"] if official else ["核心约束已记录", "正式版本不可原地覆盖"],
        "qa_status_label": ZH_UI_LABELS["qa"].get(asset["qa_status"], "质量状态已记录"),
        "reference_label": f"{ZH_UI_LABELS['scopes'].get(record['scope'], '资源库')} · 版本 {asset['version']} · 摘要已校验",
        "rights_label": _zh_rights_label(asset["rights"]),
    })
    return card


def promote_registry_asset(ref: dict[str, str], *, project_root: Path, home: Path | None = None) -> dict[str, Any]:
    home = (home or apsal_home()).resolve()
    key = tuple(ref.get(name, "") for name in ("namespace", "id", "type", "version"))
    matches = [record for record in load_layered_registry(project_root, home) if _asset_key(record["asset"]) == key]
    if not matches: raise ValidationError(f"unresolved DNA reference {_ref_label(key)}")
    record = matches[0]
    if record["scope"] == "official": raise ValidationError("official DNA is already globally available and cannot be promoted")
    return save_registry_asset(
        record["asset"], scope="personal", project_root=project_root, home=home,
        preview_path=record["preview_path"], preview_metadata=record["preview"],
    )


def catalog_index() -> dict[tuple[str, str, str, str], dict[str, Any]]:
    assets = load_catalog().get("assets", [])
    return {(a["namespace"], a["id"], a["type"], a["version"]): a for a in assets}


def _asset_index(assets: list[dict[str, Any]] | None = None) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    values = assets if assets is not None else load_catalog().get("assets", [])
    return {_asset_key(asset): asset for asset in values}


def asset_ref(asset: dict[str, Any]) -> dict[str, str]:
    return {
        "namespace": asset["namespace"], "id": asset["id"], "type": asset["type"],
        "version": asset["version"], "content_digest": digest(asset),
    }


def live_action_rendering_contract() -> dict[str, Any]:
    return {
        "medium": "live_action_photography",
        "subject_representation": "real_adult_human",
        "environment_style_may_be_handmade": True,
        "must_preserve": [
            "natural_skin_texture", "plausible_human_anatomy", "optical_depth_of_field",
            "physically_plausible_light", "photographic_material_response",
        ],
        "forbid": list(LIVE_ACTION_FORBID),
        "priority": 100,
        "instruction": {
            "en": "The set and props may use hand-drawn, crayon, or handmade textures; the adult subject must always be rendered as a real human in live-action photography.",
            "zh": "布景和道具可以具有手绘、蜡笔与手工质感；成年人物必须始终是真实人物的实拍摄影呈现。",
        },
    }


def codex_imagegen_output_contract(shot_count: int) -> dict[str, Any]:
    """Return the honest output request for Codex-managed image generation.

    Aspect ratio and quality are creative requests. The built-in Codex image
    tool owns its concrete format and pixel dimensions, so APSAL never turns a
    requested 4K size into a provider-native guarantee.
    """
    return {
        "count": shot_count, **CODEX_IMAGEGEN_OUTPUT, "independent_images": True,
        "forbid": ["collage", "grid", "contact sheet", "text", "logo", "watermark"],
    }


def codex_delivery_contract(output: dict[str, Any], shot_count: int) -> dict[str, Any]:
    """Translate any canonical output request into an honest Codex handoff."""
    contract = codex_imagegen_output_contract(shot_count)
    contract["aspect_ratio"] = output.get("aspect_ratio", contract["aspect_ratio"])
    requested_size = output.get("requested_size")
    if not requested_size and re.fullmatch(r"[1-9][0-9]*x[1-9][0-9]*", str(output.get("size", ""))):
        requested_size = output["size"]
    contract["requested_size"] = requested_size or "not_reported"
    return contract


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
    mood = _mood_profile(brief); output = theme["output"]; count = len(theme["shots"])
    arc = dict(mood["arc"])
    explicit_male = bool(re.search(r"(?:男主角|男性|男士|男人|男模|\bmale\b|\bman\b)", brief, re.I))
    protagonist = "one poised fictional East Asian adult male protagonist" if explicit_male else "one poised fictional East Asian adult female protagonist"
    return {
        "content": _decision("content", "direction", f"Turn the creator brief into one concrete photographic proposition: {brief}", {
            "theme_statement": brief, "subject_matter": "one coherent live-action photographic world",
            "central_tension": "the visible situation must reveal a change rather than a decorative pose",
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
            "variable_styling_traits": ["makeup", "hairstyle", "wardrobe", "era styling"],
            "identity_locks": ["face geometry", "age band", "skin characteristics", "hair color and hairline", "body proportions"],
        }, [
            "The same poised real adult protagonist remains identifiable across every Job.",
            "Makeup, hairstyle, wardrobe, and period styling may change deliberately without face substitution or identity drift.",
        ], ["stable identity", "adult age", "natural anatomy", "distinctive personal presence"], [
            "Identity remains continuous in all outputs.",
            "Every styling choice complements the protagonist without obscuring or replacing identity-defining features.",
        ]),
        "world": _decision("world", "worldbuilding", "Construct one coherent physical world with persistent spatial and material rules.", {
            "space": "one coherent physical location", "time": "one continuous time phase", "materials": ["photographically plausible materials"],
            "physical_rules": ["consistent geometry", "gravity", "reflection", "material response"],
            "continuity": ["location", "time", "weather", "object placement"],
        }, ["Architecture, entrances, windows, reflections and object positions remain physically coherent."],
            ["world geometry", "physical causality"], ["Every Job can be inferred to belong to the same world."]),
        "look": _decision("look", "worldbuilding", "Define wardrobe, grooming and prop ownership as world state rather than decoration.", {
            "wardrobe": "one locked wardrobe look unless a declared event changes it", "grooming": "consistent across the sequence",
            "props": [], "ownership_policy": "every prop has one declared owner, location and state",
        }, ["Wardrobe and grooming stay continuous.", "Every visible prop has stable ownership and changes state only through an event."],
            ["wardrobe continuity", "prop ownership", "material continuity"], ["No prop duplicates, floats or changes owner without cause."]),
        "event": _decision("event", "narrative", "Make an observable event change world state before designing poses.", {
            "inciting_action": "one observable action initiates the sequence", "state_changes": ["each major action leaves a visible consequence"],
            "consequences": ["later Jobs inherit the changed state"],
        }, ["Actions are physically legible and leave consequences visible in later frames."],
            ["subject identity", "world physics", "prop ownership"], ["Every action changes or reveals state rather than serving as an empty pose."]),
        "sequence": _decision("sequence", "narrative", "Organize multiple viewpoints into time, rhythm and narrative progression.", {
            "strategy": "establish → approach → trigger → develop → interiorize → reveal → turn → release → resolve" if count == 9 else "distinct functional progression",
            "rhythm": "measured progression with no duplicate shot function", "progression": list(arc.values()), "shot_count": count,
        }, [f"The {count} Jobs form a readable progression with distinct functions.", "Information, distance, action and emotion evolve across the sequence."],
            ["event consequences", "world continuity", "shot order"], ["No two Jobs repeat the same narrative function."]),
        "camera": _decision("camera", "image", "Choose necessary viewpoints and photographic coverage for each independent Job.", {
            "viewpoint": "one coherent physical camera position per Job", "coverage": f"{count} distinct viewpoints",
            "framing_language": "environment, full, medium, close and detail frames used by narrative need",
            "lens_language": "physically plausible perspective without arbitrary lens drift",
            "composition": "subject, depth, foreground, background and negative space form one relation system",
        }, ["Every Job has one motivated viewpoint and visibly distinct composition."],
            ["world geometry", "required action visibility"], ["Framing and perspective match the declared shot function."]),
        "light": _decision("light", "image", "Make time, depth, material and emotion visible through physically coherent light.", {
            "source": "one motivated key source with declared practical or ambient support", "direction": "consistent with the world",
            "quality": "physically plausible softness and falloff", "contrast": "motivated by the emotional direction",
            "time_phase": "continuous unless the sequence declares a transition", "continuity": "direction, shadow and exposure remain traceable",
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
        if require_confirmed and decision.get("status") != "confirmed": errors.append(f"{label}: creator confirmation is required")
        if decision.get("source") not in {"proposed_from_brief", "derived_from_dna", "system_policy", "creator_confirmed"}: errors.append(f"{label}: invalid source")
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
    if manifest.get("protocol_version") == "0.3.0" and manifest.get("semantic_contract_version") != SEMANTIC_CONTRACT_VERSION:
        errors.append("manifest: Protocol 0.3 requires semantic_contract_version 0.3.0")
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
    return "APSAL CONFIRMED ELEMENT DESIGN — " + " | ".join(parts) + ". " if parts else ""


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
            f"Narrative purpose: {shot['narrative_purpose']}. Framing: {shot['framing']}. Action: {shot['action']}. "
            f"Hands: {shot['hands']}. Gaze: {shot['gaze']}. Composition: {shot['composition']}. "
            f"Continuity: {canonical_json(shot['continuity'])}. Output file: {shot['output_filename']}."
            f"{observable_text}"
        )
        positive = f"{medium_prefix}{element_prefix}{shared}, {instruction}"
        reference_ids = [
            ref["reference_id"] for ref in theme.get("references", [])
            if "*" in ref.get("applies_to", []) or shot["shot_id"] in ref.get("applies_to", [])
        ]
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
                "composition": shot["composition"], "continuity": shot["continuity"],
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


def _session_dir(project_root: Path, session_id: str) -> Path:
    session_id = _safe_part(session_id, "session id")
    return _inside(project_root / ".apsal" / "drafts", project_root / ".apsal" / "drafts" / session_id)


def _session_paths(project_root: Path, session_id: str) -> tuple[Path, Path, Path]:
    root = _session_dir(project_root, session_id)
    return root, root / "session.json", root / "theme.apsal.yaml"


def _write_session(session: dict[str, Any], theme: dict[str, Any], project_root: Path) -> None:
    root, session_path, theme_path = _session_paths(project_root, session["session_id"])
    _mkdir_private(root)
    session["updated_at"] = _utc_now()
    session["theme_digest"] = digest(theme)
    theme_path.write_text(dump_yaml(theme), encoding="utf-8")
    _write_private_json(session, session_path)


def load_design_session(session_id: str, project_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    project_root = project_root.expanduser().resolve()
    _, session_path, theme_path = _session_paths(project_root, session_id)
    if not session_path.is_file() or not theme_path.is_file():
        raise ValidationError(f"unknown design session: {session_id}")
    session = load_json(session_path)
    theme = load_document(theme_path)
    if session.get("theme_digest") != digest(theme):
        raise ValidationError(f"design session draft digest mismatch: {session_id}")
    return session, theme


def _new_theme_id() -> str:
    return f"APSAL-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def start_design_session(
    brief: str, *, project_root: Path, theme_id: str | None = None, name: str | None = None,
    shot_count: int = 9, home: Path | None = None, language: str | None = "auto",
) -> dict[str, Any]:
    """Start a resumable five-layer, thirteen-element natural-language design session."""
    brief = brief.strip()
    if not brief: raise ValidationError("creative brief cannot be empty")
    project_root = project_root.expanduser().resolve(); init_workspace(project_root, home)
    theme_id = theme_id or _new_theme_id()
    theme = new_semantic_theme(theme_id, (name or brief[:80]).strip(), shot_count, native_4k=False, live_action=True)
    theme["output"] = codex_imagegen_output_contract(shot_count)
    for shot in theme["shots"]: shot["output_filename"] = f"{theme_id.lower()}_{int(shot['shot_id'].split('_')[-1]):02d}.png"
    theme["element_decisions"] = propose_element_decisions(brief, theme)
    theme["interaction_model"] = "five_layer_thirteen_element"
    session_id = f"SESSION-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:10].upper()}"
    session = {
        "schema_version": "0.7.0", "interaction_model": "five_layer_thirteen_element",
        "session_id": session_id, "brief": brief,
        "project_root": str(project_root), "state": "direction_pending", "shot_count": shot_count,
        "language": resolve_interface_language(brief, language),
        "layers": {
            layer: {"status": "pending", "roles": list(LAYER_ROLES[layer]), "selection": [], "confirmed_at": None}
            for layer in CREATIVE_LAYERS
        },
        "private_references": [], "memory_offers": [], "invalidations": [], "created_at": _utc_now(), "updated_at": _utc_now(),
        "theme_artifact": None,
    }
    _write_session(session, theme, project_root)
    return session


def set_session_language(session_id: str, language: str, *, project_root: Path) -> dict[str, Any]:
    """Set creator-facing language without changing photographic generation intent."""
    project_root = project_root.expanduser().resolve()
    session, theme = load_design_session(session_id, project_root)
    session["language"] = resolve_interface_language("", language)
    _write_session(session, theme, project_root)
    return session


def present_element_layer(session_id: str, layer: str, *, project_root: Path) -> dict[str, Any]:
    """Return creator-facing text cards for one layer without exposing YAML or JSON."""
    if layer not in CREATIVE_LAYERS: raise ValidationError(f"unknown creative layer: {layer}")
    session, theme = load_design_session(session_id, project_root.resolve())
    if session.get("schema_version") != "0.7.0": raise ValidationError("element layers require an APSAL Studio 0.7 session")
    language = session_interface_language(session)
    if language["status"] != "confirmed":
        raise ValidationError("Choose English or Chinese before continuing / 请先选择 English 或中文")
    locale = language["code"]
    layer_spec = next(item for item in load_creative_layers()["layers"] if item["id"] == layer)
    cards = []
    for role in LAYER_ROLES[layer]:
        role_meta = load_semantic_registry()["roles"][role]; decision = theme["element_decisions"][role]
        card = {
            "role": role, "title": role_meta["en"] if locale == "en" else role_meta["zh"],
            "title_en": role_meta["en"], "title_zh": role_meta["zh"],
            "question": role_meta["question_en"] if locale == "en" else role_meta["question_zh"],
            "question_en": role_meta["question_en"], "question_zh": role_meta["question_zh"],
            "status": decision["status"], "source": decision["source"],
            "intent": decision["intent"], "values": decision["values"], "observable": decision["observable"],
            "must_preserve": decision["must_preserve"], "qa_expectations": decision["qa_expectations"],
            "basis": decision["basis"], "dna_refs": decision.get("dna_refs", []),
        }
        if locale == "zh-CN": card.update(_zh_element_presentation(role, decision, session["brief"]))
        else:
            recommendation, rationale, options = _element_proposal_copy(role, decision, session["brief"], "en")
            card.update({
                "role_label": role, "status_label": decision["status"], "source_label": decision["source"],
                "display_recommendation": recommendation, "display_rationale": rationale, "display_options": options,
                "display_intent": decision["intent"],
                "display_values": {key: _display_value(role, key, value, "en") for key, value in decision["values"].items()},
                "display_observable": decision["observable"], "display_must_preserve": decision["must_preserve"],
                "display_qa_expectations": decision["qa_expectations"],
            })
        cards.append(card)
    result = {
        "session_id": session_id, "layer": layer, "language": locale,
        "title": layer_spec["en"] if locale == "en" else layer_spec["zh"],
        "title_en": layer_spec["en"], "title_zh": layer_spec["zh"],
        "layer_label": layer_spec["en"] if locale == "en" else layer_spec["zh"],
        "roles": list(LAYER_ROLES[layer]), "required_dna_types": list(LAYER_TYPES[layer]),
        "cards": cards, "status": session["layers"][layer]["status"],
    }
    if layer == "direction": result["emotion_taxonomy"] = load_creative_layers()["emotion_taxonomy"]
    return result


def _resolve_layer_refs(
    refs: list[dict[str, str]], layer: str, project_root: Path, home: Path | None,
) -> list[dict[str, Any]]:
    required = set(LAYER_TYPES[layer])
    if not required:
        if refs: raise ValidationError(f"{layer} layer does not select Registry DNA")
        return []
    records = load_layered_registry(project_root, home); by_key = {_asset_key(record["asset"]): record for record in records}
    selected = []
    for ref in refs:
        key = tuple(str(ref.get(name, "")) for name in ("namespace", "id", "type", "version")); record = by_key.get(key)
        if not record: raise ValidationError(f"unresolved DNA reference {_ref_label(key)}")
        if ref.get("content_digest") and ref["content_digest"] != digest(record["asset"]): raise ValidationError(f"DNA digest mismatch for {_ref_label(key)}")
        selected.append(record)
    actual = [record["asset"]["type"] for record in selected]
    if set(actual) != required or len(actual) != len(required): raise ValidationError(f"{layer} layer requires exactly one of {sorted(required)}")
    return selected


def _decision_compare(value: dict[str, Any]) -> dict[str, Any]:
    return {key: value.get(key) for key in ("intent", "values", "observable", "must_preserve", "qa_expectations", "basis")}


def _resolve_refs(
    refs: list[dict[str, str]], stage: str, project_root: Path, home: Path | None,
) -> list[dict[str, Any]]:
    records = load_layered_registry(project_root, home)
    by_key = {_asset_key(record["asset"]): record for record in records}
    selected: list[dict[str, Any]] = []
    for ref in refs:
        key = tuple(str(ref.get(name, "")) for name in ("namespace", "id", "type", "version"))
        record = by_key.get(key)
        if not record: raise ValidationError(f"unresolved DNA reference {_ref_label(key)}")
        if ref.get("content_digest") and ref["content_digest"] != digest(record["asset"]):
            raise ValidationError(f"DNA digest mismatch for {_ref_label(key)}")
        selected.append(record)
    required = set(STAGE_TYPES[stage]); actual = [record["asset"]["type"] for record in selected]
    if set(actual) != required or len(actual) != len(required):
        raise ValidationError(f"{stage} stage requires exactly one of {sorted(required)}")
    return selected


def store_private_reference(
    path: Path, *, home: Path | None = None, reference_id: str | None = None,
    uses: list[str] | None = None, allowed_uses: list[str] | None = None,
    forbidden_uses: list[str] | None = None, applies_to: list[str] | None = None,
    rights: dict[str, Any] | None = None, expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Copy a user reference into the private content-addressed vault."""
    source = path.expanduser().resolve()
    if not source.is_file(): raise ValidationError(f"reference image not found: {source}")
    data = source.read_bytes(); sha = hashlib.sha256(data).hexdigest()
    if expected_sha256 and expected_sha256 != sha: raise ValidationError(f"reference digest mismatch for {source.name}")
    reference_id = reference_id or f"REF_{sha[:12].upper()}"
    if not SAFE_ASSET_ID.fullmatch(reference_id): raise ValidationError("reference_id must match ^[A-Z][A-Z0-9_]*$")
    uses = uses or ["identity"]
    if not uses or set(uses) - REFERENCE_USES: raise ValidationError(f"reference uses must be selected from {sorted(REFERENCE_USES)}")
    allowed_uses = allowed_uses or list(uses)
    forbidden_uses = forbidden_uses or [item for item in sorted(REFERENCE_USES) if item not in uses]
    if "identity" not in uses and "identity" not in forbidden_uses: forbidden_uses.append("identity")
    applies_to = applies_to or ["*"]
    rights = rights or {
        "copyright_status": "user_provided_unverified", "portrait_rights": "user_provided_unverified",
        "attribution": "User-provided private reference", "redistribution_allowed": False,
    }
    home = (home or apsal_home()).resolve(); root = home / "vault" / "sha256" / sha[:2] / sha
    suffix = source.suffix.lower() if re.fullmatch(r"\.[a-z0-9]{1,8}", source.suffix.lower()) else ".bin"
    _sanitize_reference_bytes(data, suffix)
    target = root / f"reference{suffix}"
    metadata = {
        "schema_version": "0.5.0", "reference_id": reference_id, "original_sha256": sha, "sha256": sha,
        "size": len(data), "original_filename": source.name, "uses": uses,
        "allowed_uses": allowed_uses, "forbidden_uses": forbidden_uses, "applies_to": applies_to,
        "rights": rights, "rights_status": "private_user_provided_not_redistributable", "visibility": "private",
        "created_at": _utc_now(),
    }
    metadata_errors = validate_reference_metadata([metadata])
    if metadata_errors: raise ValidationError("\n".join(metadata_errors))
    for directory in (home, home / "vault", home / "vault" / "sha256", root.parent, root): _mkdir_private(directory)
    if not target.exists(): target.write_bytes(data)
    try: target.chmod(0o600)
    except OSError: pass
    metadata_path = root / "reference.json"
    if metadata_path.exists():
        existing = load_json(metadata_path)
        if existing.get("original_sha256") not in {None, sha}: raise ValidationError("vault reference digest conflict")
    _write_private_json(metadata, metadata_path)
    return {**metadata, "vault_uri": f"vault:sha256:{sha}"}


def _vault_reference_path(vault_uri: str, home: Path | None = None) -> Path:
    if not vault_uri.startswith("vault:sha256:"): raise ValidationError("unsupported private reference URI")
    sha = vault_uri.rsplit(":", 1)[-1]
    if not re.fullmatch(r"[a-f0-9]{64}", sha): raise ValidationError("invalid private reference URI")
    root = (home or apsal_home()).resolve() / "vault" / "sha256" / sha[:2] / sha
    matches = sorted(path for path in root.glob("reference.*") if path.name != "reference.json")
    if len(matches) != 1: raise ValidationError(f"vault reference is missing or ambiguous: {sha}")
    if hashlib.sha256(matches[0].read_bytes()).hexdigest() != sha: raise ValidationError(f"vault reference digest mismatch: {sha}")
    return matches[0]


def _validate_shot_replacement(shots: list[dict[str, Any]], expected_count: int) -> None:
    if len(shots) != expected_count: raise ValidationError(f"scene stage requires {expected_count} shots")
    ids = [shot.get("shot_id") for shot in shots]; filenames = [shot.get("output_filename") for shot in shots]
    if len(set(ids)) != len(ids) or len(set(filenames)) != len(filenames):
        raise ValidationError("scene shots require unique IDs and output filenames")


def commit_element_layer(
    session_id: str, layer: str, refs: list[dict[str, str]], *, project_root: Path,
    decisions: dict[str, dict[str, Any]] | None = None, home: Path | None = None,
    shots: list[dict[str, Any]] | None = None, reference_path: Path | None = None,
    reference_bindings: list[dict[str, Any]] | None = None,
    draft_assets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Confirm one of five creator layers and its complete subset of thirteen element decisions."""
    if layer not in CREATIVE_LAYERS: raise ValidationError(f"unknown creative layer: {layer}")
    project_root = project_root.expanduser().resolve(); session, theme = load_design_session(session_id, project_root)
    if session.get("schema_version") != "0.7.0": raise ValidationError("five-layer confirmation requires an APSAL Studio 0.7 session")
    if session_interface_language(session)["status"] != "confirmed": raise ValidationError("confirm the session language before confirming creative layers")
    if session["state"] in {"ready", "generating", "completed", "partial"}: raise ValidationError("a finalized or generated theme cannot be edited; create a new theme version")
    layer_index = CREATIVE_LAYERS.index(layer)
    for prior in CREATIVE_LAYERS[:layer_index]:
        if session["layers"][prior]["status"] != "confirmed": raise ValidationError(f"confirm {prior} before {layer}")

    proposed_assets = [json.loads(json.dumps(asset)) for asset in (draft_assets or [])]
    for asset in proposed_assets:
        if asset.get("type") not in LAYER_TYPES[layer]: raise ValidationError(f"draft DNA type {asset.get('type')} does not belong to {layer}")
        if "discovery" not in asset: asset["discovery"] = suggest_discovery_metadata(asset, session["brief"])
        errors = validate_registry_asset(asset)
        if errors: raise ValidationError("\n".join(errors))
        target = _registry_asset_path(project_root / ".apsal" / "registry", asset)
        if target.exists() and digest(load_json(target)) != digest(asset): raise ValidationError(f"immutable DNA conflict for {_ref_label(_asset_key(asset))}")
    created_assets = [save_registry_asset(asset, scope="project", project_root=project_root, home=home) for asset in proposed_assets]
    if proposed_assets:
        # Discovery metadata may be derived immediately before an asset is
        # written.  Always resolve a just-created draft by the digest of the
        # bytes that actually became immutable Registry content, not by a
        # caller's pre-enrichment draft digest.
        created_refs = {_asset_key(asset): created["ref"] for asset, created in zip(proposed_assets, created_assets)}
        if refs:
            refs = [created_refs.get(tuple(str(ref.get(name, "")) for name in ("namespace", "id", "type", "version")), ref) for ref in refs]
        else:
            refs = list(created_refs.values())
    records = _resolve_layer_refs(refs, layer, project_root, home)
    next_selection = [asset_ref(record["asset"]) for record in records]
    selected_types = set(LAYER_TYPES[layer])
    theme["dna"] = [ref for ref in theme["dna"] if ref["type"] not in selected_types]
    theme["dna"].extend(next_selection); theme["dna"].sort(key=lambda ref: CATEGORIES.index(ref["type"]))

    shots_changed = shots is not None and digest(shots) != digest(theme["shots"])
    if shots is not None:
        if layer != "narrative": raise ValidationError("shot changes are only allowed in the narrative layer")
        _validate_shot_replacement(shots, session["shot_count"]); theme["shots"] = shots

    bound_references: list[dict[str, Any]] = []; reference_changed = False
    if reference_path is not None:
        if layer != "worldbuilding": raise ValidationError("identity references belong to the worldbuilding layer")
        bound_references.append(store_private_reference(reference_path, home=home))
    for binding in reference_bindings or []:
        if not isinstance(binding, dict) or not binding.get("path"): raise ValidationError("reference binding requires a path")
        bound_references.append(store_private_reference(
            Path(binding["path"]), home=home, reference_id=binding.get("reference_id"), uses=binding.get("uses"),
            allowed_uses=binding.get("allowed_uses"), forbidden_uses=binding.get("forbidden_uses"),
            applies_to=binding.get("applies_to"), rights=binding.get("rights"), expected_sha256=binding.get("expected_sha256"),
        ))
    for stored in bound_references:
        previous = next((item for item in session["private_references"] if item.get("reference_id") == stored["reference_id"]), None)
        if previous != stored:
            session["private_references"] = [item for item in session["private_references"] if item.get("reference_id") != stored["reference_id"]]
            session["private_references"].append(stored); reference_changed = True
        public_metadata = {key: value for key, value in stored.items() if key not in {"vault_uri", "visibility", "created_at", "size"}}
        theme.setdefault("references", []); theme["references"] = [item for item in theme["references"] if item.get("reference_id") != stored["reference_id"]]
        theme["references"].append(public_metadata); theme["references"].sort(key=lambda item: item["reference_id"])
        if stored["rights"].get("redistribution_allowed") is not True: theme["distribution"] = "private_only"

    submitted = decisions or {}
    unknown_roles = set(submitted) - set(LAYER_ROLES[layer])
    if unknown_roles: raise ValidationError(f"{layer} decisions contain roles outside the layer: {sorted(unknown_roles)}")
    previous_decisions = {role: _decision_compare(theme["element_decisions"][role]) for role in LAYER_ROLES[layer]}
    confirmed_selections = [
        ref for prior in CREATIVE_LAYERS[:layer_index] for ref in session["layers"][prior].get("selection", [])
    ] + next_selection
    mapping = load_semantic_registry()["dna_to_protocol"]
    for role in LAYER_ROLES[layer]:
        current = json.loads(json.dumps(theme["element_decisions"][role])); supplied = submitted.get(role, {})
        if not isinstance(supplied, dict): raise ValidationError(f"{layer}.{role}: decision must be an object")
        for key in ("intent", "observable", "must_preserve", "qa_expectations", "basis"):
            if key in supplied: current[key] = supplied[key]
        if "values" in supplied:
            if not isinstance(supplied["values"], dict): raise ValidationError(f"{layer}.{role}.values must be an object")
            current["values"] = {**current.get("values", {}), **supplied["values"]}
        role_refs = [ref for ref in confirmed_selections if role in mapping.get(ref["type"], [])]
        current.update({
            "role": role, "layer": layer, "status": "confirmed", "source": "creator_confirmed",
            "dna_refs": role_refs, "confirmed_at": _utc_now(),
        })
        if "creator_confirmation" not in current["basis"]: current["basis"].append("creator_confirmation")
        theme["element_decisions"][role] = current
    errors = validate_element_decisions(theme["element_decisions"], require_confirmed=False)
    if errors: raise ValidationError("\n".join(errors))

    changed = (
        session["layers"][layer].get("selection") != next_selection or shots_changed or reference_changed
        or previous_decisions != {role: _decision_compare(theme["element_decisions"][role]) for role in LAYER_ROLES[layer]}
    )
    session["layers"][layer] = {
        "status": "confirmed", "roles": list(LAYER_ROLES[layer]), "selection": next_selection,
        "confirmed_at": _utc_now(), "created_project_assets": created_assets,
        "reference_ids": [item["reference_id"] for item in bound_references],
    }
    resolved_home = (home or apsal_home()).resolve()
    for record in records:
        _append_usage_event({"event": "dna_selection", "outcome": "selected", "stage": layer, "ref": asset_ref(record["asset"]), "context": _detect_recommendation_context(session["brief"])}, resolved_home)
    existing_offer_keys = {tuple(item.get("ref", {}).get(name, "") for name in ("namespace", "id", "type", "version")) for item in session.get("memory_offers", [])}
    for record in records:
        key = _asset_key(record["asset"])
        if record["scope"] != "project" or _registry_asset_path(resolved_home / "registry", record["asset"]).is_file() or key in existing_offer_keys: continue
        session["memory_offers"].append({
            "offer_id": f"MEMORY-{uuid.uuid4().hex[:10].upper()}", "status": "pending", "stage": layer,
            "ref": asset_ref(record["asset"]), "title": record["asset"]["id"],
            "reason": "New or revised project DNA can be reused and recommended across future projects.",
            "discovery": record["asset"].get("discovery"),
            "tag_confirmation_required": record["asset"].get("discovery", {}).get("source") != "creator_confirmed",
            "options": ["save_personal", "project_only", "not_now"],
        })
    if changed:
        for later in CREATIVE_LAYERS[layer_index + 1:]:
            if session["layers"][later]["status"] == "confirmed": session["invalidations"].append({"source": layer, "invalidated": later, "at": _utc_now()})
            session["layers"][later] = {"status": "pending", "roles": list(LAYER_ROLES[later]), "selection": [], "confirmed_at": None}
            for role in LAYER_ROLES[later]:
                stale = theme["element_decisions"][role]; stale["status"] = "proposed"
                stale["source"] = "system_policy" if role in {"job", "quality_control"} else "proposed_from_brief"
                stale.pop("confirmed_at", None); stale["dna_refs"] = []
        session["theme_artifact"] = None
    pending = next((item for item in CREATIVE_LAYERS if session["layers"][item]["status"] != "confirmed"), None)
    session["state"] = f"{pending}_pending" if pending else "review_pending"
    _write_session(session, theme, project_root)
    return session


def commit_session_stage(
    session_id: str, stage: str, refs: list[dict[str, str]], *, project_root: Path,
    home: Path | None = None, shots: list[dict[str, Any]] | None = None,
    reference_path: Path | None = None, reference_bindings: list[dict[str, Any]] | None = None,
    draft_assets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Confirm or revise one interaction stage and invalidate every affected downstream stage."""
    if stage not in INTERACTION_STAGES: raise ValidationError(f"unknown interaction stage: {stage}")
    project_root = project_root.expanduser().resolve(); session, theme = load_design_session(session_id, project_root)
    if session.get("schema_version") == "0.7.0": raise ValidationError("this session uses five-layer confirmation; call commit_element_layer")
    if session["state"] in {"ready", "generating", "completed", "partial"}:
        raise ValidationError("a finalized or generated theme cannot be edited; create a new theme version")
    proposed_assets = [json.loads(json.dumps(asset)) for asset in (draft_assets or [])]
    for asset in proposed_assets:
        if asset.get("type") not in STAGE_TYPES[stage]:
            raise ValidationError(f"draft DNA type {asset.get('type')} does not belong to {stage}")
        if "discovery" not in asset: asset["discovery"] = suggest_discovery_metadata(asset, session["brief"])
        errors = validate_registry_asset(asset)
        if errors: raise ValidationError("\n".join(errors))
        target = _registry_asset_path(project_root / ".apsal" / "registry", asset)
        if target.exists() and digest(load_json(target)) != digest(asset):
            raise ValidationError(f"immutable DNA conflict for {_ref_label(_asset_key(asset))}")
    created_assets = []
    for asset in proposed_assets:
        created_assets.append(save_registry_asset(asset, scope="project", project_root=project_root, home=home))
    if not refs and proposed_assets:
        refs = [asset_ref(asset) for asset in proposed_assets]
    records = _resolve_refs(refs, stage, project_root, home)
    resolved_home = (home or apsal_home()).resolve()
    stage_index = INTERACTION_STAGES.index(stage)
    for later in INTERACTION_STAGES[:stage_index]:
        if session["stages"][later]["status"] != "confirmed":
            raise ValidationError(f"confirm {later} before {stage}")
    selected_types = set(STAGE_TYPES[stage])
    next_selection = [asset_ref(record["asset"]) for record in records]
    shots_changed = shots is not None and digest(shots) != digest(theme["shots"])
    reference_changed = False; bound_references: list[dict[str, Any]] = []
    theme["dna"] = [ref for ref in theme["dna"] if ref["type"] not in selected_types]
    theme["dna"].extend(next_selection)
    theme["dna"].sort(key=lambda ref: CATEGORIES.index(ref["type"]))
    if shots is not None:
        if stage != "scene": raise ValidationError("shot changes are only allowed in the scene stage")
        _validate_shot_replacement(shots, session["shot_count"])
        theme["shots"] = shots
    if reference_path is not None:
        if stage != "character": raise ValidationError("private references belong to the character stage")
        stored = store_private_reference(reference_path, home=home)
        bound_references.append(stored)
    for binding in reference_bindings or []:
        if not isinstance(binding, dict) or not binding.get("path"): raise ValidationError("reference binding requires a path")
        stored = store_private_reference(
            Path(binding["path"]), home=home, reference_id=binding.get("reference_id"), uses=binding.get("uses"),
            allowed_uses=binding.get("allowed_uses"), forbidden_uses=binding.get("forbidden_uses"),
            applies_to=binding.get("applies_to"), rights=binding.get("rights"), expected_sha256=binding.get("expected_sha256"),
        )
        bound_references.append(stored)
    for stored in bound_references:
        previous = next((item for item in session["private_references"] if item.get("reference_id") == stored["reference_id"]), None)
        if previous != stored:
            session["private_references"] = [item for item in session["private_references"] if item.get("reference_id") != stored["reference_id"]]
            session["private_references"].append(stored); reference_changed = True
        public_metadata = {key: value for key, value in stored.items() if key not in {"vault_uri", "visibility", "created_at", "size"}}
        theme.setdefault("references", [])
        theme["references"] = [item for item in theme["references"] if item.get("reference_id") != stored["reference_id"]]
        theme["references"].append(public_metadata)
        theme["references"].sort(key=lambda item: item["reference_id"])
        if stored["rights"].get("redistribution_allowed") is not True: theme["distribution"] = "private_only"
    changed = session["stages"][stage].get("selection") != next_selection or shots_changed or reference_changed
    session["stages"][stage] = {
        "status": "confirmed", "selection": next_selection,
        "confirmed_at": _utc_now(), "created_project_assets": created_assets,
        "reference_ids": [item["reference_id"] for item in bound_references],
    }
    for record in records:
        _append_usage_event({"event": "dna_selection", "outcome": "selected", "stage": stage, "ref": asset_ref(record["asset"]), "context": _detect_recommendation_context(session["brief"])}, resolved_home)
    existing_offer_keys = {tuple(item.get("ref", {}).get(name, "") for name in ("namespace", "id", "type", "version")) for item in session.get("memory_offers", [])}
    for record in records:
        key = _asset_key(record["asset"])
        if record["scope"] != "project" or _registry_asset_path(resolved_home / "registry", record["asset"]).is_file() or key in existing_offer_keys: continue
        offer = {
            "offer_id": f"MEMORY-{uuid.uuid4().hex[:10].upper()}", "status": "pending", "stage": stage,
            "ref": asset_ref(record["asset"]), "title": record["asset"]["id"],
            "reason": "New or revised project DNA can be reused and recommended across future projects.",
            "discovery": record["asset"].get("discovery"),
            "tag_confirmation_required": record["asset"].get("discovery", {}).get("source") != "creator_confirmed",
            "options": ["save_personal", "project_only", "not_now"],
        }
        session["memory_offers"].append(offer)
    if changed:
        for later in INTERACTION_STAGES[stage_index + 1:]:
            previous = session["stages"][later]["status"]
            if previous == "confirmed":
                session["invalidations"].append({"source": stage, "invalidated": later, "at": _utc_now()})
            session["stages"][later] = {"status": "pending", "selection": [], "confirmed_at": None}
        session["theme_artifact"] = None
    pending = next((item for item in INTERACTION_STAGES if session["stages"][item]["status"] != "confirmed"), None)
    session["state"] = f"{pending}_pending" if pending else "review_pending"
    _write_session(session, theme, project_root)
    return session


def resolve_dna_memory_offer(
    session_id: str, offer_id: str, action: str, *, project_root: Path, home: Path | None = None,
) -> dict[str, Any]:
    if action not in {"save_personal", "project_only", "not_now"}:
        raise ValidationError("memory action must be save_personal, project_only, or not_now")
    project_root = project_root.resolve(); home = (home or apsal_home()).resolve()
    session, theme = load_design_session(session_id, project_root)
    offer = next((item for item in session.get("memory_offers", []) if item.get("offer_id") == offer_id), None)
    if not offer: raise ValidationError(f"unknown DNA memory offer: {offer_id}")
    if offer.get("status") != "pending": raise ValidationError(f"DNA memory offer is already resolved: {offer_id}")
    result = None
    if action == "save_personal":
        result = promote_registry_asset(offer["ref"], project_root=project_root, home=home)
        _append_usage_event({"event": "dna_memory", "outcome": "remembered", "ref": offer["ref"], "session_id": session_id}, home)
    offer.update({"status": "saved" if action == "save_personal" else action, "resolved_at": _utc_now()})
    _write_session(session, theme, project_root)
    return {"offer": offer, "personal_asset": result, "next_action": "Continue the current design session; future recommendations now include this preference." if action == "save_personal" else "Keep the DNA in the current project only."}


def _theme_dir(project_root: Path, theme: dict[str, Any]) -> Path:
    theme_id = _safe_part(theme["id"], "theme id"); version = _safe_part(theme["version"], "theme version")
    root = project_root / ".apsal" / "themes"
    return _inside(root, root / theme_id / version)


def _write_theme_prompts(compiled: dict[str, Any], root: Path) -> dict[str, str]:
    prompts = root / "prompts"; _mkdir_private(prompts)
    result: dict[str, str] = {}
    for shot in compiled["shots"]:
        shot_id = _safe_part(shot["shot_id"], "shot id")
        positive = prompts / f"{shot_id}.prompt.txt"; negative = prompts / f"{shot_id}.negative.txt"
        positive.write_text(shot["positive_prompt"] + "\n", encoding="utf-8")
        negative.write_text(shot["negative_prompt"] + "\n", encoding="utf-8")
        result[shot_id] = shot["prompt_digest"]
    return result


def finalize_design_session(
    session_id: str, *, project_root: Path, home: Path | None = None,
) -> dict[str, Any]:
    """Freeze a confirmed draft as YAML source, canonical JSON and three compiled targets."""
    project_root = project_root.expanduser().resolve(); session, theme = load_design_session(session_id, project_root)
    if session.get("schema_version") == "0.7.0":
        if any(session["layers"][layer]["status"] != "confirmed" for layer in CREATIVE_LAYERS):
            raise ValidationError("all five creative layers and thirteen elements must be confirmed before finalization")
        decision_errors = validate_element_decisions(theme.get("element_decisions"), require_confirmed=True)
        if decision_errors: raise ValidationError("\n".join(decision_errors))
    elif any(session["stages"][stage]["status"] != "confirmed" for stage in INTERACTION_STAGES):
        raise ValidationError("all four DNA stages must be confirmed before finalization")
    assets = registry_assets(project_root, home)
    errors = validate_theme(theme, assets)
    if errors: raise ValidationError("\n".join(errors))
    root = _theme_dir(project_root, theme)
    canonical_path = root / "theme.apsal.json"
    if canonical_path.exists():
        current = load_json(canonical_path)
        if digest(current) != digest(theme):
            raise ValidationError(f"immutable theme conflict for {theme['id']}@{theme['version']}")
    else:
        _mkdir_private(root / "compiled"); _mkdir_private(root / "references")
        (root / "theme.apsal.yaml").write_text(dump_yaml(theme), encoding="utf-8")
        write_canonical_json(theme, canonical_path)
        compiled = {target: compile_theme(theme, target, assets) for target in COMPILE_TARGETS}
        for target, value in compiled.items(): write_canonical_json(value, root / "compiled" / f"{target}.json")
        prompt_digests = _write_theme_prompts(compiled["image"], root)
        reference_manifest = {
            "schema_version": "0.5.0", "theme_id": theme["id"], "theme_version": theme["version"],
            "distribution": theme.get("distribution", "public"),
            "private_media_included": bool(session.get("private_references")),
            "redistribution_allowed": all(item.get("rights", {}).get("redistribution_allowed") is True for item in session.get("private_references", [])),
            "references": session.get("private_references", []),
        }
        write_canonical_json(reference_manifest, root / "references" / "reference_manifest.json")
        write_canonical_json(theme.get("rendering_contract", {"status": "not_declared_legacy"}), root / "references" / "rendering_contract.json")
        files = sorted(path for path in root.rglob("*") if path.is_file())
        manifest = {
            "schema_version": "0.5.0", "theme_id": theme["id"], "theme_version": theme["version"],
            "theme_digest": digest(theme), "engine_version": ENGINE_VERSION, "prompt_digests": prompt_digests,
            "reference_manifest_digest": digest(reference_manifest), "reference_count": len(reference_manifest["references"]),
            "distribution": reference_manifest["distribution"], "output_contract": theme["output"],
            "files": {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files},
            "visual_qa_status": "pending",
        }
        write_canonical_json(manifest, root / "artifact_manifest.json")
    reference_paths = {
        item["reference_id"]: _vault_reference_path(item["vault_uri"], home)
        for item in session.get("private_references", []) if item.get("vault_uri")
    }
    prompt_package_path, prompt_package_sha = pack_theme(
        theme, root / "exports", (root / "theme.apsal.yaml").read_bytes(), assets=assets,
        reference_paths=reference_paths, distribution=theme.get("distribution", "auto"),
    )
    artifact_manifest_path = root / "artifact_manifest.json"
    artifact_manifest = load_json(artifact_manifest_path)
    artifact_manifest["engine_version"] = ENGINE_VERSION
    artifact_manifest["prompt_package"] = {
        "path": str(prompt_package_path.relative_to(root)), "sha256": prompt_package_sha,
        "generation_surface": "codex_imagegen", "api_key_required": False,
        "returned_dimensions_guaranteed": False,
    }
    artifact_manifest["files"] = {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(path for path in root.rglob("*") if path.is_file() and path != artifact_manifest_path)
    }
    write_canonical_json(artifact_manifest, artifact_manifest_path)
    session["state"] = "ready"; session["theme_artifact"] = {
        "path": str(root), "theme_id": theme["id"], "version": theme["version"], "digest": digest(theme),
        "reference_count": len(session.get("private_references", [])), "distribution": theme.get("distribution", "public"),
        "rendering_medium": theme.get("rendering_contract", {}).get("medium", "not_declared"), "output": theme["output"],
        "prompt_package": {"path": str(prompt_package_path), "sha256": prompt_package_sha,
                           "generation_surface": "codex_imagegen", "api_key_required": False},
    }
    _write_session(session, theme, project_root)
    return session


def _run_dir(project_root: Path, run_id: str) -> Path:
    run_id = _safe_part(run_id, "run id"); root = project_root / ".apsal" / "runs"
    return _inside(root, root / run_id)


def load_generation_run(run_id: str, project_root: Path) -> dict[str, Any]:
    path = _run_dir(project_root.expanduser().resolve(), run_id) / "run.json"
    if not path.is_file(): raise ValidationError(f"unknown generation run: {run_id}")
    return load_json(path)


def _write_run(run: dict[str, Any], project_root: Path) -> None:
    run["updated_at"] = _utc_now()
    _write_private_json(run, _run_dir(project_root, run["run_id"]) / "run.json")


def _generation_run_status(run: dict[str, Any]) -> str:
    jobs = run.get("jobs", [])
    if any(job.get("status") == "failed" for job in jobs): return "partial"
    if jobs and all(job.get("status") == "succeeded" for job in jobs):
        if run.get("rendering_contract", {}).get("medium") == "live_action_photography":
            return "completed" if all(job.get("model_visual_qa") == "passed" for job in jobs) else "generating"
        return "completed"
    return "generating"


def start_generation_run(
    session_id: str, *, project_root: Path, confirmed: bool = False, mode: str = "generate",
    adapter: str = "codex-imagegen", model: str = "not_reported", parameters: dict[str, Any] | None = None,
    resume_run_id: str | None = None, home: Path | None = None,
) -> dict[str, Any]:
    """Prepare or resume a Codex-managed run without invoking an image API."""
    if mode not in {"generate", "prompts", "skill"}: raise ValidationError("run mode must be generate, prompts, or skill")
    if mode == "generate" and confirmed is not True:
        raise ValidationError("explicit confirmation is required before generating images")
    if adapter != "codex-imagegen": raise ValidationError("APSAL Studio uses Codex built-in image generation; direct image API adapters are disabled")
    if model not in {"", "not_reported", "codex-managed"}: raise ValidationError("Codex manages the image model; do not set a provider model")
    if parameters: raise ValidationError("Codex manages image parameters; provider API parameters are not accepted")
    project_root = project_root.expanduser().resolve(); session, theme = load_design_session(session_id, project_root)
    if session["state"] not in {"ready", "partial", "completed"} or not session.get("theme_artifact"):
        raise ValidationError("finalize the design session before starting a run")
    if resume_run_id:
        run = load_generation_run(resume_run_id, project_root)
        if run["session_id"] != session_id: raise ValidationError("run does not belong to this session")
        failed_jobs = [job for job in run["jobs"] if job.get("status") == "failed"]
        if not failed_jobs: raise ValidationError("generation run has no failed Jobs to resume")
        run["resume_count"] += 1
        for job in failed_jobs: job["status"] = "pending"; job["error"] = None
        run["status"] = "generating"
        _write_run(run, project_root); session["state"] = "generating"; _write_session(session, theme, project_root)
        return run
    theme_root = Path(session["theme_artifact"]["path"]); compiled = load_json(theme_root / "compiled" / "image.json")
    reference_manifest_path = theme_root / "references" / "reference_manifest.json"
    reference_manifest = load_json(reference_manifest_path) if reference_manifest_path.is_file() else {
        "schema_version": "0.5.0", "references": [], "reference_count": 0, "distribution": "public",
    }
    output_contract = codex_delivery_contract(theme.get("output", {}), len(compiled["shots"]))
    run_id = f"RUN-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8].upper()}"
    root = _run_dir(project_root, run_id)
    for relative in ("prompts", "outputs", "qa"): _mkdir_private(root / relative)
    jobs = []
    for shot in compiled["shots"]:
        shot_id = _safe_part(shot["shot_id"], "shot id")
        (root / "prompts" / f"{shot_id}.prompt.txt").write_text(shot["positive_prompt"] + " Negative constraints: " + shot["negative_prompt"] + "\n", encoding="utf-8")
        (root / "prompts" / f"{shot_id}.negative.txt").write_text(shot["negative_prompt"] + "\n", encoding="utf-8")
        jobs.append({
            "shot_id": shot_id, "status": "pending" if mode == "generate" else "saved",
            "prompt_digest": shot["prompt_digest"], "reference_ids": shot.get("reference_ids", []),
            "attempts": [], "output": None, "error": None, "model_visual_qa": "pending",
            "human_visual_qa": "pending",
        })
    run = {
        "schema_version": "0.9.0", "run_id": run_id, "session_id": session_id, "mode": mode,
        "status": "generating" if mode == "generate" else "completed", "theme": session["theme_artifact"],
        "dna": theme["dna"], "engine_version": ENGINE_VERSION, "adapter": "codex-imagegen",
        "model": "not_reported", "parameters": "not_reported", "output_contract": output_contract,
        "generation_surface": "codex_imagegen", "direct_api_calls": False, "api_key_required": False,
        "returned_dimensions_guaranteed": False,
        "rendering_contract": theme.get("rendering_contract", {"status": "not_declared_legacy"}),
        "reference_manifest": {key: value for key, value in reference_manifest.items() if key != "references"} | {
            "references": [{key: value for key, value in item.items() if key != "vault_uri"} for item in reference_manifest.get("references", [])]
        },
        "jobs": jobs, "resume_count": 0, "created_at": _utc_now(), "updated_at": _utc_now(),
        "lineage_note": "Prompts and reference IDs are frozen locally before Codex generates one independent image per Job. Concrete model, format and dimensions remain not_reported unless Codex returns them.",
    }
    package = session["theme_artifact"].get("prompt_package")
    if package: run["prompt_package"] = package
    if mode == "skill" and package: run["skill"] = package
    _write_run(run, project_root)
    session["state"] = "generating" if mode == "generate" else "completed"; _write_session(session, theme, project_root)
    return run


def _read_apsal_run_bundle(source: Path) -> tuple[dict[str, Any], dict[str, bytes], str, str]:
    """Read one legacy run directory or ZIP without trusting archive paths."""
    source = source.expanduser().resolve()
    files: dict[str, bytes] = {}
    if source.is_dir():
        candidates = [
            path for path in source.rglob("run.json")
            if "__MACOSX" not in path.parts and len(path.relative_to(source).parts) <= 4
        ]
        if len(candidates) != 1: raise ValidationError("APSAL package must contain exactly one run.json")
        bundle_root = candidates[0].parent
        total = 0
        for path in sorted(item for item in bundle_root.rglob("*") if item.is_file() and "__MACOSX" not in item.parts):
            relative = path.relative_to(bundle_root)
            if len(relative.parts) > 8: raise ValidationError(f"APSAL package path is too deep: {relative}")
            size = path.stat().st_size; total += size
            if size > 20_000_000 or total > 150_000_000: raise ValidationError("APSAL package exceeds safe import limits")
            files[relative.as_posix()] = path.read_bytes()
        origin = str(source)
    elif source.is_file() and source.suffix.lower() == ".zip":
        try: archive = zipfile.ZipFile(source)
        except zipfile.BadZipFile as exc: raise ValidationError("APSAL package is not a valid ZIP") from exc
        infos = [item for item in archive.infolist() if not item.is_dir() and "__MACOSX" not in Path(item.filename).parts]
        names = [item.filename for item in infos]
        if len(names) != len(set(names)): raise ValidationError("APSAL package contains duplicate paths")
        candidates = [item for item in infos if Path(item.filename).name == "run.json"]
        if len(candidates) != 1: raise ValidationError("APSAL package must contain exactly one run.json")
        prefix = Path(candidates[0].filename).parent
        total = 0
        for info in infos:
            path = Path(info.filename)
            if path.is_absolute() or ".." in path.parts or len(path.parts) > 12:
                raise ValidationError(f"unsafe APSAL package path: {info.filename}")
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValidationError(f"APSAL package symlink rejected: {info.filename}")
            try: relative = path.relative_to(prefix)
            except ValueError: continue
            if not relative.parts: continue
            total += info.file_size
            if info.file_size > 20_000_000 or total > 150_000_000:
                raise ValidationError("APSAL package exceeds safe import limits")
            files[relative.as_posix()] = archive.read(info)
        origin = str(source)
    else:
        raise ValidationError("APSAL package must be a run directory or ZIP")
    if "run.json" not in files: raise ValidationError("APSAL package is missing run.json")
    try: run = json.loads(files["run.json"])
    except json.JSONDecodeError as exc: raise ValidationError("APSAL run.json is invalid JSON") from exc
    if not isinstance(run, dict): raise ValidationError("APSAL run.json must be an object")
    source_sha = hashlib.sha256(files["run.json"]).hexdigest()
    return run, files, origin, source_sha


def _legacy_reference_candidate(
    reference: dict[str, Any], files: dict[str, bytes], home: Path,
) -> tuple[bytes, str, str] | None:
    expected = str(reference.get("original_sha256") or reference.get("sha256") or "")
    if not re.fullmatch(r"[a-f0-9]{64}", expected): return None
    declared = [reference.get(key) for key in ("packaged_file", "path", "source_path", "original_path")]
    image_suffixes = {".png", ".jpg", ".jpeg", ".webp"}
    for value in declared:
        if not isinstance(value, str) or not value: continue
        candidate = Path(value)
        if not candidate.is_absolute():
            normalized = candidate.as_posix().lstrip("./")
            data = files.get(normalized)
            if data is not None and hashlib.sha256(data).hexdigest() == expected:
                return data, candidate.suffix.lower() or ".bin", "package"
    for name, data in files.items():
        if Path(name).suffix.lower() in image_suffixes and hashlib.sha256(data).hexdigest() == expected:
            return data, Path(name).suffix.lower(), "package_digest_scan"
    vault_dir = home / "vault" / "sha256" / expected[:2] / expected
    if vault_dir.is_dir():
        for candidate in sorted(vault_dir.glob("reference.*")):
            if candidate.suffix.lower() not in image_suffixes: continue
            data = candidate.read_bytes()
            if hashlib.sha256(data).hexdigest() == expected:
                return data, candidate.suffix.lower(), "local_vault"
    return None


def _import_reference_conflicts(reference: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    forbidden = " ".join(str(item).lower() for item in reference.get("forbidden_uses", []))
    uses = {str(item).lower() for item in reference.get("uses", [])}
    if "identity" in uses and any(token in forbidden for token in ("identity", "身份", "面容", "face")):
        warnings.append("identity is declared and forbidden simultaneously; the forbidden identity rule takes precedence")
    rights = reference.get("rights") if isinstance(reference.get("rights"), dict) else {}
    if rights.get("redistribution_allowed") is not True:
        warnings.append("reference is private-only and must not be redistributed")
    return warnings


def _imported_prompt_package(run: dict[str, Any], run_root: Path) -> tuple[Path, str]:
    """Create a deterministic private Codex Skill from a fully resolved imported run."""
    missing = run.get("missing_references", [])
    if missing: raise ValidationError("cannot package imported run until every declared reference is restored")
    theme = run.get("theme", {}) if isinstance(run.get("theme"), dict) else {}
    theme_id = str(theme.get("theme_id") or "APSAL-IMPORTED-RUN")
    theme_version = str(theme.get("version") or "legacy")
    slug = re.sub(r"[^a-z0-9-]+", "-", theme_id.lower()).strip("-") or "apsal-imported-run"
    prefix = f"{slug}-codex-import/"
    references = run.get("reference_manifest", {}).get("references", [])
    jobs = []
    prompt_files: dict[str, str] = {}
    files: dict[str, bytes] = {}
    for job in run["jobs"]:
        shot_id = job["shot_id"]
        for suffix in ("prompt", "negative", "full"):
            relative = f"prompts/{shot_id}.{suffix}.txt"
            data = (run_root / relative).read_bytes()
            files[prefix + relative] = data; prompt_files[relative] = hashlib.sha256(data).hexdigest()
        jobs.append({"shot_id": shot_id, "full_prompt": f"prompts/{shot_id}.full.txt", "reference_ids": job.get("reference_ids", [])})
    packaged_references = []
    for item in references:
        local_path = Path(str(item["local_path"]))
        name = f"{item['reference_id']}{local_path.suffix.lower()}"
        data = local_path.read_bytes(); packaged = f"assets/references/{name}"
        files[prefix + packaged] = data
        packaged_references.append({key: value for key, value in item.items() if key != "local_path"} | {
            "packaged_file": packaged, "packaged_sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "schema_version": "0.9.0", "engine_version": ENGINE_VERSION, "source_kind": "legacy_run_import",
        "theme_id": theme_id, "theme_version": theme_version, "source_run_sha256": run["source"]["run_json_sha256"],
        "generation_surface": "codex_imagegen", "direct_api_calls": False, "api_key_required": False,
        "distribution": "private_only", "redistribution_allowed": False,
        "returned_dimensions_guaranteed": False, "output_request": run["output_contract"],
        "prompt_files": prompt_files, "jobs": jobs,
    }
    reference_manifest = {
        "schema_version": "0.9.0", "distribution": "private_only", "redistribution_allowed": False,
        "reference_count": len(packaged_references), "references": packaged_references,
    }
    guide_zh = f"""# {theme_id} — Codex 直接使用说明

这是由 APSAL Studio 从旧版 `run.json` 自动迁移的私人 Codex Prompt/Skill 包。旧包中的 `openai-image-api`、模型名和 API 参数只作为历史血缘保留；本包不会调用图像 API，也不需要 API Key。

## 最简单的用法

1. 在 Codex 中提供这个 Skill 目录并说：“使用 `{slug}-codex-import` 生成第一张。”
2. Codex 读取 `prompts/SHOT_01.full.txt`，实际传入该镜声明的 `assets/references/` 图片，然后用 Codex 内置图像生成一张真实摄影作品。
3. 看完说“继续”，Codex 依次生成后续未完成镜头。每次只生成一张，不生成编程界面、九宫格、拼图、文字、标志或水印。
4. 如果只需要提示词，直接打开任一 `prompts/SHOT_XX.full.txt`。

目标画幅为 {run['output_contract'].get('aspect_ratio', 'not_reported')}；{run['output_contract'].get('requested_size', 'not_reported')} 只是创作交付目标，不保证 Codex 返回该像素尺寸。

运行 `python3 scripts/validate_prompt_pack.py --list` 可以离线核对文件并列出全部镜头；它不会生成图片或访问网络。
"""
    guide_en = f"""# {theme_id} — Direct use in Codex

APSAL Studio migrated this private Codex Prompt/Skill package from a legacy `run.json`. Any previous `openai-image-api`, model name, or API parameters are preserved only as historical lineage. This package does not call an image API and does not require an API key.

## Fastest workflow

1. Provide this Skill folder to Codex and say: “Use `{slug}-codex-import` to generate the first image.”
2. Codex reads `prompts/SHOT_01.full.txt`, passes the actual declared files from `assets/references/`, and uses Codex built-in image generation for one live-action photograph.
3. After reviewing it, say “continue.” Codex advances through the remaining unfinished shots. It creates one image per turn—never a programming screen, grid, collage, text, logo, or watermark.
4. If you only need a Prompt, open any `prompts/SHOT_XX.full.txt` file directly.

The requested aspect ratio is {run['output_contract'].get('aspect_ratio', 'not_reported')}. The requested {run['output_contract'].get('requested_size', 'not_reported')} delivery size is a creative target and is not a guaranteed returned pixel dimension.

Run `python3 scripts/validate_prompt_pack.py --list` to verify files and list all shots offline. The validator does not generate images or access the network.
"""
    guide_index = f"""# {theme_id} — Prompt/Skill package

- [English instructions](PROMPT_GUIDE.en.md)
- [中文使用说明](PROMPT_GUIDE.zh-CN.md)

Codex should open the guide that matches the current conversation language. The frozen image Prompts are identical in both workflows.
"""
    skill = f"""---
name: {slug}-codex-import
description: Generate or continue the imported APSAL set {theme_id} in Codex using its frozen Prompts and restored private references. Use when the creator asks to generate, continue, inspect, or reuse this migrated legacy run without an image API.
---

# {theme_id}

Read `PROMPT_GUIDE.en.md` for English creators or `PROMPT_GUIDE.zh-CN.md` for Chinese creators, plus `references/manifest.json` and `references/reference_manifest.json`. For the next unfinished Job, use its `prompts/SHOT_XX.full.txt` and pass every declared real reference image from `assets/references/` to Codex built-in image generation.

Generate exactly one live-action photograph per turn. Never render a programming interface, JSON, terminal, prompt sheet, grid, collage, text, logo or watermark. After emitting one image, stop. On “continue”, advance to the next unfinished Job. A reference's forbidden uses outrank its declared uses. Preserve identity only when identity use is explicitly allowed; never inherit pose, camera, background or composition from a continuity anchor.

Do not call an image API, request an API key, or claim guaranteed returned dimensions. Keep Codex visual QA separate from human QA.
"""
    summary = {
        "schema_version": "0.9.0", "original_schema_version": run["source"].get("schema_version"),
        "original_run_id": run["source"].get("run_id"), "run_json_sha256": run["source"]["run_json_sha256"],
        "historical_adapter": run["source"].get("historical_adapter"), "historical_model": run["source"].get("historical_model"),
        "migration_note": "Historical provider settings are not executable in this Codex-native package.",
    }
    files.update({
        prefix + "SKILL.md": skill.encode(), prefix + "PROMPT_GUIDE.md": guide_index.encode(),
        prefix + "PROMPT_GUIDE.en.md": guide_en.encode(), prefix + "PROMPT_GUIDE.zh-CN.md": guide_zh.encode(),
        prefix + "references/manifest.json": (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "references/reference_manifest.json": (json.dumps(reference_manifest, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "references/source_run_summary.json": (json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "scripts/validate_prompt_pack.py": (plugin_root() / "assets" / "templates" / "validate_prompt_pack.py").read_bytes(),
    })
    content = _zip_bytes(files); sha = hashlib.sha256(content).hexdigest()
    output_dir = run_root / "exports"; output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{slug}-legacy-run-codex-skill-private.zip"; path.write_bytes(content)
    path.with_suffix(".zip.sha256").write_text(f"{sha}  {path.name}\n", encoding="utf-8")
    return path, sha


def import_apsal_package(
    source: Path, *, project_root: Path, home: Path | None = None,
) -> dict[str, Any]:
    """Take over a legacy run package and turn it into a Codex-native resumable run."""
    project_root = project_root.expanduser().resolve(); home = (home or apsal_home()).expanduser().resolve()
    init_workspace(project_root, home)
    legacy, files, origin, source_sha = _read_apsal_run_bundle(source)
    legacy_jobs = legacy.get("jobs")
    if not isinstance(legacy_jobs, list) or not 1 <= len(legacy_jobs) <= 24:
        raise ValidationError("APSAL run must contain 1 to 24 Jobs")
    shot_ids = [str(item.get("shot_id", "")) for item in legacy_jobs if isinstance(item, dict)]
    if len(shot_ids) != len(legacy_jobs) or len(set(shot_ids)) != len(shot_ids) or any(not SAFE_COMPONENT.fullmatch(item) for item in shot_ids):
        raise ValidationError("APSAL run has invalid or duplicate shot IDs")
    run_id = f"RUN-IMPORT-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8].upper()}"
    run_root = _run_dir(project_root, run_id)
    for relative in ("prompts", "outputs", "qa", "references", "exports"): _mkdir_private(run_root / relative)
    jobs = []
    for item in legacy_jobs:
        shot_id = str(item["shot_id"])
        positive_name = f"prompts/{shot_id}.prompt.txt"; negative_name = f"prompts/{shot_id}.negative.txt"
        positive_data = files.get(positive_name)
        if positive_data is None: raise ValidationError(f"APSAL package is missing {positive_name}")
        try: positive = positive_data.decode("utf-8").strip(); negative = files.get(negative_name, b"").decode("utf-8").strip()
        except UnicodeDecodeError as exc: raise ValidationError(f"Prompt is not UTF-8: {shot_id}") from exc
        if not positive: raise ValidationError(f"APSAL Prompt is empty: {shot_id}")
        full = positive + ("\n\nNegative constraints:\n" + negative if negative else "")
        (run_root / positive_name).write_text(positive + "\n", encoding="utf-8")
        (run_root / negative_name).write_text(negative + "\n", encoding="utf-8")
        (run_root / f"prompts/{shot_id}.full.txt").write_text(full + "\n", encoding="utf-8")
        jobs.append({
            "shot_id": shot_id, "status": "pending", "prompt_digest": hashlib.sha256(full.encode()).hexdigest(),
            "reference_ids": [str(value) for value in item.get("reference_ids", [])],
            "attempts": [], "output": None, "error": None, "model_visual_qa": "pending", "human_visual_qa": "pending",
        })
    legacy_manifest = legacy.get("reference_manifest") if isinstance(legacy.get("reference_manifest"), dict) else {"references": []}
    resolved, missing, warnings = [], [], []
    for raw in legacy_manifest.get("references", []):
        if not isinstance(raw, dict): continue
        item = json.loads(json.dumps(raw)); reference_id = str(item.get("reference_id", ""))
        if not SAFE_COMPONENT.fullmatch(reference_id): raise ValidationError("legacy reference has an invalid reference ID")
        conflicts = _import_reference_conflicts(item); warnings.extend(f"{reference_id}: {value}" for value in conflicts)
        candidate = _legacy_reference_candidate(item, files, home)
        if candidate is None:
            missing.append({"reference_id": reference_id, "sha256": item.get("original_sha256") or item.get("sha256"), "original_filename": item.get("original_filename"), "reason": "not_in_package_or_local_vault"})
            resolved.append({key: value for key, value in item.items() if key not in {"path", "source_path", "original_path", "vault_uri"}} | {"status": "missing"})
            continue
        data, suffix, recovered_from = candidate
        _sanitize_reference_bytes(data, suffix)
        target = run_root / "references" / f"{reference_id}{suffix}"
        target.write_bytes(data)
        resolved.append({key: value for key, value in item.items() if key not in {"path", "source_path", "original_path", "vault_uri"}} | {
            "status": "resolved", "local_path": str(target), "recovered_from": recovered_from,
        })
    for job in jobs:
        if job["reference_ids"]: continue
        job["reference_ids"] = [
            str(item["reference_id"]) for item in resolved
            if "*" in item.get("applies_to", []) or job["shot_id"] in item.get("applies_to", [])
        ]
    legacy_output = legacy.get("output_contract") if isinstance(legacy.get("output_contract"), dict) else {}
    theme = legacy.get("theme") if isinstance(legacy.get("theme"), dict) else {}
    sanitized_theme = {key: value for key, value in theme.items() if key != "path"}
    run = {
        "schema_version": "0.9.0", "run_id": run_id, "session_id": f"SESSION-IMPORT-{uuid.uuid4().hex[:12].upper()}",
        "source_kind": "legacy_run_import", "mode": "generate", "status": "partial" if missing else "generating",
        "theme": sanitized_theme, "dna": legacy.get("dna", []), "engine_version": ENGINE_VERSION,
        "adapter": "codex-imagegen", "model": "not_reported", "parameters": "not_reported",
        "output_contract": codex_delivery_contract(legacy_output, len(jobs)),
        "generation_surface": "codex_imagegen", "direct_api_calls": False, "api_key_required": False,
        "returned_dimensions_guaranteed": False,
        "rendering_contract": legacy.get("rendering_contract", {"status": "not_declared_legacy"}),
        "reference_manifest": {"schema_version": "0.9.0", "distribution": "private_only", "redistribution_allowed": False, "references": resolved},
        "missing_references": missing, "migration_warnings": sorted(set(warnings)), "jobs": jobs, "resume_count": 0,
        "created_at": _utc_now(), "updated_at": _utc_now(),
        "source": {"origin": origin, "run_json_sha256": source_sha, "run_id": legacy.get("run_id"), "schema_version": legacy.get("schema_version"), "historical_adapter": legacy.get("adapter", "not_reported"), "historical_model": legacy.get("model", "not_reported")},
        "lineage_note": "Legacy provider settings were preserved as history only. Codex directly generates one image per Job from the migrated Prompts and restored references.",
    }
    _write_run(run, project_root)
    if not missing:
        package, sha = _imported_prompt_package(run, run_root)
        run["prompt_package"] = {"path": str(package), "sha256": sha, "distribution": "private_only"}
        _write_run(run, project_root)
    result = {
        "run": run, "ready_for_codex": not missing, "missing_references": missing,
        "message": "Ready for Codex. Generate SHOT_01 directly; no API runner is needed." if not missing else "Attach only the listed missing reference images; APSAL already recovered all Prompts and will not follow obsolete absolute paths.",
    }
    if not missing: result["next_job"] = get_next_codex_job(run_id, project_root=project_root, home=home)
    return result


def bind_import_reference(
    run_id: str, reference_id: str, source: Path, *, project_root: Path,
) -> dict[str, Any]:
    """Restore one missing imported reference and finish the Codex package when complete."""
    project_root = project_root.expanduser().resolve(); run = load_generation_run(run_id, project_root)
    if run.get("source_kind") != "legacy_run_import": raise ValidationError("reference binding is only for imported legacy runs")
    record = next((item for item in run.get("reference_manifest", {}).get("references", []) if item.get("reference_id") == reference_id), None)
    if not record: raise ValidationError(f"unknown imported reference: {reference_id}")
    expected = str(record.get("original_sha256") or record.get("sha256") or "")
    source = source.expanduser().resolve()
    if not source.is_file(): raise ValidationError(f"reference image not found: {source}")
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected: raise ValidationError(f"reference SHA-256 mismatch: {reference_id}")
    _image_dimensions(data)
    target = _run_dir(project_root, run_id) / "references" / f"{reference_id}{source.suffix.lower()}"
    target.write_bytes(data); record.update({"status": "resolved", "local_path": str(target), "recovered_from": "creator_reattached"})
    run["missing_references"] = [item for item in run.get("missing_references", []) if item.get("reference_id") != reference_id]
    run["status"] = "partial" if run["missing_references"] else "generating"
    if not run["missing_references"]:
        package, sha = _imported_prompt_package(run, _run_dir(project_root, run_id))
        run["prompt_package"] = {"path": str(package), "sha256": sha, "distribution": "private_only"}
    _write_run(run, project_root)
    result = {"run": run, "ready_for_codex": not run["missing_references"], "missing_references": run["missing_references"]}
    if not run["missing_references"]: result["next_job"] = get_next_codex_job(run_id, project_root=project_root)
    return result


def get_next_codex_job(
    run_id: str, *, project_root: Path, home: Path | None = None,
) -> dict[str, Any]:
    """Return the next exact Codex image-generation call; never call a provider."""
    project_root = project_root.expanduser().resolve(); home = (home or apsal_home()).resolve()
    run = load_generation_run(run_id, project_root)
    if run.get("mode") != "generate": raise ValidationError("only generate-mode runs have a next Codex Job")
    if run.get("generation_surface") != "codex_imagegen" or run.get("direct_api_calls") is not False:
        raise ValidationError("this is not a Codex-native generation run")
    pending_visual = next((job for job in run["jobs"] if job.get("status") == "succeeded" and job.get("model_visual_qa") == "pending"), None)
    if pending_visual and run.get("rendering_contract", {}).get("medium") == "live_action_photography":
        raise ValidationError(f"record Codex visual QA for {pending_visual['shot_id']} before continuing")
    job = next((item for item in run["jobs"] if item.get("status") in {"pending", "failed"}), None)
    if not job:
        return {"run_id": run_id, "status": run.get("status"), "next_job": None, "message": "No pending Jobs remain."}
    if run.get("source_kind") == "legacy_run_import":
        run_root = _run_dir(project_root, run_id)
        positive = (
            "Generate the finished photographic image itself. Do not show code, JSON, a terminal, a programming interface, a Prompt sheet, or an explanation inside the image. "
            + (run_root / "prompts" / f"{job['shot_id']}.prompt.txt").read_text(encoding="utf-8").strip()
        )
        negative = (run_root / "prompts" / f"{job['shot_id']}.negative.txt").read_text(encoding="utf-8").strip()
        reference_records = {item["reference_id"]: item for item in run.get("reference_manifest", {}).get("references", [])}
        relevant_missing = [
            reference_id for reference_id in job.get("reference_ids", [])
            if reference_id not in reference_records or reference_records[reference_id].get("status") != "resolved"
        ]
        if relevant_missing:
            raise ValidationError(f"reattach missing reference images before {job['shot_id']}: {relevant_missing}")
        reference_paths = [
            Path(reference_records[reference_id]["local_path"])
            for reference_id in job.get("reference_ids", []) if reference_id in reference_records
        ]
        policy_lines = []
        for reference_id in job.get("reference_ids", []):
            record = reference_records.get(reference_id, {})
            allowed = "; ".join(str(item) for item in record.get("allowed_uses", [])) or "only the declared reference purpose"
            forbidden = "; ".join(str(item) for item in record.get("forbidden_uses", [])) or "none additionally declared"
            policy_lines.append(f"Reference {reference_id}: allowed — {allowed}; forbidden — {forbidden}. Forbidden uses take precedence.")
        policy_instruction = (" Reference policy: " + " ".join(policy_lines)) if policy_lines else ""
    else:
        session, _ = load_design_session(run["session_id"], project_root)
        theme_root = Path(session["theme_artifact"]["path"]); compiled = load_json(theme_root / "compiled" / "image.json")
        shot = next(item for item in compiled["shots"] if item["shot_id"] == job["shot_id"])
        positive, negative = shot["positive_prompt"], shot["negative_prompt"]
        local_manifest_path = theme_root / "references" / "reference_manifest.json"
        local_manifest = load_json(local_manifest_path) if local_manifest_path.is_file() else {"references": []}
        reference_records = {item["reference_id"]: item for item in local_manifest.get("references", [])}
        reference_paths = [
            _vault_reference_path(reference_records[reference_id]["vault_uri"], home)
            for reference_id in job.get("reference_ids", []) if reference_id in reference_records and reference_records[reference_id].get("vault_uri")
        ]
        policy_instruction = ""
    job_index = run["jobs"].index(job); previous = run["jobs"][job_index - 1] if job_index > 0 else None
    previous_path = Path(previous.get("output", {}).get("path", "")) if previous and isinstance(previous.get("output"), dict) else None
    local_identity_anchor = bool(previous_path and previous_path.is_file())
    recent_identity_anchor = bool(previous and previous.get("status") == "succeeded" and not local_identity_anchor and not reference_paths)
    anchor_instruction = ""
    if local_identity_anchor or recent_identity_anchor:
        anchor_instruction = (
            " Use the immediately previous accepted APSAL image only to preserve the fictional adult identity and facial continuity; "
            "do not inherit its pose, camera, background, action, wardrobe, lighting, or composition."
        )
    if local_identity_anchor and previous_path is not None: reference_paths.append(previous_path)
    prompt = positive + policy_instruction + anchor_instruction + (" Negative constraints: " + negative if negative else "")
    tool_arguments: dict[str, Any] = {"prompt": prompt}
    if reference_paths: tool_arguments["referenced_image_paths"] = [str(path) for path in reference_paths]
    elif recent_identity_anchor: tool_arguments["num_last_images_to_include"] = 1
    return {
        "run_id": run_id, "shot_id": job["shot_id"], "job_position": job_index + 1,
        "job_count": len(run["jobs"]), "prompt": prompt, "prompt_digest": hashlib.sha256(prompt.encode()).hexdigest(),
        "negative_prompt": negative, "reference_ids": job.get("reference_ids", []),
        "reference_paths": [str(path) for path in reference_paths],
        "identity_anchor": "local_previous_output" if local_identity_anchor else "recent_previous_image" if recent_identity_anchor else "none",
        "codex_tool": "built_in_image_generation", "codex_tool_arguments": tool_arguments,
        "direct_api_calls": False, "api_key_required": False,
        "requested_output": run.get("output_contract", {}), "returned_dimensions_guaranteed": False,
        "after_generation": "Emit the generated image and stop. On the creator's next 'continue', record only metadata actually available, perform Codex visual QA, then request the next Job.",
    }


def record_generation_result(
    run_id: str, shot_id: str, status: str, *, project_root: Path, output_path: Path | None = None,
    artifact_uri: str | None = None, provider_metadata: dict[str, Any] | None = None, error: str | None = None,
) -> dict[str, Any]:
    """Record one Codex-managed result, preserving successful Jobs across retries."""
    if status not in {"succeeded", "failed"}: raise ValidationError("generation status must be succeeded or failed")
    project_root = project_root.expanduser().resolve(); run = load_generation_run(run_id, project_root)
    job = next((item for item in run["jobs"] if item["shot_id"] == shot_id), None)
    if not job: raise ValidationError(f"unknown shot in run: {shot_id}")
    if job["status"] == "succeeded": raise ValidationError(f"successful output is immutable: {shot_id}")
    attempt = {
        "attempt": len(job["attempts"]) + 1, "status": status, "recorded_at": _utc_now(),
        "provider_metadata": provider_metadata if provider_metadata is not None else "not_reported",
        "generation_surface": run.get("generation_surface", "legacy_provider"),
    }
    if status == "failed":
        message = (error or "provider_error_not_reported").strip()
        attempt["error"] = message; job["error"] = message
    else:
        if output_path is None and not artifact_uri:
            raise ValidationError("successful generation requires an output path or artifact URI")
        if run.get("returned_dimensions_guaranteed") is True and run.get("output_contract", {}).get("provider_native") is True and output_path is None:
            raise ValidationError("provider-native output requires a local file for format and dimension validation")
        output: dict[str, Any] = {"artifact_uri": artifact_uri or "not_reported", "sha256": "not_reported"}
        if output_path is not None:
            source = output_path.expanduser().resolve()
            if not source.is_file(): raise ValidationError(f"generated output not found: {source}")
            data = source.read_bytes()
            actual_format = _image_format(data)
            validation_contract = dict(run.get("output_contract", {}))
            if run.get("generation_surface") == "codex_imagegen":
                # A local Codex result gives us concrete bytes to inspect even though
                # the requested delivery size is not a provider-native guarantee.
                dimensions = _image_dimensions(data)
            else:
                dimensions = _validate_output_image(data, validation_contract)
            suffix = source.suffix.lower() if re.fullmatch(r"\.[a-z0-9]{1,8}", source.suffix.lower()) else ".bin"
            target = _run_dir(project_root, run_id) / "outputs" / f"{shot_id}{suffix}"
            if target.exists(): raise ValidationError(f"output already exists: {target.name}")
            shutil.copyfile(source, target)
            output.update({
                "path": str(target), "sha256": hashlib.sha256(data).hexdigest(),
                "size": target.stat().st_size, "format": actual_format,
            })
            if dimensions: output.update({"width": dimensions[0], "height": dimensions[1]})
        attempt["output"] = output; job["output"] = output; job["error"] = None
        job["model_visual_qa"] = "pending"; job["human_visual_qa"] = "pending"
    job["attempts"].append(attempt); job["status"] = status
    qa = {
        "schema_version": "0.5.0", "run_id": run_id, "shot_id": shot_id,
        "static_record_status": "recorded", "visual_qa_status": "pending" if status == "succeeded" else "not_available",
        "model_visual_qa_status": "pending" if status == "succeeded" else "not_available",
        "human_visual_qa_status": "pending" if status == "succeeded" else "not_available", "human_conclusion": "not_reported",
    }
    _write_private_json(qa, _run_dir(project_root, run_id) / "qa" / f"{shot_id}.json")
    run["status"] = _generation_run_status(run)
    _write_run(run, project_root)
    if run.get("source_kind") != "legacy_run_import":
        session, theme = load_design_session(run["session_id"], project_root)
        session["state"] = run["status"]; _write_session(session, theme, project_root)
    return run


def _image_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        return struct.unpack(">II", data[16:24])
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP": return _webp_dimensions(data)
    if data[:2] == b"\xff\xd8":
        offset = 2
        start_of_frame = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
        while offset + 4 <= len(data):
            if data[offset] != 0xFF: offset += 1; continue
            marker = data[offset + 1]; offset += 2
            if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7: continue
            if offset + 2 > len(data): break
            length = int.from_bytes(data[offset:offset + 2], "big")
            if length < 2 or offset + length > len(data): break
            if marker in start_of_frame and length >= 7:
                height = int.from_bytes(data[offset + 3:offset + 5], "big")
                width = int.from_bytes(data[offset + 5:offset + 7], "big")
                return width, height
            offset += length
    raise ValidationError("generated output has an unsupported or invalid image header")


def _image_format(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"): return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP": return "webp"
    if data[:2] == b"\xff\xd8": return "jpeg"
    raise ValidationError("generated output has an unsupported or invalid image header")


def _validate_output_image(data: bytes, output_contract: dict[str, Any]) -> tuple[int, int] | None:
    """Validate concrete bytes whenever an image contract declares a format or native size."""
    if not output_contract.get("format") and not output_contract.get("provider_native"):
        return None
    if output_contract.get("format") == "png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValidationError("provider output format is not PNG")
    width, height = _image_dimensions(data)
    size = str(output_contract.get("size", ""))
    if output_contract.get("provider_native") is True:
        if not re.fullmatch(r"[1-9][0-9]*x[1-9][0-9]*", size):
            raise ValidationError("provider-native output contract has an invalid size")
        expected = tuple(int(value) for value in size.split("x", 1))
        if (width, height) != expected:
            raise ValidationError(f"provider output dimensions {width}x{height}, expected {size}")
    return width, height


def record_model_visual_qa(
    run_id: str, shot_id: str, status: str, *, project_root: Path, findings: list[str] | None = None,
) -> dict[str, Any]:
    if status not in {"passed", "failed"}: raise ValidationError("model visual QA status must be passed or failed")
    project_root = project_root.expanduser().resolve(); run = load_generation_run(run_id, project_root)
    job = next((item for item in run["jobs"] if item["shot_id"] == shot_id), None)
    if not job or job.get("status") != "succeeded" or not job.get("output"):
        raise ValidationError(f"model visual QA requires a successful output for {shot_id}")
    qa_path = _run_dir(project_root, run_id) / "qa" / f"{shot_id}.json"
    qa = load_json(qa_path) if qa_path.is_file() else {"schema_version": "0.5.0", "run_id": run_id, "shot_id": shot_id}
    qa.update({"model_visual_qa_status": status, "model_visual_qa_findings": findings or [], "human_visual_qa_status": "pending", "reviewed_at": _utc_now()})
    job["model_visual_qa"] = status
    if status == "failed":
        source = Path(job["output"].get("path", "")); rejected_root = _run_dir(project_root, run_id) / "qa" / "rejected"
        _mkdir_private(rejected_root)
        if source.is_file():
            rejected = rejected_root / f"{shot_id}-attempt-{len(job['attempts'])}{source.suffix}"
            shutil.move(source, rejected); qa["rejected_output"] = str(rejected)
        job["output"] = None; job["status"] = "failed"; job["error"] = "model_visual_qa_failed"
    run["status"] = _generation_run_status(run)
    _write_private_json(qa, qa_path); _write_run(run, project_root)
    if run.get("source_kind") != "legacy_run_import":
        session, theme = load_design_session(run["session_id"], project_root)
        session["state"] = run["status"]; _write_session(session, theme, project_root)
    return run


def execute_generation_run(
    run_id: str, *, project_root: Path, home: Path | None = None, max_retries: int = 2,
    max_jobs: int | None = None, adapter_callable: Any | None = None, visual_qa_callable: Any | None = None,
) -> dict[str, Any]:
    """Compatibility guard: Studio no longer performs provider/API execution."""
    raise ValidationError("direct provider execution was removed in APSAL Studio 0.8; call get_next_codex_job and let Codex use its built-in image generation")


def explain_theme_path(theme: dict[str, Any], dotted_path: str) -> dict[str, Any]:
    """Explain a value using the field registry and the nearest instance intent."""
    parts = [part for part in dotted_path.split(".") if part]
    if not parts:
        raise ValidationError("explain path cannot be empty")
    current: Any = theme
    shot: dict[str, Any] | None = None
    normalized: list[str] = []
    for part in parts:
        if isinstance(current, list):
            match = next((item for item in current if isinstance(item, dict) and item.get("shot_id") == part), None)
            if match is None: raise ValidationError(f"path not found at {part}")
            current = match; shot = match; normalized.append("*")
        elif isinstance(current, dict) and part in current:
            current = current[part]; normalized.append(part)
            if part == "shots": continue
        else:
            raise ValidationError(f"path not found at {part}")
    registry_key = ".".join(normalized)
    field = load_semantic_registry().get("fields", {}).get(registry_key)
    field_name = parts[-1]
    instance_intent = shot.get("field_intents", {}).get(field_name) if shot else None
    return {
        "path": dotted_path, "normalized_path": registry_key, "value": current,
        "field_definition": field, "instance_intent": instance_intent,
        "shot_intent": shot.get("intent") if shot else None,
    }


def check_sync(root: Path) -> list[str]:
    errors: list[str] = []
    yaml_paths = sorted([*root.rglob("*.apsal.yaml"), *root.rglob("*.apsal.yml")])
    if not yaml_paths:
        return ["sync: no .apsal.yaml source files found"]
    for source in yaml_paths:
        canonical = source.with_suffix("").with_suffix(".apsal.json")
        if not canonical.is_file():
            errors.append(f"sync: missing canonical JSON for {source.relative_to(root)}"); continue
        try:
            source_value = load_document(source); canonical_value = load_document(canonical)
        except (OSError, ValueError, json.JSONDecodeError, YamlError) as exc:
            errors.append(f"sync: {exc}"); continue
        if canonical_json(source_value) != canonical_json(canonical_value):
            errors.append(f"sync: canonical JSON differs from {source.relative_to(root)}")
    return errors


def _sanitize_reference_bytes(data: bytes, suffix: str) -> tuple[bytes, str]:
    """Strip transport metadata without altering decoded pixels."""
    suffix = suffix.lower()
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        output = bytearray(data[:8]); offset = 8
        keep = {b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS", b"sRGB", b"gAMA", b"cHRM", b"iCCP"}
        while offset + 12 <= len(data):
            length = int.from_bytes(data[offset:offset + 4], "big"); end = offset + 12 + length
            if end > len(data): raise ValidationError("reference PNG is truncated")
            chunk_type = data[offset + 4:offset + 8]
            if chunk_type in keep: output.extend(data[offset:end])
            offset = end
            if chunk_type == b"IEND": break
        return bytes(output), ".png"
    if data.startswith(b"\xff\xd8"):
        output = bytearray(b"\xff\xd8"); offset = 2
        while offset < len(data):
            if data[offset] != 0xFF: raise ValidationError("reference JPEG marker is invalid")
            marker = data[offset + 1]
            if marker == 0xD9: output.extend(b"\xff\xd9"); break
            if marker == 0xDA:
                output.extend(data[offset:]); break
            if offset + 4 > len(data): raise ValidationError("reference JPEG is truncated")
            length = int.from_bytes(data[offset + 2:offset + 4], "big"); end = offset + 2 + length
            if end > len(data): raise ValidationError("reference JPEG segment is truncated")
            if marker not in {0xE1, 0xED, 0xFE}: output.extend(data[offset:end])
            offset = end
        return bytes(output), ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        chunks = bytearray(); offset = 12
        while offset + 8 <= len(data):
            name = data[offset:offset + 4]; length = int.from_bytes(data[offset + 4:offset + 8], "little")
            end = offset + 8 + length + (length % 2)
            if end > len(data): raise ValidationError("reference WebP is truncated")
            if name not in {b"EXIF", b"XMP "}: chunks.extend(data[offset:end])
            offset = end
        return b"RIFF" + (len(chunks) + 4).to_bytes(4, "little") + b"WEBP" + bytes(chunks), ".webp"
    raise ValidationError(f"unsupported reference image format: {suffix or 'unknown'}")


def build_reference_manifest(
    theme: dict[str, Any], reference_paths: dict[str, Path] | None = None,
    *, distribution: str = "auto",
) -> tuple[dict[str, Any], dict[str, bytes]]:
    references = theme.get("references", [])
    errors = validate_reference_metadata(references, theme)
    if errors: raise ValidationError("\n".join(errors))
    reference_paths = reference_paths or {}
    if distribution not in {"auto", "private_only", "public"}: raise ValidationError("distribution must be auto, private_only, or public")
    redistributable = all(_reference_rights_allow_public(ref) for ref in references)
    resolved_distribution = "private_only" if distribution == "auto" and not redistributable else "public" if distribution == "auto" else distribution
    if theme.get("distribution") == "private_only" and resolved_distribution == "public":
        raise ValidationError("private-only theme cannot be exported for public redistribution")
    if resolved_distribution == "public" and not redistributable:
        raise ValidationError("public Skill export rejected: one or more references are not redistributable")
    packaged: list[dict[str, Any]] = []; files: dict[str, bytes] = {}
    for ref in references:
        ref_id = ref["reference_id"]; source = reference_paths.get(ref_id)
        if source is None: raise ValidationError(f"reference file is required for {ref_id}")
        source = source.expanduser().resolve()
        if not source.is_file(): raise ValidationError(f"reference file not found for {ref_id}: {source}")
        original = source.read_bytes(); actual = hashlib.sha256(original).hexdigest()
        if actual != ref["original_sha256"]: raise ValidationError(f"reference digest mismatch for {ref_id}")
        sanitized, suffix = _sanitize_reference_bytes(original, source.suffix)
        packaged_name = f"{ref_id.lower()}{suffix}"
        packaged_ref = {key: value for key, value in ref.items() if key not in {"vault_uri", "path"}}
        packaged_ref.update({
            "packaged_file": f"assets/references/{packaged_name}",
            "packaged_sha256": hashlib.sha256(sanitized).hexdigest(), "metadata_sanitized": True,
        })
        packaged.append(packaged_ref); files[packaged_name] = sanitized
    manifest = {
        "schema_version": "0.5.0", "theme_id": theme["id"], "theme_version": theme["version"],
        "distribution": resolved_distribution, "private_media_included": bool(packaged) and resolved_distribution == "private_only",
        "redistribution_allowed": redistributable, "reference_count": len(packaged), "references": packaged,
    }
    manifest["reference_manifest_digest"] = digest(manifest)
    return manifest, files


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, files[name])
    return stream.getvalue()


def _dna_rights_allow_public(asset: dict[str, Any], preview: dict[str, Any]) -> bool:
    private_tokens = ("private", "unverified", "unknown", "unresolved", "pending", "all-rights-reserved")
    for rights in (asset.get("rights", {}), preview.get("rights", {})):
        license_name = str(rights.get("license", "")).lower(); status = str(rights.get("status", "")).lower()
        if not license_name or not status or any(token in f"{license_name} {status}" for token in private_tokens): return False
        if not str(rights.get("attribution", "")).strip(): return False
    return True


def export_dna_pack(
    refs: list[dict[str, str]], *, pack_id: str, namespace: str, version: str, name: str,
    description: str, project_root: Path, output_dir: Path, home: Path | None = None,
    distribution: str = "auto",
) -> tuple[Path, str]:
    """Export selected immutable DNA as a deterministic standalone Extension Pack."""
    if not SAFE_NAMESPACE.fullmatch(pack_id): raise ValidationError("DNA pack id must use lower-case letters, digits, and hyphens")
    if not SAFE_NAMESPACE.fullmatch(namespace): raise ValidationError("DNA pack namespace is invalid")
    if namespace == "official": raise ValidationError("DNA Extension Packs must use a contributor-owned namespace")
    if not SEMVER.fullmatch(version): raise ValidationError("DNA pack version must be semantic")
    if not name.strip() or not description.strip(): raise ValidationError("DNA pack name and description are required")
    if not refs: raise ValidationError("DNA pack requires at least one DNA reference")
    if distribution not in {"auto", "private_only", "public"}: raise ValidationError("DNA pack distribution must be auto, private_only, or public")
    project_root = project_root.resolve(); home = (home or apsal_home()).resolve()
    records = load_layered_registry(project_root, home); by_key = {_asset_key(item["asset"]): item for item in records}
    selected = []; seen_refs: set[tuple[str, str, str, str]] = set()
    for ref in refs:
        key = tuple(str(ref.get(field, "")) for field in ("namespace", "id", "type", "version")); record = by_key.get(key)
        if not record: raise ValidationError(f"unresolved DNA reference {_ref_label(key)}")
        if key in seen_refs: raise ValidationError(f"duplicate DNA Pack reference {_ref_label(key)}")
        seen_refs.add(key)
        if ref.get("content_digest") and ref["content_digest"] != digest(record["asset"]): raise ValidationError(f"DNA digest mismatch for {_ref_label(key)}")
        if record["asset"]["namespace"] != namespace: raise ValidationError("every DNA in a pack must use the pack namespace")
        if "discovery" not in record["asset"]: raise ValidationError(f"shared DNA requires confirmed discovery metadata: {_ref_label(key)}")
        selected.append(record)
    public_allowed = all(
        _dna_rights_allow_public(item["asset"], item["preview"])
        and item["asset"].get("discovery", {}).get("source") == "creator_confirmed"
        for item in selected
    )
    resolved_distribution = "public" if distribution == "auto" and public_allowed else "private_only" if distribution == "auto" else distribution
    if resolved_distribution == "public" and not public_allowed: raise ValidationError("public DNA Pack export rejected: rights or attribution are unresolved")
    payload: dict[str, bytes] = {}
    assets_manifest = []
    for record in sorted(selected, key=lambda item: _asset_key(item["asset"])):
        asset = record["asset"]; base = f"registry/{namespace}/{asset['type']}/{asset['id']}/{asset['version']}"
        asset_path = f"{base}/asset.apsal.json"; preview_path = f"{base}/preview.webp"; preview_meta_path = f"{base}/preview.json"
        payload[asset_path] = (json.dumps(asset, ensure_ascii=False, indent=2) + "\n").encode()
        payload[preview_path] = record["preview_path"].read_bytes()
        preview_meta = json.loads(json.dumps(record["preview"])); preview_meta["ref"] = asset_ref(asset); preview_meta["image"] = "preview.webp"
        payload[preview_meta_path] = (json.dumps(preview_meta, ensure_ascii=False, indent=2) + "\n").encode()
        assets_manifest.append({"ref": asset_ref(asset), "asset_path": asset_path, "preview_path": preview_path, "preview_metadata_path": preview_meta_path, "dependencies": asset.get("dependencies", [])})
    license_lines = [f"DNA Pack: {name}", f"Distribution: {resolved_distribution}", "Each DNA and preview retains the independent license and attribution in its metadata.", "Reference media is not included."]
    payload["LICENSE-CONTENT.md"] = ("\n".join(license_lines) + "\n").encode()
    payload["README.md"] = (f"# {name}\n\n{description}\n\nAPSAL DNA Extension Pack `{namespace}/{pack_id}@{version}`. Install with `apsal registry install <zip>`; assets remain immutable and participate in explained scene recommendations.\n").encode()
    files = {path: hashlib.sha256(data).hexdigest() for path, data in sorted(payload.items())}
    manifest = {
        "schema_version": DNA_PACK_SCHEMA_VERSION, "protocol": "apsal-open", "protocol_version": "0.3.0",
        "pack_id": pack_id, "namespace": namespace, "version": version, "name": name, "description": description,
        "distribution": resolved_distribution, "redistribution_allowed": public_allowed,
        "assets": assets_manifest, "asset_count": len(assets_manifest), "files": files,
    }
    checksum_text = "".join(f"{sha}  {path}\n" for path, sha in sorted(files.items()))
    archive_files = {**payload, "apsal-dna-pack.json": (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode(), "checksums.sha256": checksum_text.encode()}
    content = _zip_bytes(archive_files); sha = hashlib.sha256(content).hexdigest()
    output_dir.mkdir(parents=True, exist_ok=True); suffix = "-private" if resolved_distribution == "private_only" else ""
    path = output_dir / f"{pack_id}-v{version}{suffix}.zip"; path.write_bytes(content)
    checksum_path = path.with_suffix(".zip.sha256"); checksum_path.write_text(f"{sha}  {path.name}\n", encoding="utf-8")
    if resolved_distribution == "private_only":
        for item in (path, checksum_path):
            try: item.chmod(0o600)
            except OSError: pass
    return path, sha


def _resolve_dna_pack_source(source: str | Path) -> tuple[bytes, str]:
    value = str(source)
    if value.startswith("github:"):
        match = re.fullmatch(r"github:([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)@([^#]+)#([A-Za-z0-9_.-]+\.zip)", value)
        if not match: raise ValidationError("GitHub DNA Pack source must be github:owner/repo@tag#asset.zip")
        owner, repo, tag, asset = match.groups()
        value = f"https://github.com/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/releases/download/{urllib.parse.quote(tag, safe='')}/{urllib.parse.quote(asset)}"
    if value.startswith("https://"):
        parsed = urllib.parse.urlparse(value)
        if parsed.hostname not in {"github.com", "objects.githubusercontent.com"}: raise ValidationError("remote DNA Packs must use a public GitHub release URL")
        request = urllib.request.Request(value, headers={"User-Agent": "APSAL-Studio/0.6"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response: data = response.read(50_000_001)
        except urllib.error.URLError as exc: raise ValidationError(f"DNA Pack download failed: {exc}") from exc
        if len(data) > 50_000_000: raise ValidationError("DNA Pack exceeds 50 MB")
        return data, value
    path = Path(value).expanduser().resolve()
    if not path.is_file(): raise ValidationError(f"DNA Pack not found: {path}")
    if path.stat().st_size > 50_000_000: raise ValidationError("DNA Pack exceeds 50 MB")
    return path.read_bytes(), str(path)


def _inspect_dna_pack(data: bytes) -> tuple[dict[str, Any], dict[str, bytes]]:
    try: archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc: raise ValidationError("DNA Pack is not a valid ZIP") from exc
    names = archive.namelist()
    if len(names) != len(set(names)): raise ValidationError("DNA Pack contains duplicate paths")
    files: dict[str, bytes] = {}
    total_uncompressed = 0
    for info in archive.infolist():
        path = Path(info.filename)
        if info.is_dir(): continue
        if path.is_absolute() or ".." in path.parts or len(path.parts) > 8: raise ValidationError(f"unsafe DNA Pack path: {info.filename}")
        if (info.external_attr >> 16) & 0o170000 == 0o120000: raise ValidationError(f"DNA Pack symlink rejected: {info.filename}")
        total_uncompressed += info.file_size
        if info.file_size > 10_000_000 or total_uncompressed > 100_000_000: raise ValidationError("DNA Pack expanded content exceeds safety limits")
        files[info.filename] = archive.read(info)
    for required in ("apsal-dna-pack.json", "checksums.sha256", "README.md", "LICENSE-CONTENT.md"):
        if required not in files: raise ValidationError(f"DNA Pack missing {required}")
    try: manifest = json.loads(files["apsal-dna-pack.json"])
    except json.JSONDecodeError as exc: raise ValidationError("DNA Pack manifest is invalid JSON") from exc
    if not isinstance(manifest, dict): raise ValidationError("DNA Pack manifest must be an object")
    if manifest.get("schema_version") != DNA_PACK_SCHEMA_VERSION or manifest.get("protocol") != "apsal-open": raise ValidationError("DNA Pack manifest version or protocol is unsupported")
    if not SAFE_NAMESPACE.fullmatch(str(manifest.get("pack_id", ""))) or not SAFE_NAMESPACE.fullmatch(str(manifest.get("namespace", ""))): raise ValidationError("DNA Pack id or namespace is invalid")
    if manifest.get("namespace") == "official": raise ValidationError("DNA Extension Pack cannot use the official namespace")
    if not SEMVER.fullmatch(str(manifest.get("version", ""))): raise ValidationError("DNA Pack version is invalid")
    declared = manifest.get("files")
    if not isinstance(declared, dict): raise ValidationError("DNA Pack files ledger is missing")
    if set(declared) != set(files) - {"apsal-dna-pack.json", "checksums.sha256"}: raise ValidationError("DNA Pack files ledger does not match archive")
    for path, sha in declared.items():
        if not re.fullmatch(r"[a-f0-9]{64}", str(sha)) or hashlib.sha256(files[path]).hexdigest() != sha: raise ValidationError(f"DNA Pack checksum mismatch: {path}")
    expected_ledger = "".join(f"{sha}  {path}\n" for path, sha in sorted(declared.items())).encode()
    if files["checksums.sha256"] != expected_ledger: raise ValidationError("DNA Pack checksum ledger is not canonical")
    assets = manifest.get("assets")
    if not isinstance(assets, list) or len(assets) != manifest.get("asset_count") or not assets: raise ValidationError("DNA Pack asset count is invalid")
    seen = set()
    for entry in assets:
        if not isinstance(entry, dict): raise ValidationError("DNA Pack asset entry must be an object")
        for field in ("asset_path", "preview_path", "preview_metadata_path"):
            if entry.get(field) not in files: raise ValidationError(f"DNA Pack asset entry missing {field}")
        try: asset = json.loads(files[entry["asset_path"]]); preview = json.loads(files[entry["preview_metadata_path"]])
        except json.JSONDecodeError as exc: raise ValidationError("DNA Pack asset or preview metadata is invalid JSON") from exc
        if not isinstance(asset, dict) or not isinstance(preview, dict): raise ValidationError("DNA Pack asset and preview metadata must be objects")
        errors = validate_registry_asset(asset)
        if errors: raise ValidationError("\n".join(errors))
        if asset.get("namespace") != manifest["namespace"]: raise ValidationError("DNA Pack asset namespace mismatch")
        if entry.get("ref") != asset_ref(asset): raise ValidationError("DNA Pack asset reference digest mismatch")
        key = _asset_key(asset)
        if key in seen: raise ValidationError(f"DNA Pack duplicate asset {_ref_label(key)}")
        seen.add(key)
        with tempfile.TemporaryDirectory() as temporary:
            preview_path = Path(temporary) / "preview.webp"; preview_path.write_bytes(files[entry["preview_path"]])
            preview_errors = validate_preview_file(preview_path, preview)
        if preview_errors: raise ValidationError("\n".join(preview_errors))
        dependencies = entry.get("dependencies", [])
        if not isinstance(dependencies, list) or any(not isinstance(dep, dict) for dep in dependencies): raise ValidationError("DNA Pack dependencies must be reference objects")
        entry["_asset"] = asset
    return manifest, files


def validate_dna_pack(source: str | Path) -> dict[str, Any]:
    data, origin = _resolve_dna_pack_source(source); manifest, _ = _inspect_dna_pack(data)
    return {"valid": True, "origin": origin, "sha256": hashlib.sha256(data).hexdigest(), "pack_id": manifest["pack_id"], "namespace": manifest["namespace"], "version": manifest["version"], "distribution": manifest["distribution"], "asset_count": manifest["asset_count"]}


def install_dna_pack(source: str | Path, *, project_root: Path, home: Path | None = None) -> dict[str, Any]:
    """Install a validated local or public-GitHub DNA Pack as a read-only extension layer."""
    project_root = project_root.resolve(); home = (home or apsal_home()).resolve(); init_workspace(project_root, home)
    data, origin = _resolve_dna_pack_source(source); pack_sha = hashlib.sha256(data).hexdigest(); manifest, files = _inspect_dna_pack(data)
    target = home / "extensions" / manifest["namespace"] / manifest["pack_id"] / manifest["version"]
    existing_zip = target / "pack.zip"
    if existing_zip.is_file():
        if hashlib.sha256(existing_zip.read_bytes()).hexdigest() != pack_sha: raise ValidationError("immutable DNA Pack version conflict")
        return {"installed": False, "reason": "already_installed", "path": str(target), "sha256": pack_sha, "manifest": {key: value for key, value in manifest.items() if key != "assets"}}
    official_keys = {_asset_key(asset) for asset in load_catalog().get("assets", [])}
    existing_keys = {_asset_key(item["asset"]) for item in load_layered_registry(project_root, home)}
    pack_keys = {_asset_key(entry["_asset"]) for entry in manifest["assets"]}
    official_conflicts = pack_keys & official_keys
    if official_conflicts: raise ValidationError(f"DNA Pack cannot override official ID/version: {sorted(_ref_label(key) for key in official_conflicts)}")
    conflicts = pack_keys & existing_keys
    if conflicts: raise ValidationError(f"DNA Pack conflicts with installed Registry assets: {sorted(_ref_label(key) for key in conflicts)}")
    available = existing_keys | pack_keys
    for entry in manifest["assets"]:
        for dep in entry.get("dependencies", []):
            key = tuple(str(dep.get(field, "")) for field in ("namespace", "id", "type", "version"))
            if key not in available: raise ValidationError(f"DNA Pack unresolved dependency {_ref_label(key)}")
    temporary = target.with_name(target.name + f".tmp-{uuid.uuid4().hex[:8]}"); _mkdir_private(temporary)
    try:
        for name, value in files.items():
            path = _inside(temporary, temporary / name); path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(value)
        (temporary / "pack.zip").write_bytes(data)
        target.parent.mkdir(parents=True, exist_ok=True); temporary.rename(target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True); raise
    for path in target.rglob("*"):
        try: path.chmod(0o500 if path.is_dir() else 0o400)
        except OSError: pass
    return {"installed": True, "origin": origin, "path": str(target), "sha256": pack_sha, "manifest": {key: value for key, value in manifest.items() if key != "assets"}}


def pack_theme(
    theme: dict[str, Any], output_dir: Path, source_yaml: bytes | None = None,
    *, assets: list[dict[str, Any]] | None = None, reference_paths: dict[str, Path] | None = None,
    distribution: str = "auto",
) -> tuple[Path, str]:
    compiled = compile_theme(theme, "image", assets)
    design = compile_theme(theme, "design", assets) if theme.get("schema_version") == "1.1.0" else None
    qa = compile_theme(theme, "qa", assets) if theme.get("schema_version") == "1.1.0" else None
    reference_manifest, reference_files = build_reference_manifest(theme, reference_paths, distribution=distribution)
    slug = f"{theme['id'].lower()}-{theme['version'].replace('.', '-')}"
    canonical_output = theme.get("output", {})
    output = codex_delivery_contract(canonical_output, len(theme["shots"]))
    medium_instruction = (
        "The adult subject must remain a real human in live-action photography. Handmade, crayon, painted, or illustrated styling may affect only the set and props. "
        "Reject any illustrated, anime, painted, doll-like, wax, clay, mannequin, or 3D-rendered person."
        if theme.get("rendering_contract") else
        "This legacy theme does not declare a live-action rendering contract; do not claim that it guarantees a real-human photographic result."
    )
    requested_size = output.get("requested_size") or output.get("size", "not_reported")
    execution_instruction = (
        f"Use Codex's built-in image-generation capability directly for {output.get('count', len(theme['shots']))} sequential Jobs. "
        "Do not call an image API, do not ask for an API key, and do not run an HTTP generation script. "
        f"Request {output.get('aspect_ratio', 'the declared aspect ratio')} and high quality; {requested_size} is a creative delivery request, not a guaranteed returned pixel size."
    )
    skill = f'''---
name: {slug}
description: Generate the fixed APSAL Open photography set “{theme['name']}” in Codex from its bundled Prompts, references, rendering contract and QA plan. Use when the creator asks to use this theme, generate or continue its shots, inspect its Prompt package, or reproduce the set without configuring an image API.
---

# {theme['name']}

Read `PROMPT_GUIDE.en.md` for English creators or `PROMPT_GUIDE.zh-CN.md` for Chinese creators, plus `references/theme.json`, `references/compiled.json`, `references/reference_manifest.json`, and `references/rendering_contract.json`. Also read `references/design_context.json` and `references/qa_checklist.json` when present. For a specific Job, use `prompts/SHOT_XX.full.txt` as the exact provider-neutral Prompt and pass every listed reference image from `assets/references/`; never replace the actual image with its text summary. Respect each reference's allowed and forbidden uses.

{medium_instruction}

{execution_instruction}

Generate exactly one independent image per Codex image-generation call. After emitting an image, stop; when the creator says “继续” or “下一张”, continue with the next uncompleted Job. If all required references have local paths, pass those paths. Otherwise use the smallest recent-image count that includes the immediately previous accepted shot and use it only for identity continuity; never combine mutually exclusive reference mechanisms. Do not inherit the anchor's pose, camera, background, action, wardrobe, or composition.

Never use a grid, collage, contact sheet, typography, logo, or watermark. Inspect every returned image for live-action medium, identity, skin, eyes, hands, anatomy, optics, physical light, materials, prop ownership, continuity and shot intent. Keep Codex visual review separate from human visual QA. Record actual dimensions or format only when Codex reports them; otherwise use `not_reported` and never claim native 4K.
'''
    prefix = f"{slug}/"
    prompt_files: dict[str, bytes] = {}
    for shot in compiled["shots"]:
        shot_id = shot["shot_id"]
        prompt_files[f"prompts/{shot_id}.prompt.txt"] = (shot["positive_prompt"] + "\n").encode()
        prompt_files[f"prompts/{shot_id}.negative.txt"] = (shot["negative_prompt"] + "\n").encode()
        prompt_files[f"prompts/{shot_id}.full.txt"] = (shot["positive_prompt"] + "\n\nNegative constraints:\n" + shot["negative_prompt"] + "\n").encode()
    prompt_checksums = {name: hashlib.sha256(data).hexdigest() for name, data in prompt_files.items()}
    manifest = {
        "schema_version": "0.9.0", "engine_version": ENGINE_VERSION, "skill_id": theme["id"],
        "skill_version": theme["version"], "theme_digest": digest(theme), "compiled_digest": compiled["compiled_digest"],
        "reference_manifest_digest": reference_manifest["reference_manifest_digest"],
        "credentials_included": False, "api_key_required": False, "direct_api_calls": False,
        "generation_surface": "codex_imagegen", "private_media_included": reference_manifest["private_media_included"],
        "distribution": reference_manifest["distribution"], "redistribution_allowed": reference_manifest["redistribution_allowed"],
        "output_request": output, "returned_dimensions_guaranteed": False,
        "rendering_contract_required": bool(theme.get("rendering_contract")), "prompt_files": prompt_checksums,
    }
    if theme.get("semantic_contract_version"): manifest["semantic_contract_version"] = theme["semantic_contract_version"]
    guide_zh = f'''# {theme['name']} — Codex Prompt 使用包

这个 ZIP 同时是可安装的 Codex Skill 和可独立阅读的 Prompt 包。它不会调用图像 API，也不需要 `OPENAI_API_KEY`。

## 在 Codex 中使用

1. 解压后把 `{slug}` 目录放进 Codex Skills 目录，或在 Codex 中直接提供这个目录。
2. 新建任务并说：“使用 `${slug}` 生成第一张图。”
3. Codex 读取 `prompts/SHOT_01.full.txt`，附加本镜在 `references/reference_manifest.json` 中声明的真实参考图，并直接调用 Codex 内置图像生成。
4. 每次只生成一张。看完后说“继续下一张”，Codex 会按 SHOT_02 到最后一镜依次执行。
5. 若只想复制 Prompt，直接打开任一 `prompts/SHOT_XX.full.txt`；`.prompt.txt` 与 `.negative.txt` 分别保存正向与负向部分。

## 重要说明

- 请求画幅：{output.get('aspect_ratio', 'not_reported')}；请求尺寸：{requested_size}。
- Codex 管理实际图像模型、格式和像素尺寸；除非返回元数据明确报告，否则它们记为 `not_reported`。本包不承诺原生 4K。
- 一次调用只生成一个 Job，不生成九宫格、拼图、联系表、文字、标志或水印。
- `assets/references/` 中的图片必须按用途、禁止用途与权利清单实际传入；文字分析不能替代图片。
- 后续镜头若使用上一张图保持人物身份，只继承身份，不继承姿势、机位、背景、动作、服装或构图。

Run `python3 scripts/validate_prompt_pack.py --list` to verify checksums and list every Job without making a network request.
'''
    guide_en = f'''# {theme['name']} — Codex Prompt package

This ZIP is both an installable Codex Skill and a directly readable Prompt package. It does not call an image API and does not require `OPENAI_API_KEY`.

## Use it in Codex

1. Unzip the package and place the `{slug}` folder in your Codex Skills directory, or provide the directory directly to Codex.
2. Start a new task and say: “Use `${slug}` to generate the first image.”
3. Codex reads `prompts/SHOT_01.full.txt`, attaches the real reference files declared for that shot in `references/reference_manifest.json`, and calls Codex built-in image generation.
4. Generate one image at a time. After reviewing it, say “continue to the next image.” Codex advances from SHOT_02 through the final shot.
5. To copy a Prompt without generating, open any `prompts/SHOT_XX.full.txt`. The `.prompt.txt` and `.negative.txt` files contain the positive and negative parts separately.

## Important constraints

- Requested aspect ratio: {output.get('aspect_ratio', 'not_reported')}; requested delivery size: {requested_size}.
- Codex manages the actual image model, format, and pixel dimensions. Unless returned metadata explicitly reports them, they remain `not_reported`. This package does not promise native 4K.
- One call creates one Job. Never create a grid, collage, contact sheet, text, logo, or watermark.
- Images under `assets/references/` must be passed according to their allowed uses, forbidden uses, and rights manifest. A prose analysis cannot replace the actual image.
- A prior accepted shot may preserve identity only. It must not transfer pose, camera, background, action, wardrobe, or composition.

Run `python3 scripts/validate_prompt_pack.py --list` to verify checksums and list every Job without making a network request.
'''
    guide_index = f'''# {theme['name']} — Prompt/Skill package

- [English instructions](PROMPT_GUIDE.en.md)
- [中文使用说明](PROMPT_GUIDE.zh-CN.md)

Codex should open the guide that matches the current conversation language. The frozen image Prompts are identical in both workflows.
'''
    files = {
        prefix + "SKILL.md": skill.encode(),
        prefix + "PROMPT_GUIDE.md": guide_index.encode(),
        prefix + "PROMPT_GUIDE.en.md": guide_en.encode(),
        prefix + "PROMPT_GUIDE.zh-CN.md": guide_zh.encode(),
        prefix + "references/theme.json": (json.dumps(theme, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "references/compiled.json": (json.dumps(compiled, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "references/manifest.json": (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "references/reference_manifest.json": (json.dumps(reference_manifest, ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "references/rendering_contract.json": (json.dumps(theme.get("rendering_contract", {"status": "not_declared_legacy"}), ensure_ascii=False, indent=2) + "\n").encode(),
        prefix + "scripts/validate_prompt_pack.py": (plugin_root() / "assets" / "templates" / "validate_prompt_pack.py").read_bytes(),
        prefix + "LICENSE-CONTENT.md": (
            "Theme specification content is licensed CC BY 4.0. Attribution: APSAL Open contributors.\n"
            "Bundled reference images retain the independent rights recorded in references/reference_manifest.json.\n"
            f"Distribution: {reference_manifest['distribution']}; redistribution allowed: {str(reference_manifest['redistribution_allowed']).lower()}.\n"
        ).encode(),
    }
    for name, data in prompt_files.items(): files[prefix + name] = data
    for name, data in reference_files.items(): files[prefix + "assets/references/" + name] = data
    if design is not None and qa is not None:
        files[prefix + "references/design_context.json"] = (json.dumps(design, ensure_ascii=False, indent=2) + "\n").encode()
        files[prefix + "references/qa_checklist.json"] = (json.dumps(qa, ensure_ascii=False, indent=2) + "\n").encode()
    if source_yaml is not None:
        files[prefix + "references/theme.apsal.yaml"] = source_yaml
    content = _zip_bytes(files); sha = hashlib.sha256(content).hexdigest()
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = "-private" if reference_manifest["distribution"] == "private_only" else ""
    path = output_dir / f"{slug}-codex-prompt-skill{suffix}.zip"; path.write_bytes(content)
    checksum_path = path.with_suffix(".zip.sha256"); checksum_path.write_text(f"{sha}  {path.name}\n", encoding="utf-8")
    if reference_manifest["distribution"] == "private_only":
        for private_path in (path, checksum_path):
            try: private_path.chmod(0o600)
            except OSError: pass
    return path, sha
