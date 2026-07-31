# Release Gates

`shiroe release check` runs local readiness checks for:

- version file presence
- memory layout
- audit logs
- benchmark report status
- FactGuard README scan
- EvidenceGuard memory and docs scan

Benchmark checks only confirm the local benchmark report status. They do not
authorize public ranking, superiority, or external-dataset claims.
