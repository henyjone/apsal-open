# RFC-0003 — Reference Binding, Live-Action Photography, and Native 4K

- Status: implemented in APSAL Studio 0.5.0
- Protocol compatibility: APSAL Open Protocol and Semantic Contract 0.3.0
- Author: HenyJone, APSAL founder
- Scope: reference media, rendering medium, Skill export, provider execution, and visual-QA lineage

## Abstract

A textual analysis of a reference is not the reference. A Prompt that merely says “photograph” is not a reliable live-action medium contract. An aspect ratio is not a pixel-size guarantee. APSAL Studio 0.5 makes these distinctions executable while leaving Protocol 0.3 canonical assets and old Skills readable.

The runtime chain is:

```text
natural-language intent
→ typed and rights-reviewed reference bindings
→ live-action Rendering Contract
→ nine 9:16 Job Prompts
→ nine independent n:1 provider requests
→ exact 2160×3840 validation
→ model visual QA
→ separate human visual QA
```

## Reference binding

Every generation reference MUST have a stable ID, original and packaged SHA-256, allowed role, forbidden uses, applicable Jobs, copyright/portrait-consent state, attribution, and redistribution status. Allowed roles are `style`, `world`, `prop`, `wardrobe`, `composition`, and `identity`.

The local Vault remains the source store. A theme stores purpose and a Vault URI, not media bytes in DNA JSON. A Skill contains sanitized copies in `assets/references/` and a `references/reference_manifest.json` integrity ledger because the image adapter MUST transmit the actual images. Text analysis MAY supplement but MUST NOT replace them.

Reference bytes participate in the Skill digest. Replacement requires a new theme version. A missing file, original digest mismatch, packaged digest mismatch, undeclared purpose, or unresolved dependency MUST fail packaging.

Reference media has an independent license. It never inherits CC BY 4.0 from theme text. Unverified rights, missing consent, or `redistribution_allowed: false` forces:

```yaml
distribution: private_only
private_media_included: true
redistribution_allowed: false
```

Public packaging, GitHub Release, and Hub submission MUST reject that package.

## Live-action Rendering Contract

A live-action theme declares `medium: live_action_photography` and `subject_representation: real_adult_human`. Natural skin, plausible anatomy, optical depth of field, physical light, and photographic material response are preserved. Illustrated, anime, painted, 3D-rendered, mannequin, doll, wax, and clay people are forbidden.

The compiler MUST place the medium contract before scene rhetoric. Handmade, crayon, painted, or theatrical treatment MAY apply to sets and props without changing the human subject into an illustration or object. Medium QA MUST inspect the generated pixels; Prompt validation alone cannot pass it.

## Native-4K execution

The 0.5 default output contract is:

```yaml
aspect_ratio: "9:16"
size: "2160x3840"
quality: high
format: png
provider_native: true
```

The optional `openai-image-api` adapter uses `gpt-image-2`. A Job with references uses Image Edits; one without references uses Generations. The credential is read only from `OPENAI_API_KEY` and MUST NOT enter assets, packages, logs, or run records.

Nine APSAL scenes are nine distinct Prompts, so execution MUST issue nine sequential `n: 1` requests rather than one `n: 9` request. One creator confirmation authorizes the run. A successful Job is immutable; a failed Job MAY retry twice and later resume without repeating successes. `SHOT_01`, after model visual QA, MAY be passed to later Jobs solely as a fictional identity anchor; pose, camera, background, action, wardrobe, and composition MUST NOT transfer.

Every returned file MUST parse as exactly 2160×3840 before success. An adapter without a size control cannot be called a native-4K fallback. More-than-2K output remains provider-dependent and may be experimental; a failed exact-size check produces a failed/partial run, not an upscaled or guessed success.

## QA and compatibility

Run lineage records each Job's actual references, request fields, Prompt digest, retry history, returned dimensions, provider metadata, model visual QA, and human visual QA. Missing provider metadata is `not_reported`.

Old JSON, YAML, 0.4 runs, and exported Skills remain readable. They MUST NOT be retroactively labeled reference-bound, live-action-guaranteed, or provider-native 4K. A move from 2:3 to 9:16 changes composition and therefore requires a MAJOR theme version.
