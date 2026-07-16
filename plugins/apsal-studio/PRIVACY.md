# APSAL Studio privacy

APSAL Studio 0.6 is local-first and ships without accounts, remote authentication, analytics, telemetry, a hosted API, or automatic upload.

The plugin writes creator data only to the current project's `.apsal/` directory and to `~/.apsal/` (or `APSAL_HOME` when configured). Project drafts, generation runs, caches, and the private Vault are ignored by Git by default.

Recommendation memory is stored locally under `~/.apsal/usage/events.jsonl`. It contains stable DNA references, detected controlled tags/facets, outcomes, timestamps, and an optional short note. The raw creative brief is not stored. “Save to My DNA” is always an explicit creator action; selecting a DNA for one project does not silently promote it to the personal Registry.

Installed community packs live under `~/.apsal/extensions/` as read-only Registry layers. Installing a public GitHub pack performs an explicit download from a pinned GitHub Release URL; APSAL does not search, publish, push, or upload to GitHub automatically.

Private references are copied into the content-addressed local Vault at `~/.apsal/vault/sha256/`. They are not embedded in DNA JSON, public releases, or Git commits. The creator is responsible for copyright, portrait consent, attribution, and permitted uses.

A locally exported theme Skill includes sanitized copies of its bound references so the selected image provider can receive the actual images. The package records every image's SHA-256, purpose, allowed and forbidden uses, rights state, attribution, and redistribution permission. Any unresolved or non-redistributable reference forces `distribution: private_only`; the public packager and release checks reject it. Reference media does not inherit the theme text's CC BY 4.0 license.

Image generation is optional. When a creator explicitly confirms generation, the effective Prompt and every reference bound to that Job are processed under the selected provider's terms. Native 2160×3840 execution uses the optional OpenAI Image API adapter and reads `OPENAI_API_KEY` only from the process environment. The key is never written to a theme, Skill, run record, or log. APSAL records only metadata actually returned by the provider and marks unavailable values as `not_reported`.

Removing a project `.apsal/` directory deletes its local APSAL drafts and run records. Removing `~/.apsal/` deletes personal DNA and Vault content. Make a backup first if those assets should be retained.
