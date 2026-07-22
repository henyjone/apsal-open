# Upgrade to APSAL 0.16.0

[中文](UPGRADE_GUIDE_0.16.0.zh-CN.md) · [Release notes](releases/0.16.0.md) · [Complete usage guide](USAGE_GUIDE.md)

This guide upgrades the Codex plugin to Engine/Project Protocol `0.16.0` and the local desktop application to Studio `0.3.0`. The first public build is the prerelease tag `v0.16.0-beta.1`.

## Before upgrading

- Keep every existing project directory and its `.apsal/` folder. Do not manually edit `protocol_version`.
- Back up any separately installed `/Applications/APSAL Studio.app` before replacing it.
- Close older Codex tasks after the plugin is refreshed; plugins are loaded when a task starts.
- The beta GitHub Release contains the Codex plugin ZIP and checksum only. The unsigned macOS app is built locally and is not a public release asset.

## Refresh the Codex plugin

```bash
codex plugin remove apsal-studio@apsal-open
codex plugin marketplace remove apsal-open
codex plugin marketplace add henyjone/apsal-open --ref v0.16.0-beta.1
codex plugin add apsal-studio@apsal-open
codex plugin list
```

The final command must report `apsal-studio@apsal-open` enabled at `0.16.0`. Open a new Codex task before testing MCP tools.

## Build Studio 0.3.0 locally on macOS

Requirements for development are Node.js 22+ and Python 3.11+. The packaged app embeds the tested Python Engine and needs no separate MOSA, Cowart, Node runtime, model or image provider.

```bash
git clone --branch v0.16.0-beta.1 https://github.com/henyjone/apsal-open.git
cd apsal-open/apps/apsal-studio
npm ci
npm run build
npm test -- --run
npm run test:electron
npm run desktop:pack
```

The ARM64 app is created under `apps/apsal-studio/release/mac-arm64/`. Preserve the currently installed app under a versioned backup name, copy the new `APSAL Studio.app` into `/Applications`, then launch it. This beta is locally ad-hoc/unsigned; no signing or notarization is claimed.

## Project compatibility and copy migration

- `0.16.0` projects open read-write.
- `0.15.0` projects open read-only. Studio previews a target path and performs migration only after explicit confirmation.
- Migration copies the project into a new directory and new project identity, preserves the origin ID and source protocol, and never rewrites the original.
- Declining migration keeps the original available read-only.
- Older run ZIP takeover remains private-only and is separate from Project Protocol migration.

After migration, reconcile the copy into the local library. The library database is a rebuildable projection; deleting it cannot be used to delete or repair project semantics.

## Verify the upgrade

Check that the version matrix is Open Protocol `0.4.0`, Engine/Project/Plugin `0.16.0`, Studio `0.3.0`, Library/Analysis/Share `0.1.0`, and Semantic Contract `0.3.0`. Then create a temporary two-reference project, complete analysis, build a Skill, fork one child and export a public package. The parent digest must not change, and the public ZIP must contain no reference originals, Vault URI, credential or absolute local path.

## Roll back

Remove the `0.16.0` plugin and install the previously pinned tag. Restore the versioned Studio application backup. Keep `0.16.0` projects intact: older software may open them read-only or reject them, but rollback must not rewrite them. Original `0.15.0` project directories remain the safest rollback source because migration never changed them.

## Known beta boundaries

- No signed/notarized public macOS artifact or official plugin-directory submission.
- X posts require an official developer application and user OAuth; otherwise APSAL uses composer handoff.
- Xiaohongshu is draft plus official-composer handoff and requires external completion confirmation.
- No APSAL cloud account, community feed, comments, moderation service or background import of historical generated images.
