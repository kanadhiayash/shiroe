# Inspirations

Naming the influences makes the design legible and situates the project honestly. None of the ideas below are original to Shiroe; the contribution is the combination and the enforcement.

## The name

Shiroe is named after a fictional scholar whose accumulated knowledge outlasted any single era — someone who never started from zero.

That is the design target. AI sessions today start from zero every time: you re-explain the project, lose decisions to context resets, and abandon accumulated memory when you switch tools. Long-horizon memory that stays faithful to a user's decisions and travels across harnesses is the thing worth building.

## A single canonical contract

Influenced by [agents.md](https://agents.md) and the cross-harness AGENTS convention. Source of truth lives in Markdown, not vendor-specific configuration, and every harness reads the same file or a thin stub that defers to it.

The alternative — per-tool configuration that drifts apart — fails quietly, which is the worst way to fail.

## Append-only event logs

The event log follows the event-sourcing tradition (Datomic, Kafka): append, never edit, replay to reconstruct. Pattern detection reads the log as a stream rather than querying mutable state.

An append-only history means the question "what did we believe last month, and why?" stays answerable.

## Local-first software

Directly indebted to [Local-first software](https://www.inkandswitch.com/local-first/) (Ink & Switch). Your data on your disk, in your version control. Tools synthesize on top of it rather than owning it.

The practical consequence is that a vendor going away, changing terms, or losing your account does not take your project memory with it.

## Deterministic privacy, not model judgment

Language models are not privacy enforcers. A model asked to redact can be talked out of redacting; a regex cannot. Redaction is therefore regex, Unicode normalization, homoglyph folding, and base64 decoding — running in code, before the write.

Influenced by [secure-by-design](https://www.cisa.gov/securebydesign) principles and records-management discipline: make the safe path the default path, and make the unsafe path require a deliberate act.

## Human arbitration over automatic resolution

Automated conflict resolution is where memory systems quietly become unreliable. Picking the newer claim, or the better-graded one, looks like a policy but is really a guess with a rule attached.

Shiroe surfaces both sides and waits. The design bet is that a human deciding occasionally beats a machine deciding invisibly every time.

## The Two-Strikes Rule

Original to Shiroe in this form, inspired by retrospective practice: do not codify a rule on the first occurrence of an error. One occurrence is noise; two is a pattern. Codifying on the first produces brittle rules that encode a coincidence.

## Prompt compression for handoff

Draws on grammar-prompting and structured token-compression work: drop articles, filler, and pleasantries; preserve technical substance verbatim. Compression ratio varies by content, and entity preservation — not a fixed reduction figure — is the design goal.

## Repository doctrine

Branch naming, Conventional Commits with scope, trunk-based development with a protected default branch, and semantic version tags. Conventional rather than novel, which is the point: doctrine that a new contributor already knows is doctrine they will follow.

## Related

- [[Architecture]] — how these ideas are implemented
- [[Stack]] — projects Shiroe sits alongside
- [[Home]]
