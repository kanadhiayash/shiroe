# Audit Logs

Shiroe writes append-only JSONL audit logs under `memory/audit/`.

Files:

- `writes.jsonl`
- `reads.jsonl`
- `routes.jsonl`
- `guard_failures.jsonl`
- `redactions.jsonl`
- `releases.jsonl`

Every audit event includes an event id, event type, status, actor, file,
optional memory id, guards run, reason, timestamp, and payload.

Generate a report:

```bash
shiroe audit report
shiroe audit report --since 2026-07-09
shiroe audit report --format md
```

Corrupt JSONL lines are reported instead of crashing the report.
