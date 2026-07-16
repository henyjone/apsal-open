<p align="center">
  <img src="assets/brand/apsal-worldbuilding-banner.jpg" alt="APSAL — 结构元素，构建世界" width="100%">
</p>

<h1 align="center">APSAL — 开放摄影生成协议</h1>

<p align="center"><strong>结构元素，构建世界。</strong><br>把创作意图转译为可组合、可验证、可复现的摄影世界。</p>

<p align="center">
  <a href="https://github.com/henyjone/apsal-open/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/henyjone/apsal-open/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/henyjone/apsal-open/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/henyjone/apsal-open?color=78988A"></a>
  <a href="LICENSE"><img alt="代码许可" src="https://img.shields.io/badge/code-Apache--2.0-B79A62"></a>
  <a href="CONTENT_LICENSE.md"><img alt="内容许可" src="https://img.shields.io/badge/content-CC%20BY%204.0-78988A"></a>
</p>

<p align="center"><a href="README.md">English</a> · <a href="#安装-codex-插件">安装插件</a> · <a href="#30-秒开始使用">快速开始</a> · <a href="docs/monograph/README.md">阅读方法论专著</a> · <a href="protocol/APSAL_OPEN_PROTOCOL.md">阅读协议</a></p>

---

## AI 摄影的本质，是构建世界

AI 摄影不是写出一段更长的 Prompt，而是定义一个世界：谁存在于其中，空间怎样组织，光从哪里来，时间如何流动，事件怎样发生，相机以什么视点观看。

APSAL 是描述这个世界的开放视觉语言。它把模糊的创作直觉拆解为明确的**元素、关系与约束**，再将它们编译为可独立执行的摄影 Job。

```mermaid
flowchart LR
    A["一句自然语言"] --> B["APSAL 自动拆解"]
    B --> C["Character · World · Scene · Photo DNA 卡片"]
    C --> D["创作者确认与修改"]
    D --> E["九个独立镜头 Jobs"]
    E --> F["九张图 · Prompt · Skill"]
```

| 元素 ELEMENTS | 语法 GRAMMAR | 世界 WORLD | 相机 CAMERA | 输出 OUTPUT |
|---|---|---|---|---|
| 身份、空间、光、色彩、风格、行动 | 依赖、锁定、变体、连续性 | 一个拥有记忆的统一视觉系统 | 每个 Job 对应一个独立观看视点 | 通过校验的 JSON、Prompt 与 Skill |

> **Prompt 描述一张图；APSAL 定义让这张图得以成立的世界。**

## 思想背后的开放系统

协议定义 13 类可组合模块；DNA Registry 保存可复用的视觉元素；引擎会解释哪些 DNA 适合当前场景，只记住创作者明确同意沉淀的个人方法，解析版本与依赖，校验身份和连续性，并在不依赖托管服务的情况下打包主题或独立 DNA。

## 安装 Codex 插件

推荐通过 Git marketplace 安装，协议、官方 DNA、本地引擎、卡片交互服务和打包器会一起进入 Codex：

```bash
codex plugin marketplace add henyjone/apsal-open --ref main
codex plugin add apsal-studio@apsal-open
```

