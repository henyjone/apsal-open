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
BRAND_MASTER = ROOT / "assets" / "brand" / "apsal-worldbuilding-master.png"

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

CARD_CROPS = {
    "character": (1035, 0, 1755, 540),
    "style": (855, 0, 1815, 720),
    "environment": (705, 0, 1905, 900),
    "lighting": (1095, 0, 1695, 450),
    "composition": (750, 0, 1890, 855),
    "shot": (990, 30, 1590, 480),
    "qa": (1110, 60, 1590, 420),
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

    asset_type = asset["type"]
    label, zh, axis = LABELS[asset_type]
    source = Image.open(BRAND_MASTER).convert("RGB")
    image = source.crop(CARD_CROPS[asset_type]).resize((768, 576), Image.Resampling.LANCZOS).convert("RGBA")

    shade = Image.new("RGBA", image.size, (0, 0, 0, 0))
    pixels = shade.load()
    for x in range(570):
        alpha = int(226 * (1 - x / 570) ** 1.45)
        for y in range(576):
            pixels[x, y] = (7, 9, 8, alpha)
    image = Image.alpha_composite(image, shade)

    draw = ImageDraw.Draw(image)
    ivory, celadon, lime, dim = "#F4F0E5", "#91AA9F", "#C8FF00", "#65736D"
    draw.rectangle((28, 28, 740, 548), outline=(101, 115, 109, 170), width=1)
    draw.line((62, 102, 512, 102), fill=(101, 115, 109, 170), width=1)
    draw.text((62, 58), "APSAL  元素摄影法", font=_font(18), fill=celadon)
    draw.text((62, 151), label, font=_font(48), fill=ivory)
    draw.text((64, 218), zh, font=_font(25), fill="#C1CBC6")

    draw.line((64, 302, 430, 302), fill=dim, width=1)
    draw.rectangle((444, 295, 458, 309), fill=lime)
    draw.line((600, 80, 704, 80), fill=(244, 240, 229, 150), width=1)
    draw.line((704, 80, 704, 184), fill=(244, 240, 229, 150), width=1)
    draw.ellipse((696, 72, 712, 88), outline=lime, width=2)

    draw.text((64, 492), axis, font=_font(16), fill=celadon)
    draw.text((704, 492), f"0{list(LABELS).index(asset_type) + 1}", anchor="ra", font=_font(16), fill="#A4AEA9")
    image.convert("RGB").save(path, "WEBP", quality=88, method=6)


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
                "status": "ai_assisted_original_open_content",
                "attribution": "HenyJone / APSAL Open contributors",
                "reference_media": "none",
                "ai_disclosure": True,
                "source_asset": "assets/brand/apsal-worldbuilding-master.png",
            },
            "qa_status": "static_validated",
            "visual_qa_status": "human_review_pending",
            "disclaimer": "Design preview; not generated-image quality evidence.",
        })
    catalog = {
        "schema_version": "0.1.0",
        "preview_catalog_version": "0.2.0",
        "parent_preview_catalog_version": "0.1.0",
        "changed_fields": ["previews[*].image", "previews[*].sha256", "previews[*].rights", "previews[*].visual_qa_status"],
        "change_summary": "Replace abstract protocol cards with a unified Chinese fashion-photographer editorial system; DNA references and content digests remain unchanged.",
        "previews": previews,
    }
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
    print("official DNA previews validated: 7 editorial semantic cards, 768x576 WebP, rights and SHA-256")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
