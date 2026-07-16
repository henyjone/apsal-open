# RFC-0007: Legacy run takeover

Status: Implemented in APSAL Studio and reference engine 0.9.0  
Protocol compatibility: APSAL Open Protocol 0.3.0  
Semantic Contract compatibility: 0.3.0

## Problem

Older APSAL exports could contain `run.json` and per-shot Prompts while omitting the reference images and retaining an obsolete provider adapter, model and absolute theme path. Exposing those implementation details to a creator produces the wrong experience: the creator is told that JSON is not executable and is asked to find an API runner even though the package's intended execution surface is Codex.

## Creator contract

The creator attaches a ZIP or points to a directory and asks Codex to open or use it. Studio MUST:

1. identify exactly one `run.json` without asking the creator to extract or inspect it;
2. recover every positive and negative Prompt as an immutable Job;
3. treat provider endpoint, adapter, API parameters and model as historical lineage only;
4. locate each declared reference by SHA-256 inside the package or in the private APSAL Vault, without following obsolete absolute paths from an untrusted package;
5. ask only for references that remain missing;
6. verify a reattached reference against the recorded digest;
7. create a private Codex Prompt/Skill package with usage instructions and checksums;
8. return the first unfinished Job ready for Codex built-in image generation.

The creator MUST NOT be asked to repair JSON, absolute paths, API configuration or provider code.

## Safe import

ZIP inspection rejects path traversal, absolute paths, symlinks, duplicate members, excessive path depth, oversized members and excessive expanded size. Import never executes a bundled file. Only JSON, UTF-8 Prompt text and digest-matched images are interpreted.

Imported packages are always `private_only`. Historical absolute paths and credentials are excluded from the reconstructed Skill. Reference rights remain independent and forbidden uses outrank allowed or declared roles when metadata conflicts.

## Reference resolution

Resolution order is:

```text
declared package-relative path
→ digest scan of package image files
→ ~/.apsal/vault/sha256/<prefix>/<digest>/reference.*
→ creator reattachment with digest verification
```

A missing reference blocks only Jobs that require it. Prompt recovery and migration state remain preserved. The user-facing request identifies the reference ID and original filename, not an obsolete machine path.

## Codex handoff

The migrated run declares:

```yaml
generation_surface: codex_imagegen
direct_api_calls: false
api_key_required: false
provider_native: false
returned_dimensions_guaranteed: false
```

Every imported Job is prefixed with an instruction to generate the finished photographic image itself. Code, JSON, terminals, programming interfaces, Prompt sheets, grids, collages, text, logos and watermarks are prohibited as image content.

Codex generates exactly one image per turn. “Continue” advances to the next unfinished Job after result recording and model visual QA. Successful Jobs remain immutable.

## Package layout

The reconstructed private ZIP contains `SKILL.md`, `PROMPT_GUIDE.md`, three Prompt files per Job, restored reference files, a reference manifest, a sanitized source-run summary, a Codex-native manifest and an offline Prompt validator. It contains no provider executor.

## Compatibility

This is a runtime migration and does not rewrite the source ZIP, canonical theme or DNA versions. Protocol and Semantic Contract remain 0.3.0. Source run SHA-256, original run ID, schema version, adapter and model remain recorded as history without remaining executable.
