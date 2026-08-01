# FAQ

Direct answers to the questions engineers ask before adopting Shiroe.

## How do I give an AI agent persistent project memory?

Point every AI tool you use at the same `AGENTS.md` in your project root, and let Shiroe own the files underneath it. `AGENTS.md` is the behavior contract: what a session reads first, what it may write, and what it must stop and ask about.

Because the contract and the memory both live in the repo, adding a second or third tool needs no syncing step. Each session starts with your decisions, open questions, risks, and conflicts already loaded.

## What is local-first LLM memory?

Local-first LLM memory keeps the canonical copy on your machine, in your version control, rather than in a vendor account. Shiroe keeps current state in SQLite, append-only history in JSONL, and human-readable views in Markdown — all inside the project directory.

Nothing is transmitted unless you enable it. Connectors are off by default, and `local-only` mode blocks external transmission outright.

## Is my data sent anywhere?

No, not by default. Memory is written to disk in your project. External sharing is governed by `SHARING_POLICY.md` and requires explicit per-action approval.

Setting privacy mode to `local-only` blocks outbound sync, connector traffic, and handoff push entirely.

## How do I share context between Claude Code, Cursor, and Codex?

Compile a handoff artifact in one tool and open it in the next. The handoff compiler supports five targets: `codex`, `claude`, `cursor`, `github`, and `human`.

Export fails closed. Only atoms explicitly classed public-safe are exported by default; anything unclassified is treated as private and withheld; anything classed local-only never leaves the machine even when private export is requested.

## What is agent memory that survives context loss?

Memory that gets re-read rather than re-explained. Because it is on disk instead of in a context window, closing a session, switching models, or exhausting a context limit does not destroy it.

The next session performs a boundary-first read and resumes from stored state.

## How do I stop an AI assistant from forgetting project decisions?

Store decisions where the assistant reads them at session start, and make contradicting one an event that requires your judgment. Shiroe records each decision with provenance and an evidence grade.

When a later claim conflicts, the write halts rather than overwriting. Both sides are recorded and queued for you to arbitrate.

## What does "boundary-first read" mean?

It means never loading the whole wiki to find one fact. Read `memory/hot.md` first; consult `memory/index.md` only if hot is insufficient; then load only the named section of the named page.

The result is that always-on context stays bounded regardless of how large or old the project gets.

## What happens when a new claim contradicts a stored one?

The write halts, both sides are appended to `memory/CONFLICTS.md` with their provenance, and you arbitrate — immediately or at the end of the session.

Four resolution shortcuts are refused by design: recency-wins, grade-wins, silent-drop, and indefinite-snooze. Each of those decides the question while appearing not to.

## Which AI tools does Shiroe work with?

Any harness that can read a Markdown instruction file can participate. Adapters are registered for Claude Code, Codex, Gemini CLI, Hermes, Kimi Code, Odysseus, and Grok.

Each adapter declares an enforcement level — embedded, sidecar/proxy, or context-only — so the docs never claim more control than the integration actually has.

## Which model providers does Shiroe support?

Shiroe does not call model APIs at all; it is a control plane, not an inference layer. What it does is decide which *class* of model a task is entitled to.

Core code names reasoning classes (`fast`, `balanced`, `deep`, `frontier`, plus the `local` and `private` placement constraints) and never vendor model IDs. Concrete IDs are resolved at the edge from declarative JSON descriptors in `shiroe/adapters/providers/`, shipped for `anthropic` and `openai`. Adding a provider is a config file, not a code change.

## Can two sessions write to the same memory file at once?

No. Writes go through a single-writer path with an advisory lock in `shiroe/lock.py`; a second concurrent writer aborts with a clear error rather than interleaving.

Writes are atomic, so an interrupted write does not leave a half-written file.

## How does redaction work?

Deterministically, in code. `shiroe/privacy.py` applies redaction rules before a write; nothing depends on a model choosing to be careful.

Input is NFKC-normalized, homoglyphs are folded to ASCII, and base64 payloads are decoded before pattern matching, so a credential cannot slip past a rule by changing its encoding.

## Does Shiroe publish benchmark scores?

No. Loaders exist for five public suites — LoCoMo, LongMemEval, PersonaMem, RULER, and HELMET — but no dataset runs have been performed and no scores exist.

The internal suite under `benchmarks/` scores the repo against its own rubric on internal quality axes used as release gates. Those are not benchmark rankings and are not comparable to another system's numbers.

## What are the guards?

Five checks on the write path: `fact_guard`, `evidence_guard`, `privacy_guard`, `contradiction_guard`, and `write_gate`. A claim that fails any of them does not reach the store.

`fact_guard` rejects unsupported superlatives and unsourced absolutes — which is why this documentation avoids them.

## How do I add a new skill?

Prefer not to write one by hand. Let `pattern-observer` surface a candidate from repeated work, let `pattern-to-skill` draft it, then approve it via `/review-skill`. Drafts land in `skills/drafts/` and are never auto-activated.

If you do write one manually, add it under `skills/<name>/SKILL.md` with proper frontmatter, register it, and run `python3 scripts/shiroe-validate.py`.

## How are team packs different from skill stacks?

A team pack is an on-demand multi-agent configuration you activate with `/team`. A skill stack is the specific set of skills selected for the task at hand.

When a pack is active, the stack is drawn from that pack's roster. See [[Team-Packs]].

## Where do decisions get logged?

Confirmed decisions go to `memory/DECISIONS.md` with provenance and an evidence grade. Shipped releases are recorded in `CHANGELOG.md`.

Conflicts awaiting your arbitration live separately in `memory/CONFLICTS.md`.

## Related

- [[Installation]] — setup and verification
- [[Architecture]] — full system
- [[Memory-Model]] — store invariant and read discipline
- [[Privacy-Model]] — modes and redaction classes
- [[Glossary]] — terms used here
