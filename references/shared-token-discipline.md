# Shared Token Discipline Rules
**Shiroe Skills Fleet V2 — Canonical Reference**
Version: 1.0.0 | Owner: Yash Kanadhia
Last Updated: 2026-06-19

> All Shiroe skill files reference this document instead of duplicating these rules.
> Do not modify this file without updating the version number and changelog.

---

## Purpose

These rules govern how every Shiroe skill manages output length, format selection, and information density. The goal is maximum signal per token: precise, structured, actionable outputs that respect context window limits and avoid padding.

---

## Rule 1 — State Assumptions at the Top

Every skill output must open with a labeled assumptions block before any substantive content.

**Format:**
```
Assumptions:
- [assumption 1]
- [assumption 2]
```

If no assumptions are needed, skip this block. Never silently assume without labeling.

---

## Rule 2 — Output Length by Task Type

Match output length to task complexity. Never pad to appear thorough.

| Task Type | Target Length | Max Ceiling |
|---|---|---|
| Quick answer / clarification | 1–3 sentences | 200 tokens |
| Structured analysis | 300–600 words | 800 tokens |
| Standard skill execution | 500–1000 words | 1500 tokens |
| Full skill output with handoff blocks | 800–1500 words | 2500 tokens |
| Executive review pass | 600–1200 words | 2000 tokens |
| Caveman compression | 400–800 words | 1200 tokens |
| Code review | 300–800 words | 1500 tokens |
| Memory ingest | 100–300 words | 600 tokens |
| Registry/config update | 50–200 words | 400 tokens |

If the task can be answered in fewer words, use fewer words. Length is never a quality signal.

---

## Rule 3 — Tables vs. Prose

**Use tables when:**
- Comparing 3 or more items across 2 or more dimensions
- Presenting a structured mapping (skill → layer, metric → target, etc.)
- Showing a status grid or issue registry
- Documenting an API, schema, or config

**Use prose when:**
- Explaining reasoning, rationale, or strategy
- Walking through a sequential process
- Writing copy, narrative content, or documentation
- The output has fewer than 3 items to compare

Never use a table for a list of fewer than 3 items. Never use prose when a table would make relationships clearer.

---

## Rule 4 — Lists vs. Prose

**Use bullet lists when:**
- Items are parallel, discrete, and non-sequential
- There are 3 or more items
- Each item can stand alone without sentence context

**Use numbered lists when:**
- Items are sequential steps
- Order matters

**Use prose when:**
- Fewer than 3 items
- Items require connecting context to be understood
- You are making a flowing argument

Maximum list item length: 2 lines. If a bullet item requires more than 2 lines of explanation, use a heading + paragraph instead.

---

## Rule 5 — When to Compress vs. Expand

**Compress when:**
- Summarizing context for a handoff
- The user asks for a brief or TL;DR
- Context window is approaching 60% capacity
- You are routing to another skill
- The task is a status update, not a deliverable

**Expand when:**
- The task is a primary deliverable
- The user explicitly asks for detailed reasoning
- The output will be saved as a memory file or portfolio artifact
- Ambiguity is high and specificity prevents future errors

---

## Rule 6 — Never Pad with Filler

These phrases are banned from Shiroe outputs:

- "Great question!"
- "Certainly!"
- "Of course!"
- "I'd be happy to help"
- "As an AI language model"
- "It's important to note that"
- "In conclusion, it's clear that"
- Any restating of the user's prompt as the first sentence
- Any sentence that contains no new information

If removing a sentence does not change the meaning of the output, remove it.

---

## Rule 7 — Max Section Depth

Maximum heading depth in any skill output: **3 levels** (`##`, `###`, `####`).

Do not use `#####` or deeper. If you need more hierarchy, restructure the output into separate sections.

Exception: technical documentation outputs that require 4-level depth may use it only with explicit justification.

---

## Rule 8 — List Length Caps

| List Type | Soft Cap | Hard Cap |
|---|---|---|
| Bullet list (general) | 7 items | 10 items |
| Numbered steps | 10 steps | 15 steps |
| Options / alternatives presented | 3 options | 5 options |
| Issue list in QA report | 10 issues | 20 issues |
| Trigger keywords per skill | 8 keywords | 15 keywords |

If a list exceeds the hard cap, group items under sub-headings instead.

---

## Rule 9 — Handoff Block Discipline

Every skill that produces a major deliverable should append a Handoff Block. Format:

```
## Handoff

Completed: [what was produced]
Open: [what is unresolved or needs follow-up]
Next skill: [recommended next skill to activate]
Memory update: [file to update, if any]
```

Handoff blocks are not optional for lead skills. They are optional for support skills if the output is self-contained.

---

## Rule 10 — Context Economy

- Do not restate the user's objective after acknowledging it.
- Do not summarize your own output in a conclusion paragraph unless it adds new synthesis.
- Do not include a "sources" section if you have no external sources.
- Do not explain what you are about to do. Do it.
- Do not include boilerplate disclaimers not required by the task.

**Exception to Rule 10:** Legal, financial, security, and medical tasks must include role-specific disclaimers at the top of the output, regardless of context economy. See `references/shared-anti-hallucination.md` for exact disclaimer language.

---

## Version History

| Version | Date | Change |
|---|---|---|
| 2.0.0 | 2026-05-12 | Initial V2 canonical reference — extracted from all 18 skill files |
| 1.0.0 | Prior | Rules embedded individually in each skill file (legacy pattern) |
