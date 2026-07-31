# Team Packs

A team pack is an on-demand configuration that declares which agents are active, which skills may be used, and what the session's budget envelope is. Packs are activated with `/team` and their definitions live in `team-packs/<name>.md`.

Packs come in two kinds, and they answer different questions. **Role packs** answer "what shape of work is this?" **Size packs** answer "how much may this session spend?"

## Role packs

| Pack | Roster | Use |
|---|---|---|
| `solo` | One primary plus the memory engine | Default. Single-agent operation. |
| `build` | Planner, Implementer, Reviewer | Multi-module features: plan, execute, review. |
| `research` | Investigator, Synthesizer, Fact-checker | Evaluating an approach or technology. |
| `red` | Attacker, Security reviewer, Constraint checker, Evidence recorder | Adversarial review. **Read-only by default.** |
| `audit` | Reader, Linter, Quality gate | Pre-ship review of docs, specs, and code. |
| `ship` | Changelog drafter, Release reviewer, Deploy verifier | Release preparation. |

Outputs land under `team/`, never inline-only, so the work product survives the session that produced it.

`red` is read-only by default because an adversarial roster that can also write is a roster that can act on its own findings without review.

## Size packs

Size packs set the cost envelope: token targets and hard caps, the default reasoning tier, how many background agents are active, and the per-task skill ceiling.

| Pack | Active background agents | Posture |
|---|---|---|
| `small` | Memory writer only | Tightest budget. Lowest default tier; higher tiers only when the default is insufficient. |
| `medium` | Memory writer, privacy guardian, evidence curator, sync coordinator | Typical project work. Top tier reserved for critical-weight tasks. |
| `enterprise` | All background agents | Widest budget. Adversarial verification panels enabled. |

Size packs constrain cost; they do not grant capability. The per-task skill cap applies globally regardless of which size pack is active, and the reasoning-class entitlement rule in `shiroe/core/reasoning.py` still governs what any given task may buy. A wider envelope raises the ceiling, not the floor.

## Activation

```
/team                 show available packs and the active one
/team solo            revert to the default single-agent configuration
/team build           activate the build roster
/team research        activate the research roster
/team red             activate the read-only adversarial roster
/team audit           activate the audit roster
/team ship            activate the ship roster
```

Pack-specific arguments:

```
/team red --write                grant write access — not recommended
/team audit --scope=<path>       scope the audit to a path
/team audit --diff               audit the working-tree diff against base
/team ship --version=<semver>    target release version
/team ship --dry                 produce artifacts without tagging
```

## Activation sequence

1. Read `team-packs/<name>.md`.
2. If the pack does not exist, list available packs and stop.
3. Verify the roster against the agent cap; refuse a pack that declares more.
4. Activate the roster.
5. Ensure `team/` exists.
6. Record the activation in session memory.

A pack that violates its own cap is refused rather than trimmed, because silently dropping a declared role would change what the pack means without saying so.

## Packs and skill selection

A team pack sets the candidate roster. Skill selection for a given task draws from that roster and stays within the pack's caps.

## Related

- [[Architecture]] — agents, skills, reasoning classes
- [[Memory-Model]] — where pack output is recorded
- [[Glossary]] — canonical terms
