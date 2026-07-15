---
name: apsal-theme-creator
description: Create, validate, compile, or package an APSAL photography theme from a natural-language brief using the bundled offline DNA catalog. Use for 摄影主题, 场景 JSON, 九宫格之外的九张独立照片, DNA 组合, APSAL theme, shot plan, or packaging a Codex photography Skill.
---

# APSAL Theme Creator

Use the bundled `scripts/apsal.py`; it performs no network calls. APSAL Open has three separate layers: Apache-2.0 protocol, Apache-2.0 reference engine, and explicitly licensed content.

1. Ask for the overall creative brief, subject constraints, and desired shot count. Default to nine independent images.
2. Run `python3 scripts/apsal.py catalog` and select one compatible asset from every required category. Never invent a catalog ID or version.
3. Run `python3 scripts/apsal.py new --id <ID> --name <NAME> --shots <COUNT> -o <theme.apsal.yaml>` to create the Semantic Contract authoring source. YAML is editable; canonical JSON is generated.
4. Edit only the YAML source. Fill every element and shot intent with purpose, affected paths, invariants, allowed variation, expected effects, QA expectations and registered semantic tags. Fill each shot with a distinct narrative purpose, framing, action, hands, gaze, composition, continuity state, and unique output filename.
5. Preserve the same fictional adult identity and shared world across the set. Each output is an independent finished image: no collage, grid, contact sheet, text, logo, or watermark.
6. Record rights status, semantic version, parent version, changed fields, change summary, and QA status. Static checks must not be described as visual QA.
7. Run `normalize` to produce `.apsal.json`, then `check-sync`. Never edit YAML and JSON independently.
8. Run `compile --target design`, `compile --target image`, and `compile --target qa`. Use design context for scene reasoning, image output for generation, and QA output for evidence checks.
9. Run `validate`, fix every error, then `pack` to create an installable theme Skill ZIP. Report its SHA-256 and the validation result.

When reviewing or importing an existing modular package, extract it outside the repository and run `validate-package`. Calling a file a protocol is not a license. Do not import any content until license, attribution, reference-media rights, lineage, checksums, and QA state all pass.

For a generation-intent change, create a new semantic version. Never overwrite a published version or include private reference media in a theme package.

Chinese aesthetic concepts may explain the method, but never convert 经营位置、气韵、意境、虚实 or 游观 into arbitrary numeric parameters. Use the bilingual semantic registry and observable fields.
