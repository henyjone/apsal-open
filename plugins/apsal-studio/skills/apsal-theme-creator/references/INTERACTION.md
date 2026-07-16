# APSAL Studio 0.4 interaction contract

## What creators see

The creator sees natural language, preview cards, the nine-shot overview, and generation progress. YAML is the editable background source; canonical JSON is the immutable execution and lineage artifact. Do not expose either by default.

Each DNA card must display its preview, title, core attributes, scope (`project`, `personal`, or `official`), version, rights license, attribution, and QA state. A semantic card is a design aid, not evidence of final image quality. In a client without MCP Apps, print the same choices as a numbered list and accept a number or natural-language revision.

## Four creator-facing DNA groups

The UI uses four understandable groups without introducing competing protocol types:

| Stage | Internal DNA | Creator decision |
|---|---|---|
| Character | character | adult identity, reference, immutable locks |
| World | environment | space, materials, physical rules, time, continuity |
| Scene | composition + shot | sequence strategy, nine events, order, viewpoints |
| Photo | style + lighting | photographic rhetoric, optics, light and color |

QA DNA remains an internal required dependency and is not presented as a creative style choice.

## State transitions

Use this order:

```text
brief
→ character_pending
→ world_pending
→ scene_pending
→ photo_pending
→ review_pending
→ ready
→ generating
→ completed / partial
```

A creator may return to an earlier stage. Committing a changed upstream selection invalidates all confirmed downstream stages and compiled prompts. Explain which stages need confirmation again.

## Natural-language revision

Translate requests such as “人物更成熟，但保留短发” into a proposed DNA revision. Explain the one intended variable and the locks that remain. Save drafts automatically to the project. Confirmation promotes the draft to project DNA; copy it to personal DNA only after an explicit “保存到我的 DNA”. Never edit a formal ID/version in place.

At Scene, first explain the sequence arc, then show nine Scene summaries. Every frame needs a unique narrative function, observable action, motivated gaze, hand plan, composition, continuity phase, and output filename. Default is one Job and one 2:3 image.

## Local storage

- Bundled official Registry: read-only and shipped with the plugin.
- `~/.apsal/` or `APSAL_HOME`: reusable personal DNA and private Vault.
- `<project>/.apsal/`: drafts, project DNA, frozen themes, prompts, runs, outputs, and QA.

Store provider-neutral theme prompts under the frozen theme version. Store exact effective prompts again under every run. Chat history is never the only lineage record.

Private identity references go to `~/.apsal/vault/sha256/`. Retain only their vault URI and digest in the session. They never enter theme DNA, public Git, a release, or an exported Skill.

## Final choices

After the nine-shot overview, offer:

1. Generate nine images — requires explicit confirmation and nine independent calls.
2. Save prompts only — no image provider call.
3. Export Skill — reproducible ZIP plus SHA-256.

For partial runs, show successful, failed, and pending Jobs separately. Resume only failed or pending Jobs.
