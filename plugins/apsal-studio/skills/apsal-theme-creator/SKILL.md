---
name: apsal-theme-creator
description: Create, validate, compile, or package an APSAL photography theme from a natural-language brief using the bundled offline DNA catalog. Use for 摄影主题, 场景 JSON, 九宫格之外的九张独立照片, DNA 组合, APSAL theme, shot plan, or packaging a Codex photography Skill.
---

# APSAL Theme Creator

Use the bundled `scripts/apsal.py`; it performs no network calls.

1. Ask for the overall creative brief, subject constraints, and desired shot count. Default to nine independent images.
2. Run `python3 scripts/apsal.py catalog` and select one compatible asset from every required category. Never invent a catalog ID or version.
3. Run `python3 scripts/apsal.py new --id <ID> --name <NAME> --shots <COUNT> -o <theme.json>` to create the canonical skeleton.
4. Edit only the new theme file. Fill each shot with a distinct narrative purpose, framing, action, hands, gaze, foreground, background, continuity state, and unique output filename.
5. Preserve the same fictional adult identity and shared world across the set. Each output is an independent finished image: no collage, grid, contact sheet, text, logo, or watermark.
6. Record rights status, semantic version, parent version, changed fields, change summary, and QA status. Static checks must not be described as visual QA.
7. Run `validate`, then `compile`. Fix every error before packaging.
8. Run `pack` to create an installable theme Skill ZIP. Report its SHA-256 and the validation result.

For a generation-intent change, create a new semantic version. Never overwrite a published version or include private reference media in a theme package.
