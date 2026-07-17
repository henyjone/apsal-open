# RFC 0009 — Controlled Variation and Set Strategy

Status: implemented in APSAL Studio / Engine 0.13.0

Protocol compatibility: APSAL Open Protocol 0.3.0

Semantic Contract compatibility: 0.3.0

## Abstract

An AI photography set needs both variation and continuity. “Keep everything consistent” produces repetitive scenes, styling, poses and optics; “make every image different” produces nine unrelated pictures. APSAL therefore declares a set organization strategy before World, Look, Event, Sequence and Camera decisions are finalized.

Studio exposes two creator-facing choices:

- **Chaptered Variation / 章节式丰富变化** — the default for new nine-image sessions;
- **Continuous Narrative / 连续叙事** — selected explicitly or inferred from an explicit same-scene/same-look request.

This RFC does not introduce a new DNA type or a fourteenth protocol role. It coordinates values already owned by Content, World, Look, Event, Sequence, Camera and Quality Control.

## Chaptered Variation

The default nine-image plan contains three chapters of three Jobs:

| Chapter | World and Look | Shot functions |
|---|---|---|
| One | first related sub-scene + first coordinated look | environment, full-action, natural medium |
| Two | second related sub-scene + second coordinated look | transition, interaction, emotional close |
| Three | final related sub-scene + final coordinated look | changed relation, material detail, resolution |

The three scenes must be visibly different but inferably part of one world. The three looks must be visibly different but remain the same person. One look is locked inside each chapter; a change is legal only at a declared chapter boundary.

Each Job receives one action-led body state. Hands, gaze, weight and consequence are declared before pose. The default camera plan uses functional environmental-wide, full-action, natural-medium, emotional-close and hand/prop-detail perspectives. Nominal focal lengths are stored for photographic intent, but compiled Prompts also state the observable perspective purpose.

The following remain invariant across chapters:

- stable adult identity and reference rights;
- live-action photographic medium;
- world physics and material grammar;
- photographic rhetoric and color system;
- one Job, one independent image.

## Continuous Narrative

Continuous Narrative keeps one core scene, one confirmed look and one causally continuous event. It still requires distinct actions, body states, gaze, hand plans, framing and functional focal perspectives. Continuity is stricter: geometry, object state, wardrobe, grooming, light phase and event consequences must be traceable from one Job to the next.

## Role ownership

| Protocol role | Strategy responsibility |
|---|---|
| Content | stores the controlled `set_strategy` choice |
| World | declares scene strategy, count, chapters and shared world rules |
| Look | declares styling strategy, look count, chapter locks and transition rule |
| Event | declares nine action-led body states and consequences |
| Sequence | declares chapter/event plan, variation axes and continuity axes |
| Camera | declares focal plan plus observable perspective purpose per Job |
| Quality Control | verifies variation and continuity as separate evidence groups |

The seven Registry DNA categories remain Character, Style, Environment, Lighting, Composition, Shot and QA. DNA may support the selected strategy, but the strategy itself is a theme-level orchestration decision.

## Authoring and invalidation

The Direction layer presents both choices as selectable text buttons. A click requests a revision; it does not silently confirm the layer. Changing the strategy rebuilds all downstream proposals and per-Job plans, then invalidates confirmed Worldbuilding, Narrative, Image and Delivery layers.

New Studio 0.13 sessions store the strategy in the local session and theme artifact. Older session-schema 0.7 artifacts without the field retain their existing generation intent. They remain valid and are not assigned a new default during load or confirmation.

## Compilation

The design target retains the full strategy, chapter, scene/look, action, focal and QA structure. The image target places the confirmed set strategy in the Prompt and adds Job-specific optics, perspective purpose, body state and chapter lock. The QA target generates:

- variation checks for scenes, looks, action/body states and shot functions;
- continuity checks for identity, medium, world physics, color and any scene/look locks;
- per-Job checks that the declared focal perspective and body state are visible.

Static validation proves only that the contract is complete and internally consistent. Generated-image quality, identity, hands, optics and continuity still require model visual review and separate human visual QA.

## Compatibility and versioning

This is an additive Studio/Engine MINOR release. Protocol and Semantic Contract remain 0.3.0, session schema remains 0.7.0, official DNA content and versions remain unchanged, and frozen themes are never rewritten. A creator who changes a frozen theme's set strategy must create a new semantic theme version because the change affects scene, styling, event and camera generation intent.
