# Theme format

A theme references exact DNA assets using `namespace`, `id`, `type`, and `version`. The engine verifies the content digest through its bundled catalog, compiles layers in category order, and appends the shot-specific instruction.

Every shot requires a unique ID, title, framing, action, hands, gaze, composition, continuity state, and output filename. The default count is nine, but any count from 1 through 24 is supported.

Modular protocol packages use eleven module roles (`subject`, `world`, `style`, `look`, `emotion`, `event`, `camera`, `light`, `color_post`, `quality_control`, `content`), one `sequence`, and one or more single-image `job` files. See the bundled package and module schemas.
