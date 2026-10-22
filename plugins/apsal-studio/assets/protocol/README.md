# APSAL Open Protocol (plugin note)

This file ships inside the Codex plugin as a pointer. The normative text is
the repository's [APSAL Open Protocol](../../../../protocol/APSAL_OPEN_PROTOCOL.md).
`manifest/CURRENT_VERSION_MAP.json` is the version matrix for a checkout.

Current public versions:

- Open Protocol `0.4.0` (Apache-2.0). It keeps Protocol 0.3 semantic themes and Protocol 0.2 JSON packages readable.
- Project protocol, reference engine, and this Codex plugin: `0.16.0`.
- Semantic Contract: `0.3.0`.
- APSAL Studio Desktop is a separate package at `0.3.0`. It is not a second protocol.

Creators edit safe `.apsal.yaml`. The engine normalizes canonical `.apsal.json`, explains field intent, and compiles separate `design`, `image`, and `qa` targets. Run `apsal.py check-sync <directory>` before publishing a YAML/JSON pair, and `apsal.py validate-package <directory>` before publishing a modular package.

Protocol 0.4 project packages, reference-analysis summaries, parent/child lineage, and confirmed share records live under a project's `.apsal/` directory. The local library is a rebuildable projection and is not part of the portable theme digest.
