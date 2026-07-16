# Changelog

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
