# APSAL 0.15.0 升级实施规格

状态：0.15.0 规范基线
配套版本：APSAL Open / Codex 插件 / Engine 0.15.0，APSAL Studio Desktop 0.2.0
适用对象：负责升级 APSAL Open、Codex 插件和 APSAL Studio 的开发者

这不是功能介绍，而是一份实施合同。升级完成后的判断标准只有一个：

> Codex 和 Studio 对同一个项目执行同一组操作，必须看到同一个项目 ID、同一个 revision、同一套五层十三要素、同一份 Prompt，以及字节一致的最终 ZIP。

## 1. 0.15.0 要解决的问题

0.15.0 以前，Codex 插件和 Studio Workflow 容易形成两份状态：

- Codex 维护会话、DNA、Prompt、Run 和 QA；
- Studio 维护节点、属性和工作流持久化；
- 两边即使表达同一个主题，也可能出现不同 ID、不同确认状态和不同最终产物。

0.15.0 必须改为：

- Python APSAL Engine 是唯一语义执行器；
- <项目目录>/.apsal/ 是唯一项目真源；
- Codex 是对话入口；
- Studio 是节点化可视入口；
- Studio Workflow 是可丢弃投影，不是第二份语义数据库；
- finalize_theme 是唯一最终化入口。

## 2. 版本合同

| 组件 | 版本 | 责任 |
|---|---:|---|
| APSAL Protocol | 0.15.0 | 项目、revision、领域接口和投影合同 |
| APSAL Engine | 0.15.0 | 五层、十三角色、DNA、权利、失效、Prompt、Run、QA、打包 |
| Codex 插件 | 0.15.0 | 对话、MCP 工具和可选 Studio 路由 |
| APSAL Studio | 0.2.0 | sidecar、画布投影、变更确认和 Codex 联动页 |
| Studio View Schema | 0.1.0 | 纯 UI 布局状态 |

Studio 0.2.0 与 Engine/Protocol 0.15.0 使用严格版本握手。版本不一致时：

- 允许读取项目状态；
- 禁止语义写入；
- UI 显示“协议不兼容，需要升级”；
- 不允许由 TypeScript 猜测、转换或补写协议数据。

## 3. 总体架构

~~~mermaid
flowchart LR
    C["Codex 对话"] --> M["APSAL MCP 0.15"]
    M -->|"Studio 未连接"| P["Python APSAL Engine"]
    M -->|"Studio 已连接"| B["127.0.0.1 认证桥"]
    B --> S["Electron Engine sidecar"]
    S --> P
    U["Studio 画布和右栏"] --> S
    P --> A["项目目录/.apsal/"]
    A --> P
    P --> Z["确定性 Prompt/Skill ZIP"]
    U -. "仅视图状态" .-> V[".apsal/studio/view.json"]
~~~

硬性边界：

1. Studio 不得在 TypeScript 中重写五层、十三角色、失效规则、Prompt 编译或打包规则。
2. Codex 与 Studio 不得分别保存主题真源。
3. Studio 画布坐标不得进入主题 digest、Prompt digest 或最终 ZIP。
4. Studio 不包含本地生成引擎、模型或供应商设置；正式生成只由 Codex 执行。

## 4. 项目目录合同

新项目必须由 project.init 初始化目录：

~~~text
<project>/
└── .apsal/
    ├── project.json
    ├── .gitignore
    ├── drafts/
    │   └── <session_id>/
    │       └── proposals/
    │           └── <preview_id>.json
    ├── registry/
    ├── themes/
    ├── runs/
    ├── cache/
    │   ├── protocol-operations.json
    │   ├── protocol-transaction.json
    │   └── history/
    │       └── <operation_id>/
    └── studio/
        └── view.json
~~~

<code>project.json</code> 的最低结构：

