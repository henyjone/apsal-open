# APSAL Studio 0.10 Complete Usage Guide

[中文](USAGE_GUIDE.zh-CN.md) · [Documentation hub](README.md) · [Project home](../README.md)

This guide covers the complete creator workflow: installation, natural-language theme design, five-layer confirmation, DNA and reference management, nine-image generation in Codex, Prompt/Skill delivery, visual QA, and takeover of older APSAL run ZIPs.

## 1. The intended experience

```text
One natural-language idea
→ five creator layers
→ scene-matched DNA recommendations
→ creator confirmation or natural-language revision
→ thirteen-element and nine-shot review
→ automatic Prompt/Skill package
→ one Codex-generated image per turn
→ “continue” for the next Job
→ model visual QA + separate human visual QA
```

Creators do not hand-write JSON/YAML, configure an image API, or find a separate provider runner. Structured files remain background assets for reuse, versioning, validation and lineage.

## 2. Install

Install the pinned stable release:

```bash
codex plugin marketplace add henyjone/apsal-open --ref v0.10.0
codex plugin add apsal-studio@apsal-open
```

Restart Codex or open a new task, then verify:

```bash
codex plugin list
```

You should see `apsal-studio@apsal-open`, enabled at version `0.10.0`.

To replace an older pinned installation:

```bash
codex plugin remove apsal-studio@apsal-open
codex plugin marketplace remove apsal-open
codex plugin marketplace add henyjone/apsal-open --ref v0.10.0
codex plugin add apsal-studio@apsal-open
```

Use `--ref main` instead of the release tag only when you intentionally want the current development branch.

## 3. Create a new nine-image theme

Open a dedicated project folder in Codex so `.apsal/` lineage is stored with the project. Then ask:

> Use APSAL Studio to create a nine-image Eastern-minimalist live-action window portrait theme.

For a more directed brief:

```text
Use APSAL Studio to create a nine-image live-action photography theme.
Proposition: an unposted letter and a decision that remains partly unresolved.
Subject: one fictional East Asian adult woman, identity locked by the attached image.
World: one east-facing room from cool morning to warm afterglow.
Emotion: hesitation → encounter → decision → restrained release.
Photography: editorial, natural skin, physical window light, subtle grain.
Must preserve: one letter owned by the subject, room geometry, wardrobe, light direction.
Forbid: illustrated person, 3D person, grids, text, logo and watermark.
Reference role: identity only; do not copy pose, background or composition.
```

Unspecified decisions can remain open; Studio proposes them in the appropriate layer.

### How interface language works

APSAL Studio follows the current Codex conversation rather than showing a mandatory first-run language screen. An English brief creates an English session; a Chinese brief creates a Chinese session. Card titles, questions, buttons, explanations and text fallback use that one language instead of showing both at once.

If the first usable message is genuinely ambiguous—such as only “APSAL”—Studio asks once:

> English or 中文?

Answer normally; Studio stores the choice in the local design session. To switch later, say “switch to Chinese” or “use English.” Switching changes presentation only. It does not restart the session, invalidate confirmed elements, or change DNA references, theme generation intent, canonical artifacts or Prompt digests.

## 4. Confirm five layers and all thirteen roles

| Layer | Protocol roles | Creator decision |
|---|---|---|
| Direction | Content, Emotion | proposition, primary/secondary mood, valence, arousal and nine-shot emotional arc |
| Worldbuilding | Subject, World, Look | identity, age, space, time, physics, wardrobe, grooming, props and ownership |
| Narrative | Event, Sequence | what changes in each Job and why the nine images progress rather than repeat poses |
| Image | Camera, Light, Style, Color/Post | framing, viewpoint, optics, composition, source/direction/quality of light, palette and post-processing |
| Delivery | Job, Quality Control | one image per Job, output request, rejection rules, model QA and human QA |

Every text card includes intent, values, provenance, observable effects, locks and QA expectations. Confirm a layer, or revise one target in natural language:

> Make the subject 32–38 while preserving the short hair and restrained temperament.

> Make SHOT_04 sadder without changing room geometry, wardrobe or lighting.

