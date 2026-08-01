# EvidenceGuard

EvidenceGuard makes evidence quality visible for memory cards and public docs.

Evidence grades:

- `A`: Direct primary source, exact, current
- `B`: Repo file, project doc, or user-confirmed source
- `C`: User-provided claim, not independently verified
- `D`: Model inference from partial context
- `F`: Unsupported, contradicted, or unsafe

Commands:

```bash
shiroe evidence grade memory/hot.md
shiroe evidence check memory/
shiroe evidence list --grade D
shiroe evidence upgrade mem_2026_07_09_0001 --source docs/ARCHITECTURE.md
shiroe evidence report
```

Release blockers include grade `D` or `F` claims in public docs, missing source
references on factual memory cards, unsupported capability claims, and
benchmark claims without dated reproducible evidence.
