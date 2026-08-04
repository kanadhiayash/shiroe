# ADR-0006: Graph projection invariant

**Status:** Accepted
**Date:** 2026-08-04

## Context

ADR-0001 settled where the record of truth lives: SQLite holds current state, JSONL holds append-only history, and every human-readable rendering is derived from those. It did not say anything about graphs, and graphs are the surface most likely to quietly re-acquire authority. `shiroe/memory/graph.py` already builds a node/edge structure into `memory/indexes/derived-graph.json`, task execution is described as a graph in the mission and team-compiler layers, and hosted graph databases are a standing temptation for anything that looks like a knowledge graph.

A graph earns trust it has not been granted. It looks complete because it is connected, it looks settled because it renders, and an inferred edge is indistinguishable at a glance from an observed one. Three concrete failure modes follow from leaving this unstated:

1. **Silent promotion to canon.** A rebuild is skipped "because the graph is expensive", the graph drifts from the store, and readers start believing the graph.
2. **Unfalsifiable claims.** An edge with no provenance cannot be checked, retracted, or graded — it is a claim with the evidence discipline stripped off.
3. **Unbounded traversal.** Cyclic dependency resolution, transitive expansion, and agent-driven graph walks have no natural stopping point, and an irreversible action reached by traversal is an irreversible action nobody approved.

The same reasoning applies whether the graph is a task graph (topology of one run) or a knowledge graph (entities and relations mined from memory). Both are projections. Neither is a store.

## Decision

**A graph is a projection over canonical state. It is never canonical state itself.** Concretely, and enforced wherever graph code is added:

- **Deletable.** Deleting every graph artifact must destroy no information. If removing `memory/indexes/derived-graph.json` (or any successor) loses something, that something was canonical and belonged in SQLite or the event log.
- **Rebuildable.** Every graph is reproducible from the canonical store alone, deterministically, with no side inputs. Rebuild-from-scratch is the supported repair path — there is no graph migration, only regeneration.
- **Run-scoped topology.** A task graph describes the structure of one run. It is not durable project state, it does not accumulate across runs, and it is not consulted as a memory of what happened; the event log is.
- **Candidate, not fact.** Knowledge-graph output is a set of candidate relations, not verified facts. A candidate carries a confidence and an evidence grade, is never rendered as a settled claim, and never satisfies a query that asked for a fact.
- **Provenance on every edge.** Every edge names what produced it and what it derives from — source record id, extraction method, and timestamp at minimum. An edge that cannot state its provenance is not written.
- **Bounded cycles.** Every traversal, expansion, and resolution loop declares a maximum depth and a maximum node budget before it starts, and terminates at that bound with a partial result rather than running to exhaustion. Cycle detection is mandatory, not best-effort.
- **Human gate on irreversible paths.** No irreversible action is reached by graph traversal without an explicit human approval step. Graph-derived plans are subject to the `ALWAYS_REQUIRE_APPROVAL` set in `docs/adr/ADR-0005-policy-precedence.md` exactly as any other plan; being computed rather than written changes nothing.
- **Promotion uses the standard write path.** Moving anything from a graph into canonical memory is an ordinary write. It passes the same evidence, privacy, contradiction, policy, and approval path as every other write — no graph-specific shortcut, no bulk import that bypasses the guards.
- **SQLite and the standard library at the core.** Core graph construction, storage, and traversal use SQLite and the Python stdlib — no graph library, no third-party engine. Shiroe's zero-mandatory-dependency guarantee covers graph work.
- **Hosted graph systems are optional adapters.** Any graph database or hosted graph service is an optional adapter at the edge, disabled by default, governed by `SHARING_POLICY.md`. Core code never imports one, and no feature may require one to function.

## Consequences

- `shiroe/memory/graph.py` and any successor must keep their derived-graph output under an index/cache path, never under `memory/state/`, and must carry a docstring stating the artifact is derived.
- Any future graph store gets a rebuild entry point before it gets a read path. Shipping a graph without a working rebuild is the defect this ADR names, so the rebuild is the acceptance gate, not a follow-up.
- Retrieval and recall may rank with graph structure but must resolve every returned claim back to a canonical record. A response citing only a graph edge is unsourced.
- Traversal bounds are parameters of the call, not global constants — a caller that does not supply them gets the conservative default, never "unlimited".
- Promotion of graph-derived candidates is expected to be rare and reviewed. If promotion volume grows enough to make per-item review impractical, that is a signal the extraction is being trusted too far, not a reason to relax the gate.
- This ADR constrains graphs only. It does not reopen ADR-0001; SQLite remains current state and the JSONL log remains history.
