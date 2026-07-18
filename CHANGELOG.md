# Changelog

## 0.15.0 - 2026-07-18

- Added the open-source APSAL Studio Desktop 0.2.0 under `apps/apsal-studio` as a protocol-only visual frontend for the Codex plugin. It contains no AiPhoto legacy workflow, local image engine, model runtime, provider settings, or private case media.
- Added a stable five-layer/thirteen-role canvas, Codex preview confirmation/rejection, protocol undo, read-only incompatibility state, view-only node layout, and the authenticated loopback link. Formal image generation remains in Codex.
- Made Studio builds copy the tested Engine/Protocol from the same repository with a strict component-version check, eliminating the previous machine-specific source path and independently authored Engine bundle.
- Added the APSAL Project Protocol 0.15.0: one `.apsal/` project source, stable project/session/element IDs, a monotonic revision, and one Python domain dispatcher shared by Codex and the Studio 0.2.0 sidecar.
- Added project locking, atomic semantic files, crash journals, bounded operation replay, intent-bound `operationId`, stale-revision rejection, recovery history, and revision-incrementing undo.
- Added revision-bound design previews with isolated ghost elements, whole-layer confirmation/rejection, downstream invalidation, and view-only state under `.apsal/studio/view.json`.
- Added seven optional `apsal_frontend_*` MCP tools and a loopback-only authenticated Studio client. Linked writes never fall back after route selection; incompatible projects remain read-only and are not migrated in place.
- Added deterministic Prompt/Skill packages with a run manifest and complete in-package SHA-256 ledger. Studio view state remains outside generation truth and package digests.
- Added direct/stdio golden contract, concurrency, idempotency, recovery, view isolation, compatibility, path-safety, and deterministic ZIP tests. APSAL Open asset Protocol and Semantic Contract remain 0.3.0.

## 0.14.0 - 2026-07-17

- Added a localized five-stage semantic thumbnail strip above the complete element text cards. DNA selection cards remain text-only. The 4:3 thumbnails show Direction, Worldbuilding, Narrative, Image and Delivery progress in Chinese or English without replacing the proposals.
- Added deterministic Chinese and English SVG stage previews to every newly exported Prompt/Skill package, with a separate `preview_manifest.json`, SHA-256 ledger, accessibility text and `generation_input: false` enforcement.
- Added one core visual anchor declaration whenever real references are packaged. Explicit creator choice wins; otherwise identity, all-shot and first-reference precedence applies. The anchor never broadens declared uses or applicable Jobs.
- A Skill without real references now records `core_visual_anchor_status: not_bound`; semantic thumbnails cannot masquerade as reference images.
- Upgraded the reference manifest to 0.6.0 and Prompt/Skill package manifest to 0.10.0. Protocol and Semantic Contract remain 0.3.0; session schema remains 0.7.0; older themes and packages remain readable.

## 0.13.0 - 2026-07-17

- Added a creator-visible set organization choice: `chaptered_variation` (“章节式丰富变化”) or `continuous_narrative` (“连续叙事”). New nine-image sessions default to Chaptered Variation unless the brief explicitly requests one continuous scene/look/event.
- Materialized Chaptered Variation as three related scenes, three coordinated looks locked per chapter, nine distinct action-led body states and five functional focal-perspective families. Identity, live-action medium, world physics, photographic grammar and color remain coherent.
- Made scene/look/action/pose/framing/focal variation and identity/world/medium/color continuity explicit in the existing Content, World, Look, Event, Sequence, Camera and Quality Control roles; no new protocol role or DNA category was introduced.
- Added per-Job chapter, scene/look lock, action/body state, nominal focal length and observable perspective purpose to design and image compilation, plus separate set-level variation and continuity QA checks.
- Rebuild downstream proposals and invalidate confirmed downstream layers when the Direction strategy changes. Older session-schema 0.7 artifacts without a strategy retain their previous intent.
- Turned every card adjustment direction into a touch- and keyboard-accessible button. Selecting a direction requests a card revision and never silently confirms a layer.
- Added RFC 0009, complete bilingual usage guidance and release notes. Protocol and Semantic Contract remain 0.3.0; official DNA and frozen theme versions remain unchanged.

## 0.12.0 - 2026-07-17

