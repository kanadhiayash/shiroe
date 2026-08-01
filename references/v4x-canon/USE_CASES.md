# USE_CASES.md — Shiroe at 110% Strength

> Six use cases demonstrating Shiroe's full capability: Shiroe AI Tactician + privacy layer + team packs + pattern detection + skill generation + harness portability + God Mode.

---

## Use Case 1: Multi-Month Product Build (Solo Developer)

Powers used: Wiki persistence · Harness translation · Pattern detection · Skill generation · God Mode

A developer builds a SaaS product over 4 months, switching between Claude Code, Cursor, and Gemini CLI.
- /start in Claude Code. Schema interview creates WIKI.md. Sensitive classes: no client names, no revenue figures.
- Architecture decisions written to wiki. Dependency map maintained across all sessions.
- Developer switches to Cursor for UI sprint. AGENTS.md loads identically. memory/hot.md provides last 3 sessions. Zero re-onboarding.
- After week 2, Shiroe detects Stripe webhook handling pasted manually 4 times in 72 hours. Surfaces skill recommendation.
- Developer approves. skills/drafts/stripe-webhooks.md created. Reviewed and activated.
- 4 months later: Claude Opus used. God Mode activates. Full parent-child wiki sync, deep conflict analysis, pattern retrospective shows 8 skills extracted from natural work patterns.

Result: 4 months of compounding context. Zero re-explanation. 8 reusable skills from real patterns.

---

## Use Case 2: Client Agency Work (Privacy-Critical)

Powers used: Privacy layer · REDACT.md · Schema interview · Team packs (build + audit) · Parent wiki

A design agency works on a confidential rebrand. Multiple team members. Client name is sensitive.
- Schema interview: Client work. Sensitive: client name (replace with [CLIENT_A]), financial scope.
- All wiki entries use [CLIENT_A]. Memory mode: abstract-only. All connectors: OFF.
- Build team activated: /team build. Planner + Implementer + Reviewer. Output to team/build-sprint-01.md.
- Audit team activated pre-delivery: /team audit. Checks all deliverables for REDACT.md violations. Zero violations.
- SHARING_POLICY.md blocks all external sync. Nothing leaves the project boundary.

Result: Sensitive project handled safely. No data leakage. Audit trail maintained locally.

---

## Use Case 3: Open Source Library Maintainer

Powers used: Parent wiki · Decision log · Contradiction flagging · Research team · AGENTS.md standard

A maintainer manages a popular library with multiple contributors.
- Library repo is parent wiki. Each contributor's branch has a child wiki.
- Contributor proposes a breaking change. Child wiki records it.
- /sync-parent: Shiroe detects the child decision contradicts a parent decision from 8 months ago. FLAGS to maintainer.
- /compile: Old decision has medium confidence (90-day decay). New decision has high confidence. Maintainer confirms. Old archived.
- Research team: /team research. Investigator + Synthesizer + Fact-checker review architectural question.
- Result published to DECISION_LOG.md in parent wiki. All contributors load this in subsequent sessions.

Result: Architectural decisions don't get relitigated. Contradictions surfaced before they become bugs.

---

## Use Case 4: Security Audit Sprint

Powers used: Red team pack · PRIVACY.md · God Mode · Pattern detection

Senior developer reviews a payment processing service before launch. Claude Opus active: God Mode.
- /team red. Attacker + Security reviewer + Constraint checker + Evidence recorder.
- Red team: read-only. They propose. Developer approves before any change applied.
- Attacker runs OWASP top 10 against codebase. Constraint checker cross-references with PRIVACY.md.
- Security reviewer writes findings to team/red-team-report-2026-05.md.
- God Mode: deep conflict analysis flags 3 architectural decisions in wiki that contradict security findings.
- Developer resolves each in /compile. Updated decisions: high confidence + security_reviewed: true metadata.

Result: Security review has institutional memory. Findings don't disappear after the sprint.

---

## Use Case 5: Knowledge Worker — Research Analyst

Powers used: Wiki per project · Schema interview · Research team · Privacy layer · Notion MCP (enabled for sharing)

Research analyst builds competitive intelligence across 12 company assessments over 12 months.
- Each company assessment = separate child wiki. Parent wiki = "Competitive Intelligence 2026".
- Schema interview: Employer work. Sensitive: financial projections, individual names. Abstract-only mode.
- Research team for each assessment: /team research.
- After 6 months: /compile shows 12 child wikis with high-confidence summaries.
- /sync-parent pushes approved summaries to parent wiki.
- Analyst enables Notion MCP specifically for parent wiki summaries (approved in SHARING_POLICY.md).
- New team member onboards. Reads parent wiki via Notion. Full context without a single meeting.

Result: 12 months of competitive intelligence in a queryable parent wiki. New team members instant onboard.

---

## Use Case 6: Cross-Harness Developer

Powers used: AGENTS.md harness translation · memory/ file structure · hot.md startup · skill portability

Developer uses Claude Code for deep coding, Gemini CLI for long-context analysis, Cursor for quick edits, Codex for automated PR review.
- All four harnesses read the same AGENTS.md. Zero reconfiguration.
- Claude Code writes to memory/MEMORY.md. Gemini CLI reads the same file.
- PATTERNS.jsonl written by all four harnesses. Pattern detection runs at /stop regardless of which harness.
- Skill approved in Claude Code. SKILL.md portable: Cursor and Codex read it in subsequent sessions.
- Developer switches from Claude Opus to Gemini 3.5 Pro for a long-context task. God Mode stays active.

Result: True harness portability. One Shiroe AI Tactician across four tools. Skills work everywhere.
