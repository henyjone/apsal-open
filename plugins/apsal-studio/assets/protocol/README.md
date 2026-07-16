# APSAL Open Protocol 0.3

The protocol, reference engine, and content licenses are separate layers. A public modular package contains eleven module roles (`subject`, `world`, `style`, `look`, `emotion`, `event`, `camera`, `light`, `color_post`, `quality_control`, `content`), one sequence, and one or more single-image jobs.

Every package and module declares stable identity, semantic version, parent, changed fields, rights, content license, dependencies, QA state, and SHA-256 integrity. Provider parameters and private references are outside the canonical core. Run `apsal.py validate-package <directory>` before importing or publishing any package.

Studio 0.6 adds a Registry exchange layer without changing Protocol 0.3. Discovery tags/facets aid explained recommendation but never replace IDs, dependencies or rights. Standalone DNA Extension Packs contain immutable canonical DNA plus preview sidecars and checksums; installed packs are read-only and cannot override official or existing ID/version pairs.

Studio 0.7 adds a five-layer authoring interaction without changing Protocol 0.3 or Semantic Contract 0.3. It exposes all thirteen roles as creator-confirmed text cards, while the existing seven Registry DNA categories remain the reusable asset layer.

Studio 0.8 removes direct image-provider execution from the Codex plugin. Finalization creates a complete Codex Prompt/Skill ZIP with one positive, negative and full Prompt per Job, bundled permitted references, checksums and a usage guide. Codex then generates one image per turn through its built-in image-generation capability. Requested delivery dimensions are not treated as guaranteed returned dimensions.

Studio 0.9 safely takes over legacy run directories and ZIPs. Historical API/model fields remain non-executable lineage only. The importer restores Prompts, locates omitted references by SHA-256 in the package or private Vault, asks only for truly missing media, and creates a private Codex Prompt/Skill package ready for one-image-per-turn generation.

Protocol 0.3 preserves 0.2 JSON and adds Semantic Contract authoring. Creators edit safe `.apsal.yaml`; the engine normalizes `.apsal.json`, explains field intent, and compiles separate `design`, `image`, and `qa` targets. Run `apsal.py check-sync <directory>` before publishing YAML/JSON pairs.
