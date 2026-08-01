# Memory Writes

Guarded memory writes use a proposal file before a card is stored.

```bash
shiroe memory propose "User prefers public-safe copy by default."
shiroe memory write --from proposal.json
```

The write gate checks:

- memory type, privacy class, evidence grade, and source references
- `secret` and `do_not_store` privacy blockers
- unsupported success language
- high-risk same-title contradictions against active cards

Accepted and rejected writes are recorded in `memory/state/events.jsonl`.
Dedicated audit logs are added by the audit subsystem.

Useful card commands:

```bash
shiroe memory list
shiroe memory list --type decision
shiroe memory show mem_2026_07_09_0001
shiroe memory archive mem_2026_07_09_0001
shiroe memory supersede mem_2026_07_09_0001 --with mem_2026_07_09_0002
```
