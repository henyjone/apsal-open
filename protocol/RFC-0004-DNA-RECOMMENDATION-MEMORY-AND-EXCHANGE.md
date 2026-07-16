# RFC-0004 — DNA Recommendation, Memory, and Exchange 0.6

- Status: implemented in APSAL Studio 0.6.0
- Protocol compatibility: APSAL Open Protocol and Semantic Contract 0.3.0
- Author: HenyJone, APSAL founder
- Scope: local recommendation, discovery metadata, explicit personal memory, usage feedback, and DNA Extension Packs

## Abstract

APSAL should not ask a creator to browse an undifferentiated catalog. It should interpret the scene, recommend compatible DNA, explain the match, let the creator confirm or revise, and then ask whether new knowledge should become reusable personal DNA. Rights-cleared DNA may also travel independently from a theme as a deterministic Extension Pack.

```text
scene intent
→ explainable DNA recommendation
→ creator selection or revision
→ controlled tag/facet confirmation
→ project DNA
→ explicit Save to My DNA
→ private usage feedback
→ future recommendation
→ optional Extension Pack
```

This layer does not change the canonical meaning of Protocol 0.3 assets. Stable IDs, versions, dependencies, rights, locks and Semantic Contracts remain authoritative.

## Discovery metadata

New or revised Registry DNA MAY declare:

```yaml
discovery:
  schema_version: 0.6.0
  semantic_tags:
    - subject.identity.locked
    - style.editorial.restrained
  facets:
    subject.age: adult
    world.feature: window
    lighting.source: natural-window-light
    output.medium: live_action_photography
  keywords:
    - portrait
    - window
  source: creator_confirmed
  source_brief_digest: <sha256>
```

`semantic_tags` come from the controlled Semantic Registry and support relationship reasoning. Facets use a controlled key vocabulary and support retrieval. Keywords are limited supplementary terms. None may replace a stable reference, version, dependency, identity lock, right, or QA state.

APSAL MAY propose deterministic metadata. Public sharing requires the creator to confirm it. Changing discovery metadata on a formal version follows ordinary immutability and version-lineage rules.

## Explainable recommendation

Recommendation MUST filter by the current interaction stage and MUST disclose reasons. Ranking follows:

1. identity, rights and rendering medium;
2. scene intent and controlled facets;
3. explicit compatibility with confirmed upstream DNA;
4. camera, light, color and style language;
5. local creator feedback;
6. QA state and Registry scope.

Registry resolution remains project → personal → extension → official. Scope is a tie-breaker, not proof of aesthetic quality. A recommendation response includes matched tags/facets, QA, rights, source scope and a human-readable reason. Hidden scoring MUST NOT be presented as objective taste.

## Explicit personal memory

Confirmation first creates or selects project DNA. Only a new or revised project version triggers one memory choice:

- `save_personal` — copy the immutable version into `~/.apsal/registry/`;
- `project_only` — retain it only under the project Registry;
- `not_now` — keep the offer pending.

Official, extension and already-personal DNA do not trigger the question. APSAL MUST NOT silently promote a project asset.

Accepted, rejected, successful and failed outcomes MAY be recorded under `~/.apsal/usage/events.jsonl`. Events contain stable references, controlled context, timestamps and optional short notes. Raw creative briefs are excluded; only their SHA-256 and detected tags/facets are retained.

## DNA Extension Pack

A standalone pack has this root layout:

```text
apsal-dna-pack.json
checksums.sha256
LICENSE-CONTENT.md
README.md
registry/<namespace>/<type>/<id>/<version>/
├── asset.apsal.json
├── preview.webp
└── preview.json
```

One pack uses one namespace and semantic version. The manifest records exact content-digest references, dependencies, distribution, rights state and every payload SHA-256. The ZIP is deterministic.

A public pack requires creator-confirmed discovery metadata, redistributable DNA and preview licenses, attribution, valid QA sidecars and resolved dependencies. It contains no private Vault media. Otherwise it MUST be `private_only` or public export MUST fail.

Installation accepts a local ZIP or a pinned public GitHub Release source:

```text
github:owner/repository@v1.0.0#pack-v1.0.0.zip
```

Installed packs are read-only under `~/.apsal/extensions/`. The installer rejects path traversal, symlinks, duplicate paths, checksum mismatch, decompression limits, missing dependencies and any existing or official ID/type/version collision. A pack never executes code and cannot mutate official assets.

## Compatibility

Protocol and Semantic Contract remain 0.3.0. Studio 0.4 and 0.5 themes, Registry assets, Skills and runs remain readable. Legacy DNA without discovery metadata remains usable and receives runtime-only tag suggestions; it cannot be publicly re-exported as a 0.6 Extension Pack until metadata is confirmed in a new, correctly versioned asset.
