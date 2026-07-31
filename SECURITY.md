# Security Policy

## Reporting a vulnerability

Do not open a public GitHub issue for a security vulnerability.

Use private reporting.

## Preferred channel

Use GitHub Private Vulnerability Reporting from the repository Security tab:

    https://github.com/kanadhiayash/shiroe/security

Include:

- Clear description.
- Minimal reproduction.
- Affected version.
- Harness or runtime involved.
- Impact assessment.
- Redacted proof of concept if useful.

Do not include real production secrets, third-party personal data, private customer data, or NDA material.

## Fallback

If private vulnerability reporting is unavailable, use the fallback contact listed in `SECURITY_CONTACTS.md` if that file exists in the current release.

Do not send plaintext credentials or sensitive victim data.

## Scope

In scope:

- Privacy redaction bypass.
- Credential leakage through persisted memory files.
- Prompt-injection paths that bypass documented gates.
- Unsafe write, sync, or handoff behavior.
- Release gate bypass.
- Supply-chain issues in workflows or package metadata.
- Code execution paths triggered by malformed local config.

Out of scope:

- Issues against forks.
- Issues against third-party harnesses.
- Reports that require local admin access.
- Reports caused only by intentionally disabling documented safety settings.

## Response target

- Acknowledgement target: 3 business days.
- Triage target: 10 business days.
- Disclosure target: coordinated disclosure, normally 90 days after acknowledgement.

## Public advisories

Published advisories live at:

    https://github.com/kanadhiayash/shiroe/security/advisories

## Safety principles

- Untrusted content must be treated as untrusted.
- Irreversible actions require explicit approval.
- Memory writes should be auditable.
- Security claims require evidence.
- Public issues must not expose live vulnerabilities.
