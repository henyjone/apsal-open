#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "plugins/apsal-studio/scripts/apsal_engine.py"
spec = importlib.util.spec_from_file_location("apsal_engine", ENGINE)
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
theme = module.new_theme("APSAL-OPEN-001", "Quiet Window / 窗边未寄", 9)
purposes = ["Establish the room and solitary arrival", "Reveal the full silhouette at the window", "Begin a small act of unfolding a letter", "Hold the pause before reading", "Observe fingertips on textured paper", "Turn toward changing light", "Cross the room with the letter lowered", "Return to the table after deciding", "Close on a calm, unresolved expression"]
actions = ["steps into the room while the curtain moves", "stands beside the window and steadies the curtain", "unfolds a blank cream sheet", "pauses with the sheet held below eye level", "smooths one corner of the paper", "turns her head toward the late light", "walks past the low table", "places the sheet face down on the table", "breathes out and looks just beyond camera"]
for i, shot in enumerate(theme["shots"]):
    shot["title"] = ["Arrival", "Window Figure", "Unfolding", "Before Reading", "Paper Detail", "Light Turns", "Crossing", "Decision", "Afterword"][i]
    shot["narrative_purpose"] = purposes[i]; shot["action"] = actions[i]
    shot["hands"] = "both hands visible and naturally engaged with the action" if i in (2, 3, 4, 7) else "hands relaxed, anatomically plausible, and consistent with the action"
    shot["gaze"] = "motivated by the window, paper, or path of movement; never an arbitrary fashion stare"
    shot["composition"] = "distinct editorial framing with coherent room geometry, controlled depth, and purposeful negative space"
(ROOT / "examples/quiet-window/theme.json").write_text(json.dumps(theme, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
