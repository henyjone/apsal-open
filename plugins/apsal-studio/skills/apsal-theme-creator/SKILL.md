---
name: apsal-theme-creator
description: Create, revise, resume, generate, or package an APSAL photography theme; recommend scene-matched DNA, tag and remember confirmed personal DNA, and export or install shareable DNA Extension Packs. Use for AI 摄影主题、九张独立照片、人物锁定、场景设计、DNA 推荐/入库/分享、Prompt 保存或 APSAL Skill 导出。
---

# APSAL Theme Creator

Keep JSON and YAML in the local artifact layer. Never ask a creator to write or inspect them unless they explicitly request developer mode.

## Create through four confirmations

1. Call `start_design_session` with the creator's natural-language brief. Default to nine independent 9:16, 2160×3840 high-quality PNG images and a live-action photography Rendering Contract.
2. For `character`, `world`, `scene`, then `photo`, call `recommend_dna` with the complete scene brief and current session. Show the top matching cards and their concrete recommendation reasons; use `search_dna` only for an explicit lookup.
3. If the creator makes or revises DNA, call `suggest_dna_tags`, show the controlled semantic tags and facets, and obtain confirmation before including that discovery metadata in `draft_assets`.
4. Call `commit_stage` only after the creator confirms that stage. For Scene, present the sequence strategy and nine distinct Scene cards; support accepting the set, revising one shot, redesigning one shot, or changing order.
5. When `commit_stage` returns a pending memory offer, ask exactly once: “保存到我的 DNA、仅保留在当前项目，还是稍后决定？” Call `resolve_dna_memory` with the answer. Do not ask for official, extension, or already-personal DNA.
6. If an upstream choice changes, respect the returned invalidations and reconfirm every affected downstream stage. Never reuse stale prompts.
7. At `review_pending`, show a compact nine-shot overview and offer exactly: generate nine images, save prompts only, or export a Skill.
8. Call `finalize_theme` after the creator confirms the overview. Treat the returned local artifact as the source of truth.

At every stage, confirm each supplied reference image's role (`style`, `world`, `prop`, `wardrobe`, `composition`, or `identity`), allowed and forbidden uses, applicable Jobs, rights/consent, attribution, and redistribution status. Pass these as `reference_bindings`; never replace the image itself with a prose analysis.

Read [references/INTERACTION.md](references/INTERACTION.md) for card contents, natural-language revision rules, state transitions, identity references, and storage behavior.

## Learn and exchange DNA

- Use controlled `semantic_tags` for protocol reasoning and controlled `facets` for scene retrieval. Do not replace stable IDs, versions, rights, dependencies, or locks with free-form tags.
- After a real result, call `record_dna_feedback` as `successful` or `failed`; record an explicit rejection as `rejected`. Raw briefs are not stored in recommendation history.
- Export selected DNA with `export_dna_pack`, not the theme Skill packager. Public packs require one namespace, creator-confirmed discovery metadata, resolved licenses/attribution, valid previews, dependencies, and checksums. Otherwise export `private_only`.
- Install only a local ZIP or a pinned public GitHub Release source such as `github:owner/repo@v1.0.0#pack-v1.0.0.zip`. Installed packs are read-only `extension` Registry layers and cannot override official or installed ID/version pairs.

## Generate one Job at a time

Before any paid or remote generation, show the live-action contract, reference count, private/public status, 9:16 size, nine separate requests, and possible provider charges. Obtain one explicit “生成九张图” confirmation and pass `confirmed: true` to `start_generation_run`.

- For guaranteed provider-native 2160×3840 output, use `adapter: openai-image-api`, `model: gpt-image-2`, and then call `execute_generation_run`. The API key comes only from `OPENAI_API_KEY`. Each Job is an independent `n: 1` request with its own Prompt and bound references.
- `execute_generation_run` produces at most one unreviewed image by default. Inspect it for live-action adult-human medium, skin, eyes, hands, anatomy, optical depth, physical light, material response, identity and continuity; record the result with `record_model_visual_qa`, then continue. Human visual QA remains separately pending.
- A failed Job may retry twice. Resume only failed or pending Jobs, and never overwrite a successful Job. `SHOT_01` may become an identity-only runtime anchor; never inherit its pose, background, action, wardrobe, camera, or composition.
- Keep provider/model parameters as `not_reported` when the provider did not return them; never infer metadata.
- Codex ImageGen does not guarantee the requested native 4K size. Do not silently use it as a native-4K fallback. Without `OPENAI_API_KEY`, use `mode: prompts` or `mode: skill`, or explicitly label the result “dimensions not guaranteed.”
- Never request a grid, contact sheet, collage, typography, logo, or watermark.
- Static validation and semantic cards are not photographic visual QA. Review identity, hands, anatomy, geometry, reflection, prop ownership, lighting, continuity, intent, and restricted output manually.

Original references remain in the local content-addressed Vault and never enter DNA JSON, Git, or chat exports. A local exported Skill includes sanitized copies plus an integrity-checked purpose manifest so the generation model can actually receive them. If rights or redistribution are unresolved, package only as `private_only`; never publish it to GitHub or APSAL Hub. A public Skill may include a reference only when its independent license, consent, attribution, and redistribution permission are explicit.

## Preserve APSAL invariants

Identity and rights outrank world continuity; world continuity outranks event and shot function; those outrank camera/light/color; style rhetoric comes last. A published DNA version is immutable. Any generation-intent change creates a new semantic version with parent version, changed fields, summary, rights, and QA status.

Chinese aesthetic concepts—including 经营位置、意境、气韵、虚实 and 散点观看—explain relationships in world construction. Do not reduce them to arbitrary numeric sliders.