~~~json
{
  "schema_version": "0.15.0",
  "project_id": "PROJECT-0123456789AB",
  "protocol_version": "0.15.0",
  "engine_version": "0.15.0",
  "active_session_id": "SESSION-0123456789AB",
  "revision": 12,
  "storage": "local_first",
  "created_at": "2026-07-18T00:00:00Z"
}
~~~

字段规则：

- <code>project_id</code> 创建后永久稳定。
- <code>revision</code> 只允许 Engine 单调递增。
- <code>active_session_id</code> 指向当前设计会话，可以为空。
- <code>protocol_version</code> 和 <code>engine_version</code> 由 Engine 写入。
- Studio 和 Codex 都不得直接编辑此文件。

<code>studio/view.json</code> 只保存：

~~~json
{
  "schema_version": "0.1.0",
  "view_revision": 3,
  "nodes": {
    "THEME-001:subject": {"x": 320, "y": 180, "collapsed": false}
  },
  "viewport": {"x": 30, "y": 30, "zoom": 0.72},
  "selected_element_id": "THEME-001:subject",
  "expanded_cards": ["THEME-001:subject"]
}
~~~

<code>view_revision</code> 与项目 <code>revision</code> 完全独立。保存视图不能：

- 增加项目 revision；
- 改变主题 digest；
- 使下游层失效；
- 改变 Prompt；
- 改变最终 ZIP。

## 5. 五层与十三角色

十三个协议角色是固定槽位，不能删除：

| 层 | 协议角色 | Studio 投影 |
|---|---|---|
| Direction | Content、Emotion | 全局控制 |
| Worldbuilding | Subject、World、Look | 人物、场景、妆造/道具 |
| Narrative | Event、Sequence | 事件、镜头序列、Job 容器 |
| Image | Camera、Light、Style、Color/Post | 相机、灯光、后期 |
| Delivery | Job、Quality Control | 输出任务、质量检查 |

每个正式节点必须带：

~~~json
{
  "protocol_element_id": "THEME-001:subject",
  "layer_id": "worldbuilding",
  "role_id": "subject",
  "status": "confirmed"
}
~~~

稳定 ID 规则：

- 角色节点：<code>&lt;theme_id&gt;:&lt;role_id&gt;</code>；
- 属性：<code>&lt;theme_id&gt;:&lt;role_id&gt;:&lt;attribute_key&gt;</code>；
- Studio 节点 ID 必须从 <code>protocol_element_id</code> 投影，不得随机重建语义 ID。

人物、道具、场景、镜头等“实例”属于对应角色的决策内容。0.15.0 中：

- 可以通过 <code>design.propose</code> 增加、修改或删除角色下实例；
- 删除实例必须先形成预览，并在 Studio 再确认；
- 不允许通过删除十三个角色节点来表达“清空”；
- 可选值可以为空，但角色槽位必须仍然存在。

## 6. 统一领域接口

Engine 对 Codex 进程内路径和 Electron stdio sidecar 暴露同一 dispatcher。

### 6.1 读取接口

| 方法 | 用途 | 是否增加 revision |
|---|---|---|
| project.open | 打开项目 | 否 |
| project.snapshot | 获取统一快照 | 否 |
| design.present | 获取某层展示卡 | 否 |
| generation.next | 获取下一个 Codex Job | 否 |
| studio.view.get | 获取画布布局 | 否 |

### 6.2 写入接口

| 方法 | 用途 |
|---|---|
| project.init | 初始化新项目 |
| project.undo | 撤销可撤销操作 |
| design.start | 建立设计会话 |
| design.language | 修改呈现语言 |
| design.propose | 创建草稿预览 |
| design.commit_preview | 确认预览并提交整层 |
| design.reject_preview | 拒绝预览 |
| design.commit_layer | 无预览时提交整层 |
| design.finalize / finalize_theme | 唯一最终化入口 |
| generation.start | 建立正式 Codex Run |
| generation.record | 记录 Job 结果 |
| qa.record | 记录模型视觉 QA |
| studio.view.save | 保存视图；例外，不增加语义 revision |

### 6.3 字段命名

公共 MCP 工具使用：

