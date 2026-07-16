#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "assets" / "brand"
MASTER = BRAND / "apsal-worldbuilding-master.png"
SOCIAL_SIZE = (1280, 640)
MASTER_SIZE = (1920, 960)

JPEG_TARGETS = (
    "apsal-readme-banner.jpg",
    "apsal-social-preview-v2.jpg",
    "apsal-social-preview.jpg",
    "apsal-worldbuilding-banner.jpg",
    "apsal-worldbuilding-social-preview.jpg",
)
PNG_TARGETS = ("apsal-social-preview-v2.png",)


def generate() -> None:
    image = Image.open(MASTER).convert("RGB")
    if image.size != MASTER_SIZE:
        raise ValueError(f"brand master must be {MASTER_SIZE[0]}x{MASTER_SIZE[1]}, got {image.size}")
    social = image.resize(SOCIAL_SIZE, Image.Resampling.LANCZOS)
    for name in JPEG_TARGETS:
        social.save(BRAND / name, "JPEG", quality=94, optimize=True, progressive=True, subsampling=0)
    for name in PNG_TARGETS:
        image.save(BRAND / name, "PNG", optimize=True)


def check() -> list[str]:
    errors: list[str] = []
    if not MASTER.is_file():
        return [f"missing brand master: {MASTER.relative_to(ROOT)}"]
    if Image.open(MASTER).size != MASTER_SIZE:
        errors.append(f"brand master must be {MASTER_SIZE[0]}x{MASTER_SIZE[1]}")
    for name in JPEG_TARGETS:
        path = BRAND / name
        if not path.is_file():
            errors.append(f"missing brand asset: {path.relative_to(ROOT)}")
        elif Image.open(path).size != SOCIAL_SIZE:
            errors.append(f"{name}: expected {SOCIAL_SIZE[0]}x{SOCIAL_SIZE[1]}")
        elif path.stat().st_size >= 1_000_000:
            errors.append(f"{name}: exceeds GitHub's 1 MB social-preview limit")
    for name in PNG_TARGETS:
        path = BRAND / name
        if not path.is_file():
            errors.append(f"missing brand asset: {path.relative_to(ROOT)}")
        elif Image.open(path).size != MASTER_SIZE:
            errors.append(f"{name}: expected {MASTER_SIZE[0]}x{MASTER_SIZE[1]}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        generate()
    errors = check()
    if errors:
        print("\n".join(errors))
        return 1
    print("APSAL brand images validated: one 1920x960 master and five GitHub-safe 1280x640 JPEGs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