- Filled every five-layer element card with the complete APSAL proposal: recommendation, rationale, adjustable directions, concrete values, observable results, invariants and acceptance criteria. Deliberately unset values now explain what should be decided later instead of showing an empty area.
- Added a default poised East Asian adult female protagonist with stable camera presence and broad compatibility across classical, contemporary, editorial and ceremonial makeup, hair and wardrobe. An explicit male-subject brief still overrides the default.
- Separated styling versatility from identity mutability. New sessions lock facial geometry, adult age, natural skin, hair color/hairline and body proportions while allowing declared makeup, hairstyle, wardrobe and period-styling changes.
- Added presence and styling-fit checks to the quality proposal and compiled the subject observables into every image Prompt, so the requirement is not merely interface copy.
- Added the missing acceptance-criteria section to the interactive element card and expanded the CLI/IDE text fallback with the same proposal, reason, values, expected effects, locks and QA.
- Kept Protocol and Semantic Contract at 0.3.0, session schema at 0.7.0, official DNA versions unchanged and legacy themes readable. This release changes the default proposal for newly created sessions; existing frozen themes and DNA remain immutable.

## 0.11.0 - 2026-07-17

- Added a strict creator-facing Chinese projection for all five creative layers, thirteen protocol roles and seven official Registry DNA categories. Chinese cards no longer expose English machine role names, layer IDs, statuses, sources, field keys, enum values, Registry scopes, QA states, recommendation reasons or asset IDs.
- Kept stable English machine identifiers, canonical theme data, DNA digests and provider-neutral Prompts unchanged underneath the presentation layer.
- Added curated Chinese titles, summaries and core constraints for every official starter DNA plus safe Chinese fallbacks for project, personal and extension assets.
- Reworked both card surfaces with an accessible celadon highlight system: stronger layer and card titles, highlighted intent blocks and key values, emphasized recommendation reasons, clearer selected state and a filled primary confirmation action.
- Removed visible `JSON`, `YAML`, `Registry`, raw digest and namespace language from Chinese cards while preserving those records in the local artifact layer.
- Added regression checks that reject Latin letters in every creator-visible Chinese element-card field and official DNA-card field.
- Kept Protocol and Semantic Contract at 0.3.0 and session schema at compatible 0.7.0. This release changes presentation only, not photographic generation intent.

## 0.10.0 - 2026-07-16

- Added complete creator-facing Chinese (`zh-CN`) and English (`en`) interaction across session start/resume, thirteen-element cards, DNA cards, text fallback, starter prompts and usage documentation.
- Made the current Codex conversation or user-message language the default. Clear Chinese or English starts immediately; only genuinely ambiguous input triggers the one-line choice “English or 中文?”.
- Added `set_session_language` and persisted the choice locally in the resumable design session. Explicit switching is presentation-only and does not invalidate layers or change DNA, theme, canonical artifact or Prompt digests.
- Removed mixed bilingual labels from individual UI cards. Each session now displays one consistent creator language while retaining stable machine identifiers underneath.
- Added complete `PROMPT_GUIDE.en.md` and `PROMPT_GUIDE.zh-CN.md` files to new and migrated Prompt/Skill packages, with `PROMPT_GUIDE.md` as the language index.
- Added the bilingual interaction RFC, language privacy disclosure, English starter prompts and regression tests for detection, ambiguity, resume, switching and digest invariance.
- Kept Protocol and Semantic Contract at 0.3.0, session asset schema at compatible 0.7.0 and generation delivery unchanged: one Codex-built-in image Job per turn, no provider API key.

## 0.9.0 - 2026-07-16

