# RFC-0006: Codex-native generation and Prompt delivery

Status: Implemented in APSAL Studio and reference engine 0.8.0  
Protocol compatibility: APSAL Open Protocol 0.3.0  
Semantic Contract compatibility: 0.3.0

## Abstract

APSAL Studio is a Codex plugin. Its final execution surface is therefore Codex itself, not a second image-provider client hidden inside the plugin. This RFC removes direct image API execution, makes the Prompt package an automatic creator deliverable, and defines a resumable one-image-per-turn handoff to Codex built-in image generation.

```text
Natural-language brief
→ five layers and thirteen confirmed elements
→ frozen theme and deterministic Prompt/Skill ZIP
→ one Codex image Job
→ Codex visual QA
→ “continue”
→ next unfinished Job
```

## Normative decisions

### 1. No direct image-provider execution

The Studio engine and MCP server MUST NOT:

- request or read an image API key;
- select a provider model or endpoint;
- send an HTTP image generation/edit request;
- expose a tool that claims to execute a provider run;
- bundle an executable network generation client into a theme Skill.

`start_generation_run` prepares local lineage only. `get_next_codex_job` returns the next immutable Job's full Prompt and the exact reference arguments that Codex should use. Codex owns the actual image-generation call.

### 2. One image per Codex turn

Every Job corresponds to one independent finished image and one Codex image-generation call. After Codex emits an image, the Skill MUST stop its response. On the creator's next “continue” or equivalent instruction, the run records only metadata actually available, completes Codex visual review, and advances to the next unfinished Job.

A successful Job is immutable. A failed Job may be retried without regenerating successful Jobs. The resulting run may be `generating`, `partial`, or `completed`.

### 3. Reference handoff

If a Job has bound local references, Codex receives their actual filesystem paths and their declared purposes and restrictions. A textual analysis never substitutes for the image bytes.

When there are no bound local references, the immediately previous accepted image MAY be supplied through Codex recent-image context as an identity-only anchor. The anchor MUST NOT transfer pose, camera, background, action, wardrobe, lighting or composition. Local-path references and recent-image context are mutually exclusive handoff mechanisms for one call.

### 4. Automatic Prompt/Skill package

Finalization MUST export a deterministic ZIP containing:

```text
<theme>-codex-prompt-skill[-private].zip
├── SKILL.md
├── PROMPT_GUIDE.md
├── prompts/
│   ├── SHOT_01.prompt.txt
│   ├── SHOT_01.negative.txt
│   ├── SHOT_01.full.txt
│   └── ... SHOT_09
├── references/
│   ├── theme.json
│   ├── compiled.json
│   ├── design_context.json
│   ├── qa_checklist.json
│   ├── rendering_contract.json
│   ├── reference_manifest.json
│   └── manifest.json
├── assets/references/
└── scripts/validate_prompt_pack.py
```

The manifest records the SHA-256 of every Prompt, reference lineage, rights and distribution state. Missing or digest-mismatched references fail packaging. Private or non-redistributable media force `private_only` and prohibit public release.

`PROMPT_GUIDE.md` explains both Codex use and direct Prompt reading. The verifier is offline and makes no network request.

### 5. Output honesty

Studio requests 9:16, high quality and a 2160×3840 creative delivery target. Because Codex manages the image model and exposed controls, the package and run MUST set:

```yaml
generation_surface: codex_imagegen
provider_native: false
size: not_guaranteed
returned_dimensions_guaranteed: false
```

Actual model, provider, format and dimensions are recorded only when Codex exposes them; otherwise they are `not_reported`. A requested delivery target MUST NOT be represented as a provider-native or returned-pixel guarantee.

## Compatibility

Protocol and Semantic Contract remain 0.3.0. Official DNA, theme intent, YAML, canonical JSON and legacy packages remain readable. The Studio 0.5 direct-provider executor is historical and unsupported in 0.8; an attempted compatibility call fails explicitly rather than silently making a network request.

The live-action photography Rendering Contract, independent-image rule, reference rights, identity locks, QA separation and one-Job-one-image semantics remain unchanged.
