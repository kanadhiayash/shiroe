# DECISION_LOG.md — Shiroe 4.x Design Decisions
> All architectural decisions made during the Shiroe 4.0 upgrade session (May 2026).

---

## D1: Memory Architecture
**Decision:** One wiki per project/repo. Child wikis push approved summaries and decisions to a parent wiki.
**Rationale:** Project/repo boundary is meaningful to developers. Maps to Git.
**Status:** Confirmed
**Open question:** Recommend /sync-parent as explicit user action (not auto-push) to prevent unintended parent contamination.

---

## D2: Schema Interview Format
**Decision:** Conversational chat flow. Runs only at project setup when no WIKI.md schema exists.
**Status:** Confirmed

---

## D3: Context Rot / Supersession
**Decision:** Shiroe detects contradictions automatically. User resolves from flagged list only. Confidence decays after 90 days without reference. Global rules define system behavior; project wikis manage project-specific decay.
**Status:** Confirmed

---

## D4: Pattern Detection
**Decision:** Passive logger in memory/patterns/PATTERNS.jsonl. 48-80hr window, 3x repetition threshold. Skill drafts go to skills/drafts/ for user review before activation. Harness-agnostic via shared file log.
**Status:** Confirmed

---

## D5: Token Budget / God Mode
**Decision:** Auto-detected by model. No separate unlock. Free to install; capability scales with user's own model tier. No hosted service.
**Status:** Confirmed
**Note:** Long-term monetization option: premium AGENTS.md skill packs (no hosted service needed).

---

## D6: Audience Hierarchy
**Decision:** Developers First → Knowledge Workers Second → End Users with no harness.
**Impact:** Default project boundary = Git repo. Schema defaults to developer schema. /skill outputs valid SKILL.md files immediately.
**Status:** Confirmed

---

## D7: Harness Agnosticism
**Decision:** AGENTS.md is source of truth. CLAUDE.md = one line stub.
**Rationale:** AGENTS.md is Linux Foundation-hosted open standard, 60k+ repos, 20+ tools natively supported.
**Status:** Confirmed

---

## D8: Privacy Model
**Decision:** Local-first canonical memory. PRIVACY.md + REDACT.md + SHARING_POLICY.md at every project setup. Default = abstract-only writes. All connectors OFF by default.
**Status:** Confirmed

---

## D9: Archive Policy
**Decision:** Never hard delete. Superseded entries → memory/archive/. Quarterly compaction.
**Status:** Confirmed

---

## D10: Team Packs
**Decision:** On-demand only. /team [type]. Never always-on. Max 4 agents. Red team read-only by default.
**Status:** Confirmed

---

## D11: Connector / MCP Stack
**Decision:** No bundled tools. Recommendation-only after detecting repeated manual behavior.
**Recommended free core stack:** GitHub MCP · Linear MCP · Notion MCP · DuckDuckGo MCP
**Status:** Confirmed

---

## Rejected Directions
| Direction | Why Rejected |
|-----------|-------------|
| Shiroe as agent harness | Breaks portability |
| Shiroe as skill fleet | Forces unwanted scope on users |
| Shiroe dedicated to single user | Limits adoption |
| Ruflo, LLM Council as core | Too opinionated, removed |
| CEO persona | Wrong framing for a context engine |
| Bundled tools | Forces tool choices before consent |
| Claude-first architecture | Breaks harness-agnostic goal |
| Hosted Shiroe service | Not needed. Free install is the model. |
| Hermes-exclusive pattern detection | Breaks harness-agnostic goal |
| Manual rot-hunting by user | Does not scale |