- Added direct takeover of legacy APSAL run directories and ZIPs: creators can attach a package instead of extracting it, inspecting `run.json`, repairing paths, or finding an API runner.
- Added safe archive inspection with traversal, symlink, duplicate-path, depth and expanded-size safeguards.
- Added automatic Prompt recovery and SHA-256 reference restoration from bundled media, declared valid local paths, or the private APSAL Vault.
- Added `import_apsal_package` and `bind_import_reference` MCP tools plus `import-run` and `run-bind-reference` CLI commands.
- Converted historical provider, model and API fields to non-executable lineage metadata; imported runs always use Codex built-in image generation and honest non-guaranteed output dimensions.
- Added automatic private Codex Prompt/Skill repackaging for imported runs, including positive/negative/full Prompts, restored reference media, rights metadata, checksums, offline validation and a plain-language guide.
- Added a high-priority imported-run instruction to generate the finished photograph itself and reject code, JSON, terminals, programming interfaces and Prompt sheets as image content.
- Added missing-reference recovery that asks only for the exact omitted image and verifies its original digest before continuing.
- Added a bilingual documentation hub and complete creator usage guides covering installation, five-layer confirmation, DNA memory, reference roles, Codex continuation, Prompt/Skill installation, legacy ZIP takeover, storage, visual QA and troubleshooting.

## 0.8.0 - 2026-07-16

- Removed direct image-provider/API execution from APSAL Studio and its exported Skills; the plugin no longer reads an image API key or exposes an HTTP generation executor.
- Added `get_next_codex_job`, which hands one frozen Prompt plus the permitted local or recent-image references to Codex built-in image generation without making a provider call.
- Changed the creator flow to one image per Codex turn: after an image is emitted, the Skill stops; “continue” resumes the next unfinished Job while preserving successful results.
- Made Prompt delivery automatic at finalization. Every theme now exports a deterministic Codex Prompt/Skill ZIP containing nine positive Prompts, nine negative Prompts, nine combined Prompts, references, rights, checksums, QA context and `PROMPT_GUIDE.md`.
- Replaced the networked generation script in exported Skills with an offline `validate_prompt_pack.py` verifier and Job lister.
- Kept the live-action adult-human Rendering Contract and reference binding, while treating 9:16, high quality and 2160×3840 as requested creative delivery targets rather than guaranteed returned dimensions.
- Preserved Protocol and Semantic Contract 0.3, the five-layer/thirteen-role interaction, Registry formats and legacy 0.4–0.7 assets and runs.

## 0.7.0 - 2026-07-16

- Replaced the incomplete four-group confirmation for new sessions with five creator layers: Direction, Worldbuilding, Narrative, Image and Delivery.
- Exposed all thirteen existing protocol roles as text-only decision cards with intent, structured values, provenance, observable effects, locks and QA expectations.
- Added controlled emotional direction covering primary tone, undertone, valence, arousal, expression, energy, tension and a start/turn/end arc.
- Made wardrobe, props and ownership; light source/direction/quality/contrast; palette, temperature, saturation, curve, grain, sharpness, dynamic range and skin-tone policy explicit creator decisions.
- Added `recommend_layer_dna`, `present_element_layer` and `commit_element_layer` MCP tools, bringing the local server to 18 tools and two text-card resources.
- Added the `creative-layers.json` contract, element-decision schema, five-layer CLI commands and automatic downstream invalidation.
- Compiled confirmed observable element instructions into every image Prompt and every role's expectations into QA.
- Kept all seven Registry DNA types, Protocol 0.3, Semantic Contract 0.3, official DNA, legacy assets and four-stage session compatibility unchanged.

## 0.6.1 - 2026-07-16

- Replaced image-led DNA selection with compact text-only protocol cards.
- Removed preview-image Base64 payloads from interactive MCP recommendations and choices.
- Kept Registry preview sidecars for rights review, validation and Extension Pack integrity; DNA assets and generation intent are unchanged.
- Improved card hierarchy around stable reference, core constraints, recommendation reasons, matched tags, rights and QA.

## 0.6.0 - 2026-07-16

- Added scene-aware DNA recommendations with controlled semantic tags, retrieval facets, explicit upstream compatibility, QA/rights checks, Registry scope and local outcome memory.
- Every recommendation now explains matched tags, facets, source, QA, rights and personal-history contribution instead of presenting an opaque ranking.
- Added deterministic tag/facet suggestions for new or revised DNA and creator confirmation before public sharing.
- Added one post-confirmation memory offer for new/revised project DNA: Save to My DNA, current project only, or decide later. Official, extension and already-personal DNA do not trigger the question.
- Added private usage feedback at `~/.apsal/usage/events.jsonl`; raw creative briefs are excluded.
- Added deterministic DNA Extension Pack export with one namespace, canonical DNA, previews, licenses, dependencies and SHA-256 ledger.
- Added local ZIP and pinned GitHub Release installation into the read-only `extension` Registry layer, with collision, path, symlink, checksum, dependency and decompression safety checks.
- Expanded the local MCP from 9 to 15 tools and updated visual cards to show recommendation reasons.
- Kept Protocol and Semantic Contract at 0.3.0 and preserved all 0.4/0.5 theme, Registry, Skill and run compatibility.

