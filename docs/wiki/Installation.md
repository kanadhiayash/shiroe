# Installation

> **Zeref is not an operating system.** It is a local-first memory and context layer that plugs into an AI harness you already use. The repository and plugin identifier is `zeref-os`; the product is **Zeref Memory Engine**.

Zeref v3.0.0-alpha.1 installs as a Claude Code plugin. Other harnesses read `AGENTS.md` directly through a thin per-harness stub.

## Claude Code

### Install

```bash
claude plugin marketplace add kanadhiayash/zeref-os
claude plugin install zeref-os@zeref-os
```

The plugin lands at `~/.claude/plugins/cache/zeref-os/zeref-os/`.

### Verify

```bash
claude plugin list | grep zeref-os
# zeref-os@zeref-os  v3.0.0-alpha.1  enabled

cd ~/my-project
claude
> /zeref-os:start
```

A successful boot reports the project name, the last session timestamp, counts of active decisions, open questions, and unresolved conflicts, the active privacy mode, and the always-on context size.

### Run the validator

```bash
cd ~/.claude/plugins/cache/zeref-os/zeref-os
python3 scripts/shiroe-validate.py
```

The validator checks that every registered skill, agent, command, and team pack resolves on disk, that the root privacy files are present, that harness stubs are intact, that the memory layout is well-formed, and that the append-only event log passes its schema lint. It prints a per-surface tally and exits non-zero on any finding.

## Other harnesses

Each harness reads its own stub, and every stub defers to `AGENTS.md`.

| Harness | Reads |
|---|---|
| Claude Code | `AGENTS.md` (via plugin) |
| Codex | `AGENTS.md` natively |
| Cursor | `.cursor/rules/shiroe.mdc` |
| Gemini CLI | `GEMINI.md` |
| Hermes | `AGENTS.md` natively |
| Kimi Code | `AGENTS.md` natively |
| Odysseus | `AGENTS.md` natively |
| Grok | `GROK.md` |

Adapters report an enforcement level — embedded, sidecar/proxy, or context-only — so you can see how much Zeref can actually govern each one. See [[Architecture]].

Full per-harness detail: [`references/harness-translation-map.md`](https://github.com/kanadhiayash/zeref-memory-engine/blob/main/references/harness-translation-map.md).

## Standalone (any harness)

Clone into the project and point your tool at the contract:

```bash
git clone https://github.com/kanadhiayash/zeref-memory-engine.git .zeref
```

```text
.shiroe/AGENTS.md
```

## Per-project setup

On the first `/zeref-os:start` in a project with no `config/PROJECT.md`, the `project-setup` skill runs an interview and captures:

- project name and optional parent project
- privacy mode (defaults to `abstract`)
- budget warning threshold

It then writes `config/PROJECT.md`, the root privacy files (`PRIVACY.md`, `REDACT.md`, `SHARING_POLICY.md`), `config/PERMISSIONS.md`, `config/BUDGET.md`, and — if a parent was named — `config/PARENT_SYNC.md`.

If you cancel mid-interview, Zeref boots read-only until the configuration is complete. It does not guess at values you did not supply.

## Python runtime

The `shiroe/` runtime provides the CLI and structured queries:

```bash
cd ~/.claude/plugins/cache/zeref-os/zeref-os
pip install -e .
python3 -m shiroe --help
```

Core commands:

```
zeref status              summarize current memory state
zeref write-decision      append a decision through the guarded write path
zeref grade <claim>       grade evidence for a claim
zeref audit               structural validation and privacy audit
zeref init                scaffold memory and config
zeref db-status           report storage backend availability
```

## Verify the install end to end

```bash
python3 -m shiroe --version
python3 scripts/shiroe-validate.py
python3 scripts/check-version-consistency.py
python3 -m pytest -q
python3 benchmarks/run-all.py
```

The version is read from `shiroe/VERSION`, which is the single source of truth; `check-version-consistency.py` fails if any surface disagrees with it.

## Uninstall

```bash
claude plugin uninstall zeref-os@zeref-os
```

Your project's `memory/` and `config/` files are left intact — Zeref archives rather than hard-deletes. To purge them yourself:

```bash
rm -rf memory/ config/PROJECT.md PRIVACY.md REDACT.md SHARING_POLICY.md
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `unknown event type` in event-log lint | A custom event type was written | Add it to the event schema in `scripts/shiroe-validate.py`, or rename the event |
| Handoff artifact not produced on tool switch | Handoff compilation was skipped | Confirm the session ended through `/stop` and that the target is one of the five supported |
| Handoff blocked on a path containing a look-alike character | Homoglyph guard fired during normalization | Replace with ASCII, or confirm explicitly if intentional |
| Validator reports a missing surface | Partial install or renamed directory | Re-run the install; adapters and skills must resolve from the registry |
| Version check fails | A surface disagrees with `shiroe/VERSION` | Update the surface; never add a second source of version truth |

## Related

- [[Architecture]] — system overview
- [[Memory-Model]] — what lands on disk
- [[Privacy-Model]] — configure privacy before first write
- [[FAQ]] — common questions
- [`AGENTS.md`](https://github.com/kanadhiayash/zeref-memory-engine/blob/main/AGENTS.md) — canonical contract
