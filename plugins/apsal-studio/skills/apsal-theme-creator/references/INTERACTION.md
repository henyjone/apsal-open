# APSAL Studio 0.16 interaction and delivery contract

## Language before creative decisions

Follow the current Codex conversation language automatically when it is clearly Chinese or English. Do not insert a mandatory language screen at installation or first use. If the first usable message is genuinely ambiguous, ask the one-line bilingual question “English or 中文?” and persist the answer with `set_session_language`. Switching language later changes presentation only and does not invalidate confirmed layers or recompile the theme.

## Authoring mode choice

Before the frontend question, ask once whether this creation uses “全自动创作（推荐）” or “逐步确认”. Store the choice as session-only `authoring_mode`; it is independent from `frontend_mode` and does not enter theme or Prompt digests.

`automatic` is up-front permission to select the top valid explained Registry recommendation for every required DNA type, confirm the five layers in protocol order, and finalize the Prompt/Skill package in one project revision. The resulting element source is `automatic_default`, not `creator_confirmed`. `guided` preserves the existing cards, revisions, explicit layer confirmations and final overview confirmation. Existing sessions without the field behave as guided.

Automatic mode may pause only for information that cannot be safely inferred: interface language, reference role/rights/consent, a missing required DNA type, protocol incompatibility or validation failure. Reference bindings that have already been resolved are passed with `start_design_session` and applied at Worldbuilding. Automatic mode never broadens image rights, bypasses QA, generates collages, or claims human visual QA. Image generation remains a separate delivery action after the automatically created package.

## Codex-first frontend choice

Codex is always the creative entry. Before a new or resumed workflow calls `start_design_session`, ask once whether to open APSAL Studio for this creation. The Chinese choices are “打开并联动（推荐）” and “仅在 Codex 中继续”; the English choices are “Open and link (Recommended)” and “Continue in Codex only”. An explicit choice in the creator's request skips the question.

The selected value is passed as `frontend_mode`. `studio` means the start tool creates or resumes the canonical project, launches Studio with that exact project, and opts this MCP process into linked routing. `headless` means the complete Python Engine path and must ignore a separately opened Studio. A bridge descriptor alone is never consent to link. Studio has no manual link switch: a standalone launch remains a read-only projection waiting for Codex to start a link.

If an opted-in Studio link drops or switches projects, the current operation fails. It must never silently fall back to the direct Engine path. Frontend choice is presentation/session state and never enters theme, DNA, Prompt, revision, or package digests.

## Legacy package takeover

An attached APSAL ZIP or directory with `run.json` is a creator artifact, not a programming assignment. Import it before describing it. APSAL restores Prompts and references, discards provider execution assumptions, creates a private Codex Prompt/Skill package, and returns the next image Job. Never respond with “this JSON cannot be executed” or direct the creator to install an API runner. If SHA-256 recovery fails, name only the missing reference images and bind them after the creator reattaches them.

## What creators see

The creator sees natural language, compact text-only element and DNA cards, a five-stage semantic thumbnail strip, the nine-shot overview, and generation progress. YAML is the editable background source; canonical JSON is the immutable execution and lineage artifact. Do not expose either by default.

Reference analysis progress is an auditable execution timeline rather than a raw model transcript. Studio shows whether Codex is linked, which per-image or synthesis Job was claimed, Schema-validated result/failure writes, retries, and completion. It never exposes hidden chain-of-thought. A pending Job with no claim event means Codex has not started it; do not describe that state as slow or in progress.

Each DNA card is textual and must display its title, stable reference, core constraints, scope (`project`, `personal`, `extension`, or `official`), version, rights license, attribution, QA state, recommendation reason, matched tags and relevant scene facets. Do not render Registry thumbnails in the selection flow. Preview sidecars remain background assets for rights review, validation and Extension Pack exchange. In a client without MCP Apps, print the same choices as a numbered list and accept a number or natural-language revision.

The stage thumbnail strip is a different surface. It contains one localized 4:3 semantic summary for Direction, Worldbuilding, Narrative, Image and Delivery, showing confirmed/current/pending progress. It may appear above the element text cards, but it must not replace the complete proposal. Each thumbnail is accessible, deterministic, rights-clear, and explicitly marked `generation_input: false`. Never place it under `assets/references/` or send it to Codex image generation.

## Recommendation and memory

