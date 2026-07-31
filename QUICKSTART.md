<!-- privacy-audit: allow-file "Quickstart with example install / env-var / decision commands. No real user data." -->

# Shiroe — Quickstart

5 steps from zero to first decision. Match [INSTALL.md](INSTALL.md) for the
canonical install channels.

---

## 1. Install

```bash
# From the current release (published on PyPI as `shiroe` for URL compat, per D2):
pip install shiroe                    # zero-dependency core
pip install "shiroe[all]"             # with litellm, duckdb, pyyaml
```

Or from this repo:

```bash
git clone https://github.com/kanadhiayash/shiroe
cd shiroe
pip install -e .
```

Verify:
```bash
shiroe --help
shiroe db-status          # shows backend availability
```

---

## 2. Initialise a Project

```bash
cd ~/my-project
shiroe init --name "My Project" --privacy abstract --tier auto --parent ''
```

Scaffolds:
- `config/PROJECT.md`
- `PRIVACY.md`, `REDACT.md`, `SHARING_POLICY.md`
- `config/BUDGET.md`
- `memory/` flat layout (`hot.md`, `index.md`, `DECISIONS.md`, ...)
- `skills/drafts/`

Inspect:
```bash
shiroe status
```

---

## 3. Write Your First Decision

```bash
shiroe write-decision \
  --title "Use PostgreSQL for relational workloads" \
  --why "Better transactional guarantees than MongoDB" \
  --evidence "internal benchmark 2026-06-01" \
  --grade high
```

If input contains PII you'll see `PII scrubbed from inputs: N token(s)` — `shiroe write-decision` scrubs before write.

---

## 4. Grade a Claim

```bash
shiroe grade "PostgreSQL beats MongoDB for relational data"
```

Heuristic without an API key. With `litellm` + key, it's LLM-graded.

---

## 5. Audit

```bash
shiroe audit-privacy --directory memory/   # PII scan
shiroe audit                               # structural validation
```

---

## Daily Loop

```bash
shiroe status            # session start
# ...work...
shiroe write-decision    # capture each decision
shiroe grade <claim>     # grade open questions
# /done in harness consolidates hot.md
```

---

## Cheat Sheet

| Command | Purpose |
|---|---|
| `shiroe init` | Scaffold new project |
| `shiroe status` | hot.md + tier + registry |
| `shiroe write-decision` | Append to DECISIONS.md (scrubs PII) |
| `shiroe grade <claim>` | Evidence grader |
| `shiroe audit-privacy` | Scan for PII hits |
| `shiroe audit` | Structural validation |
| `shiroe db-status` | Backend availability |

---

## Next

- `AGENTS.md` — canonical spec
- `CHANGELOG.md` — release notes
- `GITHUB_OS.md` — per-repo doctrine
- `docs/wiki/` — full documentation
