# APSAL Studio 0.6 interaction contract

## What creators see

The creator sees natural language, preview cards, the nine-shot overview, and generation progress. YAML is the editable background source; canonical JSON is the immutable execution and lineage artifact. Do not expose either by default.

Each DNA card must display its preview, title, core attributes, scope (`project`, `personal`, `extension`, or `official`), version, rights license, attribution, QA state, recommendation reason, matched tags and relevant scene facets. A semantic card is a design aid, not evidence of final image quality. In a client without MCP Apps, print the same choices as a numbered list and accept a number or natural-language revision.

## Recommendation and memory

Recommend from the complete scene requirement, not from the DNA type alone. Ranking order is identity/rights/medium, scene intent, explicit dependency compatibility, photographic language, local creator memory, QA and Registry scope. Always explain why an asset matches; never present a hidden score as taste authority.

For new or revised DNA, show suggested controlled tags and facets before stage confirmation. The creator may edit them. Stable identity, version, dependencies, locks and rights remain authoritative; tags aid retrieval and never replace them.

After confirmation, ask whether project DNA should move to “My DNA.” Offer exactly:

1. Save to My DNA — copy the immutable version to the personal Registry.
2. Current project only — keep it under `<project>/.apsal/registry/`.
3. Decide later — leave the memory offer pending.

Do not ask for bundled official DNA, installed extension DNA, or a version already in the personal Registry. Record successful/failed/rejected usage as private scoring memory without storing the raw brief.

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

At Scene, first explain the sequence arc, then show nine Scene summaries. Every frame needs a unique narrative function, observable action, motivated gaze, hand plan, 9:16-safe composition, continuity phase, and output filename. Default is one Job and one 2160×3840 PNG.

## Reference binding

Do not accept “use this image” as an untyped instruction. For every supplied image, confirm:

- stable reference ID and applicable Jobs;
- one or more allowed roles: style, world, prop, wardrobe, composition, or identity;
- forbidden uses such as copying a face, body, pose, exact composition, text, signature, or watermark;
- copyright, portrait consent, attribution, and redistribution status.

The image is stored in the private Vault by SHA-256. Theme DNA stores only purpose, restrictions, rights metadata, and the Vault URI needed by the local engine. Replacing bytes creates a new content digest and requires a new theme version. A prose analysis can supplement a reference but cannot replace the actual image sent to the provider.

## Local storage

- Bundled official Registry: read-only and shipped with the plugin.
- `~/.apsal/` or `APSAL_HOME`: reusable personal DNA and private Vault.
- `~/.apsal/extensions/`: installed, immutable community Extension Packs.
- `<project>/.apsal/`: drafts, project DNA, frozen themes, prompts, runs, outputs, and QA.

Resolution order is project → personal → extension → official. A pack may add a new namespace but cannot override an existing or official ID/version.

Store provider-neutral theme prompts under the frozen theme version. Store exact effective prompts again under every run. Chat history is never the only lineage record.

Private references go to `~/.apsal/vault/sha256/`. Retain only their Vault URI, digest, roles, scope, and rights state in the session/theme. They never enter public Git or a public Release. A local `private_only` Skill contains sanitized copies and an integrity manifest because the image model must actually see them; it explicitly forbids redistribution.

## Final choices

After the nine-shot overview, offer:

1. Generate nine images — show the live-action contract, reference count, private/public status, 9:16, 2160×3840, nine provider requests, and possible cost; then require one explicit confirmation.
2. Save prompts only — no image provider call.
3. Export Skill — reproducible ZIP plus SHA-256. Private references force `private_only` packaging; public export fails unless redistribution rights are explicit.

Native 4K execution uses `gpt-image-2` through the optional OpenAI Image API adapter. Run nine independent `n: 1` Jobs sequentially, not one `n: 9` call. References are attached through Image Edits; jobs without references use Generations. `SHOT_01` becomes an identity-only runtime anchor after it passes model visual QA. Every output must parse as exactly 2160×3840 or the Job fails. For partial runs, show successful, failed, and pending Jobs separately and resume only failed or pending Jobs.

Keep model visual QA and human visual QA separate. Prompt validation never proves that the result is a real human photograph.

## DNA Extension Packs

Use an Extension Pack to share reusable DNA independently from a theme Skill. A public pack contains `apsal-dna-pack.json`, canonical DNA, preview sidecars, license/attribution, README and a deterministic checksum ledger. It contains no private Vault media. Any unresolved license, attribution, tag confirmation or dependency forces a private pack or blocks public export.
