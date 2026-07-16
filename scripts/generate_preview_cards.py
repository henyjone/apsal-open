#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "apsal-studio"
OUTPUT = PLUGIN / "assets" / "previews"
ENGINE_PATH = PLUGIN / "scripts" / "apsal_engine.py"

spec = importlib.util.spec_from_file_location("apsal_engine_previews", ENGINE_PATH)
engine = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(engine)

LABELS = {
    "character": ("CHARACTER DNA", "身份与连续性", "IDENTITY / PRESENCE"),
    "style": ("STYLE DNA", "视觉修辞", "TEXTURE / RHYTHM"),
    "environment": ("WORLD DNA", "空间与物理", "SPACE / MATERIAL"),
    "lighting": ("LIGHT DNA", "时间与光线", "DIRECTION / PHASE"),
    "composition": ("SCENE DNA", "经营位置", "ORDER / RELATION"),
    "shot": ("SHOT DNA", "视点与事件", "VIEWPOINT / EVENT"),
    "qa": ("QA DNA", "证据与边界", "VERIFY / PRESERVE"),
}


def _font(size: int):
    from PIL import ImageFont

    candidates = (
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    for candidate in candidates:
        if Path(candidate).is_file():
            try: return ImageFont.truetype(candidate, size)
            except OSError: pass
    return ImageFont.load_default()


def _draw_card(asset: dict, path: Path) -> None:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (768, 576), "#111513")
    draw = ImageDraw.Draw(image)
    ivory, celadon, dim = "#EEEADF", "#84A99C", "#3D4B46"
    asset_type = asset["type"]
    label, zh, axis = LABELS[asset_type]

    draw.rectangle((28, 28, 740, 548), outline=dim, width=1)
    draw.rectangle((52, 52, 716, 524), outline="#26312D", width=1)
    draw.line((78, 122, 690, 122), fill=dim, width=1)
    draw.text((78, 73), "APSAL / OPEN PHOTOGRAPHY PROTOCOL", font=_font(17), fill=celadon)
    draw.text((78, 154), label, font=_font(44), fill=ivory)
    draw.text((80, 216), zh, font=_font(24), fill="#B9C5BE")

    # A reusable protocol glyph: one world frame, modular nodes, and a selected viewpoint.
    draw.rectangle((80, 302, 414, 438), outline="#60746C", width=2)
    draw.arc((118, 330, 266, 478), 187, 338, fill=celadon, width=4)
    draw.line((250, 370, 390, 330), fill="#53665F", width=2)
    draw.line((250, 370, 390, 408), fill="#53665F", width=2)
    for x, y, radius in ((250, 370, 10), (390, 330, 7), (390, 408, 7)):
        draw.ellipse((x-radius, y-radius, x+radius, y+radius), outline=ivory, fill="#111513", width=2)
    draw.rectangle((468, 302, 690, 438), outline="#60746C", width=2)
    draw.line((491, 327, 667, 413), fill="#36443F", width=1)
    draw.line((667, 327, 491, 413), fill="#36443F", width=1)
    draw.ellipse((548, 342, 610, 404), outline=celadon, width=3)

    draw.text((80, 474), axis, font=_font(16), fill=celadon)
    draw.text((690, 474), f"0{list(LABELS).index(asset_type) + 1}", anchor="ra", font=_font(16), fill="#7D8983")
    image.save(path, "WEBP", quality=86, method=6)


def generate() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    previews = []
    for asset in engine.load_catalog()["assets"]:
        image_name = f"{asset['type']}.webp"
        image_path = OUTPUT / image_name
        _draw_card(asset, image_path)
        previews.append({
            "schema_version": "0.1.0",
            "ref": engine.asset_ref(asset),
            "image": image_name,
            "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            "kind": "semantic_card",
            "rights": {
                "license": "CC-BY-4.0",
                "status": "original_open_content",
                "attribution": "HenyJone / APSAL Open contributors",
            },
            "qa_status": "static_validated",
            "visual_qa_status": "not_applicable_semantic_card",
            "disclaimer": "Design preview; not generated-image quality evidence.",
        })
    catalog = {"schema_version": "0.1.0", "preview_catalog_version": "0.1.0", "previews": previews}
    (OUTPUT / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check: generate()
    errors = engine.validate_official_previews()
    if errors:
        print("\n".join(errors))
        return 1
    print("official DNA previews validated: 7 semantic cards, 768x576 WebP, rights and SHA-256")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
