# Frontend System Review v2.0.1

This patch makes the v2 release archive genuinely byte-for-byte reproducible across operating systems and Python/zlib environments.

- UTF-8 text payloads are normalized to LF inside the archive.
- ZIP entries use deterministic stored mode rather than environment-dependent codec output.
- `.gitattributes` fixes repository text checkout semantics.
- A 38th regression test verifies repeated hashes, line endings, storage mode, and the bundled MIT license.

All seven skills and runtime-review behavior are unchanged from v2.0.0.
