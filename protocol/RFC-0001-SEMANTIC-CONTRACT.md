# RFC-0001: APSAL Semantic Contract 0.3

Status: Accepted for the `APSAL-OPEN-001@1.1.0` pilot  
Author: HenyJone, Founder of APSAL  
License: Apache-2.0  
Date: 2026-07-15

## Problem

Protocol 0.2 preserves values, versions and dependencies, but a field value alone does not explain why it was chosen, what it affects, what must remain locked or how its success should be judged. The reference compiler concatenates prompt fragments, so descriptive metadata cannot guide scene design or become QA evidence.

## Decision

Protocol 0.3 introduces a machine-readable Semantic Contract with `purpose`, `affects`, `must_preserve`, `may_vary`, `expected_effects`, `qa_expectations`, controlled `semantic_tags` and `priority`.

Schema descriptions carry permanent field meaning. Instance `intent` carries the reason for a choice in one theme or Job. Creative fields may add field-level intent with purpose, affected paths, expected effects and QA expectations.

The official registry is the sole authority for thirteen role definitions, seven-to-thirteen DNA mapping, field definitions and allowed tags. Free prose may clarify meaning but cannot replace IDs, paths, dependencies or locks.

## Serialization

Safe `.apsal.yaml` is the authoring format; normalized `.apsal.json` is canonical. YAML comments are never semantic data. Both parse to one JSON-compatible value. The reference engine rejects unsafe YAML features and detects divergence with `check-sync`.

## Compilation

- `design` is planning context for Codex and retains semantic reasoning.
- `image` is provider-neutral observable image language and excludes Schema commentary.
- `qa` is a bilingual, evidence-oriented checklist.

Static validation establishes structure, lineage, tags and reproducibility only. Human visual QA still requires generated-image evidence.

## Compatibility and migration

Existing 0.2 JSON and theme schema 1.0.0 remain readable. A compatible semantic enrichment increments the content MINOR version, records its parent, lists semantic paths in `changed_fields`, preserves DNA digests and does not claim a generation-intent change.

The first and only pilot is `APSAL-OPEN-001@1.1.0`, derived from `1.0.0`. Bulk migration is deferred until the pilot demonstrates useful design and QA output.

## Rejected alternatives

- Comments-only YAML: comments disappear during normalization and cannot be validated.
- Tags-only semantics: tags classify but do not explain purpose, effects or evidence.
- Wrapping every scalar in a large object: excessive repetition consumes context and creates migration noise.
- Independent YAML and JSON editing: creates two conflicting authorities.

