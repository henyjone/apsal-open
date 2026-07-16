---
name: apsal-theme-creator
description: Create, revise, resume, generate, or package an APSAL photography theme from one natural-language brief through interactive Character, World, Scene, and Photo DNA cards. Use for AI 摄影主题、九张独立照片、人物锁定、场景设计、摄影语言、DNA 选择、Prompt 保存或 APSAL Skill 导出。
---

# APSAL Theme Creator

Keep JSON and YAML in the local artifact layer. Never ask a creator to write or inspect them unless they explicitly request developer mode.

## Create through four confirmations

1. Call `start_design_session` with the creator's natural-language brief. Default to nine independent 2:3 images.
2. For `character`, `world`, `scene`, then `photo`, call `present_dna_cards`. Explain the design consequence in natural language and let the creator select, revise, or ask for another option.
3. Call `commit_stage` only after the creator confirms that stage. For Scene, present the sequence strategy and nine distinct Scene cards; support accepting the set, revising one shot, redesigning one shot, or changing order.
4. If an upstream choice changes, respect the returned invalidations and reconfirm every affected downstream stage. Never reuse stale prompts.
5. At `review_pending`, show a compact nine-shot overview and offer exactly: generate nine images, save prompts only, or export a Skill.
6. Call `finalize_theme` after the creator confirms the overview. Treat the returned local artifact as the source of truth.

Read [references/INTERACTION.md](references/INTERACTION.md) for card contents, natural-language revision rules, state transitions, identity references, and storage behavior.

## Generate one Job at a time

Before any paid or remote generation, obtain an explicit “生成九张图” confirmation and pass `confirmed: true` to `start_generation_run`.

- When Codex ImageGen is available, generate each pending Job in its own call from the saved effective prompt. Never request a grid, contact sheet, collage, typography, logo, or watermark.
- Record every success or failure with `record_generation_result`. Do not repeat a successful Job because another Job failed.
- Resume only failed or pending Jobs. Keep provider/model parameters as `not_reported` when the provider did not return them; never infer metadata.
- When ImageGen is unavailable, use `mode: prompts` or `mode: skill`. Tell the creator where the local artifacts were saved.
- Static validation and semantic cards are not photographic visual QA. Review identity, hands, anatomy, geometry, reflection, prop ownership, lighting, continuity, intent, and restricted output manually.

Private reference images belong only in the local content-addressed Vault. Never place them in DNA JSON, Git, chat exports, or a Skill ZIP.

## Preserve APSAL invariants

Identity and rights outrank world continuity; world continuity outranks event and shot function; those outrank camera/light/color; style rhetoric comes last. A published DNA version is immutable. Any generation-intent change creates a new semantic version with parent version, changed fields, summary, rights, and QA status.

Chinese aesthetic concepts—including 经营位置、意境、气韵、虚实 and 散点观看—explain relationships in world construction. Do not reduce them to arbitrary numeric sliders.