~~~json
{
  "expectedRevision": 12,
  "operationId": "CODEX-APPLY-01"
}
~~~

Engine JSON-RPC 使用：

~~~json
{
  "expected_revision": 12,
  "operation_id": "CODEX-APPLY-01"
}
~~~

Engine 边界可以接收两种写法，但内部统一为 snake_case。新代码不得在业务层混用。

旧 MCP 工具为兼容自然对话，可以在调用方没有显式提供时读取最新 revision 并生成 operationId。七个 <code>apsal_frontend_*</code> 工具必须显式携带 revision 和 operationId，因为它们直接参与跨进程确认。

## 7. 统一项目快照

<code>project.snapshot</code> 至少返回：

~~~json
{
  "project_root": "/path/to/project",
  "project": {
    "project_id": "PROJECT-0123456789AB",
    "revision": 12
  },
  "protocol_version": "0.15.0",
  "engine_version": "0.15.0",
  "revision": 12,
  "session": {
    "session_id": "SESSION-0123456789AB",
    "state": "image_pending",
    "layers": {},
    "invalidations": []
  },
  "theme": {
    "id": "THEME-001",
    "version": "1.0.0",
    "digest": "sha256..."
  },
  "elements": [],
  "stage_previews": [],
  "previews": []
}
~~~

Studio 只能用这份快照重建语义节点。刷新、重启或删除内存缓存后，画布应能从：

1. <code>project.snapshot</code>；
2. <code>studio.view.get</code>；

完整恢复。

## 8. revision、operationId 与原子写入

每次语义写入执行固定流程：

~~~text
解析项目目录
→ 获取项目锁
→ 检查 operationId 是否已经完成
→ 校验 expectedRevision == project.revision
→ 保存可恢复历史
→ 写入 protocol-transaction.json
→ 执行业务操作
→ 原子替换语义文件
→ project.revision + 1
→ 记录 protocol-operations.json
→ 删除 transaction journal
→ 释放项目锁
~~~

规则：

- 同一 <code>operationId</code> 重试时返回首次结果，并标记 <code>idempotent_replay: true</code>。
- 调用方不得把同一个 operationId 用于另一种业务意图。
- revision 不匹配必须失败，禁止 last-write-wins。
- Engine 崩溃后，下次 <code>project.init/open</code> 根据 journal 恢复到操作前状态。
- history 只为可撤销操作保留；Run、Job 结果和 QA 记录不可用普通撤销覆盖。
- 撤销本身是一个新操作，也必须增加 revision。

## 9. 预览与确认

任何来自 Codex 或 Studio 的语义修改都先调用 <code>design.propose</code>。

假设当前项目 revision 为 12：

1. 调用 <code>design.propose(expectedRevision=12)</code>；
2. Engine 保存预览并把项目 revision 增加为 13；
3. 返回的 <code>preview.base_revision</code> 为 13；
4. Studio 显示幽灵节点；
5. 确认时调用 <code>design.commit_preview(expectedRevision=13)</code>；
6. 提交成功后 revision 变为 14。

这是升级中最容易出错的地方：确认预览时使用的是“创建预览后的当前 revision”，不是创建前的 revision。

预览失效条件：

- 当前项目切换；
- active session 切换；
- 当前 revision 不再等于 preview.base_revision；
- 预览已经 applied 或 rejected。

预览失效后必须重新读取快照并重新 propose。禁止把旧预览静默套用到新 revision。

幽灵节点必须：

- 标记 <code>ghost: true</code>；
- 标记 <code>participatesInPrompt: false</code>；
- 使用独立预览 ID；
- 不替换正式节点；
- 允许定位、确认和拒绝；
- 不进入主题、Prompt 或最终 ZIP。

## 10. 层确认与下游失效

只有整层确认可以进入正式主题。

~~~text
Direction 改变
→ Worldbuilding、Narrative、Image、Delivery 变为 pending

Worldbuilding 改变
→ Narrative、Image、Delivery 变为 pending

