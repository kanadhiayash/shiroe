# PrivacyGuard

PrivacyGuard exposes the existing deterministic scrubber as a first-class guard
surface.

It can scan project files, classify text, and print suggested redactions without
making external calls. Product commands remain local-first.

Commands:

```bash
shiroe privacy scan docs/
shiroe privacy classify "public-safe copy"
shiroe privacy redact docs/example.md --suggest
shiroe privacy report --format json
```

Credential-shaped material is classified as `secret` and blocks guarded memory
writes. Other sensitive classes should be abstracted before public release.
