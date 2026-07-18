---
name: apsal-theme-creator
description: Create, revise, resume, generate, or package an APSAL photography theme; recommend scene-matched DNA, tag and remember confirmed personal DNA, and export or install shareable DNA Extension Packs. Use for AI 摄影主题、九张独立照片、人物锁定、场景设计、DNA 推荐/入库/分享、Prompt 保存或 APSAL Skill 导出。
---

# APSAL Theme Creator

Keep JSON and YAML in the local artifact layer. Never ask a creator to write or inspect them unless they explicitly request developer mode.

## Match the creator's language

Use the current Codex conversation or user-message language as the creator-facing language. Pass `language: zh-CN` or `language: en` to `start_design_session` whenever it is clear. Do not ask every creator to choose a language. If the message is too short, genuinely mixed, or otherwise ambiguous, let the session return `language_confirmation_required` and ask only: “English or 中文?” Then call `set_session_language` before showing element or DNA cards. An explicit request to switch language always wins and may be applied at any time.

Language affects conversation, card labels, explanations, and user guides only. It must never alter DNA IDs, rights, theme generation intent, canonical JSON, provider-neutral image Prompts, checksums, or compiled Prompt digests. Read [references/LANGUAGE.md](references/LANGUAGE.md) for the complete policy and exact bilingual wording.

For a Chinese session, present only the localized creator-facing fields returned by the tools. Never repeat raw role names, layer IDs, field keys, statuses, sources, Registry scopes, QA states, semantic tags, digests or asset IDs inside a visible choice card. Stable machine identifiers remain available to tools for exact selection and validation. Important creator decisions should follow the card hierarchy: highlighted title, intent, key values, recommendation reason and primary confirmation action.

## Open an APSAL package without exposing internals

When the creator attaches or points to an APSAL ZIP/directory containing `run.json`, call `import_apsal_package` before explaining the package. Do not answer that `run.json` is not executable, do not tell the creator to find an API runner, and never generate a screenshot of code, JSON, a terminal, or a programming interface.

The importer treats old provider/model/API fields as historical lineage only, recovers all Prompt files, searches the package and local private Vault for each reference by SHA-256, converts the Jobs to Codex-native generation, and creates a documented private Prompt/Skill ZIP. If `ready_for_codex` is true, summarize the theme and shot count in creator language, show the new package path, and offer or perform the returned `next_job` according to the creator's existing generation confirmation. If it is false, ask only for the images in `missing_references`; do not ask the creator to repair paths or edit JSON. Use `bind_import_reference` for each reattached file, then continue directly.

If the creator already asked to generate the set, a ready import is sufficient to generate SHOT_01 immediately through Codex built-in image generation. Otherwise ask once: “现在生成第一张吗？”

## Use the optional Studio projection

Call `apsal_frontend_status` when the creator asks to coordinate with APSAL Studio. If it reports `connected`, read the current canonical snapshot with `apsal_frontend_get_project`; create revisions with `apsal_frontend_preview_changes`, then use `apsal_frontend_apply_preview` or `apsal_frontend_reject_preview` only after explicit confirmation. Use `apsal_frontend_focus_elements` for visual location and `apsal_frontend_undo_operation` only for an operation the creator chose to undo.

If Studio linkage is unconfigured, disabled, or offline, continue through the ordinary design tools. They call the same Python Engine in-process; do not make Studio availability a prerequisite for five-layer design, DNA, generation, QA, or final packaging. Never silently retry a linked write through the direct path after a bridge error, because that could cross a project switch or stale revision boundary.

## Create through five complete layers