> The letter is owned by the subject, exists only once and cannot float or duplicate.

An upstream change invalidates affected downstream choices and Prompts. Reconfirm them instead of reusing stale compilation.

Before finalization, verify distinct shot functions, identity locks, prop ownership, physical space, light continuity, hands/reflections and the priority of live-action human photography over decorative set rhetoric.

## 5. DNA recommendations and memory

Studio recommends Character, Environment, Composition, Shot, Style, Lighting and QA DNA with match reasons, source, version, rights and QA status.

| Layer | Location | Behavior |
|---|---|---|
| Official | installed plugin | rights-cleared read-only starter DNA |
| Personal | `~/.apsal/` | reusable creator-approved DNA |
| Extension | `~/.apsal/extensions/` | installed read-only community packs |
| Project | `<project>/.apsal/` | drafts, project DNA, themes, Prompts, runs and QA |

Resolution order is project → personal → extension → official.

After new or revised project DNA is confirmed, Studio asks once whether to save it to My DNA, keep it only in the current project, or decide later. Nothing is silently promoted. A formal DNA change creates a new immutable semantic version.

To share reusable knowledge without exposing the private theme, ask Studio to export selected rights-cleared DNA as an Extension Pack. Public packs require confirmed controlled tags, valid previews, attribution, resolvable dependencies and SHA-256 integrity.

## 6. Bind references correctly

Declare each reference as `identity`, `style`, `world`, `prop`, `wardrobe`, or `composition`.

An identity reference may stabilize identity but must not silently transfer pose, background, camera or composition. A style reference may transfer palette and material language but not the depicted person's identity. Forbidden uses always outrank conflicting declared roles.

Example:

> Use this image only for style and world: take the cool violet-gray palette, dark wood and mirror-space language; do not copy the person, pose or exact composition.

Studio records SHA-256, scope, allowed/forbidden uses, copyright, portrait consent, attribution and redistribution state. Original private references live in `~/.apsal/vault/sha256/`, outside DNA JSON and public Git. Unresolved redistribution rights force `private_only` packaging.

## 7. Review and finalize

The final review should show all thirteen decisions, nine distinct Jobs, live-action Rendering Contract, references and rights, requested output, independent-image restrictions and separate model/human QA.

After approval, finalization always creates the canonical theme artifacts and a reproducible Codex Prompt/Skill ZIP, even if you choose immediate generation. Chat history is never the only lineage record.

The ZIP contains:

```text
SKILL.md
PROMPT_GUIDE.md
PROMPT_GUIDE.en.md
PROMPT_GUIDE.zh-CN.md
prompts/SHOT_01..09.prompt.txt
prompts/SHOT_01..09.negative.txt
prompts/SHOT_01..09.full.txt
references/theme.json
references/compiled.json
references/design_context.json
references/qa_checklist.json
references/rendering_contract.json
references/reference_manifest.json
references/manifest.json
assets/references/
scripts/validate_prompt_pack.py
```

## 8. Generate with Codex

Say:

> Use Codex to generate the first image now.

Studio prepares a resumable run and passes the frozen SHOT_01 full Prompt plus its permitted real references to Codex built-in image generation. It does not call an external image API or request an API key.

Exactly one independent image is generated in the current turn. After it appears, say:

> Continue.

Studio records the prior result, performs model visual QA and advances to the next unfinished Job. One confirmation starts the set, but nine independent Jobs preserve shot variation, per-shot references, retries and QA. It does not mean one nine-grid request.

For a failed shot, identify the Job and failure:

> SHOT_04 failed live-action medium QA because the subject looks 3D. Record the failure and retry only this Job while preserving identity, world and light locks.

Successful Jobs are not overwritten. When no bound identity reference exists, the immediately previous accepted image may be an identity-only runtime anchor; pose, camera, world and composition must not transfer.

## 9. Use the Prompt/Skill package without generation

- `.prompt.txt` contains positive observable image language.
- `.negative.txt` contains rejection constraints.
- `.full.txt` combines both and is the normal copy/paste entry point.

