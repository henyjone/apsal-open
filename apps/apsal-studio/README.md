# APSAL Studio 0.2.0

APSAL Studio is the visual desktop frontend for the APSAL Open Codex plugin. It does not maintain a second creative database and it does not run an image provider.

## Product boundary

- `<project>/.apsal/` is the only semantic source of truth.
- Codex owns the creative conversation, formal generation flow, and model visual QA.
- Studio visualizes the five layers and thirteen protocol roles, shows Codex change previews, and lets the creator confirm, reject, focus, undo, and arrange nodes.
- Node geometry is stored only in `.apsal/studio/view.json`; it cannot change the project revision, Prompt digest, or final ZIP.
- Old AiPhoto projects, `.aiproject`, IndexedDB drafts, local workflow persistence, ComfyUI, MLX, models, and provider credentials are intentionally unsupported.

## Interface model

Studio 0.2.0 keeps the original APSAL Studio warm-light photography-desk visual language while narrowing the product to the Codex protocol frontend:

- the top bar identifies the current APSAL set, Engine revision, and Codex connection;
- the left panel shows project controls and the five protocol layers;
- the center canvas projects the thirteen stable roles and supports selection, keyboard movement, zoom, and automatic layout;
- the right panel separates read-only element properties from Codex link, preview confirmation, and operation history;
- both side panels can be collapsed or resized with pointer drag or arrow keys.

## Development

Requirements: Node.js 22 and Python 3.11+.

```bash
cd apps/apsal-studio
npm ci
npm run build
npm test -- --run
npm run test:electron
npm run desktop:start
```

`npm run prepare:engine` copies the tested Engine and Protocol from `plugins/apsal-studio` into the ignored `.build/apsal-engine` directory. The app never keeps an independently authored Engine copy.

An existing APSAL 0.15 project can be opened directly when Studio starts. This is useful for Codex launchers and local integration checks; it does not enable the Codex link automatically.

```bash
open -a "APSAL Studio" --args --project-root "/absolute/path/to/project"
```

## Codex link

The link is disabled by default. When the creator enables it, Studio:

- listens only on `127.0.0.1` using a random port;
- creates a new 32-byte token for the current process;
- writes a mode-0600 descriptor under `~/.apsal/frontend-link.json`;
- accepts only the APSAL domain-method allowlist;
- binds every request to the project currently open in Studio;
- refuses incompatible semantic writes and never exposes arbitrary filesystem or process access.

See [RFC-0011](../../protocol/RFC-0011-SINGLE-PROJECT-DUAL-ENTRY.md) and the [0.15.0 upgrade specification](../../docs/UPGRADE_GUIDE_0.15.0.zh-CN.md) for the complete contract.

## License

Studio source code is covered by the repository Apache-2.0 license. No model, native runtime, generated photograph, private reference, or AiPhoto case image is included.