1. Call `start_design_session` with the creator's natural-language brief and the clear current conversation language. Default to nine independent 9:16 high-quality image requests, a live-action photography Rendering Contract, and `chaptered_variation` unless the brief explicitly asks for one continuous scene/look/event. Treat 2160×3840 as a requested delivery target only; Codex-managed generation does not guarantee returned pixel dimensions or format.
2. For each layer, call `present_element_layer`. Never skip or hide a protocol role:
   - `direction`: Content + Emotion. First confirm the set strategy: `chaptered_variation` (“章节式丰富变化”, default) or `continuous_narrative` (“连续叙事”). Then confirm the theme proposition, primary/secondary mood, valence, arousal, expression, energy, tension and nine-shot emotional arc. This layer uses no Registry DNA.
   - `worldbuilding`: Subject + World + Look. Call `recommend_layer_dna` for Character and Environment DNA; explicitly confirm identity, space, time, wardrobe, grooming, props and ownership. Chaptered Variation defaults to three related sub-scenes and three coordinated looks, each locked within its three-shot chapter. Continuous Narrative defaults to one core scene and one confirmed look.
   - `narrative`: Event + Sequence. Recommend Composition and Shot DNA; show the sequence strategy and nine distinct Scene cards with consequences and order. Every Job must have a different action-led body state with declared hand function, gaze motivation and weight distribution.
   - `image`: Camera + Light + Style + Color/Post. Recommend Style and Lighting DNA; explicitly confirm viewpoint, coverage, optics, composition, light source/direction/quality/contrast, palette, temperature, saturation, curve, grain, sharpness, dynamic range and skin-tone policy. Default focal coverage uses environment, full-action, natural-medium, emotional-close and necessary-detail perspectives according to shot function; compile the observable perspective purpose as well as the nominal focal length.
   - `delivery`: Job + Quality Control. Recommend QA DNA; confirm one-Job-one-image outputs, format, dimensions, rejection rules and separate model/human QA.
3. Treat every element card as a complete proposal. Fill the card itself with the recommendation, why it fits the current brief, adjustable directions, concrete values, observable effects, locks and QA expectations; do not leave proposal sections blank and do not move substantive suggestions into surrounding chat. Accept a natural-language revision to one element, show its downstream effects, and preserve all non-target locks.
   - Keep DNA choice cards text-only. Above the element cards, show the five localized semantic stage thumbnails returned by the tool. They summarize progress only, contain no hidden photographic instruction, and must never be passed to image generation.
   - Unless the creator specifies otherwise, propose a poised, distinctive East Asian adult female protagonist with stable camera presence and broad compatibility across classical, contemporary, editorial and ceremonial makeup, hair and wardrobe.
   - Styling versatility never means identity drift. Preserve facial geometry, adult age, natural skin, hair color/hairline and body proportions. In Chaptered Variation, lock one of three coordinated looks inside each chapter and change only at a declared boundary. In Continuous Narrative, keep one confirmed look unless an explicit event motivates a change.
   - Treat card options as selectable design directions. A click expresses a revision request; update the affected card and explain downstream invalidations before confirmation. Never treat an option click as permission to skip the layer confirmation.
4. If the creator makes or revises DNA, call `suggest_dna_tags`, show the controlled semantic tags and facets, and obtain confirmation before including that discovery metadata in `draft_assets`.
5. Call `commit_element_layer` only after every element in that layer is explicitly confirmed. Never call legacy `commit_stage` for a new five-layer session.
6. When confirmation returns a pending memory offer, ask exactly once: “保存到我的 DNA、仅保留在当前项目，还是稍后决定？” Call `resolve_dna_memory` with the answer. Do not ask for official, extension, or already-personal DNA.
7. If an upstream choice changes, respect the returned invalidations and reconfirm every affected downstream layer. Never reuse stale Prompts.
8. At `review_pending`, show all thirteen confirmed decisions plus a compact nine-shot overview. Include the chosen set strategy, per-Job scene, look, action/body state, framing, focal perspective and the invariants that bind the set together.
9. Call `finalize_theme` after the creator confirms the overview. It automatically creates one deterministic Codex Prompt/Skill ZIP containing all positive, negative and full Prompts, actual permitted references, five-stage semantic thumbnails, QA, checksums, and equally complete English and Chinese guides. Show its path and SHA-256 to the creator. Treat it as the source of truth.
10. Offer exactly: “现在用 Codex 生成第一张” or “只交付 Prompt/Skill 使用包”. The package already exists in both paths.

