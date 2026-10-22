# APSAL Documentation

APSAL documentation is organized by what you want to do. Creators can stay entirely in natural-language conversation; JSON and YAML are background assets unless developer mode is explicitly requested.

## Start here

| Goal | English | 中文 |
|---|---|---|
| Install and use APSAL Studio from first idea to nine images | [Complete usage guide](USAGE_GUIDE.md) | [完整使用手册](USAGE_GUIDE.zh-CN.md) |
| Understand APSAL Elemental Photography | [Methodology monograph](monograph/README.md) | [《构建可见世界》](monograph/README.md) |
| Build against the machine contract | [APSAL Open Protocol](../protocol/APSAL_OPEN_PROTOCOL.md) | [APSAL 开放协议](../protocol/APSAL_OPEN_PROTOCOL.md) |
| See what changed in the current plugin | [APSAL Creative Library 0.16.0](releases/0.16.0.md) | [APSAL 创作项目库 0.16.0](releases/0.16.0.md) |
| Upgrade Codex and Studio to the creative-library architecture | [0.16.0 upgrade guide](UPGRADE_GUIDE_0.16.0.md) | [0.16.0 中文升级指南](UPGRADE_GUIDE_0.16.0.zh-CN.md) |
| Build the Studio 0.3.0 project library and Codex frontend | [Desktop frontend](../apps/apsal-studio/README.md) | [桌面项目库](../apps/apsal-studio/README.md) |
| Contribute original DNA or protocol work | [Contribution guide](../CONTRIBUTING.md) | [贡献指南](../CONTRIBUTING.md) |

## Creator paths

- **Create from references:** 1–24 rights-scoped images → per-image and set analysis → five layers and thirteen roles → Prompt/Skill package → child-project generation → confirmed sharing.
- **Create a new theme:** one natural-language idea → Chaptered Variation or Continuous Narrative → five creator layers → thirteen confirmed elements → nine-shot review → Prompt/Skill package → one Codex-generated image per turn.
- **Open an old APSAL ZIP:** attach the ZIP → automatic Prompt and reference recovery → private Codex Skill package → first image ready. No JSON repair or image API runner is required.
- **Reuse DNA:** accept a scene-matched recommendation, revise it, keep it in the project, or explicitly save it to My DNA for future recommendations.
- **Share DNA:** export rights-cleared reusable DNA as an independent Extension Pack without publishing private themes or reference media.

## Specification index

- [Semantic Contract](../protocol/RFC-0001-SEMANTIC-CONTRACT.md)
- [Local Registry and conversational authoring](../protocol/RFC-0002-LOCAL-REGISTRY-AND-CONVERSATIONAL-AUTHORING.md)
- [Reference binding and live-action photography](../protocol/RFC-0003-REFERENCE-BINDING-LIVE-ACTION-AND-NATIVE-4K.md)
- [DNA recommendation, memory and exchange](../protocol/RFC-0004-DNA-RECOMMENDATION-MEMORY-AND-EXCHANGE.md)
- [Five-layer, thirteen-element authoring](../protocol/RFC-0005-FIVE-LAYER-THIRTEEN-ELEMENT-AUTHORING.md)
- [Codex-native generation and Prompt delivery](../protocol/RFC-0006-CODEX-NATIVE-GENERATION-AND-PROMPT-DELIVERY.md)
- [Legacy run takeover](../protocol/RFC-0007-LEGACY-RUN-TAKEOVER.md)
- [Bilingual creator interaction](../protocol/RFC-0008-BILINGUAL-INTERACTION.md)
- [Controlled variation and set strategy](../protocol/RFC-0009-CONTROLLED-VARIATION-SET-STRATEGY.md) — the 0.13 three-scene table stays in that RFC; [Engine 0.16 uses one scene and one look per Job](../protocol/RFC-0009-CONTROLLED-VARIATION-SET-STRATEGY.md#engine-016-per-job-scene-and-look)
- [Visual anchor and stage previews](../protocol/RFC-0010-VISUAL-ANCHOR-AND-STAGE-PREVIEWS.md)
- [Single project kernel and Codex/Studio dual entry](../protocol/RFC-0011-SINGLE-PROJECT-DUAL-ENTRY.md)
- [Creative project library, reference analysis and confirmed sharing](../protocol/RFC-0012-CREATIVE-PROJECT-LIBRARY-ANALYSIS-AND-SHARING.md)

Historical upgrade and release documents remain immutable records. Start with the 0.16 guides above for current installation instructions. `docs/releases/` and older upgrade guides describe the release they name; they are not rewritten when later behavior changes. RFC-0009 keeps its 0.13 three-scene / chapter-locked-look table. The current scene and look count is that RFC's [Engine 0.16 status note](../protocol/RFC-0009-CONTROLLED-VARIATION-SET-STRATEGY.md#engine-016-per-job-scene-and-look): one scene and one look per Job.

## Repository layout

| Path | Role |
|---|---|
| `protocol/` | Normative Open Protocol and RFCs. When an RFC keeps an older table, its status note is the current rule. |
| `plugins/apsal-studio/` | Codex plugin: dependency-free engine, MCP, schemas, DNA, Skill |
| `apps/apsal-studio/` | Electron desktop library at its own `0.3.0` version |
| `manifest/CURRENT_VERSION_MAP.json` | Version matrix checked by `scripts/check_docs.py` |
| `examples/quiet-window/` | Committed semantic-contract pilot |
| `scripts/` | Validators, example checks, and `release.py` |
| `dist/` | Generated plugin ZIP. Not part of the source tree |

`scripts/release.py` builds `dist/apsal-studio-codex-plugin-<tag>.zip` during CI and the release workflow uploads it. Do not commit that ZIP. The desktop app copies the plugin engine into the ignored `apps/apsal-studio/.build/` directory at build time.

Static validation proves structure, lineage and reproducibility. Generated photographs still require Codex visual review and a separate human visual-QA decision.
