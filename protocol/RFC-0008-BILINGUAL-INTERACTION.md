# RFC-0008 — Bilingual Creator Interaction

Status: Implemented in 0.10.0; strict Chinese presentation added in 0.11.0
Protocol compatibility: APSAL Open 0.3.0  
Interface languages: `zh-CN`, `en`

## Abstract

APSAL Studio supports complete Chinese and English creator interaction without forking the protocol, DNA Registry or photographic generation assets. The current Codex conversation or creator message determines presentation language when it is clear. A language choice is requested only when the first usable input is genuinely ambiguous. The choice persists in the local resumable session and may be changed at any time without altering generation intent.

## Why this is an interface contract

Language preference belongs to the creator experience, not the photographic world. Subject identity, world physics, event sequence, camera, light, color, rights and QA remain the same regardless of whether they are discussed in Chinese or English. Therefore language state must not enter the canonical theme or any Prompt digest.

APSAL does not assume that every Codex host exposes a stable account, operating-system or application locale to a local MCP service. The Skill supplies the current conversation language when clear; the engine can also detect the new brief deterministically.

## Resolution order

1. Explicit creator request: `use English`, `切换到中文`, or the equivalent.
2. Language explicitly supplied by the APSAL Skill from the current Codex conversation.
3. Deterministic Chinese/English detection from the new design brief.
4. If still ambiguous, ask exactly one concise question: `English or 中文?`

A clear input must not be interrupted by a language chooser. An ambiguous choice must be resolved before element or DNA cards are confirmed.

## Session representation

```json
{
  "language": {
    "code": "en",
    "status": "confirmed",
    "source": "message_detected",
    "supported": ["zh-CN", "en"]
  }
}
```

For ambiguous input, `code` is `null`, `status` is `pending`, and the MCP start result sets `language_confirmation_required: true`. `set_session_language` confirms or switches the value. Existing 0.7 sessions without this optional object remain readable and use a deterministic legacy fallback.

## Localized surfaces

- Codex conversation and explanations;
- element-card layer titles, role titles, questions, controls and text fallback;
- DNA-card labels, controls, empty state and selection message;
- starter prompts, README and complete usage guide;
- exported Prompt/Skill instructions.

Each card displays one active language. Machine fields such as `content`, `camera`, `namespace`, IDs, semantic tags and digests remain stable and are not translated into competing identifiers.

Beginning with Studio 0.11.0, a Chinese card must render only creator-facing localized fields. Raw machine role names, layer IDs, field keys, statuses, sources, Registry scopes, QA states, semantic tags, digests and asset IDs remain available in structured tool output but are not visible in the card or Chinese text fallback. The localization projection does not enter canonical theme or DNA digests.

## Packaged guides

Every new or migrated Prompt/Skill package contains:

```text
PROMPT_GUIDE.md          language index
PROMPT_GUIDE.en.md       complete English workflow
PROMPT_GUIDE.zh-CN.md    complete Chinese workflow
```

Frozen provider-neutral image Prompts remain identical in both workflows. The selected interface language does not create a new theme version or a different package intent.

## Privacy

Language detection reads the current creator message or brief only. The selected value is stored in the local session under the project `.apsal/` directory. APSAL Studio does not read or transmit an operating-system locale, Codex account preference or remote profile.

## Conformance

An implementation conforms when:

- clear Chinese and English briefs start in the matching language without a chooser;
- ambiguous input cannot proceed until one of the two supported languages is confirmed;
- resume preserves the selected language;
- an explicit switch updates all subsequent creator-facing presentation;
- switching does not alter theme digest, compiled Prompt digest, DNA references or confirmed layer status;
- exported new-theme and imported-legacy packages include both complete guides;
- old sessions, themes, runs and Skills remain readable.
