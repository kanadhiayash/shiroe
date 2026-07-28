# Connector Advisory

> Sourced from ZEREF_OS §9 + DECISION_LOG D11. Zeref ships **zero** bundled MCP tools. Recommendation-only.

## Rules

1. **OFF by default.** Every connector starts disabled in `SHARING_POLICY.md`.
2. **No bundled installation.** Zeref never installs an MCP server. User installs, user enables.
3. **Recommendation triggered by signal.** Zeref suggests a connector only after `pattern-observer` detects repeated manual behavior that the connector would automate.
4. **Per-action approval for external writes** even after enablement.
5. **Redact before send.** Every external transmission runs through `REDACT.md` classes listed per-connector in `SHARING_POLICY.md`.

## Recommended Free MCP Stack

### Core (cheap, broadly useful, high signal-to-noise)
| MCP | Use | Trigger to recommend |
|---|---|---|
| **GitHub MCP** | repo context, issues, PRs, diffs | user manually pasted issue/PR text 3× in 72h |
| **Linear MCP** | issue and project tracking | user referenced ticket IDs without context 3× |
| **Notion MCP** | shared docs, human-readable surfaces | user copy-pasted Notion pages or mentioned them 3× |
| **DuckDuckGo MCP** | cheap web grounding, no auth | user asked agent to "look up" or "search for" 3× |

### Workflow
| MCP | Use | Trigger to recommend |
|---|---|---|
| **Playwright MCP** | browser automation | user described UI flows agent should run 3× |
| **Context7 MCP** | live library docs, code-reference retrieval | user asked about library version-specific behavior 3× |
| **Sequential Thinking MCP** | structured decomposition for complex tasks | user reasoning chains exceed 5 steps with `/status` showing token strain |

### Optional Power
| MCP | Use | Notes |
|---|---|---|
| **Supabase MCP** | structured cloud memory or sync | Zeref local-first; only recommend if user explicitly wants cloud overlay |
| **Desktop Commander** | local file ops and execution | only recommend on Free tier where Bash is constrained |
| **Firecrawl MCP** | heavy web ingestion | only recommend for research-heavy projects |

## Recommendation Format

When the trigger fires, Zeref says (in `/status` or inline):

> "Detected: you pasted GitHub issue text 3× in the last 48h.
> Recommendation: GitHub MCP would automate this.
> Install: `claude mcp add github ...`
> Enable in SHARING_POLICY.md: set `github.enabled: true` and configure `allowed_surfaces: [issues, prs]`.
> Continue without it? Yes / Show install instructions."

## Anti-Patterns

- Auto-installing on the user's behalf (§11)
- Recommending a connector before the user has hit the trigger threshold
- Enabling read-context without explicit `read_project_context: true`
- Pushing external writes without per-action approval

## Related

- `SHARING_POLICY.md` — per-connector allowlist (this is where users enable)
- `PRIVACY.md` — modes and global policy
- `REDACT.md` — concrete sensitive classes
- `agents/pattern-observer.md` — detects the triggering signal
- `references/v4x-canon/ZEREF_OS.md` §9
