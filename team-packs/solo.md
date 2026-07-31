---
name: solo
default: true
agents: 1
max_agents: 4
read_only: false
description: One primary agent plus the Shiroe AI Tactician. Default for most work.
---

# solo team pack

> Sourced from SHIROE_OS §8.

## Roster

| Role | Auto-load | Notes |
|---|---|---|
| primary | yes | Whatever model the user invoked; handles all task work |
| Shiroe AI Tactician | yes | Composed of `memory-keeper` + `privacy-guardian` + `pattern-observer` (background) |

## When to use

- Default for everything unless another team is explicitly activated.
- Single-file edits, debugging, conversational work, quick lookups.

## Activation

Automatic. `/team solo` to explicitly revert from another team.

## Outputs

- No `team/` files written. Standard flow into `memory/`.

## Rules

- Shiroe AI Tactician writes go through `privacy-guardian` per `PRIVACY.md`.
- `pattern-observer` logs to `memory/patterns/PATTERNS.jsonl` in the background.
- No multi-agent orchestration. If task needs >1 specialized agent, switch to a different team.
