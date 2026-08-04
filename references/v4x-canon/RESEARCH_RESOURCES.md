# RESEARCH_RESOURCES.md — Shiroe 4.x Reference Links and Sources

> **Superseded snapshot.** Retired v4.x canon, archived under
> `references/v4x-canon/**` by `docs/canon/SOURCE_AUTHORITY.md`. The links were
> collected in May 2026 and are not checked or maintained.

---

## Foundational References

### AGENTS.md / CLAUDE.md Standard
- AGENTS.md official spec: https://agents.md (Linux Foundation hosted open standard, 60k+ repos, 20+ tools)
- Deep dive survey (6000+ words): https://redreamality.com/blog/claude-md-agents-md-deep-dive/
- Anthropic CLAUDE.md best practices: https://docs.anthropic.com/claude/docs/claude-md-best-practices
- HumanLayer: Writing a good CLAUDE.md: https://humanlayer.dev/blog/writing-a-good-claude-md
- Modern Agent Harness Blueprint 2026: https://gist.github.com/amazingvince/52158d00fb8b3ba1b8476bc62bb562e3

### Karpathy Paradigm Shifts
- Karpathy on context engineering: https://x.com/karpathy (June 25, 2025)
- karpathy/autoresearch (program.md): https://github.com/karpathy/autoresearch
- karpathy/llm-council CLAUDE.md: https://github.com/karpathy/llm-council
- forrestchang/andrej-karpathy-skills (43k installs in one week): https://github.com/forrestchang/andrej-karpathy-skills
- affaan-m/ecc (ECC / AgentShield): https://github.com/affaan-m/ecc
- Karpathy LLM Wiki gist: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- multica-ai/andrej-karpathy-skills (analyzed in this session): https://github.com/multica-ai/andrej-karpathy-skills

### Canonical AGENTS.md / CLAUDE.md Samples
- openai/codex AGENTS.md: https://github.com/openai/codex
- vercel/vercel AGENTS.md: https://github.com/vercel/vercel
- openai/openai-agents-python AGENTS.md: https://github.com/openai/openai-agents-python
- vercel-labs/open-agents: https://github.com/vercel-labs/open-agents
- vercel-labs/agent-skills SKILL.md: https://github.com/vercel-labs/agent-skills
- anthropics/anthropic-cookbook AGENTS.md: https://github.com/anthropics/anthropic-cookbook

### Community Mental Models
- Armin Ronacher: Logs as APIs, No Dead Ends: https://lucumr.pocoo.org/2025/6/12/agentic-coding/
- Geoffrey Huntley: stdlib and Ralph Wiggum technique: https://ghuntley.com/specs/
- Harrison Chase: Model / Harness / Context layers (Sequoia podcast)
- Hamel Husain: Evals as living PRD: https://hamel.dev
- Simon Willison on AGENTS.md: https://simonwillison.net

### Memory and Evolution Patterns
- jack60810/claude-evolve (Darwinian memory, EMA rule ratings): https://github.com/jack60810/claude-evolve
- MEMORY.md read/write separation: community-wide pattern, multiple sources
- Two-Strikes Rule: Anthropic CLAUDE.md best practices
- Auto Dream (relative → absolute date hygiene): community pattern

### Spec-Driven Development
- BMAD-METHOD (43k stars): https://github.com/bmad-method
- GitHub Spec Kit (6-phase, human-gated): https://github.com/github-spec-kit
- Martin Fowler: SDD Tools Comparison: https://martinfowler.com
- Kiro (AWS VS Code fork with steering files): AWS product

### Knowledge Management Use Cases
- ballred/obsidian-claude-pkm (PARA starter kit): https://github.com/ballred/obsidian-claude-pkm
- AgriciDaniel/claude-obsidian (Karpathy-style LLM Wiki): https://github.com/AgriciDaniel/claude-obsidian

### Shiroe Space Source References
- bytebytego.com/courses/system-design-interview/scale-from-zero-to-millions-of-users
- copper-tv-288.notion.site/Shiroe-Skills-Fleet-Command-Center-358d695d836a81af9f6adf30770217c3
- gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- github.com/addyosmani/agent-skills
- github.com/affaan-m/ecc
- github.com/AgriciDaniel/claude-obsidian
- github.com/browser-use/browser-harness
- github.com/claude-world/notebooklm-skill
- github.com/D4Vinci/Scrapling

---

## Key Community Data Points (May 2026)
- AGENTS.md: 60,000+ repos at time of research
- forrestchang/andrej-karpathy-skills: 43,000 installs in one week
- BMAD-METHOD: 43,000 GitHub stars
- CLAUDE.md instruction compliance: ~70% (community consensus). Red lines need PreToolUse hooks.
- Optimal CLAUDE.md length: 60-250 lines typical projects
- Frontier model reliable instruction count: ~150-200 before compliance decays
- Context window target: 40-60% utilization (Geoffrey Huntley). Above 60% = quality drops.

---

## Shiroe Choices That Diverge From Community Defaults
| Community Default | Shiroe 4.x Choice | Reason |
|------------------|-----------------|--------|
| CLAUDE.md as primary file | AGENTS.md primary, CLAUDE.md = stub | Harness-agnostic |
| Skills bundled in harness | Skills recommended only | User consent and portability |
| Memory in hosted service | Memory in local markdown | Privacy-first |
| Team agents always available | On-demand only | Token budget |
| Immediate skill activation | Review-first, approval required | Prevents misdetection |
| Single-user persona | Free for all users | Explicit design requirement |
