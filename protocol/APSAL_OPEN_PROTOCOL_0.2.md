# APSAL Open Protocol 0.2

License: Apache-2.0. Historical stable specification preserved for compatibility.

APSAL Open Protocol 0.2 is a vendor-neutral JSON format for portable, versioned photography-generation packages. It separates protocol, reference engine and explicitly licensed content.

Its thirteen roles are eleven modules—`subject`, `world`, `style`, `look`, `emotion`, `event`, `camera`, `light`, `color_post`, `quality_control`, `content`—plus `sequence` and one or more single-image `job` files.

Every public package declares stable IDs, semantic versions, parent lineage, changed fields, dependencies, rights, QA state, output rules and SHA-256 checksums. Identity locks outrank prose fluency; provider parameters stay outside the canonical core; inherited negative rules cannot disappear silently; each Job compiles to one independent image.

Protocol 0.3 extends this contract without invalidating conforming 0.2 JSON packages. See the repository history at tag `v0.2.0` for the complete original release state.

