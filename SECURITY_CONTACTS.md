<!-- privacy-audit: allow-file "Public security contact page. Contains one maintainer email by design — the whole point of the file is to publish the disclosure channel." -->

# Security Contacts — Shiroe

Used by [`SECURITY.md`](SECURITY.md) as the fallback channel when GitHub
Private Vulnerability Reporting is not available.

## Encrypted email

- **Address:** `security+shiroe@kanadhiayash.dev`
  *(maintainer email — replace with the address you actually monitor)*
- **PGP fingerprint:** *to be published — see below.*

Until the PGP key is published, use GitHub Private Vulnerability Reporting
as the primary channel.

## How to publish the PGP fingerprint

The maintainer publishes a long-lived PGP public key whose fingerprint is
recorded here, plus a copy uploaded to <https://keys.openpgp.org>. Steps:

1. Generate the key:
   ```bash
   gpg --quick-generate-key 'Shiroe Security <security+shiroe@kanadhiayash.dev>' \
       ed25519 cert,sign 2y
   gpg --quick-add-key <KEY-ID> cv25519 encr 2y
   ```
2. Export and publish:
   ```bash
   gpg --armor --export <KEY-ID> | gpg --send-keys --keyserver keys.openpgp.org <KEY-ID>
   gpg --fingerprint <KEY-ID>
   ```
3. Replace the **PGP fingerprint** line above with the 40-char hex
   fingerprint produced by step 2.
4. Commit the change with a `chore(security): publish PGP fingerprint`
   message.

## Key rotation

- Rotate the key every 24 months (or immediately on compromise).
- Issue a `chore(security): rotate PGP fingerprint` commit when rotating.
- Keep the previous fingerprint in this file for one release cycle so
  reporters mid-flight know which key was current.

## Out-of-band contact

If both GitHub PVR and email are unavailable (e.g. the maintainer's
account is suspended), reach out via:

- LinkedIn: <https://www.linkedin.com/in/yashkanadhia>

Use these channels **only** to request a private channel; do not send
exploit details over them.