Recommend from the complete scene requirement, not from the DNA type alone. Ranking order is identity/rights/medium, scene intent, explicit dependency compatibility, photographic language, local creator memory, QA and Registry scope. Always explain why an asset matches; never present a hidden score as taste authority.

For new or revised DNA, show suggested controlled tags and facets before stage confirmation. The creator may edit them. Stable identity, version, dependencies, locks and rights remain authoritative; tags aid retrieval and never replace them.

After confirmation, ask whether project DNA should move to “My DNA.” Offer exactly:

1. Save to My DNA — copy the immutable version to the personal Registry.
2. Current project only — keep it under `<project>/.apsal/registry/`.
3. Decide later — leave the memory offer pending.

Do not ask for bundled official DNA, installed extension DNA, or a version already in the personal Registry. Record successful/failed/rejected usage as private scoring memory without storing the raw brief.

## Five layers expose all thirteen protocol roles

The UI groups decisions for human comprehension without inventing competing protocol types:

| Layer | Protocol roles | Registry DNA | Creator decision |
|---|---|---|---|
| Direction | Content + Emotion | none | proposition, mood, energy, tension and emotional arc |
| Worldbuilding | Subject + World + Look | character + environment | identity, space, time, wardrobe, grooming, props and ownership |
| Narrative | Event + Sequence | composition + shot | event, consequences, rhythm, nine functions and order |
| Image | Camera + Light + Style + Color/Post | style + lighting | viewpoint, lens, composition, light, palette and rendering |
| Delivery | Job + Quality Control | qa | output contract, rejection rules and evidence |

The seven DNA categories remain reusable Registry assets. The thirteen roles remain the machine protocol. The five layers are only the conversation order that ensures none of those roles is omitted.

Each element card shows a fully populated design proposal, rationale, adjustable directions, purpose, current values, source, observable effect, invariants and QA expectations. Do not render empty proposal areas or hide the useful recommendation in chat outside the card. A deliberately empty machine value such as no secondary mood or no prop yet must be presented as a meaningful recommendation explaining when it should be added.

Unless the brief explicitly requests another subject, the default Subject proposal is a poised, distinctive East Asian adult female protagonist with reliable camera presence and broad compatibility across classical, contemporary, editorial and ceremonial makeup, hair and wardrobe. Preserve facial geometry, facial features, adult age, natural skin identity and body proportions so styling versatility never becomes face substitution. The current set follows its confirmed set strategy: Chaptered Variation gives every Job a different makeup/hair/wardrobe design while preserving the face; Continuous Narrative locks one confirmed look unless an observable event explicitly motivates a change.

## Set organization strategy and controlled variation

Confirm one of two strategies in the Direction layer before Worldbuilding:

1. **Chaptered Variation** (default): three narrative chapters of three Jobs, but all nine Jobs use different scene designs, makeup, hair, wardrobe, action/body state, hand plan, gaze, face orientation, body orientation, expression, composition, focal length, perspective purpose and physically motivated lighting. Facial identity, adult age, body proportions and live-action medium remain coherent.
2. **Continuous Narrative**: one core scene, one confirmed look and one causally continuous event. Action/body state, hand plan, gaze, framing and focal perspective still vary by Job function, while scene, styling and event state remain strongly continuous.

The visible card labels are “章节式丰富变化” and “连续叙事” in Chinese. The internal controlled values are `chaptered_variation` and `continuous_narrative`. Card option buttons request a revision and must not silently confirm a layer.

For the nine-Job default, Chaptered Variation uses nine distinct focal lengths—24, 28, 35, 40, 50, 65, 85, 105 and 135 mm—with a different composition and observable perspective purpose for each. Every Prompt also freezes that Job's complete scene, pose/action, gaze/face direction, makeup/hair/wardrobe and lighting design. A model cannot be assumed to simulate a lens from a number alone, so the observable purpose is mandatory.

When an identity reference is bound, every Job uses the actual image only for the same adult facial identity. It must not inherit the reference pose, action, hands, gaze, face direction, expression, scene, composition, makeup, hair, wardrobe, lens, lighting or background. The finalized Skill ZIP must contain a sanitized copy under `assets/references/`, list it in `references/reference_manifest.json`, and map it to each applicable Job in `references/run_manifest.json`.

Changing the set strategy rebuilds World, Look, Event, Sequence, Camera and Quality Control proposals plus the per-Job scene/look/focal/body-state plan. Any confirmed downstream layer becomes pending again. Existing 0.7 sessions that do not contain a set strategy preserve their prior intent and are not silently migrated.