At every stage, confirm each supplied reference image's role (`style`, `world`, `prop`, `wardrobe`, `composition`, or `identity`), allowed and forbidden uses, applicable Jobs, rights/consent, attribution, and redistribution status. Pass these as `reference_bindings`; set `core_visual_anchor: true` for exactly one image when the creator chooses it. If no image is chosen, Studio prefers an identity reference, then an all-shot reference, then the first reference. Never broaden the chosen anchor's declared Job scope. Never replace the image itself with a prose analysis.

Read [references/INTERACTION.md](references/INTERACTION.md) for card contents, natural-language revision rules, state transitions, identity references, and storage behavior.

## Learn and exchange DNA

- Use controlled `semantic_tags` for protocol reasoning and controlled `facets` for scene retrieval. Do not replace stable IDs, versions, rights, dependencies, or locks with free-form tags.
- After a real result, call `record_dna_feedback` as `successful` or `failed`; record an explicit rejection as `rejected`. Raw briefs are not stored in recommendation history.
- Export selected DNA with `export_dna_pack`, not the theme Skill packager. Public packs require one namespace, creator-confirmed discovery metadata, resolved licenses/attribution, valid previews, dependencies, and checksums. Otherwise export `private_only`.
- Install only a local ZIP or a pinned public GitHub Release source such as `github:owner/repo@v1.0.0#pack-v1.0.0.zip`. Installed packs are read-only `extension` Registry layers and cannot override official or installed ID/version pairs.

## Generate through Codex, one Job per turn

Before generation, show the live-action contract, reference count, private/public status, requested 9:16 aspect ratio, requested 2160×3840 delivery target, nine separate images and the explicit statement that concrete dimensions are not guaranteed. Obtain one “现在用 Codex 生成” confirmation and call `start_generation_run` with `confirmed: true`.

- Call `get_next_codex_job`. It returns the exact full Prompt plus either local `referenced_image_paths` or the smallest valid recent-image count. Pass its `codex_tool_arguments` unchanged to Codex's built-in image-generation capability. Never make an HTTP image request, invoke an external image adapter, ask for an API key, or run a provider script.
- Generate exactly one image in the current turn. After the built-in image tool emits the result, stop without commentary or further tools. When the creator says “继续” or “下一张”, first record the preceding result using only metadata actually available, perform Codex visual QA, then request and generate the next Job.
- If Codex exposes a local file or artifact identifier, record it. Otherwise record `artifact_uri: not_reported` and keep model, format, dimensions and provider parameters as `not_reported`; never infer them.
- When no bound local references are needed, the immediately previous accepted image may be used as an identity-only recent-image anchor. When local reference paths are present, use those paths and do not combine mutually exclusive image-input mechanisms. Never inherit an anchor's pose, background, action, wardrobe, camera, lighting or composition.
- A failed Job remains resumable. Never overwrite a successful Job. Keep Codex visual QA separate from human visual QA.
- Never request a grid, contact sheet, collage, typography, logo, or watermark.
- Static validation and semantic cards are not photographic visual QA. Review identity, hands, anatomy, geometry, reflection, prop ownership, lighting, continuity, intent, and restricted output manually.

Original references remain in the local content-addressed Vault and never enter DNA JSON, Git, or chat exports. The automatically exported Prompt/Skill package includes sanitized copies plus an integrity-checked purpose manifest so Codex can actually receive them. If rights or redistribution are unresolved, package only as `private_only`; never publish it to GitHub or APSAL Hub. A public package may include a reference only when its independent license, consent, attribution, and redistribution permission are explicit.

The Skill also contains `references/preview_manifest.json` and localized SVGs under `assets/previews/stages/`. These are deterministic semantic summaries, use `generation_input: false`, and are strictly separate from real files under `assets/references/`. A Skill with no real reference must say `core_visual_anchor_status: not_bound`; never disguise a stage thumbnail as the missing reference.

## Preserve APSAL invariants

Identity and rights outrank world continuity; world continuity outranks event and shot function; those outrank camera/light/color; style rhetoric comes last. A published DNA version is immutable. Any generation-intent change creates a new semantic version with parent version, changed fields, summary, rights, and QA status.

Chinese aesthetic concepts—including 经营位置、意境、气韵、虚实 and 散点观看—explain relationships in world construction. Do not reduce them to arbitrary numeric sliders.
