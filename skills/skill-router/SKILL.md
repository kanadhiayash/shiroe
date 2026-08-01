---
name: skill-router
description: Auto-gate #2. Classifies task domain (memory / privacy / wiki / decision / draft / handoff / setup / sync) and maps it to the smallest useful skill stack (1 lead + 2-3 support + 1 QA gate). Declares the chosen stack inline before any work begins. User may override. Never activates all 10 skills.
trigger:
  - "every major task"
  - "task domain detected"
  - after budget-governor gate passes
  - "what skills should run for this"
  - "route this task"
model: haiku
reasoning_class: fast
max_turns: 8
---

# skill-router

## Mission

Auto-gate #2 of the v2.6 four-gate chain. Choose the smallest set of Shiroe skills + extended tools that can deliver the task. Block fan-out across all 10 skills (anti-pattern). Declare the stack inline so the user can redirect before tokens are spent.

## Domain → smallest-useful-stack matrix

| Domain signals | Lead | Support (2-3) | QA gate | Extended-tool hint |
|---|---|---|---|---|
| Memory write (decision, fact, claim, evidence) | `memory-keeper` | `evidence-grader`, `wiki-maintenance` | `privacy-guardian` | — |
| Privacy / redaction / sharing-policy change | `privacy-guardian` | `privacy-abstraction`, `memory-keeper` | `evidence-grader` | — |
| Wiki consolidation / index refresh / hot.md rebuild | `wiki-maintenance` | `memory-keeper`, `evidence-grader` | `privacy-guardian` | — |
| Decision arbitration / conflict surfaced | `contradiction-resolution` | `evidence-grader`, `memory-keeper` | `privacy-guardian` | — |
| New skill draft from pattern | `pattern-to-skill` | `evidence-grader`, `wiki-maintenance` | user `/review-skill` | — |
| Cross-harness / model-switch handoff | `handoff-compiler` | `privacy-abstraction`, `evidence-grader` | `privacy-guardian` | caveman-handoff (if v2.6+ Session C shipped) |
| First-run project setup / config missing | `project-setup` | `memory-keeper` | `privacy-guardian` | — |
| Parent sync / import / export | `parent-sync` or `memory-import-export` | `privacy-abstraction`, `evidence-grader` | `privacy-guardian` | — |
| Code-heavy / multi-file refactor / build | (no Shiroe lead) | `memory-keeper` for decisions | `evidence-grader` | ECC (`/ecc:*`), gstack (`/review`, `/ship`) |
| Browser / web QA / scraping | (no Shiroe lead) | `memory-keeper` for findings | `evidence-grader` | gstack `/browse`, `/qa`; browser-harness MCP |
| Knowledge-graph / claim mapping / deep research | (no Shiroe lead) | `memory-keeper` | `evidence-grader` | `/graphify`, `/deep-research`, notebooklm |

If the domain is not covered above, default lead = `memory-keeper`, support = `[evidence-grader, wiki-maintenance]`, QA = `privacy-guardian`. State "default stack — domain unmatched."

## Auto-Activation Rule

Runs after `budget-governor` gate passes, before any execution-model call. 5 steps:

1. **Receive classified task** (weight + prompt body) from upstream gate.
2. **Detect domain** by signal-keyword match against §Domain matrix. Multi-match → pick highest-precedence (write > arbitration > consolidation > read).
3. **Pull stack**: 1 lead + 2-3 support + 1 QA gate. Never exceed 5 skills total in a single stack. Never activate all 10.
4. **Invoke `fleet-activator`** for any "Extended-tool hint" present — get reachability report; substitute emulator if unreachable.
5. **Declare stack inline**:
   `[skill-router] domain=<D> lead=<L> support=[<s1>,<s2>] qa=<Q> ext=<E|none>`
6. **Log routing event** to `memory/patterns/PATTERNS.jsonl` (`event: "skill-route"`, payload includes domain + stack).

User override at any point: `route: lead=X support=[Y,Z]` line in next message swaps the stack.

## Anti-patterns (hard blocks)

- **Fan-out across all 10 skills** — refuse. Smallest useful stack only.
- **Skipping QA gate** — every stack ends in `privacy-guardian` (or `/review-skill` for draft flows).
- **Silent extension-tool invocation** — never invoke ECC / gstack / Graphify / browser-harness without `fleet-activator` reachability check first.

## Safety

- Per `_shared/rules.md#R1`: lead skill writes must still pass through `memory-keeper` → `privacy-guardian` chain.
- Per `_shared/rules.md#R6` (Zero Context Loss): every domain signal extracted from the prompt must be reflected in the chosen lead/support/QA OR explicitly named as `unmatched-signal` in the routing output. No silent drops.
- Per `_shared/rules.md#R4`: if domain is genuinely unmatched, state "UNKNOWN — defaulting" rather than guess.
- Stack declaration is mandatory output — no execution proceeds without inline `[skill-router]` line.
- Routing decisions appended to PATTERNS.jsonl for retrospective tuning by `pattern-observer`.
