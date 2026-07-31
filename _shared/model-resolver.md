---
---

# model-resolver (DEPRECATED)

Deprecated in 2.0.0-alpha.1. Canonical model resolution moved to code:

- Reasoning classes: `shiroe/core/reasoning.py` (fast / balanced / deep / frontier / local / private)
- Provider mappings: `shiroe/adapters/providers/<provider>.json`
- Aliases (one deprecation cycle, removed 2.1.0): `shiroe/core/deprecations.py`

The old alias table (haiku/sonnet/opus/opus48) maps to fast/balanced/deep/frontier via the anthropic provider adapter. Do not add model ids to this file.
