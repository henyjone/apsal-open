# APSAL Open Protocol 0.3

License: Apache-2.0.

APSAL Open Protocol is a vendor-neutral format for portable, versioned photography-generation packages. The protocol is open; an individual package is redistributable only when its own content license and rights metadata permit it.

Protocol 0.3 adds the APSAL Semantic Contract and safe YAML authoring while preserving Protocol 0.2 JSON packages. The [0.2 compatibility specification](APSAL_OPEN_PROTOCOL_0.2.md) remains available.

APSAL Studio 0.4 adds a natural-language authoring UX, layered local Registry, preview sidecars and generation-run lineage. Studio 0.5 adds reference binding, a live-action Rendering Contract, private Skill media manifests, and sequential native-4K execution. Studio 0.6 adds explainable recommendation, explicit personal memory and portable DNA Extension Packs. These runtime layers do not change Protocol 0.3 canonical compatibility. See [RFC-0002](RFC-0002-LOCAL-REGISTRY-AND-CONVERSATIONAL-AUTHORING.md), [RFC-0003](RFC-0003-REFERENCE-BINDING-LIVE-ACTION-AND-NATIVE-4K.md), and [RFC-0004](RFC-0004-DNA-RECOMMENDATION-MEMORY-AND-EXCHANGE.md).

## Authoring and canonical formats

- `.apsal.yaml` is the editable authoring source for creators and Codex.
- `.apsal.json` is the canonical machine artifact used for validation, hashing and packaging.
- YAML and JSON express the same data model and MUST NOT be maintained as independent sources.
- YAML is restricted to the safe APSAL YAML 1.2 subset: no custom tags, anchors, aliases, merge keys, duplicate keys, tabs or multiple documents.
- Integrity digests are calculated over normalized canonical JSON values, not YAML bytes or comments.

Legacy JSON remains valid. New Semantic Contract assets use theme/module schema `1.1.0` and record `semantic_contract_version: 0.3.0`.

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

Protocol 0.3 exposes three deterministic compilation targets:

1. `design` preserves purpose, relations, constraints and intent for Codex or another planning model.
2. `image` emits only observable image instructions and inherited negative constraints.
3. `qa` turns expected effects and QA expectations into evidence-based checks.

Conflict precedence is fixed: identity and rights; world physics and continuity; event and shot function; camera, light and color; style rhetoric.

## Public-package safeguards

- No collage, grid, contact sheet, storyboard, text, logo, or watermark unless a separate post-layout stage explicitly requests it.
- No credential, personal reference image, private identity anchor, or unlicensed third-party source.
- Named living-artist or photographer imitation mappings are rejected from the official namespace; describe observable visual properties instead.
- “Static validated” never means “visual QA passed.” Visual QA requires evidence linked in the manifest.
