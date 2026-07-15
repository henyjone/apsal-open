<p align="center">
  <img src="assets/brand/apsal-readme-banner.jpg" alt="APSAL — Open Photography Protocol" width="100%">
</p>

<h1 align="center">APSAL — Open Photography Protocol</h1>

<p align="center">
  Turn a creative brief into versioned photography DNA, independent shot jobs, validated JSON, and an installable Codex Skill.
</p>

<p align="center">
  <a href="https://github.com/henyjone/apsal-open/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/henyjone/apsal-open/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/henyjone/apsal-open/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/henyjone/apsal-open?color=78988A"></a>
  <a href="LICENSE"><img alt="Code license" src="https://img.shields.io/badge/code-Apache--2.0-B79A62"></a>
  <a href="CONTENT_LICENSE.md"><img alt="Content license" src="https://img.shields.io/badge/content-CC%20BY%204.0-78988A"></a>
  <a href="protocol/APSAL_OPEN_PROTOCOL.md"><img alt="Protocol" src="https://img.shields.io/badge/protocol-APSAL%20Open%200.2-F1EEE4?labelColor=111412"></a>
  <a href="plugins/apsal-studio"><img alt="Codex plugin" src="https://img.shields.io/badge/Codex-APSAL%20Studio-78988A"></a>
</p>

<p align="center">
  <a href="#install-the-codex-plugin"><strong>Install Plugin</strong></a> ·
  <a href="#30-second-start"><strong>Quick Start</strong></a> ·
  <a href="protocol/APSAL_OPEN_PROTOCOL.md"><strong>Read Protocol</strong></a> ·
  <a href="README.zh-CN.md"><strong>中文文档</strong></a>
</p>

---

## What is APSAL?

APSAL is a vendor-neutral protocol and offline reference engine for modular, reproducible, and traceable AI photography. Instead of hiding an entire photo set inside one giant prompt, APSAL separates identity, world, style, wardrobe, emotion, events, camera, light, color, content, sequence, and per-image Jobs into versioned assets.

```mermaid
flowchart LR
    A["Creative idea"] --> B["DNA Registry"]
    B --> C["APSAL Protocol"]
    C --> D["Independent Shot Jobs"]
    D --> E["Validated JSON"]
    D --> F["Installable Skill"]
```

| Protocol | Registry | Execution | Trust | Delivery |
|---|---|---|---|---|
| 13 modular roles | Bundled offline DNA | One Job, one image | Rights, lineage, SHA-256 | JSON and Codex Skill ZIP |

## Install the Codex plugin

The Git marketplace is the recommended path. It installs the protocol, DNA Registry, validator, compiler, templates, and Skill packager together.

```bash
codex plugin marketplace add henyjone/apsal-open --ref main
codex plugin add apsal-studio@apsal-open
```

Restart Codex or open a new task after installation. You can also download the pinned ZIP from the [latest release](https://github.com/henyjone/apsal-open/releases/latest).

## 30-second start

Ask Codex:

> Use APSAL Studio to create a nine-shot Eastern-minimalist window portrait theme. Keep one fictional adult identity, make every shot narratively distinct, validate the package, and export an installable Skill.

APSAL Studio will:

1. Select exact, versioned assets from the bundled DNA Registry.
2. Create independent shot definitions with identity and continuity locks.
3. Validate rights, lineage, checksums, filenames, and output rules.
4. Export canonical JSON, compiled shot prompts, and a reproducible Skill ZIP.

Expected artifacts:

```text
theme.json
compiled.json
your-theme-1-0-0.zip
your-theme-1-0-0.zip.sha256
```

## Use the engine directly

No account, hosted API, or model key is required for validation and packaging.

```bash
python3 plugins/apsal-studio/scripts/apsal.py catalog
python3 plugins/apsal-studio/scripts/apsal.py validate examples/quiet-window/theme.json
python3 plugins/apsal-studio/scripts/apsal.py compile examples/quiet-window/theme.json -o build/compiled.json
python3 plugins/apsal-studio/scripts/apsal.py pack examples/quiet-window/theme.json -o build
python3 plugins/apsal-studio/scripts/apsal.py validate-package path/to/extracted-package
```

## Choose your path

| Creator | Developer | Contributor |
|---|---|---|
| Describe a theme in Codex and receive a validated package. | Build against the [protocol](protocol/APSAL_OPEN_PROTOCOL.md), [schemas](plugins/apsal-studio/assets/schemas), and offline CLI. | Submit original DNA through the [DNA template](https://github.com/henyjone/apsal-open/issues/new?template=dna-submission.yml) and follow [CONTRIBUTING.md](CONTRIBUTING.md). |

## Open does not mean unlicensed

The protocol and reference engine are Apache-2.0. Official starter DNA and examples are CC BY 4.0. An individual theme is public only when it carries its own license, attribution, provenance, version lineage, checksums, and honest QA state. Private references, credentials, personal media, and unlicensed source material are excluded.

Static validation proves structure and reproducibility—not generated-image quality. Visual QA requires human evidence.

## Project map

- [APSAL Open Protocol](protocol/APSAL_OPEN_PROTOCOL.md)
- [APSAL Studio plugin](plugins/apsal-studio)
- [Starter DNA Registry](plugins/apsal-studio/assets/dna/catalog.json)
- [Example theme](examples/quiet-window/theme.json)
- [Contribution guide](CONTRIBUTING.md)
- [Governance](GOVERNANCE.md)
- [Security policy](SECURITY.md)
- [Latest release](https://github.com/henyjone/apsal-open/releases/latest)

<p align="center"><strong>Ideas become assets. Assets become reproducible photo systems.</strong></p>
