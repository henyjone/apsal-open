# RFC-0002 — Local Registry and Conversational Authoring 0.4

- Status: implemented in APSAL Studio 0.4.0
- Protocol compatibility: APSAL Open Protocol 0.3.0
- Author: HenyJone, APSAL founder
- Scope: authoring UX, local asset resolution, preview presentation and generation lineage

## Abstract

APSAL Studio 0.4 removes JSON and YAML from the creator-facing workflow without removing them from the protocol. A creator begins with one natural-language idea, confirms four understandable DNA groups through preview cards, reviews nine independent scenes, and then chooses image generation, Prompt export, or Skill export.

This RFC does not add new canonical DNA types. Character, World, Scene and Photo are interaction groups mapped onto the existing seven DNA categories and thirteen APSAL protocol elements.

## Authoritative chain

```text
natural-language brief
→ four confirmed interaction stages
→ background YAML authoring source
→ canonical JSON
→ design / image / QA compilation
→ exact run prompts
→ nine independent results
```

Chat history is not a lineage artifact. Theme-level provider-neutral Prompts and run-level effective Prompts MUST be written locally before image generation.

## Registry layers

Resolution order is project, personal, then official:

1. `<project>/.apsal/registry/` — mutable working scope with immutable formal versions.
2. `~/.apsal/registry/` — reusable personal scope; `APSAL_HOME` MAY override the home root.
3. plugin `assets/dna/catalog.json` — read-only official scope.

Every reference MUST contain namespace, ID, type, semantic version and canonical content digest. The first matching layer wins only when every duplicate has the same digest. A duplicate ID/type/version with a different digest MUST fail.

Promotion from project to personal scope requires an explicit creator action. Official assets cannot be promoted or overwritten. A changed formal asset requires a new version and complete lineage.

## Preview sidecars

Every selectable asset MUST have `preview.webp` and `preview.json`. Official preview images are exactly 768×576 WebP. The sidecar records image digest, kind, rights, attribution, QA status and the required disclaimer.

Preview bytes are presentation metadata and are excluded from the DNA content digest. Replacing a preview therefore does not change generation intent or the DNA version. A generated or abstract semantic card MUST NOT be presented as evidence of photographic output quality.

## Private references

Private character references MUST be stored in the user's content-addressed Vault under `~/.apsal/vault/sha256/`. Themes and sessions MAY retain a vault URI and digest. They MUST NOT embed the media, place it in Git, export it in a Skill, or upload it automatically.

This 0.4 export rule is superseded for new 0.5 Skills by [RFC-0003](RFC-0003-REFERENCE-BINDING-LIVE-ACTION-AND-NATIVE-4K.md): a local `private_only` Skill may contain sanitized, manifest-bound copies so the provider receives the real references. The Git and automatic-upload prohibitions remain unchanged. Existing 0.4 Skills retain their original semantics.

## Session semantics

The state order is:

```text
character_pending → world_pending → scene_pending → photo_pending
→ review_pending → ready → generating → completed / partial
```

Changing an upstream stage MUST invalidate every confirmed downstream stage and all compiled Prompt artifacts. Scene design defaults to nine Jobs; each Job produces one independent image. A failed Job MAY be retried without repeating successful Jobs.

## Provider boundaries

The local engine does not require an account, hosted API, network access or a single image provider. Remote generation requires explicit confirmation. A run record MUST identify the adapter, model and parameters actually reported. Missing provider metadata MUST be `not_reported` and MUST NOT be inferred.

## Compatibility

Protocol 0.3.0 schemas, old JSON, old YAML, existing Skill ZIPs, official DNA versions and the `APSAL-OPEN-001@1.1.0` pilot retain their generation intent. Studio/engine 0.4.0 adds an authoring and runtime layer only.
