# APSAL Open Protocol (plugin note)

This note is packed inside the Codex plugin ZIP, which does not include the
rest of the repository. The summary below is enough to use the plugin. The
normative protocol text is
[APSAL Open Protocol 0.4](https://github.com/henyjone/apsal-open/blob/trunk/protocol/APSAL_OPEN_PROTOCOL.md).

Current public versions:

- Open Protocol: `0.4.0` (Apache-2.0). It keeps Protocol 0.3 semantic themes and Protocol 0.2 JSON packages readable.
- Reference engine and Codex plugin: `0.16.0`.
- Semantic Contract: `0.3.0`.
- APSAL Studio Desktop: `0.3.0`. Desktop is a separate package, not a second protocol.

Creators edit safe `.apsal.yaml`. The engine normalizes canonical `.apsal.json`, explains field intent, and compiles separate `design`, `image`, and `qa` targets. Run `apsal.py check-sync <directory>` before publishing a YAML/JSON pair, and `apsal.py validate-package <directory>` before publishing a modular package.

Protocol 0.4 project packages, reference-analysis summaries, parent/child lineage, and confirmed share records live under a project's `.apsal/` directory. The local library is a rebuildable projection and is not part of the portable theme digest. A nine-image Chaptered Variation set uses three narrative chapters and one distinct scene plus one distinct look per Job.