安装后重新启动 Codex，或打开一个新任务。也可以从[最新 Release](https://github.com/henyjone/apsal-open/releases/latest)下载固定版本插件 ZIP。

## 30 秒开始使用

直接告诉 Codex：

> 创建一套九张东方极简窗边人像主题。

插件会完成：

1. 理解场景，以简洁的纯文字卡片依次推荐 Character、World、Scene、Photo DNA，并说明推荐理由。
2. 让你点击选择，也可以直接说“人物更成熟，但保留短发”或“重新设计第 4 镜”。
3. 为新 DNA 建议受控标签，再询问“保存到我的 DNA、仅当前项目，还是稍后决定”。
4. 展示九镜头总览，等你确认后再执行。
5. 确认真人摄影契约与参考图用途后，逐张生成九张 9:16 图片，或只保存 Prompt、导出可复现 Skill。

创作者不需要看见或手写 JSON/YAML。Protocol 0.3 把它们保留在本地资产层，用来复用、编辑、版本管理、编译和 QA。Studio 0.6 增加可解释的场景推荐、明确授权的个人记忆和可分享 DNA Extension Pack，同时保留 0.5 的真实参考图绑定与真人摄影执行。图片生成前只需明确确认一次；始终一 Job 一张图，单镜失败不会重做已经成功的镜头。

### DNA 保存在哪里

| 层级 | 位置 | 用途 |
|---|---|---|
| 官方 | 安装插件内部 | 只读、权利清晰的起步 DNA 与预览 |
| 个人 | `~/.apsal/` 或 `APSAL_HOME` | 跨项目复用的个人 DNA，以及私有参考图 Vault |
| 扩展 | `~/.apsal/extensions/` | 已安装、不可原地修改的社区 DNA Pack |
| 项目 | `<project>/.apsal/` | 草稿、项目 DNA、主题、精确 Prompt、运行记录、图片与 QA |

解析顺序是“项目 → 个人 → 扩展 → 官方”。确认后的草稿先成为项目 DNA；只有你明确选择“保存到我的 DNA”，才会复制到个人库。选择与结果记忆只保存在 `~/.apsal/usage/`，不保存原始创作描述。参考图原件进入 `~/.apsal/vault/sha256/`，不会写入 DNA JSON 或 Git。导出的本地 Skill 会包含清理后的副本和用途/权利清单，让图像模型真正看到图片；权利未解决时只能打包为 `private_only`，公开导出会失败。

界面背后，最终主题与每次真实生成都会留下完整血缘：

```text
.apsal/themes/<theme-id>/<version>/   创作源、规范资产、三类编译结果与 18 个 Prompt 文件
.apsal/runs/<run-id>/                 实际 Prompt、九张输出、失败重试与逐镜 QA
```

### 真人、真参考图、原生 4K

Studio 新主题默认要求真实成年人的实拍摄影呈现，并输出九张独立的 9:16、2160×3840、高质量 PNG。布景和道具可以保留手绘、蜡笔、绘画或戏剧化语言，但人物不能变成插画、动漫、玩偶、人体模型、蜡像或 3D 角色。

原生 4K 执行是可选能力：设置 `OPENAI_API_KEY`，选择 `openai-image-api` 与 `gpt-image-2`，APSAL 会顺序发出九次 `n: 1` 请求。有参考图的 Job 使用 Image Edits，没有参考图的使用 Generations；返回文件必须严格为 2160×3840。Codex ImageGen 不会被静默冒充为“保证原生 4K”的后备方案。GPT Image 2 支持该尺寸，但 2K 以上输出仍属于实验范围，详见 [OpenAI 官方说明](https://developers.openai.com/api/docs/guides/image-generation)。

模型视觉检查会检查媒介、皮肤、眼睛、手部、人体结构、光学景深、光线和材质；人工视觉 QA 仍单独保持 pending。Schema 或 Prompt 通过，不能证明成片已经是真人摄影。

### 经你允许，Registry 才会越用越懂你

推荐会综合受控语义标签、场景 facets、明确依赖、QA、权利、Registry 层级和私有使用结果。每张卡片都会解释为什么匹配。只有新建或修改的项目 DNA 才询问是否保存到个人库，APSAL 不会静默入库。

可复用 DNA 可以脱离主题，独立导出为确定性的 Extension Pack。公开包必须具备统一 namespace、已确认标签、权利清晰的 DNA 与预览、署名、已解析依赖和 SHA-256。安装固定 GitHub Release 包：

```bash
python3 plugins/apsal-studio/scripts/apsal.py registry install 'github:owner/repo@v1.0.0#my-pack-v1.0.0.zip'
```

安装包只读，不能覆盖官方或已有的同 ID/版本资产。

## 直接使用本地引擎

验证和打包不需要 APSAL 账号、托管 API 或模型密钥：

```bash
python3 plugins/apsal-studio/scripts/apsal.py init
python3 plugins/apsal-studio/scripts/apsal.py session start "创建一套九张东方极简窗边人像主题"
python3 plugins/apsal-studio/scripts/apsal.py registry recommend "安静的东方极简窗边人像" --stage world
python3 plugins/apsal-studio/scripts/apsal.py registry search --stage character
python3 plugins/apsal-studio/scripts/apsal.py catalog
python3 plugins/apsal-studio/scripts/apsal.py validate examples/quiet-window/theme.apsal.yaml
python3 plugins/apsal-studio/scripts/apsal.py normalize examples/quiet-window/theme.apsal.yaml -o build/theme.apsal.json
python3 plugins/apsal-studio/scripts/apsal.py explain examples/quiet-window/theme.apsal.yaml --path shots.SHOT_04.framing
python3 plugins/apsal-studio/scripts/apsal.py compile examples/quiet-window/theme.apsal.yaml --target design -o build/design.json
python3 plugins/apsal-studio/scripts/apsal.py compile examples/quiet-window/theme.apsal.yaml --target image -o build/image.json
python3 plugins/apsal-studio/scripts/apsal.py compile examples/quiet-window/theme.apsal.yaml --target qa -o build/qa.json
python3 plugins/apsal-studio/scripts/apsal.py check-sync examples/quiet-window
python3 plugins/apsal-studio/scripts/apsal.py pack examples/quiet-window/theme.apsal.yaml -o build
python3 plugins/apsal-studio/scripts/apsal.py validate-package path/to/extracted-package
```

原生 4K 本地流程还提供 `session finalize`、`run --confirm`、`run-execute` 与 `run-model-qa`；可用 `python3 plugins/apsal-studio/scripts/apsal.py --help` 查看。验证与打包本身仍可完全离线运行。

## 你可以怎样参与

| 创作者 | 开发者 | 贡献者 |
|---|---|---|
| 用一句话构建世界，选择 DNA 卡片，再生成九张独立图片。 | 基于[协议](protocol/APSAL_OPEN_PROTOCOL.md)、[Schema](plugins/apsal-studio/assets/schemas)、本地 MCP 和 CLI 开发工具。 | 使用 [DNA 投稿模板](https://github.com/henyjone/apsal-open/issues/new?template=dna-submission.yml)贡献原创资产。 |

## 开放不等于无授权

协议与参考引擎采用 Apache-2.0；官方起步 DNA 和示例采用 CC BY 4.0。任何主题只有在明确声明许可证、署名、来源、版本血缘、校验和与 QA 状态后，才能作为开放内容发布。参考图拥有独立许可与肖像授权记录，不会自动继承主题文字的 CC BY 4.0；私人或权利未明媒体不会进入本仓库和公开 Release。

静态校验只能证明结构与可复现性，不能证明生成图片已经通过人工视觉 QA。

## 项目导航

- [《构建可见世界：APSAL 元素摄影法》](docs/monograph/README.md)
- [Semantic Contract RFC](protocol/RFC-0001-SEMANTIC-CONTRACT.md)
- [本地 Registry 与对话创作 RFC](protocol/RFC-0002-LOCAL-REGISTRY-AND-CONVERSATIONAL-AUTHORING.md)
- [参考图绑定、真人摄影与原生 4K RFC](protocol/RFC-0003-REFERENCE-BINDING-LIVE-ACTION-AND-NATIVE-4K.md)
- [DNA 推荐、记忆与交换 RFC](protocol/RFC-0004-DNA-RECOMMENDATION-MEMORY-AND-EXCHANGE.md)
- [APSAL Studio 0.6.1 发布与安装说明](docs/releases/0.6.1.md)
- [《窗边未寄》语义契约试点](examples/quiet-window/theme.apsal.yaml)
- [APSAL Open Protocol](protocol/APSAL_OPEN_PROTOCOL.md)
- [APSAL Studio 插件](plugins/apsal-studio)
- [DNA Registry](plugins/apsal-studio/assets/dna/catalog.json)
- [语义化示例主题](examples/quiet-window/theme.apsal.yaml)
- [贡献指南](CONTRIBUTING.md)
- [治理规则](GOVERNANCE.md)
- [安全策略](SECURITY.md)
- [最新 Release](https://github.com/henyjone/apsal-open/releases/latest)

<p align="center"><strong>让创意成为资产，让资产成为可复现的摄影系统。</strong></p>
