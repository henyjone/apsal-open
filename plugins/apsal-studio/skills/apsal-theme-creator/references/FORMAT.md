# Theme format

A theme references exact DNA assets using `namespace`, `id`, `type`, and `version`. The engine verifies the content digest through its bundled catalog, compiles layers in category order, and appends the shot-specific instruction.

Every shot requires a unique ID, title, framing, action, hands, gaze, composition, continuity state, and output filename. The default count is nine, but any count from 1 through 24 is supported.

Studio 0.7 stores a creator-confirmed `element_decisions` object containing exactly the thirteen protocol roles. It records the five-layer conversation position, intent, structured values, observable image effects, invariants, QA expectations, source, DNA references and confirmation state. The five layers are authoring UX; they do not change Protocol or Semantic Contract 0.3.

Studio 0.8 packages every Job as `.prompt.txt`, `.negative.txt` and `.full.txt` inside a deterministic Codex Prompt/Skill ZIP. `PROMPT_GUIDE.md` is the creator-facing entry point. `references/manifest.json` must declare `generation_surface: codex_imagegen`, `direct_api_calls: false`, `api_key_required: false` and `returned_dimensions_guaranteed: false`.

Protocol 0.3 authoring uses safe `.apsal.yaml`. Each meaningful element has a Semantic Contract: bilingual purpose, affected paths, non-target locks, allowed variation, observable expected effects, evidence-based QA expectations, controlled tags, and priority. Each creative shot field also explains its instance-level purpose, affected paths, expected effect, and QA check.

Use `normalize` to create canonical `.apsal.json`; hashes and packages use JSON values, never YAML comments. `design`, `image`, and `qa` compilation targets have separate audiences and must not be collapsed into one oversized provider prompt.

Modular protocol packages use eleven module roles (`subject`, `world`, `style`, `look`, `emotion`, `event`, `camera`, `light`, `color_post`, `quality_control`, `content`), one `sequence`, and one or more single-image `job` files. See the bundled package and module schemas.
