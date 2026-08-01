# Pattern Detection

> Imagine your editor noticing you run the same five-step ritual every week, and offering — but never imposing — a macro. That is what pattern detection does.

Shiroe extends itself only through review-first drafts. Repeated work is surfaced as a candidate, drafted into a skill, and held for your approval. Nothing self-installs.

## The loop

```
session events → append-only event log
    → pattern-observer scans a rolling window
    → cluster similar task signatures
    → score and surface top candidates
    → pattern-to-skill drafts a SKILL.md into skills/drafts/
    → user reviews via /review-skill (approve / edit / reject / defer)
    → approved drafts are promoted, preserving history
```

The observer runs in the background and never blocks active work.

## Why drafts are never auto-activated

A system that writes its own skills and then runs them can change its behavior without anyone deciding that it should. The review step is where a person decides whether a repeated pattern is a workflow worth codifying or a bad habit worth breaking.

Automation that proposes is useful. Automation that installs is a governance problem.

## The Two-Strikes Rule

**Do not codify a rule on the first occurrence of an error.** Wait for the second.

| Occurrence | Action |
|---|---|
| First | Log it as a trap noticed. |
| Second | Promote it to a rule. |

One occurrence is noise. Two is a pattern. Codifying on the first produces brittle rules that encode a coincidence and then have to be maintained forever.

See [`references/two-strikes-rule.md`](https://github.com/kanadhiayash/shiroe/blob/main/references/two-strikes-rule.md).

## How candidates are found

The observer scans the append-only event log over a rolling window and looks for repeated task shapes:

1. **Signature** — each task is reduced to a verb, a subject, and qualifier n-grams, with stop-words stripped.
2. **Similarity** — signatures are compared by n-gram overlap against a similarity threshold.
3. **Clustering** — similar signatures are grouped; clusters below the minimum member count are discarded.
4. **Scoring** — clusters are ranked by frequency weighted against how tightly they are spaced in time, so dense recent repetition outranks a slow trickle.
5. **Surfacing** — the top-ranked candidates are emitted; the rest are logged as suppressed rather than dropped, so nothing disappears silently.
6. **Deduplication** — an existing candidate is updated with new members rather than duplicated.

The thresholds are what keep this from being noise: a cluster has to recur enough times, closely enough together, and similarly enough in shape to count.

## Review

```
/review-skill
```

Each draft can be approved, edited, rejected, or deferred. Approved drafts are promoted from `skills/drafts/` into the active skill directory in a way that preserves their history.

A rejected draft stays rejected — the observer does not re-propose it on the next scan simply because the underlying work recurred again.

## Disabling it

Pattern detection can be turned off in `config/BUDGET.md`:

```yaml
pattern_detection: false
```

## Related

- [[Memory-Model]] — the event log pattern detection reads
- [[Architecture]] — where skills sit in the system
- [[Glossary]] — Two-Strikes Rule, review-first extension
