# 升级到 APSAL 0.16.0

[English](UPGRADE_GUIDE_0.16.0.md) · [预发布说明](releases/0.16.0.md) · [中文完整使用手册](USAGE_GUIDE.zh-CN.md)

本指南把 Codex 插件升级到 Engine/Project Protocol `0.16.0`，把本机桌面应用升级到 Studio `0.3.0`。首个公开版本采用预发布标签 `v0.16.0-beta.1`。

## 升级前

- 保留每个旧项目目录及其中的 `.apsal/`，不要手工修改 `protocol_version`。
- 替换 `/Applications/APSAL Studio.app` 前，先保存一个带版本和时间戳的备份。
- 插件刷新后关闭旧 Codex 任务并新建任务；插件在任务启动时加载。
- beta GitHub Release 只包含 Codex 插件 ZIP 和校验和。未签名的 macOS 应用只在本机构建，不作为公开附件。

## 刷新 Codex 插件

```bash
codex plugin remove apsal-studio@apsal-open
codex plugin marketplace remove apsal-open
codex plugin marketplace add henyjone/apsal-open --ref v0.16.0-beta.1
codex plugin add apsal-studio@apsal-open
codex plugin list
```

最后应看到 `apsal-studio@apsal-open` 已启用且版本为 `0.16.0`。然后新建 Codex 任务再验证 MCP 工具。

## 在 macOS 本机构建 Studio 0.3.0

开发构建需要 Node.js 22+ 和 Python 3.11+。打包应用会内嵌经过测试的 Python Engine，不需要另装 MOSA、Cowart、Node 运行时、模型或生图供应商。

```bash
git clone --branch v0.16.0-beta.1 https://github.com/henyjone/apsal-open.git
cd apsal-open/apps/apsal-studio
npm ci
npm run build
npm test -- --run
npm run test:electron
npm run desktop:pack
```

ARM64 应用位于 `apps/apsal-studio/release/mac-arm64/`。把当前应用保存为带版本的备份，再将新的 `APSAL Studio.app` 复制到 `/Applications` 并启动。本 beta 仅为本地 ad-hoc/未签名构建，不宣称开发者签名或公证。

## 旧项目兼容与复制迁移

- `0.16.0` 项目正常读写。
- `0.15.0` 项目以只读方式打开；Studio 先显示迁移目标，再在明确确认后迁移。
- 迁移复制到新目录并建立新的本地项目 ID，同时保存来源项目 ID 和旧协议版本，绝不改写原目录。
- 拒绝迁移后仍可继续只读查看原项目。
- 更早的 run ZIP 接管继续是私有流程，与 Project Protocol 迁移相互独立。

迁移完成后可将副本协调进本地项目库。项目库数据库只是可重建投影，删除数据库不能替代项目删除，也不能修复项目语义。

## 升级验收

确认版本矩阵为 Open Protocol `0.4.0`、Engine/Project/Plugin `0.16.0`、Studio `0.3.0`、Library/Analysis/Share `0.1.0`、Semantic Contract `0.3.0`。再用临时目录建立一个双参考图项目，完成分析、构建 Skill、创建一个子项目并导出公共包。父项目摘要必须不变；公共 ZIP 不得包含参考图原件、Vault URI、账号凭据或本机绝对路径。

## 回滚

移除 `0.16.0` 插件并重新安装此前固定的标签，恢复带版本的 Studio 应用备份。保留 `0.16.0` 项目不动：旧软件可以只读打开或拒绝打开，但回滚过程不能改写它。因为复制迁移从未修改旧 `0.15.0` 目录，原目录是最可靠的回滚来源。

## beta 边界

- 暂无签名/公证的公开 macOS 附件，也不提交官方插件目录。
- X 直发需要官方开发者应用与用户 OAuth；没有凭据时退化为官方发布页交接。
- 小红书只生成草稿并拉起官方流程，必须等待外部完成确认。
- 不建设 APSAL 云账号、社区、评论和审核服务，也不后台导入历史生成图片。
