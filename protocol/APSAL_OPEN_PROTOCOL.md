# APSAL Open Protocol 0.2

License: Apache-2.0.

APSAL Open Protocol is a vendor-neutral format for portable, versioned photography-generation packages. The protocol is open; an individual package is redistributable only when its own content license and rights metadata permit it.

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

## Public-package safeguards

- No collage, grid, contact sheet, storyboard, text, logo, or watermark unless a separate post-layout stage explicitly requests it.
- No credential, personal reference image, private identity anchor, or unlicensed third-party source.
- Named living-artist or photographer imitation mappings are rejected from the official namespace; describe observable visual properties instead.
- “Static validated” never means “visual QA passed.” Visual QA requires evidence linked in the manifest.
