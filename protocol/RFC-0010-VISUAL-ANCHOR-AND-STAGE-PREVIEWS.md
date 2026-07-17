# RFC 0010 — Visual Anchor and Stage Previews

Status: implemented in APSAL Studio / Engine 0.14.0

Protocol compatibility: APSAL Open 0.3.0

Semantic Contract compatibility: 0.3.0

## Problem

A theme Skill needs enough visual context for Codex to use real references correctly, while the authoring interface needs a compact visual account of what has already been designed. Treating those needs as one image class creates two failures: an abstract progress graphic can accidentally influence generation, or a private photograph can be exposed as ordinary interface decoration.

## Decision

APSAL 0.14 defines two disjoint asset classes.

### Real generation references

Real images remain under `assets/references/` and are governed by `reference_manifest.json`. Every image records its stable ID, original and packaged SHA-256, allowed and forbidden uses, applicable Jobs, copyright, portrait consent, attribution and redistribution status.

When at least one real image is packaged, exactly one is designated `core_visual_anchor`. Selection order is:

1. explicit creator choice;
2. an identity reference;
3. a reference applicable to every Job;
4. the first packaged reference.

The anchor is a package-level entry point, not a permission override. It may be passed only to Jobs and uses already declared in its record. With no real reference, the manifest records `core_visual_anchor_reference_id: null` and `core_visual_anchor_status: not_bound`.

### Semantic stage previews

The interface displays one localized 4:3 summary for each authoring layer:

1. Direction and Emotion;
2. Subject, World and Look;
3. Event and Sequence;
4. Camera, Light, Style and Color/Post;
5. Job and Quality Control.

These deterministic SVG assets contain only APSAL visual grammar, localized layer copy and progress state. They are not photographic examples. Exported Skills store Chinese and English variants under `assets/previews/stages/` and verify them through `preview_manifest.json`.

Every stage preview must declare:

```json
{
  "visual_kind": "semantic_stage_summary",
  "generation_input": false,
  "width": 768,
  "height": 576
}
```

Stage previews never appear under `assets/references/`, never enter `reference_manifest.json`, never substitute for a missing image and never become Codex image-generation inputs. DNA selection cards remain text-only; the thumbnail strip belongs only to the five-layer progress surface.

## Digests and versioning

- Reference bytes and their anchor declaration participate in the reference manifest and Skill package digests.
- Stage preview bytes participate in the preview manifest and Skill package digests.
- Stage previews do not change the canonical theme digest or DNA version because they are presentation artifacts.
- Replacing a real reference changes generation lineage and requires the appropriate theme version change.

## Rights and privacy

Stage previews are original APSAL vector assets licensed with project content. Real references retain their independent licenses and portrait permissions. Unresolved real-reference rights force `private_only`; preview rights never make a private reference publishable.

## Validation

The package validator checks exactly five stages in both supported languages, every preview SHA-256, `generation_input: false`, strict directory separation, one valid core anchor when real references exist, and `not_bound` when none exist. Static validation proves structure and lineage only; it does not prove photographic quality.
