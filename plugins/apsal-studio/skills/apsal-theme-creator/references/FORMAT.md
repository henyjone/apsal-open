# Theme format

A theme references exact DNA assets using `namespace`, `id`, `type`, and `version`. The engine verifies the content digest through its bundled catalog, compiles layers in category order, and appends the shot-specific instruction.

Every shot requires a unique ID, title, framing, action, hands, gaze, composition, continuity state, and output filename. The default count is nine, but any count from 1 through 24 is supported.

Protocol 0.3 authoring uses safe `.apsal.yaml`. Each meaningful element has a Semantic Contract: bilingual purpose, affected paths, non-target locks, allowed variation, observable expected effects, evidence-based QA expectations, controlled tags, and priority. Each creative shot field also explains its instance-level purpose, affected paths, expected effect, and QA check.

Use `normalize` to create canonical `.apsal.json`; hashes and packages use JSON values, never YAML comments. `design`, `image`, and `qa` compilation targets have separate audiences and must not be collapsed into one oversized provider prompt.

Modular protocol packages use eleven module roles (`subject`, `world`, `style`, `look`, `emotion`, `event`, `camera`, `light`, `color_post`, `quality_control`, `content`), one `sequence`, and one or more single-image `job` files. See the bundled package and module schemas.