Direction must classify emotion with a controlled primary tone, optional secondary tones, undertone, valence, arousal, expression, energy and tension, plus a `start → turn → end` arc. If the brief combines positive and negative tones, keep both and propose mixed valence instead of silently discarding one. Chinese concepts such as 意境 or 气韵 may explain relationships, but do not replace observable behavior, light, color, space or sequence decisions.

For Chinese sessions, the creator-visible projection is Chinese-only. Do not expose the English machine role, layer, value-key, enum, status, source, scope, QA, tag, digest or asset-ID fields in the card. Use the localized display fields and localized text fallback; keep internal references available only for the actual tool call.

## State transitions

Use this order:

```text
brief
→ language auto-detected, or one concise choice if ambiguous
→ authoring_mode: automatic or guided
→ automatic: ready (five layers confirmed and packaged in one revision)
  or guided:
→ direction_pending
→ worldbuilding_pending
→ narrative_pending
→ image_pending
→ delivery_pending
→ review_pending
→ ready
→ generating
→ completed / partial
```

A creator may return to an earlier layer. Committing a changed upstream decision invalidates all confirmed downstream layers and compiled Prompts. Explain which layers and elements need confirmation again.

## Natural-language revision

Translate requests such as “人物更成熟，但保留短发” into a proposed DNA revision. Explain the one intended variable and the locks that remain. Save drafts automatically to the project. Confirmation promotes the draft to project DNA; copy it to personal DNA only after an explicit “保存到我的 DNA”. Never edit a formal ID/version in place.

At Narrative, first explain the sequence arc, then show nine Scene summaries. Every frame needs a unique narrative function, observable action, motivated gaze, hand plan, weight/body state, 9:16-safe composition, chapter or continuous-event lock, focal perspective and output filename. Default is one Job and one requested 2160×3840 PNG.

## Reference binding

Do not accept “use this image” as an untyped instruction. For every supplied image, confirm:

- stable reference ID and applicable Jobs;
- one or more allowed roles: style, world, prop, wardrobe, composition, or identity;
- forbidden uses such as copying a face, body, pose, exact composition, text, signature, or watermark;
- copyright, portrait consent, attribution, and redistribution status.

The image is stored in the private Vault by SHA-256. Theme DNA stores only purpose, restrictions, rights metadata, and the Vault URI needed by the local engine. Replacing bytes creates a new content digest and requires a new theme version. A prose analysis can supplement a reference but cannot replace the actual image sent to the provider.

When at least one real reference is bound, designate exactly one core visual anchor. Prefer an explicit creator choice; otherwise prefer identity, then an all-shot reference, then the first bound reference. “Core” means easiest package entry point, not permission expansion: uses, forbidden uses and applicable Jobs still control every call. With no real reference, record `not_bound` and continue without inventing one.

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

Finalization always creates and displays a reproducible Codex Prompt/Skill ZIP plus SHA-256. It contains a language index plus complete English and Chinese guides, three Prompt files per Job, reference media allowed for local use, a core-anchor declaration, ten localized stage preview assets, rights metadata, QA and checksums. Private references force `private_only`; public export fails unless redistribution rights are explicit.

After the package is ready, offer exactly:

1. Use Codex now — require one explicit confirmation, prepare the run and generate SHOT_01 with Codex's built-in image generation.
2. Deliver the Prompt/Skill package only — make no image-generation call.

Do not call an image API or request `OPENAI_API_KEY`. Generate one Job per Codex turn. After the image tool emits one image, stop; “继续” begins the next Job in the same resumable run. Bound local references are passed as real paths. When there are no bound paths, the immediately previous accepted image may serve as a recent identity-only anchor. Never combine mutually exclusive reference mechanisms. Requested 9:16, high quality and 2160×3840 are creative delivery targets; actual model, format and dimensions are `not_reported` unless Codex explicitly returns them.

Keep model visual QA and human visual QA separate. Prompt validation never proves that the result is a real human photograph.

## DNA Extension Packs

Use an Extension Pack to share reusable DNA independently from a theme Skill. A public pack contains `apsal-dna-pack.json`, canonical DNA, preview sidecars, license/attribution, README and a deterministic checksum ledger. It contains no private Vault media. Any unresolved license, attribution, tag confirmation or dependency forces a private pack or blocks public export.
