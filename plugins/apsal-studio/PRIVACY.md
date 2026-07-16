# APSAL Studio privacy

APSAL Studio 0.4 is local-first and ships without accounts, remote authentication, analytics, telemetry, a hosted API, or automatic upload.

The plugin writes creator data only to the current project's `.apsal/` directory and to `~/.apsal/` (or `APSAL_HOME` when configured). Project drafts, generation runs, caches, and the private Vault are ignored by Git by default.

Private character references are copied into the content-addressed local Vault at `~/.apsal/vault/sha256/`. They are not embedded in DNA JSON, exported Skills, releases, or Git commits. The creator is responsible for the rights and consent needed to use any reference they provide.

Image generation is optional. When a creator explicitly confirms generation and Codex ImageGen or another adapter is available, the effective prompt and any deliberately supplied reference are processed under that provider's terms. APSAL records only metadata actually returned by the provider and marks unavailable values as `not_reported`.

Removing a project `.apsal/` directory deletes its local APSAL drafts and run records. Removing `~/.apsal/` deletes personal DNA and Vault content. Make a backup first if those assets should be retained.
