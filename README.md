# APSAL Open

APSAL Open turns photography ideas into reusable, versioned assets instead of one-off prompts. Its canonical chain is:

`DNA catalog → theme JSON → shot compilation → validation → Codex Skill package`

The repository ships `apsal-studio`, a self-contained Codex plugin. Installing one release gives Codex the curated DNA catalog, deterministic compiler, validator, example theme, and Skill packager. No APSAL account or hosted API is required.

## Quick start

```bash
python3 plugins/apsal-studio/scripts/apsal.py catalog
python3 plugins/apsal-studio/scripts/apsal.py validate examples/quiet-window/theme.json
python3 plugins/apsal-studio/scripts/apsal.py compile examples/quiet-window/theme.json -o build/compiled.json
python3 plugins/apsal-studio/scripts/apsal.py pack examples/quiet-window/theme.json -o build
```

Install the repository marketplace in Codex, or download the plugin ZIP from GitHub Releases. Then ask Codex to use `apsal-studio` to create a photography theme.

## Open-source boundaries

- Code and schemas: Apache-2.0.
- DNA definitions, example themes, and documentation: CC BY 4.0; attribution is recorded per asset.
- Credentials, private identity references, generated images, personal media, and assets without documented rights are not accepted.
- Static validation verifies structure and reproducibility. It does not claim that generated images passed human visual QA.

See [CONTRIBUTING.md](CONTRIBUTING.md), [GOVERNANCE.md](GOVERNANCE.md), and [SECURITY.md](SECURITY.md).