Narrative 改变
→ Image、Delivery 变为 pending

Image 改变
→ Delivery 变为 pending
~~~

Engine 是失效规则的唯一实现者。Studio 只显示快照里的 <code>invalidations</code> 和层状态，不在前端自行推导最终结果。

旧 Prompt 在上游层失效后必须视为不可用。只有重新确认所有受影响层并再次 finalize，才能产生新的正式包。

## 11. Codex 双路径路由

### 11.1 未连接 Studio

~~~text
Codex MCP
→ handle_domain_method
→ Python APSAL Engine
→ <project>/.apsal/
~~~

创作者在插件开始创作时选择“仅在 Codex 中继续”，或 Studio 未安装、关闭、桥描述文件不存在时，插件必须保持完整能力。独立打开的 Studio 不得让当前 Codex 创作自动改走联动路径。

### 11.2 已连接 Studio

~~~text
Codex MCP（本次创作已明确选择 Studio）
→ 读取 ~/.apsal/frontend-link.json
→ Bearer Token 调用 127.0.0.1:<随机端口>/v1/rpc
→ Electron sidecar
→ 同一 Python dispatcher
→ <project>/.apsal/
~~~

一旦一次写操作选择了联动路径，途中断线必须返回错误，禁止静默改走进程内路径重试。否则同一个用户动作可能被执行两次。

`start_design_session` 通过 `frontend_mode=studio|headless` 记录本次 MCP 创作进程的选择。新建项目先由统一 Engine 初始化，再由插件使用固定的 APSAL Studio 应用路径和 `--project-root ... --codex-link` 启动前端。只有插件本次明确选择的项目才能进入联动路由；磁盘上已有 descriptor 不等于本次创作已经授权。

### 11.3 七个前端联动工具

| MCP 工具 | 领域方法 | UI 结果 |
|---|---|---|
| apsal_frontend_status | GET /v1/status | 显示连接、版本、项目和 revision |
| apsal_frontend_get_project | project.snapshot | 刷新统一快照 |
| apsal_frontend_preview_changes | design.propose | 创建变更卡和幽灵节点 |
| apsal_frontend_apply_preview | design.commit_preview | 确认整层 |
| apsal_frontend_reject_preview | design.reject_preview | 拒绝草稿 |
| apsal_frontend_undo_operation | project.undo | 撤销已提交操作 |
| apsal_frontend_focus_elements | ui.focus_elements | 定位节点，不改语义 |

## 12. Studio 0.2.0 设计

### 12.1 Electron sidecar

Electron 主进程启动打包资源中的：

~~~text
resources/apsal-engine/scripts/apsal_rpc.py
~~~

通信为一行一个 JSON-RPC 2.0 消息。启动后先调用 <code>initialize</code>：

~~~json
{
  "name": "apsal-protocol-engine",
  "engine_version": "0.15.0",
  "protocol_version": "0.15.0",
  "transport": "stdio-jsonrpc"
}
~~~

版本必须同时匹配才允许写入。sidecar 退出时：

- 拒绝所有 pending RPC；
- UI 进入离线/只读状态；
- 重启后重新读取项目快照；
- 不使用 Zustand 内存恢复语义。

### 12.2 Zustand

Zustand 只缓存：

- Engine snapshot；
- Studio view；
- pending preview；
- 最近操作的显示信息；
- 当前连接状态。

Zustand 不得独立持久化：

- 角色决策；
- 层确认状态；
- DNA；
- Prompt；
- Run；
- QA；
- 最终主题。

### 12.3 右栏

右栏保留两个页签：

1. 属性：显示 Engine 管理节点的只读语义；编辑动作创建 preview。
2. Agent 联动：显示连接、项目 ID、revision、五层状态、变更卡、下游影响、确认、拒绝、定位和撤销。

Codex 对话仍然发生在 Codex，不在 Studio 内复制聊天窗口。

### 12.4 画布限制

