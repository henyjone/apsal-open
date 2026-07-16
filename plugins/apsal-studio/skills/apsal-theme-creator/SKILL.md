---
name: apsal-theme-creator
description: Create, revise, resume, generate, or package an APSAL photography theme; recommend scene-matched DNA, tag and remember confirmed personal DNA, and export or install shareable DNA Extension Packs. Use for AI 摄影主题、九张独立照片、人物锁定、场景设计、DNA 推荐/入库/分享、Prompt 保存或 APSAL Skill 导出。
---

# APSAL Theme Creator

Keep JSON and YAML in the local artifact layer. Never ask a creator to write or inspect them unless they explicitly request developer mode.

## Create through five complete layers

1. Call `start_design_session` with the creator's natural-language brief. Default to nine independent 9:16, 2160×3840 high-quality PNG images and a live-action photography Rendering Contract.
2. For each layer, call `present_element_layer`. Never skip or hide a protocol role:
   - `direction`: Content + Emotion. Confirm the theme proposition, primary/secondary mood, valence, arousal, expression, energy, tension and nine-shot emotional arc. This layer uses no Registry DNA.
   - `worldbuilding`: Subject + World + Look. Call `recommend_layer_dna` for Character and Environment DNA; explicitly confirm identity, space, time, wardrobe, grooming, props and ownership.
   - `narrative`: Event + Sequence. Recommend Composition and Shot DNA; show the sequence strategy and nine distinct Scene cards with consequences and order.
   - `image`: Camera + Light + Style + Color/Post. Recommend Style and Lighting DNA; explicitly confirm viewpoint, coverage, optics, composition, light source/direction/quality/contrast, palette, temperature, saturation, curve, grain, sharpness, dynamic range and skin-tone policy.
   - `delivery`: Job + Quality Control. Recommend QA DNA; confirm one-Job-one-image outputs, format, dimensions, rejection rules and separate model/human QA.
3. Treat every element card as a proposal with source, intent, values, observable effects, locks and QA expectations. Accept a natural-language revision to one element, show its downstream effects, and preserve all non-target locks.
4. If the creator makes or revises DNA, call `suggest_dna_tags`, show the controlled semantic tags and facets, and obtain confirmation before including that discovery metadata in `draft_assets`.
5. Call `commit_element_layer` only after every element in that layer is explicitly confirmed. Never call legacy `commit_stage` for a new 0.7 session.
6. When confirmation returns a pending memory offer, ask exactly once: “保存到我的 DNA、仅保留在当前项目，还是稍后决定？” Call `resolve_dna_memory` with the answer. Do not ask for official, extension, or already-personal DNA.
7. If an upstream choice changes, respect the returned invalidations and reconfirm every affected downstream layer. Never reuse stale Prompts.
8. At `review_pending`, show all thirteen confirmed decisions plus a compact nine-shot overview, then offer exactly: generate nine images, save prompts only, or export a Skill.
9. Call `finalize_theme` after the creator confirms the overview. Treat the returned local artifact as the source of truth.

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
