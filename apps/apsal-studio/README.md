# APSAL Studio 0.3.0

APSAL Studio is the creative project library and visual desktop frontend for the APSAL Open Codex plugin. It does not maintain a second semantic database and it does not run an image provider.

## Product boundary

- `<project>/.apsal/` is the only semantic source of truth.
- Codex owns the creative conversation, formal generation flow, and model visual QA.
- Studio creates rights-scoped multi-reference root projects, then visualizes the five layers and thirteen protocol roles, Codex change previews, lineage, exports, and confirmed share drafts.
- `~/.apsal/library/` stores only a rebuildable SQLite index and content-addressed output objects; it never supersedes project state.
- Node geometry is stored only in `.apsal/studio/view.json`; it cannot change the project revision, Prompt digest, or final ZIP.
- Old AiPhoto projects, `.aiproject`, IndexedDB drafts, local workflow persistence, ComfyUI, MLX, models, and provider credentials are intentionally unsupported.

## Interface model

Studio 0.3.0 keeps the original APSAL Studio warm-light photography-desk visual language and adds the creative library without replacing the workflow with a generic dashboard:

- the project-library home provides covers, search, tags, favorites, archive state, lineage, analysis progress, package export, and social previews;
- the reference-project sheet records copyright, portrait, redistribution, AI-modification, and identity permissions before automation;
- the top bar identifies the current APSAL set, Engine revision, and Codex connection;
- the left panel shows project controls and the five protocol layers;
- the center canvas projects the thirteen stable roles and supports selection, keyboard movement, zoom, and automatic layout;
- the right panel separates read-only element properties from Codex link, preview confirmation, and operation history;
- both side panels can be collapsed or resized with pointer drag or arrow keys.

## Development

Development requirements: Node.js 22 and Python 3.11+. The packaged macOS application embeds the tested Python sidecar and does not require a separate MOSA, Cowart, or Node installation.

```bash
cd apps/apsal-studio
npm ci
npm run build
npm test -- --run
npm run test:electron
npm run desktop:start
```

`npm run prepare:engine` copies the tested Engine and Protocol from `plugins/apsal-studio` into the ignored `.build/apsal-engine` directory. The app never keeps an independently authored Engine copy.

An existing APSAL 0.15 project opens read-only. Use the explicit previewed copy migration to create a 0.16 project; rejecting migration never rewrites the original. Opening Studio by itself never enables Codex linkage.

```bash
open -a "APSAL Studio" --args --project-root "/absolute/path/to/project"
```

Codex launches the authenticated projection only after the creator chooses it in the APSAL plugin:

```bash
"/Applications/APSAL Studio.app/Contents/MacOS/APSAL Studio" --project-root "/absolute/path/to/project" --codex-link
```

## Codex link

The link is disabled by default and has no manual UI switch. When the creator starts or resumes APSAL creation in Codex and chooses “Open and link”, the plugin launches Studio with the current project. Studio then:

- listens only on `127.0.0.1` using a random port;
- creates a new 32-byte token for the current process;
- writes a mode-0600 descriptor under `~/.apsal/frontend-link.json`;
- accepts only the APSAL domain-method allowlist;
- binds every request to the project currently open in Studio;
- refuses incompatible semantic writes and never exposes arbitrary filesystem or process access.

See [RFC-0011](../../protocol/RFC-0011-SINGLE-PROJECT-DUAL-ENTRY.md), the [0.16 release notes](../../docs/releases/0.16.0.md), and the [MOSA adaptation boundary](../../docs/MOSA_ADAPTATION.md) for the complete contract.

## License

Studio source code is covered by the repository Apache-2.0 license. MOSA-derived local-library designs retain their MIT notice in [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md). No model, generated photograph, private reference, or AiPhoto case image is included.