- 十三个正式角色节点不能删除；
- 正式角色节点不能用旧 Workflow action 直接改语义；
- 移动、缩放、折叠和选择只写 view.json；
- 破坏性实例删除必须先 propose，再由 Studio 明确确认；
- 前端不包含旧 IndexedDB 自动保存和旧 Workflow undo；
- 协议撤销必须调用 project.undo。

## 13. 本地认证桥

联动默认关闭，Studio 不提供手动联动开关。只有创作者在 Codex 的 APSAL 插件开始或恢复创作时选择“打开并联动”，插件才使用当前项目启动 Studio。启动后：

- 仅监听 <code>127.0.0.1</code>；
- 使用随机端口；
- 每次启动生成新的 32 字节随机 token；
- token 写入 <code>~/.apsal/frontend-link.json</code>；
- 信任记录写入 <code>~/.apsal/frontend-trust.json</code>；
- 目录权限为 0700，文件权限为 0600；
- 停止桥时删除属于当前 token 的 descriptor；
- 请求体最大 1 MiB；
- 只允许白名单领域方法；
- 请求项目必须等于 Studio 当前项目；
- token 使用常量时间比较；
- 响应使用 <code>Cache-Control: no-store</code>。

桥只有两个 HTTP 入口：

~~~text
GET  /v1/status
POST /v1/rpc
~~~

不开放公网地址，不提供 CORS，不接受任意文件路径或任意方法代理。

## 14. 正式生成与 Studio 边界

正式 Codex 生成链路：

~~~text
finalize_theme
→ generation.start
→ generation.next
→ Codex 内置图像生成
→ generation.record
→ qa.record
~~~

Studio 0.2.0 不提供本地生成入口。它只能：

- 展示 Engine 快照中的 Run、Job 和 QA 状态；
- 展示 Codex 创建的语义变更预览和幽灵节点；
- 确认、拒绝、定位或撤销协议操作；
- 保存不参与语义编译的画布布局。

Studio 不读取图像 API Key，不启动 ComfyUI、MLX 或其他模型运行时，也不直接调用 <code>generation.start</code>、<code>generation.record</code> 或 <code>qa.record</code>。这些正式操作由 Codex 插件通过统一 Engine 完成。

模型视觉 QA 与人工视觉 QA 必须分别记录。静态校验通过不等于照片视觉验收通过。

## 15. finalize_theme 与最终 ZIP

finalize_theme 必须先验证：

- 五层全部 confirmed；
- 十三个角色完整；
- 所有引用的用途、禁止用途、权利、同意、归属和再分发状态明确；
- 每个 Job 合法且文件名唯一；
- QA 结构完整；
- 没有 stale preview 被当作正式决策；
- 没有 pending 下游层；
- 当前 revision 与请求一致。

最终 ZIP 包含：

- 中英文使用指南；
- 主题 YAML 和 canonical JSON；
- 每个 Job 的 positive、negative 和 full Prompt；
- 允许进入包内的真实引用；
- 引用用途与权利清单；
- Run manifest；
- QA checklist/manifest；
- 五阶段语义预览；
- checksum ledger。

最终 ZIP 不包含：

- studio/view.json；
- 节点坐标、缩放、折叠或选择状态；
- Codex 聊天记录；
- IndexedDB 数据；
- 未获再分发许可的公开引用；
- API Key 或 provider credential。

确定性要求：

- ZIP 文件顺序固定；
- 时间戳固定；
- canonical JSON 排序固定；
- 同一 revision 多次 finalize 得到相同字节；
- Codex 与 Studio finalize 得到相同 SHA-256、theme_id 和 version。

## 16. 失败处理