## 0.5.0 - 2026-07-16

- Added typed, rights-aware reference binding. Local Skills now contain sanitized reference images, per-image SHA-256, permitted/forbidden uses, Job scope, attribution, and independent redistribution state.
- Added public-export gates: unverified or non-redistributable media forces `private_only` and cannot enter GitHub Release or APSAL Hub publication.
- Added a high-priority live-action photography Rendering Contract that keeps adult subjects photographic while allowing handmade, crayon, painted, or theatrical sets and props.
- Added live-action QA for medium, skin, eyes, hands, anatomy, optical depth, physical light, and material response; model visual QA and human visual QA are recorded separately.
- Changed new Studio themes to nine independent 9:16, 2160×3840, high-quality PNG Jobs.
- Added the optional `openai-image-api` / `gpt-image-2` executor: nine sequential `n: 1` requests, two retries, exact-dimension validation, partial-run resume, and a `SHOT_01` identity-only runtime anchor.
- Added a self-contained `scripts/generate_set.py` to exported Skills and two MCP tools for execution and model visual-QA recording.
- Kept Protocol and Semantic Contract at 0.3.0. Existing 0.4 themes, runs, and Skills remain readable without gaining false reference-binding or native-4K claims.
- Migrated 《蜡笔梦游》 locally to `APSAL-006@2.0.0` as a private-only package with five verified file digests. Its media and Skill are excluded from the public repository while redistribution rights and human visual QA remain unresolved.

## 0.4.0 - 2026-07-16

- Added a natural-language-first four-stage creator flow with Character, World, Scene, and Photo DNA cards; JSON and YAML remain background artifacts.
- Added project, personal, and official local Registry layers with exact version/digest resolution, immutable formal versions, explicit promotion, and `APSAL_HOME` support.
- Added seven original 768×576 WebP semantic preview cards with rights, attribution, SHA-256, QA sidecars, and no effect on DNA generation-intent digests.
- Added resumable design sessions, upstream invalidation, hidden YAML/canonical JSON finalization, three compile targets, and 18 locally saved Prompt files for nine-shot themes.
- Added explicit-confirmation generation runs with one Job per image, exact effective Prompt lineage, partial status, failed-Job resume, and successful-output protection.
- Added a dependency-free local stdio MCP server with seven tools, an MCP Apps DNA card resource, and numbered-text fallback for CLI/IDE clients.
- Added private content-addressed reference Vault storage and a public local-first privacy policy.
- Kept Protocol and Semantic Contract at 0.3.0; the Quiet Window pilot and official DNA catalog remain byte-for-byte unchanged.

## 0.3.0 - 2026-07-15

- Added Semantic Contract 0.3 with bilingual purpose, effects, locks, controlled tags, priorities, and evidence-oriented QA expectations.
- Added dependency-free safe APSAL YAML authoring and deterministic canonical JSON normalization.
- Added `normalize`, `explain`, `check-sync`, and `compile --target design|image|qa` CLI workflows.
- Added `APSAL-OPEN-001@1.1.0` as the only semantic pilot while preserving `1.0.0` and all seven DNA dependencies.
- Added the thirteen-element monograph companion and generated bilingual semantic references.

## 0.2.0 - 2026-07-15

- Defined APSAL Open Protocol as a separately licensed specification, reference engine, and content layer.
- Added the thirteen-role modular package contract: eleven modules, sequence, and one-image Jobs.
- Added package/module schemas and offline `validate-package` checks for rights, lineage, checksums, QA, and outputs.
- Recorded APSAL-006-001 v4.0 as a structure-only migration input; no unlicensed theme content was redistributed.

## 0.1.0 - 2026-07-14

- Initial public APSAL Open release.
- Self-contained `apsal-studio` Codex plugin.
- Curated seven-category DNA starter catalog.
- Offline theme validation, deterministic prompt compilation, and Skill packaging.
