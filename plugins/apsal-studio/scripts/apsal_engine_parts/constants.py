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

ENGINE_VERSION = "0.16.0"
OPEN_PROTOCOL_VERSION = "0.4.0"
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
AUTHORING_MODES = ("guided", "automatic")
STAGE_PREVIEW_SCHEMA_VERSION = "0.1.0"
STAGE_PREVIEW_COLORS = {
    "direction": ("#F7C873", "#583A14"),
    "worldbuilding": ("#EDB44E", "#523513"),
    "narrative": ("#E6A13A", "#4C2F0E"),
    "image": ("#F5A524", "#5B350A"),
    "delivery": ("#D98A0E", "#4B2B08"),
}
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
SET_STRATEGIES = ("chaptered_variation", "continuous_narrative")
DEFAULT_SET_STRATEGY = "chaptered_variation"
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
SAFE_ID = re.compile(r"^[A-Z][A-Z0-9-]*$")
SAFE_ASSET_ID = re.compile(r"^[A-Z][A-Z0-9_]*$")
SAFE_NAMESPACE = re.compile(r"^[a-z][a-z0-9-]*$")
SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
REFERENCE_USES = {
    "identity", "subject", "world", "space", "composition", "lighting",
    "wardrobe", "color", "style", "prop",
}
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
