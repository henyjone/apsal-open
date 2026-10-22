# Contributing

Contributions are welcome through GitHub pull requests.

1. Use a globally distinct namespace and stable asset ID.
2. Add semantic version, parent version, changed fields, change summary, rights metadata, and QA status.
3. A single-variable variant changes exactly one declared dotted path.
4. Never submit credentials, personal photos, generated-output archives, photographer imitation mappings, or material without redistribution rights.
5. Run `python3 -m unittest discover -s tests -v`, `python3 scripts/check_docs.py`, and `python3 scripts/release.py --check`.
6. Do not commit `dist/`, plugin ZIPs, or other build outputs. CI rebuilds the current plugin archive from `plugins/apsal-studio/`.
7. Keep `manifest/CURRENT_VERSION_MAP.json` aligned with `pyproject.toml`, the plugin manifest, `apps/apsal-studio/package.json`, and the engine/protocol version constants. Plugin/engine `0.16.0` and Studio Desktop `0.3.0` are separate version lines.
8. Modular packages must conform to `protocol/APSAL_OPEN_PROTOCOL.md`, include SHA-256 for every referenced file, and pass `apsal validate-package`.
9. Public DNA Extension Packs use one contributor-owned namespace, creator-confirmed discovery tags/facets, rights-cleared DNA and previews, resolved dependencies, deterministic checksums, and semantic versions. Validate with `apsal registry validate-pack <zip>` before publishing a pinned GitHub Release asset.

Official namespace changes require maintainer review. Community extensions must not replace any official or installed ID/version, even with similar content. Publish changes as a new version; never replace a Release ZIP in place.
