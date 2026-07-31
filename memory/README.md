# memory/

Local memory layer. Populated per-user-project — never bundled in this repo.

Bootstrap a fresh memory tree with:

```bash
python3 -m shiroe init
```

After init, this directory holds:

- `hot.md` — last few sessions, current context (≤500 words, read first)
- `index.md` — domain index across the flat memory files
- `DECISIONS.md`, `RISKS.md`, `OPEN_QUESTIONS.md`, `CONFLICTS.md` — durable project memory registers
- `MEMORY.md` — agent-written session notes
- `patterns/PATTERNS.jsonl` — append-only event log
- `raw/`, `snapshots/`, `sync/` — local-only working state

All entries are governed by `PRIVACY.md` + `REDACT.md` at the repo root. Default privacy mode is `abstract` — `privacy-abstraction` rewrites sensitive content before any write.
