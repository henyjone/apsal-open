# RFC-0012 — Creative Project Library, Reference Analysis and Confirmed Sharing

Status: implemented in APSAL Open Protocol 0.4.0, Engine/Project Protocol and Codex plugin 0.16.0, APSAL Studio Desktop 0.3.0, and Library/Analysis/Share schemas 0.1.0.

## Decision

APSAL treats a rights-scoped group of 1–24 references as one root creative project. Every subsequent creative direction is a child project, not an in-place overwrite. `<project>/.apsal/` remains authoritative; `~/.apsal/library/` is a rebuildable cross-project index, thumbnail cache and content-addressed output archive.

The Engine owns validation, lineage, revisions, packaging and confirmation state. Codex performs visual understanding and image generation through explicit Jobs. Studio is the project-library and editorial projection over the same Engine. The Engine does not call external vision or image providers.

## Project and analysis model

`project.json` declares `root`, `fork` or `imported` plus parent/origin IDs, source assets, fork type and parent snapshot digest. A fork copies the permitted design state into a new directory and verifies that the parent's semantic digest is unchanged.

Each reference records source, copyright/attribution, portrait consent, redistribution, AI-modification and identity permissions. Analysis separates observable facts from creative inference, records uncertainty/risk, covers all thirteen roles per image, and ends with set-level visual DNA, conflicts, complements and recommended directions. APSAL never performs person identification. Identity locking requires explicit authorization.

Analysis Jobs are schema-bound, resumable and idempotent. A failed Job can be retried; a completed result cannot become a silent duplicate. `design.build_from_analysis` is allowed only after the required image and synthesis Jobs are complete.

## Domain surface

- Project: `project.create_from_references`, `project.fork`, `project.export`, `project.import`, `project.migration_preview`, `project.migrate`
- Analysis: `analysis.start`, `analysis.next`, `analysis.record`, `analysis.status`, `design.build_from_analysis`
- Library: `library.status`, `library.reconcile`, `library.list`, `library.get`, `library.update`, `library.archive`, `library.lineage`
- Share: `share.draft`, `share.preview`, `share.confirm`, `share.publish`, `share.status`

All semantic mutations retain the revision and operation-ID guarantees of [RFC-0011](RFC-0011-SINGLE-PROJECT-DUAL-ENTRY.md). Library-only display metadata cannot alter Prompt or project digests.

## Export and privacy

A public package contains the APSAL theme, positive and negative Prompts, QA, analysis summary, Skill, checksums, import manifest and static showcase. It excludes private media, Vault URIs, credentials and absolute paths. Original references are absent by default and are eligible only with explicit redistribution permission plus a second public-release confirmation.

A private backup may include sanitized, authorized references and complete run history. Import always creates a new local project ID and retains the source project ID, package digest and provenance.

## Confirmed social delivery

`share.preview` freezes selected images, copy, platform, permissions and their digest. `share.confirm` returns a token bound to that unchanged digest. Editing any input invalidates the token.

X may use official OAuth, media upload and post creation when credentials exist in macOS Keychain; otherwise the Engine returns exported media/copy and the official composer URL. Generated media requests the platform AI label where supported. Xiaohongshu always uses official-composer handoff in this version and remains `awaiting_external_confirmation` until completion is separately confirmed. Opening a composer is never publication.

## Compatibility

Projects at 0.15.0 open read-only until the creator previews and explicitly confirms a copy migration. The source directory is never rewritten. Declining migration keeps read-only access. This RFC does not introduce an APSAL cloud account, community feed, comments, moderation backend or unattended import of historical generated images.
