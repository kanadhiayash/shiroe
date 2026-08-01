---
name: red
agents: 4
max_agents: 4
read_only: true                # default per SHIROE_OS §8: red team read-only by default
description: Attacker + Security reviewer + Constraint checker + Evidence recorder. Adversarial stress test.
output_dir: team/
---

# red team pack

> Sourced from SHIROE_OS §8. **Read-only by default.**

## Roster

| Role | Responsibility |
|---|---|
| **Attacker** | Tries to break the system. Proposes attacks, edge cases, abuse paths. Does NOT execute destructive actions. |
| **Security reviewer** | Audits code/config for vulns: authn/authz, injection, secrets, deps. |
| **Constraint checker** | Verifies declared invariants (rate limits, quotas, irreversibility guards, data residency). |
| **Evidence recorder** | Documents every finding with reproducer, severity, suggested fix. Writes `team/red-team-report.md`. |

## When to use

- Pre-launch security review
- Adversarial stress test before a contentious release
- Post-incident retrospective
- Compliance / audit prep

## Activation

`/team red`

User may pass `--write` to grant write access (NOT recommended; defeats the read-only safety).

## Outputs

| File | Owner |
|---|---|
| `team/red-team-report.md` | Evidence recorder |
| `team/red-team-attacks.md` | Attacker (catalog of attempted exploits, outcomes) |

## Rules

- **Read-only by default.** Agents propose patches; user applies them.
- **Per-attack approval for any execution.** Even a benign-looking probe needs explicit user OK if it touches anything beyond local file reads.
- **Severity classification mandatory** on every finding: `critical | high | medium | low | informational`.
- **Reproducer required** for every `critical` or `high` finding.
- No raw exploit code stored outside `team/red-team-attacks.md`; that file is gitignored by default (add `team/red-team-attacks.md` to project `.gitignore` if it contains sensitive payloads).

## Rules of engagement

- No live destructive actions (DROP, DELETE, irreversible API calls).
- No third-party probing outside the scope agreed with user.
- All findings cross-referenced to `references/shiroe-safety-principles.md`.
