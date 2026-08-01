---
name: skill-importer
description: Pull a skill from the user's broader skill directory into this Shiroe project. Provenance-tracked, review-first — imports never auto-activate. Compatible with sandbox reference-only mode (see skills/imported/*/README.md).
skill: skill-importer
version: "1.1.0"
model: sonnet
reasoning_class: balanced
model_alias: sonnet
risk_level: medium
triggers:
  - import skill from
  - pull skill from user directory
  - adopt skill <name>
  - /skill-importer
deliverables:
  - skills/<name>/SKILL.md copied with provenance frontmatter
  - skills/<name>/PROVENANCE.md created (source path, source repo, import date, checksum)
  - skill registered in shiroe-registry.json with model + risk_level
  - skill NOT auto-activated — awaits /review-skill
---

# skill-importer

**Purpose.** Pull a skill from the user's broader skill directory (e.g.
`~/.claude/skills/`, `~/.codex/skills/`, a sibling project, or a public
skill repo) into this Shiroe project. The import is provenance-tracked
and does **not** auto-activate the skill — the user reviews it via
`/review-skill` first.

## Activation

This skill is the destination side of "adaptivity". When the user says
"import skill X from my Claude directory", `skill-router` routes here.

## Steps

1. **Locate.** Search known skill roots:
   - `~/.claude/skills/`
   - `~/.codex/skills/`
   - `~/.cursor/skills/`
   - Any operator-configured skill vault path.
   - Any path explicitly named by the user.
2. **Read source.** Load `SKILL.md` and any sibling files (`PROVENANCE.md`,
   reference docs).
3. **Hash.** Compute SHA-256 of the source `SKILL.md` for tamper
   detection later.
4. **Privacy filter.** Run `privacy-guardian` over the source. If the
   source contains credentials, paths, or PII per `REDACT.md`, abort and
   surface to user. Never import a skill that itself contains secrets.
5. **Stage.** Copy to `skills/<name>/SKILL.md` with a new YAML frontmatter
   field:
   ```yaml
   imported_from: ~/.claude/skills/<name>
   imported_at: <iso-date>
   imported_sha256: <hex>
   activation: pending-review     # NOT active
   ```
6. **Write `skills/<name>/PROVENANCE.md`** with: source path, source
   project, original author (if known), import date, source SHA-256.
7. **Append to `shiroe-registry.json`** with `risk_level: medium` and the
   declared trigger phrases — but with an `activation: false` flag so
   `skill-router` does **not** pick it up.
8. **Notify the user**: "Imported `<name>` to `skills/<name>/`. Run
   `/review-skill <name>` to activate."

## Safety

- **No auto-activate.** Every imported skill must pass `/review-skill`
  before `skill-router` considers it.
- **No credential ingestion.** Imports that fail the privacy filter are
  rejected.
- **No silent overwrite.** If `skills/<name>/` already exists with a
  different SHA, surface a `contradiction-resolution` event and let the
  user decide.

## Refusal cases

- Source is on a remote URL (this skill is local-disk only — use a fetch
  pipeline first).
- Source has no `SKILL.md` (not a valid skill).
- Privacy filter flags credentials in the source.
- Import target name collides with a built-in Shiroe skill.
