# APSAL Open Protocol 0.2

The protocol, reference engine, and content licenses are separate layers. A public modular package contains eleven module roles (`subject`, `world`, `style`, `look`, `emotion`, `event`, `camera`, `light`, `color_post`, `quality_control`, `content`), one sequence, and one or more single-image jobs.

Every package and module declares stable identity, semantic version, parent, changed fields, rights, content license, dependencies, QA state, and SHA-256 integrity. Provider parameters and private references are outside the canonical core. Run `apsal.py validate-package <directory>` before importing or publishing any package.
