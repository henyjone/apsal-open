# Contributing

Contributions are welcome through GitHub pull requests.

1. Use a globally distinct namespace and stable asset ID.
2. Add semantic version, parent version, changed fields, change summary, rights metadata, and QA status.
3. A single-variable variant changes exactly one declared dotted path.
4. Never submit credentials, personal photos, generated-output archives, photographer imitation mappings, or material without redistribution rights.
5. Run `python3 -m unittest discover -s tests -v` and `python3 scripts/release.py --check`.
6. Modular packages must conform to `protocol/APSAL_OPEN_PROTOCOL.md`, include SHA-256 for every referenced file, and pass `apsal validate-package`.
7. Public DNA Extension Packs use one contributor-owned namespace, creator-confirmed discovery tags/facets, rights-cleared DNA and previews, resolved dependencies, deterministic checksums, and semantic versions. Validate with `apsal registry validate-pack <zip>` before publishing a pinned GitHub Release asset.

Official namespace changes require maintainer review. Community extensions must not replace any official or installed ID/version, even with similar content. Publish changes as a new version; never replace a Release ZIP in place.
