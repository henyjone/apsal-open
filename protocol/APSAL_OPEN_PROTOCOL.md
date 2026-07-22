# APSAL Open Protocol 0.4

License: Apache-2.0.

APSAL Open Protocol is a vendor-neutral format for portable, versioned photography-generation packages. The protocol is open; an individual package is redistributable only when its own content license and rights metadata permit it.

Protocol 0.4 adds portable creative-project packages, reference-analysis summaries, project lineage, public/private distribution boundaries, static showcase pages, and digest-bound share records. It preserves Protocol 0.3 Semantic Contract themes and Protocol 0.2 JSON packages. The [0.2 compatibility specification](APSAL_OPEN_PROTOCOL_0.2.md) remains available.

APSAL Studio runtime releases add natural-language authoring, the local Registry, reference binding, five-layer/thirteen-element confirmation, Codex-native generation, legacy-package recovery, and the single project kernel. Engine 0.16 and Studio 0.3 add the creative project library, multi-reference analysis Jobs, immutable parent/child lineage, content-addressed output projection, public/private project packages, and confirmed platform drafts. Runtime state remains outside portable themes unless explicitly included by the 0.4 project package contract. See [RFC-0002](RFC-0002-LOCAL-REGISTRY-AND-CONVERSATIONAL-AUTHORING.md) through [RFC-0011](RFC-0011-SINGLE-PROJECT-DUAL-ENTRY.md) and the [0.16 release notes](../docs/releases/0.16.0.md).

## Authoring and canonical formats

- `.apsal.yaml` is the editable authoring source for creators and Codex.
- `.apsal.json` is the canonical machine artifact used for validation, hashing and packaging.
- YAML and JSON express the same data model and MUST NOT be maintained as independent sources.
- YAML is restricted to the safe APSAL YAML 1.2 subset: no custom tags, anchors, aliases, merge keys, duplicate keys, tabs or multiple documents.
- Integrity digests are calculated over normalized canonical JSON values, not YAML bytes or comments.

Legacy JSON remains valid. New Semantic Contract assets use theme/module schema `1.1.0` and record `semantic_contract_version: 0.3.0`.

## Creative project package contract

A Protocol 0.4 creative project package MUST declare its distribution as
`public` or `private`, preserve the source project ID and package digest, and
include checksums for every file. Imported packages receive a new local project
ID while retaining source provenance.

A public package MUST NOT contain original private references, vault URIs,
absolute paths, credentials, platform tokens, or nested private Skill archives.
It MAY contain generated project outputs, the APSAL theme, Prompts, negative
constraints, QA rules, a reference-free `SKILL.md`, an analysis summary, and a
static showcase page. Reference metadata does not grant media redistribution.

A private package MAY contain sanitized reference copies and complete run
records for an authorized recipient. It is not thereby public or
redistributable.

Project lineage records `parent_project_id`, `origin_project_id`,
`source_asset_ids`, `fork_type`, and `parent_snapshot_digest`. Forking creates a
new project; it MUST NOT mutate the parent snapshot.

## Semantic Contract

Every new semantic module and every meaningful creative choice declares:

- bilingual `purpose`;
- semantic paths it `affects`;
- non-target fields it `must_preserve`;
- fields that `may_vary`;
- bilingual, observable `expected_effects`;
- evidence-based `qa_expectations`;
- controlled `semantic_tags` from the registry;
- integer conflict `priority` from 0 through 100.

Schema descriptions define what a field always means. Instance intent explains why one value was chosen for one world or Job. Tags support retrieval and reasoning; they never replace stable IDs, dependencies or explicit constraints.

Chinese visual concepts such as 经营位置、意境、气韵、虚实 and 游观 are interpretive and methodological context. They MUST NOT be reduced to unvalidated numeric parameters or used as substitutes for observable machine fields.

## Three layers

1. **Protocol** — schemas, IDs, lineage, dependency rules, deterministic compilation order, QA states, and package layout. Licensed Apache-2.0.
2. **Reference engine** — validator, compiler, migrator, digest ledger, and Codex Skill packager. Licensed Apache-2.0.
3. **Content** — DNA modules, themes, copy, and examples. Each asset carries an explicit content license and rights record; official open content defaults to CC BY 4.0.

Calling a document a “protocol” does not make its content open source. A conforming public package MUST include license, rights, provenance, lineage, and checksums.

## Package layout

```text
package/
├── manifest.json
├── LICENSE-CONTENT.md
├── modules/
│   ├── subject.json
│   ├── world.json
│   ├── style.json
│   ├── look.json
│   ├── emotion.json
│   ├── event.json
│   ├── camera.json
│   ├── light.json
│   ├── color_post.json
│   ├── quality_control.json
│   └── content.json
├── sequences/
│   └── sequence.json
└── jobs/
    └── shot_*.json
```

The thirteen protocol roles are the eleven module families plus `sequence` and `job`. Files may be split further, but all dependencies must resolve through manifest entries.

## Required manifest contract

- `protocol`: `apsal-open`
- `protocol_version`: semantic version
- stable package `id`, content `version`, `parent_version`, `changed_fields`, and `change_summary`
- `license.code` and `license.content`
- `rights.status`, `rights.attribution`, AI disclosure, and reference-media declaration
- exact module, sequence, and job paths
- SHA-256 for every package file except the manifest itself
- output policy declaring independent images and unique filenames
- QA state that distinguishes static validation from human visual QA

## Module contract

Every module has a stable ID, type, semantic version, parent version, changed fields, change summary, content license, rights status, QA state, dependencies, and payload. Published ID/version pairs are immutable.

Identity locks outrank prose fluency. Platform/model parameters belong in optional adapters, not canonical modules. A single-variable variant identifies exactly one changed dotted path.

## Deterministic compilation order

`subject → world → style → look → emotion → event → camera → light → color_post → content → sequence → job → quality_control`

Negative constraints are inherited and cannot disappear silently. Each Job compiles into exactly one independent finished image.

Protocol 0.3 and 0.4 expose three deterministic theme compilation targets:

1. `design` preserves purpose, relations, constraints and intent for Codex or another planning model.
2. `image` emits only observable image instructions and inherited negative constraints.
3. `qa` turns expected effects and QA expectations into evidence-based checks.

Conflict precedence is fixed: identity and rights; world physics and continuity; event and shot function; camera, light and color; style rhetoric.

## Public-package safeguards

- No collage, grid, contact sheet, storyboard, text, logo, or watermark unless a separate post-layout stage explicitly requests it.
- No credential, personal reference image, private identity anchor, or unlicensed third-party source.
- Named living-artist or photographer imitation mappings are rejected from the official namespace; describe observable visual properties instead.
- “Static validated” never means “visual QA passed.” Visual QA requires evidence linked in the manifest.
