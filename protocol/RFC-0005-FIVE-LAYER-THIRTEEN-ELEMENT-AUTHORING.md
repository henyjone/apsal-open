# RFC-0005: Five-Layer, Thirteen-Element Conversational Authoring

Status: Implemented in APSAL Studio and reference engine 0.7.0

Protocol compatibility: APSAL Open Protocol 0.3.0

Semantic Contract compatibility: 0.3.0

License: Apache-2.0

## Abstract

APSAL Studio originally reduced the creator experience to four understandable choices: Character, World, Scene and Photo DNA. That made structured authoring approachable, but it hid important protocol decisions. Mood, props, lighting, color, post-processing, output policy and QA could appear to be implementation details instead of authored parts of the photographic world.

This RFC introduces a five-layer conversation that exposes all thirteen existing APSAL protocol roles without asking creators to edit JSON or YAML and without inventing thirteen competing DNA libraries.

```text
Natural-language brief
→ Direction: Content + Emotion
→ Worldbuilding: Subject + World + Look
→ Narrative: Event + Sequence
→ Image: Camera + Light + Style + Color/Post
→ Delivery: Job + Quality Control
→ Nine-shot review → Prompt / generation / Skill
```

The five layers are an interaction order. The thirteen roles remain the protocol. The seven DNA types remain reusable Registry assets.

## Why four DNA groups were insufficient

The previous interface correctly exposed reusable assets but conflated three different things:

1. **DNA** is reusable visual knowledge.
2. **Protocol roles** describe everything a reproducible photographic world must decide.
3. **Conversation layers** determine when a creator can understand and confirm those decisions.

Character, World, Scene and Photo were useful entry points, but they did not prove that every required role had been considered. A theme could appear confirmed while its emotional direction, prop ownership, light motivation, color relationships, post-processing boundary or rejection criteria remained merely implicit.

Studio 0.7 therefore makes completeness visible. Finalization fails until every one of the thirteen roles has a confirmed decision with provenance and QA expectations.

## The five creator layers

| Layer | Existing protocol roles | Registry DNA selected in the layer | Questions answered |
|---|---|---|---|
| Direction | `content`, `emotion` | none | What is the work about? What should it feel like, and how does that feeling evolve? |
| Worldbuilding | `subject`, `world`, `look` | `character`, `environment` | Who exists? Where and when? What do they wear, hold and own? |
| Narrative | `event`, `sequence` | `composition`, `shot` | What changes? What consequences persist? Why do nine views exist in this order? |
| Image | `camera`, `light`, `style`, `color_post` | `style`, `lighting` | Where is the camera? How is the world lit, rendered and chromatically organized? |
| Delivery | `job`, `quality_control` | `qa` | What is generated, one Job at a time, and what evidence accepts or rejects it? |

Every protocol role appears exactly once. Every Registry DNA type appears exactly once. A role may inherit DNA selected in an earlier layer; a confirmed decision is not required to have a one-to-one DNA asset.

## Element decision contract

Every theme created through this flow stores exactly thirteen element decisions:

```yaml
element_decisions:
  light:
    role: light
    layer: image
    status: confirmed
    source: creator_confirmed
    intent: Make time, material and emotion visible through motivated light.
    values:
      source: east-facing window
      direction: camera-left to camera-right
      quality: soft directional daylight
      contrast: restrained
      time_phase: continuous late morning
      continuity: direction, shadow and exposure remain traceable
    observable:
      - Shadow direction and falloff agree with the declared window.
    must_preserve:
      - natural skin tone
      - world geometry
    qa_expectations:
      - No contradictory shadow or unmotivated light change appears.
    basis:
      - natural_language_brief
      - creator_confirmation
    dna_refs: []
```

Required fields are:

- `role` and `layer` for unambiguous placement;
- `status` and `source` for proposal/confirmation provenance;
- `intent` for why the decision exists in this theme;
- structured `values` for the actual decision;
- `observable` for image-language compilation;
- `must_preserve` for non-target locks;
- `qa_expectations` for evidence-oriented review;
- `basis` and exact `dna_refs` for lineage.

The image compiler uses observable language rather than dumping schemas or abstract explanations into the provider Prompt. The QA compiler turns every role's expectations into checks. The design compiler retains the full reasoning context.

## Emotion is a designed system, not a label

The Direction layer cannot stop at “happy,” “sad,” or “cinematic.” It uses a controlled but editable structure:

