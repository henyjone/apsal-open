# Security policy

Report vulnerabilities privately through GitHub Security Advisories. Do not open a public issue containing credentials, private media, identity anchors, or exploitable details.

Validation, Registry, compilation, and packaging are offline. The optional `openai-image-api` adapter makes a network call only after explicit generation confirmation and reads its credential only from `OPENAI_API_KEY`; packages and run records never contain environment variables or credentials.

Local `private_only` Skill packages may deliberately contain sanitized reference images plus a SHA-256 purpose-and-rights manifest. They must never be committed, uploaded, or released. Public packaging rejects non-redistributable references, and path checks prevent files outside the selected theme/Vault bindings from being added implicitly.