| 场景 | 必须行为 |
|---|---|
| expectedRevision 过期 | 拒绝；重新 snapshot 和 propose |
| operationId 重试 | 返回首次结果，不重复创建节点 |
| preview 过期 | 标记 stale；禁止确认 |
| Studio 切换项目 | 拒绝旧项目请求 |
| sidecar 崩溃 | 回滚 journal；重启后 snapshot |
| 桥中途离线 | 当前写入失败；禁止静默 fallback |
| 协议不兼容 | 只读并提示升级 |
| 正式 Job 已成功 | 禁止覆盖；只能继续下一 Job |
| view.json 损坏或缺失 | 生成默认布局，不影响主题 |

## 17. 不迁移范围

0.15.0 不迁移：

- .aiproject；
- 旧 Studio Workflow；
- IndexedDB 草稿；
- 旧画布导入格式；
- 旧 Workflow 节点 ID；
- 旧 Studio undo 栈。

打开这些格式时应明确提示“0.15.0 仅支持新 APSAL 项目”，而不是隐式转换。

升级前的旧项目只保留为备份。需要继续创作时，在新目录创建 APSAL 0.15 项目，并人工确认需要重新建立的创作决策。

## 18. 实际升级操作

### 18.1 升级前

1. 关闭 APSAL Studio，停止正在执行的生成任务。
2. 备份旧 Studio 项目和需要保留的本地素材。
3. 不要把旧 .aiproject 或 IndexedDB 数据复制进新项目的 .apsal/。
4. 保留旧应用作为只读备份，但不要让 0.14 Engine 写入 0.15 项目。

### 18.2 升级 Codex 插件

发布 0.15.0 后，使用正式版本引用安装：

~~~bash
codex plugin marketplace add henyjone/apsal-open --ref v0.15.0
codex plugin list
~~~

确认输出为 <code>apsal-studio@apsal-open 0.15.0</code>，然后重启 Codex 或新建任务。

不要直接修改 <code>~/.codex/plugins/cache/</code>。该目录是 Codex 管理的安装缓存，不是发布源。

### 18.3 升级 Studio

1. 安装或替换为 APSAL Studio 0.2.0。
2. 单独启动一次，确认 Agent 联动页显示“等待 Codex 启动”，且没有手动联动开关。
3. 可以在 Studio 中打开项目做只读投影检查，但不要把这一步当作 Codex 联动。
4. 确认界面显示 Engine 0.15.0、Protocol 0.15.0 和 revision 0。
5. 关闭并重新打开项目，确认 project_id 不变。

### 18.4 首次联调

1. 在 Codex 中打开 APSAL 插件并开始创作。
2. 对“是否同时打开 APSAL Studio 前端？”选择“打开并联动（推荐）”。
3. 插件通过 `start_design_session(frontend_mode=studio)` 创建或恢复项目，并自动启动 Studio。
4. 调用 apsal_frontend_status，必须返回 connected、compatible、selected_for_codex 和当前项目。
5. 先做一个 Direction 层 preview，不要直接升级完整主题。
6. 确认 Studio 出现幽灵节点和受影响层。
7. 在 Studio 确认整层，再从 Codex 读取快照。
8. 两端一致后再继续 Worldbuilding 到 Delivery。

### 18.5 回退边界

如果联动异常：

- 当前已选择联动的写操作必须报错，不得自动重放；
- 明确恢复同一 session 并选择“仅在 Codex 中继续”后，Codex 0.15.0 才通过进程内 Engine 继续；
- 不要使用 0.14 插件或旧 Studio 写入已经创建的 0.15 项目；
- 保留项目目录和 operation ledger，修复版本后重新 snapshot；
- 不要通过复制旧 Workflow 或手工编辑 project.json“修复”项目。

## 19. 推荐开发升级顺序

### 阶段 A：先升级 APSAL Open / Engine

1. 固定 Protocol 和 Engine 版本为 0.15.0。
2. 建立 project.json 与 revision 合同。
3. 建立项目锁、原子写、operation ledger、transaction journal 和 undo history。
4. 建立统一 domain dispatcher。
5. 建立 stdio JSON-RPC 服务。
6. 将 MCP 语义写入全部改走 dispatcher。
7. 增加七个 apsal_frontend_* 工具。
8. 完成直接路径与 stdio 路径黄金契约测试。