- primary tone: quiet joy, tenderness, serenity, hope, nostalgia, melancholy, sorrow, tension, mystery, solemnity or contemplation;
- zero or more secondary tones when the brief deliberately combines feelings; opposite valences make the proposal mixed rather than silently discarding one side;
- undertone: anticipation, intimacy, relief, longing, hesitation, loneliness, loss, unease, awe or none;
- valence: positive, negative, mixed or neutral;
- arousal: low, medium or high;
- expression: restrained, clear or intense;
- energy: still, slow, flowing or urgent;
- tension: stable, suspended, rising or released;
- arc: `start → turn → end`.

These values organize reasoning and retrieval. They must still be translated into observable gaze, breath, gesture, distance, light, rhythm and consequence. Chinese aesthetic concepts such as 意境、气韵 and 虚实 may explain the relationship between feeling and world, but they are not reduced to mechanical sliders.

## Props, lighting, color and post-processing

Studio 0.7 makes previously implicit decisions explicit:

- Look records wardrobe, grooming, props and ownership. A prop must have a stable owner, location and state; change requires an event.
- Light records source, direction, quality, contrast, time phase and continuity.
- Color/Post records palette, temperature, saturation, contrast curve, grain, sharpness, dynamic range and a natural, stable skin-tone policy.
- Quality Control records required checks, rejection conditions and the separation between model visual QA and human visual QA.

Style cannot silently override identity, physics, event, light or skin. Color/Post is a relation among skin, wardrobe, props, space, time and emotion—not a global decorative filter.

## State and invalidation

New sessions use:

```text
direction_pending
→ worldbuilding_pending
→ narrative_pending
→ image_pending
→ delivery_pending
→ review_pending
→ ready
→ generating
→ completed / partial
```

Layers are confirmed in order. Changing an upstream layer invalidates every confirmed downstream layer and all compiled Prompts. The creator must reconfirm affected decisions. Existing Studio 0.4–0.6 four-stage sessions remain readable and use the legacy state path; they are not falsely upgraded to thirteen confirmed decisions.

## Text-only interaction

Both DNA and element choices use text cards. Element cards display the role, question, source, intent, structured values, observable result, invariants and QA expectation. A creator may approve the layer or revise one element in natural language. Clients without MCP Apps receive the same content as a numbered text fallback.

Preview sidecars remain in the Registry for rights review, Extension Pack validation and exchange, but they are not displayed as decorative selection images.

## Studio 0.12 proposal-complete cards

Beginning with Studio 0.12, every element card must contain the actual design proposal, its rationale, adjustable directions, concrete values, expected effects, invariants and acceptance criteria. Useful recommendations cannot live only in surrounding chat, and a deliberately unset machine value must be explained rather than rendered as an empty area. The numbered-text fallback must carry the same content.

New sessions use a poised, distinctive East Asian adult female protagonist as the default when the creator has not specified another subject. The default supports classical, contemporary, editorial and ceremonial makeup, hair and wardrobe. Styling variables remain separate from immutable identity: facial geometry, adult age, natural skin, hair color/hairline and body proportions stay locked. Within one set, the confirmed styling state remains continuous unless an observable event explicitly changes it. Explicit creator subject requirements override the default.

## Compatibility and versioning

- APSAL Open Protocol remains 0.3.0.
- Semantic Contract remains 0.3.0.
- Studio and reference engine become 0.7.0.
- The official seven-category catalog and existing theme generation intent remain unchanged.
- New themes include `interaction_model: five_layer_thirteen_element` and `element_decisions`.
- Legacy JSON, YAML, Skills, Registry assets, runs and four-stage sessions remain readable.

## Acceptance criteria

An implementation conforms to this RFC when:

1. five layers cover exactly thirteen protocol roles with no duplicate or missing role;
2. their Registry selections cover the seven DNA types with no duplicate or missing type;
3. finalization fails until all thirteen decisions are creator-confirmed;
4. emotion contains the controlled dimensions and a complete arc;
5. lighting, props, color/post and QA are visible creator decisions;
6. each image Prompt includes confirmed observable element instructions;
7. QA contains expectations originating from every protocol role;
8. changing an upstream layer invalidates affected downstream decisions and Prompts;
9. text-card and numbered-text interfaces expose equivalent information;
10. legacy assets remain readable without being misrepresented as Studio 0.7 confirmations.
