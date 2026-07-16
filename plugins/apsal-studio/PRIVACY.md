# APSAL Studio privacy

APSAL Studio 0.12 is local-first and ships without accounts, remote authentication, analytics, telemetry, a hosted API, or automatic upload.

The selected creator-facing language (`zh-CN` or `en`) is stored inside the local design session. Detection uses only the current creator message or brief. APSAL Studio does not read or transmit an operating-system locale, Codex account preference, or remote profile.

The plugin writes creator data only to the current project's `.apsal/` directory and to `~/.apsal/` (or `APSAL_HOME` when configured). Project drafts, generation runs, caches, and the private Vault are ignored by Git by default.

Recommendation memory is stored locally under `~/.apsal/usage/events.jsonl`. It contains stable DNA references, detected controlled tags/facets, outcomes, timestamps, and an optional short note. The raw creative brief is not stored. “Save to My DNA” is always an explicit creator action; selecting a DNA for one project does not silently promote it to the personal Registry.

Five-layer authoring stores the creator-confirmed Content, Emotion, Subject, World, Look, Event, Sequence, Camera, Light, Style, Color/Post, Job and Quality Control decisions inside the current project's local APSAL theme artifact. These decisions are not uploaded by APSAL Studio. The raw brief remains in the local resumable session because it is part of the current project, but it is excluded from cross-project recommendation history.

Installed community packs live under `~/.apsal/extensions/` as read-only Registry layers. Installing a public GitHub pack performs an explicit download from a pinned GitHub Release URL; APSAL does not search, publish, push, or upload to GitHub automatically.

Private references are copied into the content-addressed local Vault at `~/.apsal/vault/sha256/`. They are not embedded in DNA JSON, public releases, or Git commits. The creator is responsible for copyright, portrait consent, attribution, and permitted uses.

A locally exported Codex Prompt/Skill package includes sanitized copies of its bound references so Codex built-in image generation can receive the actual images. The package records every image's SHA-256, purpose, allowed and forbidden uses, rights state, attribution, and redistribution permission. Any unresolved or non-redistributable reference forces `distribution: private_only`; the public packager and release checks reject it. Reference media does not inherit the theme text's CC BY 4.0 license.

When importing a legacy run ZIP or directory, Studio reads only the contained run manifest, Prompt text and candidate image files after path, size, symlink and archive-safety checks. It may search the local private Vault by the run's declared SHA-256 to restore an omitted reference. Imported references and the reconstructed run remain inside the current project's ignored `.apsal/` directory. Imported packages are always `private_only`; historical absolute paths are removed from the new Prompt/Skill package.

Image generation is optional. APSAL Studio does not call an image API and does not request or read `OPENAI_API_KEY`. When a creator explicitly confirms generation, Codex itself sends the current Job's frozen Prompt and permitted references through its built-in image-generation capability under the applicable Codex product terms. APSAL records only metadata actually exposed to the task and marks unavailable model, format, dimensions and provider values as `not_reported`. Requested 9:16, high quality and 2160×3840 are creative targets, not guaranteed returned properties.

Removing a project `.apsal/` directory deletes its local APSAL drafts and run records. Removing `~/.apsal/` deletes personal DNA and Vault content. Make a backup first if those assets should be retained.
