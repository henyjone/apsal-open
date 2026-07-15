# APSAL Open Protocol 0.3

The protocol, reference engine, and content licenses are separate layers. A public modular package contains eleven module roles (`subject`, `world`, `style`, `look`, `emotion`, `event`, `camera`, `light`, `color_post`, `quality_control`, `content`), one sequence, and one or more single-image jobs.

Every package and module declares stable identity, semantic version, parent, changed fields, rights, content license, dependencies, QA state, and SHA-256 integrity. Provider parameters and private references are outside the canonical core. Run `apsal.py validate-package <directory>` before importing or publishing any package.

Protocol 0.3 preserves 0.2 JSON and adds Semantic Contract authoring. Creators edit safe `.apsal.yaml`; the engine normalizes `.apsal.json`, explains field intent, and compiles separate `design`, `image`, and `qa` targets. Run `apsal.py check-sync <directory>` before publishing YAML/JSON pairs.
