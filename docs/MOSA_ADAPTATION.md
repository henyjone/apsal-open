# MOSA adaptation boundary

APSAL uses the MOSA commit pinned in [third-party notices](../THIRD_PARTY_NOTICES.md)
as the design source for the local gallery and archive projection. The
adaptation is intentionally narrow.

| MOSA idea | APSAL implementation | Semantic authority |
| --- | --- | --- |
| Local asset database | `~/.apsal/library/library.sqlite3` | Rebuildable projection only |
| Content-addressed archive | `~/.apsal/library/objects/<sha-prefix>/<sha>.<ext>` | Original `.apsal/runs` record |
| Gallery, search, favorite, archive | APSAL Studio project library | `.apsal/project.json` plus library-only view metadata |
| Source/provenance links | `project_assets` join and project lineage | `.apsal/project.json` lineage and run records |
| Thumbnail/cover browsing | Restricted `apsal-media:` protocol | Library cover projection |

Not imported:

- the MOSA standalone HTTP service or web application;
- Cowart discovery, bridge, or canvas code;
- the Node 22 runtime requirement;
- automatic scanning of `~/.codex/generated_images` or Codex task history;
- MOSA account, settings, or API routes.

APSAL Studio is packaged with the APSAL Python sidecar, including
`apsal_creative.py`. A creator does not install MOSA, Cowart, or Node 22 to use
the packaged application. Headless Codex/MCP calls use the same Engine without
launching Studio.
