# RFC-0011 — Single APSAL Project Kernel and Dual Entry

Status: implemented in APSAL Engine / Codex plugin 0.15.0 and APSAL Studio Desktop 0.2.0.

## Decision

Codex and APSAL Studio operate one `<project>/.apsal/` project. Python APSAL Engine is the only executor for the five layers, thirteen roles, DNA, reference rights, invalidation, Prompt compilation, generation Runs, QA, and final packaging. Codex is the conversational entry; Studio is a discardable node projection plus `.apsal/studio/view.json`.

Every semantic mutation carries `expected_revision` and `operation_id`. The Engine serializes it with a project lock, rejects stale revisions, journals crash recovery, writes atomically, increments `project.json.revision`, and replays an already recorded operation without duplicating content. View-only mutations do not increment semantic revision and do not affect theme or Prompt digests.

## Domain surface

- `project.init`, `project.open`, `project.snapshot`, `project.undo`
- `design.start`, `design.present`, `design.language`, `design.propose`, `design.commit_preview`, `design.reject_preview`, `design.commit_layer`, `design.finalize`
- `generation.start`, `generation.next`, `generation.record`, `qa.record`
- `studio.view.get`, `studio.view.save`

The same dispatcher is exposed in-process to the Codex MCP and as line-delimited stdio JSON-RPC to the Electron sidecar. Contract tests replay every operation through both paths and compare snapshots, revisions, theme digests, package bytes, and SHA-256.

## Studio link

Codex linkage is off by default. When enabled, Studio creates an authenticated HTTP bridge bound only to `127.0.0.1`. Its bearer token is stored in a mode-0600 descriptor, rotates on every bridge start, and disappears when the bridge stops. The bridge binds requests to Studio's current project and rejects project switching or protocol-incompatible writes.

The thirteen role nodes have stable `protocol_element_id`, `layer_id`, and `role_id`. They cannot be deleted or semantically edited inside the projection cache. Proposed changes appear as non-Prompt ghost nodes until the creator confirms the whole layer. Upstream confirmation invalidates downstream layers in the Engine, so Codex and Studio receive the same new snapshot.

## Packaging and compatibility

`finalize_theme` is the only finalization path. The deterministic Prompt/Skill ZIP excludes Studio view state. APSAL Studio 0.2.0 creates or opens only directory-based APSAL 0.15 projects; it does not migrate `.aiproject`, legacy IndexedDB workflows, or old Studio import formats.
