# FactGuard

FactGuard is a deterministic local scanner for unsupported public claims.

It flags:

- unsupported superlatives
- superiority claims without proof
- release-maturity claims without proof
- benchmark claims without dated reproducible evidence
- broad success claims with no named evidence
- factual claims with no source references

Commands:

```bash
shiroe factguard scan README.md
shiroe factguard scan docs/
shiroe factguard check --claim "Shiroe is ready for every team."
shiroe factguard report --format md
```

FactGuard suggests safer, bounded wording instead of making marketing claims.
