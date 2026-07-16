# APSAL Studio bilingual interaction policy

APSAL Studio supports `zh-CN` and `en` as complete creator-facing interface languages.

## Resolution order

1. An explicit creator request such as “use English” or “切换到中文”.
2. The language passed by the APSAL Skill from the current Codex conversation or user message.
3. Deterministic detection from the new design brief.
4. A one-time bilingual question only when the result remains ambiguous.

Do not claim to read a Codex-wide locale or operating-system preference. Local MCP clients do not guarantee that such a field is available. Do not show a mandatory language chooser when the current language is already clear.

## Exact ambiguous-language prompt

Use only:

> English or 中文?

After the answer, call `set_session_language` with `en` or `zh-CN`. Do not restart the session.

## What language changes

- conversation and explanations;
- element and DNA card titles, questions, labels, buttons, and text fallback;
- quick-start and packaged usage guides shown to the creator.

In a Chinese session, card rendering must read `role_label`, `status_label`, `source_label`, `display_intent`, `display_values`, `display_observable`, `display_must_preserve`, localized DNA labels and localized recommendation reasons. Raw machine fields remain in structured tool output for execution but must not appear in the visible Chinese card or its text fallback.

## What language cannot change

- stable namespace, DNA ID, type, version, content digest, dependencies, or rights;
- theme generation intent, element decisions, shot order, or continuity;
- canonical YAML/JSON data model;
- provider-neutral image Prompt content and Prompt digests;
- Skill reproducibility and validation results.

Provider-neutral image Prompts remain English because the language switch is a presentation preference, not a new theme version. The package contains complete guides in both languages so it remains portable after sharing.