在阶段 A 结束前不要改 Studio 语义持久化，否则会短暂形成第三种状态。

### 阶段 B：升级 Studio 0.2.0

1. 将已通过测试的 Engine 资源同步进 Electron package。
2. 启动 sidecar 并完成 0.15.0 握手。
3. 增加新建/打开 APSAL 项目目录。
4. 建立 snapshot → Workflow 投影。
5. 隔离 studio/view.json。
6. 阻止旧 Workflow action 修改协议节点。
7. 增加幽灵节点和 Agent 联动页。
8. 增加默认关闭的认证桥。
9. 将协议项目的撤销改为 project.undo。

### 阶段 C：联调

1. Codex 创建项目并确认 Direction。
2. Studio 打开同一项目，确认 project_id、session_id 和 revision。
3. Codex 创建 Worldbuilding preview。
4. Studio 看到同一变更卡和幽灵节点。
5. Studio 确认后，Codex snapshot 看到同一正式节点。
6. Studio 修改上游元素并重新确认。
7. 两端看到相同下游 pending 状态。
8. 从任一端 finalize，并比较 ZIP。

### 阶段 D：切换版本

1. 发布 APSAL Open / Codex 插件 0.15.0。
2. 发布 APSAL Studio 0.2.0。
3. 先升级插件，再升级 Studio，或保持联动关闭。
4. 两端版本匹配后再开启 Codex 联动。
5. 新建一个空白项目执行冒烟测试。

## 20. 验收矩阵

| 验收项 | 通过条件 |
|---|---|
| 双路径一致 | 每一步 snapshot 和 revision 完全相同 |
| Prompt 一致 | canonical JSON 和 Prompt digest 相同 |
| 最终包一致 | ZIP 字节和 SHA-256 相同 |
| UI 隔离 | 移动节点后主题和 ZIP 不变 |
| 失效一致 | 上游修改后两端下游状态相同 |
| 幂等 | 相同 operationId 不产生重复 preview/节点 |
| 并发 | 同 revision 的两个写入最多一个成功 |
| 崩溃恢复 | 不产生半写入项目 |
| 离线 | Studio 关闭时 Codex 完整可用 |
| 安全 | 桥只监听 loopback，错误 token 返回 401 |
| 兼容 | 版本不匹配只读 |
| 生成 | succeeded Job 不被覆盖 |

建议执行：

~~~bash
# APSAL Open
python3 -m unittest tests.test_protocol -v
python3 -m unittest tests.test_engine -v
python3 scripts/validate_plugin_bundle.py
python3 scripts/release.py

# APSAL Studio
npm run typecheck
npm test -- --run
npm run test:electron
npm run build
~~~

打包后再直接检查 sidecar：

~~~bash
python3 "APSAL Studio.app/Contents/Resources/apsal-engine/scripts/apsal_rpc.py" <<'EOF'
{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}
EOF
~~~

返回的 Engine 和 Protocol 都必须是 0.15.0。

## 21. 升级完成定义

以下条件全部满足才算升级完成：

- [ ] Codex 插件显示 0.15.0。
- [ ] Studio 显示 0.2.0。
- [ ] sidecar 握手显示 Engine/Protocol 0.15.0。
- [ ] 新项目只产生一个 .apsal/ 真源。
- [ ] 十三个角色节点 ID 稳定且不可删除。
- [ ] Studio 编辑先形成 preview 和幽灵节点。
- [ ] 确认预览后 revision 正确递增。
- [ ] revision 冲突不会静默覆盖。
- [ ] Studio 布局变化不改变 Prompt 或 ZIP。
- [ ] Codex 未连接 Studio 时仍可完整创作和打包。
- [ ] 两条路径的最终 ZIP 字节一致。
- [ ] 旧 .aiproject 和 IndexedDB 项目没有被隐式迁移。

任何一项未满足，都不能把两端称为“同一个 APSAL 项目”。