Text does not replace a declared reference image. Pass the actual files listed for that Job in `reference_manifest.json`.

To install the exported theme as a personal Skill:

1. Extract the ZIP.
2. Find the top-level directory containing `SKILL.md`.
3. Copy that directory under `~/.codex/skills/`.
4. Restart Codex or open a new task.
5. Ask Codex to use the named Skill for SHOT_01, then say “continue”.

Verify an extracted package offline from its Skill root:

```bash
python3 scripts/validate_prompt_pack.py --list
```

This checks Prompt/reference digests and lists Jobs. It never generates an image or makes a network request.

## 10. Open a legacy APSAL ZIP

Attach the ZIP directly and say:

> Open this APSAL package and generate the first image.

Studio safely finds the single `run.json`, recovers positive and negative Prompts, turns obsolete provider/model/API fields into non-executable history, restores references by SHA-256 from the ZIP or private Vault, removes obsolete absolute paths, and creates a new private Codex Prompt/Skill package.

If a reference is truly absent, Studio asks only for its reference ID and original filename. Reattach that image; its digest must match. You do not repair JSON, fix paths or install a provider runner.

## 11. Local storage

```text
<project>/.apsal/
├── drafts/
├── registry/
├── themes/<theme-id>/<version>/
└── runs/<run-id>/

~/.apsal/
├── registry/
├── extensions/
├── usage/
└── vault/sha256/
```

Project drafts, runs, cache and Vault content are ignored by Git by default. Never publish `private_only` Skills, personal references, Vault content or generated outputs by accident.

## 12. Human visual-QA checklist

Check real-adult live-action medium; identity and age; eyes, hands and anatomy; wardrobe/grooming; prop count, ownership and state; space and reflections; light direction, weather and time; unique narrative function; reference-use boundaries; and absence of grids, text, logos and watermarks.

Schema, Prompt and digest validation establish structure and lineage, not photographic quality.

## 13. Troubleshooting

| Symptom | Action |
|---|---|
| Studio does not trigger | Restart Codex/open a new task and explicitly say “Use APSAL Studio” |
| Codex explains `run.json` instead of using the package | Confirm version 0.10.0 and say “Open this APSAL package and generate the first image” |
| English input still shows Chinese cards | Open a new task after upgrading to 0.10.0, or say “use English”; the session should report language `en` |
| Studio asks for language every time | Use a clear Chinese or English brief; the chooser should appear only for an ambiguous first message |
| A programming interface or code image appears | Reject the current image as visual-QA failure and retry that Job; it is never a valid photographic output |
| The human looks illustrated, doll-like or 3D | Fail live-action medium QA and retry only that Job with the Rendering Contract preserved |
| Only one image appears | Expected; inspect it and say “continue” |
| Output is not exactly 2160×3840 | It is a creative delivery target, not a guaranteed returned Codex pixel size |
| Reference is missing | Reattach only the listed original; a digest mismatch means it is not the bound file |
| Package is `private_only` | Reference redistribution rights are unresolved; this is a safety gate |
| Upstream change invalidates Prompts | Reconfirm affected downstream layers and recompile |

## 14. Developer CLI

Creators do not need these commands, but local diagnostics and automation can use:

```bash
python3 plugins/apsal-studio/scripts/apsal.py init
python3 plugins/apsal-studio/scripts/apsal.py import-run path/to/legacy-run.zip
python3 plugins/apsal-studio/scripts/apsal.py run-bind-reference RUN-ID REF-ID path/to/reference.png
python3 plugins/apsal-studio/scripts/apsal.py run-next RUN-ID
python3 plugins/apsal-studio/scripts/apsal.py validate path/to/theme.apsal.yaml
python3 plugins/apsal-studio/scripts/apsal.py check-sync path/to/theme-directory
python3 plugins/apsal-studio/scripts/apsal.py registry search "quiet window"
python3 plugins/apsal-studio/scripts/apsal.py registry recommend-layer "quiet live-action window portrait" --layer image
```

APSAL keeps structured complexity behind the interface so creators can work in photographic, narrative and aesthetic language while retaining reproducible assets and honest lineage.
