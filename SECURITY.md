# Security policy

Report vulnerabilities privately through GitHub Security Advisories. Do not open a public issue containing credentials, private media, identity anchors, or exploitable details.

Validation, Registry, compilation, Prompt packaging, and run preparation are offline. APSAL Studio does not contain an image-provider executor, read image API credentials, or send HTTP image-generation requests. After explicit confirmation, Codex—not the local APSAL engine—uses its built-in image-generation capability under the applicable Codex product terms.

Local `private_only` Skill packages may deliberately contain sanitized reference images plus a SHA-256 purpose-and-rights manifest. They must never be committed, uploaded, or released. Public packaging rejects non-redistributable references, and path checks prevent files outside the selected theme/Vault bindings from being added implicitly.

DNA Extension Pack installation accepts local ZIPs or pinned public GitHub Release URLs only. The validator rejects path traversal, symlinks, duplicate paths, checksum drift, oversized expanded content, unresolved dependencies, and any attempt to override an official or installed ID/version. Installation never executes code from a pack; only canonical DNA JSON and validated WebP preview sidecars enter the read-only extension Registry.
