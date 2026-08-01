# Routing

Shiroe includes a local routing policy for classifying work before execution.

Commands:

```bash
shiroe route classify "redact credentials before release"
shiroe route explain "scan benchmark claims"
shiroe route policy show
shiroe route policy validate
shiroe route report
```

The policy is deterministic and local. It does not call hosted services or
enable agent orchestration by itself.
