# APSAL Bilingual Semantic Terms / APSAL 双语语义术语

> Generated from the normative semantic registry. Interpretive aesthetic relations explain method; they are not machine parameters.

## Thirteen roles / 十三类角色

| ID | English | 中文 | Core question | 核心问题 | 中国视觉思想关联 |
|---|---|---|---|---|---|
| `subject` | Subject | 主体 | Who exists, and what makes the identity remain the same? | 谁存在于世界中，什么使其保持同一身份？ | 与传神、气韵形成思想关联；机器约束仍以明确身份字段为准。 |
| `world` | World | 世界 | What reality contains the subject and which rules persist? | 人物处于怎样的现实，哪些规则持续生效？ | 关联意境、卧游以及可行、可望、可游、可居。 |
| `style` | Style | 风格 | Which observable visual decisions remain coherent across images? | 哪些可观察的视觉决定需要跨镜头保持一致？ | 关联骨法与气韵，但不以艺术家姓名替代视觉属性。 |
| `look` | Look | 造型 | How do wardrobe, grooming and props belong to subject and world? | 服装、妆发和道具如何属于人物与世界？ | 关联应物与随类，造型服从人物、事件和世界。 |
| `emotion` | Emotion | 情绪 | How does inner state become observable without becoming a label? | 内在状态如何成为可见行为，而不只是抽象标签？ | 关联情景交融与气韵，通过动作和关系呈现。 |
| `event` | Event | 事件 | What changes the world state and leaves a consequence? | 什么改变了世界状态，并留下可延续的结果？ | 关联生动与势，强调事件先于姿势。 |
| `camera` | Camera | 相机 | Who looks, from where, and why is this viewpoint necessary now? | 谁从哪里观看，为什么此刻需要这一视点？ | 关联三远与游观；一 Job 一视点，一序列一游观。 |
| `light` | Light | 光线 | How does the world become visible and time become perceptible? | 世界如何变得可见，时间如何被感知？ | 与虚实、明晦形成解释关系，不机械参数化阴阳概念。 |
| `color_post` | Color and Post | 色彩与后期 | How do color and rendering organize material, mood and time? | 色彩与成像如何组织材质、情绪和时间？ | 关联随类赋彩，色彩服从对象与关系而非滤镜名称。 |
| `quality_control` | Quality Control | 质量控制 | What evidence makes an output acceptable or rejectable? | 什么证据决定输出可以接受或必须拒绝？ | 六法提供整体品评启示，现代 QA 另需身份、解剖、连续性与权利证据。 |
| `content` | Content | 内容 | What is the work about, beyond the objects shown? | 作品超越画面物体之后，真正表达什么？ | 关联意与境，创作命题通过具体世界变得可感。 |
| `sequence` | Sequence | 序列 | How do multiple viewpoints become time, rhythm and narrative? | 多次观看如何形成时间、节奏与叙事？ | 关联卷轴、游观与步移景异。 |
| `job` | Job | 镜头任务 | What single independent act of looking must this image complete? | 这张图必须完成哪一次独立观看？ | 关联经营位置，将共享世界重新组织为一个明确视点。 |

## Controlled tags / 受控标签

| Tag | English | 中文 | Valid roles |
|---|---|---|---|
| `subject.identity.locked` | Stable fictional adult identity | 稳定的虚构成年人物身份 | `subject`, `job`, `quality_control` |
| `world.space.coherent` | Coherent reusable spatial geometry | 连贯且可复用的空间几何 | `world`, `camera`, `quality_control` |
| `world.prop.ownership` | Stable prop ownership | 稳定的道具归属 | `world`, `look`, `event`, `quality_control` |
| `style.editorial.restrained` | Restrained editorial visual decisions | 克制的编辑摄影视觉决定 | `style`, `color_post` |
| `look.wardrobe.locked` | Locked wardrobe continuity | 锁定的服装连续性 | `look`, `quality_control`, `job` |
| `emotion.expression.restrained` | Restrained observable expression | 克制且可观察的情绪表达 | `emotion`, `job` |
| `event.state.transition` | Event changes world state | 事件改变世界状态 | `event`, `sequence`, `job` |
| `camera.viewpoint.single` | One coherent viewpoint per Job | 每个 Job 保持一个连贯视点 | `camera`, `job`, `quality_control` |
| `light.direction.consistent` | Physically consistent light direction | 物理一致的光线方向 | `light`, `world`, `quality_control` |
| `color.palette.natural` | Natural relational color palette | 自然且关系一致的色彩体系 | `color_post`, `style` |
| `content.theme.decision` | Theme concerns an unspoken decision | 主题围绕未说出口的决定 | `content`, `emotion`, `sequence` |
| `sequence.function.progression` | Distinct functions form narrative progression | 不同镜头职能形成叙事递进 | `sequence`, `event`, `job` |
| `job.output.independent` | One independent finished image | 一张独立完成图 | `job`, `quality_control` |
| `qa.identity` | Identity evidence check | 身份一致性证据检查 | `quality_control` |
| `qa.anatomy` | Anatomy and hands evidence check | 解剖与手部证据检查 | `quality_control` |
| `qa.continuity` | World and sequence continuity check | 世界与序列连续性检查 | `quality_control`, `sequence` |
| `qa.no_text` | No text, logo, watermark or grid | 无文字、标志、水印或拼图 | `quality_control`, `job` |
