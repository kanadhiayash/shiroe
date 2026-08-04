# History rewrite runbook (SHR-029, SHR-031)

> ## STOP
>
> **No step in this document may be run without written owner approval of a
> specific version of `docs/security/HISTORY_REDACTION_MANIFEST.md`.**
>
> Approval means: the owner names the manifest's commit SHA, names which
> candidate ids are approved for removal, and says so in writing. "Go ahead and
> clean up the history" is not approval — it does not identify what gets removed
> or which version of the evidence was read. Blanket approval does not carry
> forward to a later manifest version.
>
> This runbook is the procedure **if** that approval arrives. As of the commit
> that introduced this file, it has not. Nothing here has been executed.
>
> Before running any of it, read
> [`HISTORY_REDACTION_MANIFEST.md` → What the owner is being asked to decide](HISTORY_REDACTION_MANIFEST.md#what-the-owner-is-being-asked-to-decide).
> The cheapest fix for the one finding that matters is **not** a history rewrite,
> and doing the rewrite first wastes the expensive option on a problem the free
> one solves better.

---

## Approval record

Fill this in before step 1. If any row is blank, stop.

| Field | Value |
|---|---|
| Manifest version approved (commit SHA) | |
| Candidate ids approved for removal | |
| Approved by (name) | |
| Approved on (UTC) | |
| Where the written approval lives | |
| Executed by | |
| Executed on (UTC) | |

---

## Preconditions

- `git-filter-repo` installed (`pipx install git-filter-repo`). **Not**
  `filter-branch`, which is deprecated, and **not** BFG, which cannot express
  the replacement rules below.
- A clone you are willing to destroy. `filter-repo` refuses to run on a
  non-fresh clone without `--force`, and that refusal is a feature — do not pass
  `--force` to get around it, make a fresh clone instead.
- Admin rights on the GitHub repository (branch protection on `main` must be
  temporarily lifted and then restored).
- Every collaborator notified **before** you start, not after. After the force
  push, their existing clones cannot be reconciled by fetching.
- At least 2 GB free for the mirror backup.

---

## Step 1 — Offline mirror backup

Take this before anything else. It is the only way back.

```bash
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP="$HOME/shiroe-history-backup-$STAMP"

git clone --mirror https://github.com/kanadhiayash/shiroe.git "$BACKUP.git"
git -C "$BACKUP.git" fsck --full
tar -czf "$BACKUP.tar.gz" -C "$(dirname "$BACKUP.git")" "$(basename "$BACKUP.git")"
shasum -a 256 "$BACKUP.tar.gz" | tee "$BACKUP.tar.gz.sha256"
```

Move the tarball to storage that is **not** the machine doing the rewrite and
**not** any cloud folder that syncs back to it. Record the SHA-256 in the
approval record above.

Verify the backup is restorable before continuing — an unverified backup is not
a backup:

```bash
git clone "$BACKUP.git" /tmp/restore-check && git -C /tmp/restore-check log --oneline | head -3
rm -rf /tmp/restore-check
```

## Step 2 — Refs manifest

Capture the exact pre-rewrite state so step 6 has something to diff against.

```bash
OUT="$BACKUP-refs"
mkdir -p "$OUT"

git -C "$BACKUP.git" for-each-ref --format='%(objectname) %(refname)' | sort > "$OUT/refs-before.txt"
git -C "$BACKUP.git" rev-list --all | sort                                     > "$OUT/commits-before.txt"
git -C "$BACKUP.git" tag --list                                                > "$OUT/tags-before.txt"
git -C "$BACKUP.git" count-objects -v                                          > "$OUT/objects-before.txt"

wc -l "$OUT"/*.txt
```

Expected at the manifest's recorded commit: 29 refs, 243 commits, 3 tags. If
your counts differ, the repository moved since the manifest was recorded — **go
back and re-run the scan and re-approve**, do not proceed against stale evidence.

## Step 3 — Baseline scan

```bash
bash scripts/scan-history-sensitive.sh --repo "$BACKUP.git" | tee "$OUT/scan-before.txt"
```

This is the "before" half of the proof. Keep it.

## Step 4 — Write the replacement expressions

`filter-repo` reads replacements from a file. **Create it outside the
repository and never commit it** — it contains, in plaintext, exactly the
strings this whole exercise exists to remove.

```bash
EXPR="$OUT/expressions.txt"   # outside the working tree, deliberately
touch "$EXPR" && chmod 600 "$EXPR"
```

Put one rule per line, `literal==>replacement`, or `regex:<pattern>==>replacement`.
Write only the rules for the candidate ids in the approval record.

For **SHR-029-C2 / SHR-029-C3** (the Notion URL) — write the host with real
dots, not the defanged form the manifest uses:

```
regex:https?://copper-tv-288\.notion\.site/[A-Za-z0-9-]*==><redacted:private-notion-url>
regex:copper-tv-288\.notion\.site==><redacted-notion-host>
```

Order matters: the URL rule must come before the bare-host rule, or the host
rule fires first and leaves a dangling path fragment behind.

For **SHR-029-C5** (operator home paths) — the manifest deliberately does not
spell the two account-name segments. Read them off the machine instead of
copying them from a document:

```bash
HOMEROOT="/Users"        # "/home" on Linux
printf 'regex:%s/%s(?=/)==>%s/<operator>\n' "$HOMEROOT" "$(id -un)" "$HOMEROOT" >> "$EXPR"
```

(The home root is assembled from a variable rather than typed as a literal for
the same reason the account name is read from `id -un`: this file is tracked, and
`tests/test_no_private_operational_references.py` is right to reject a rooted
operator path in a tracked file even when the file is describing how to remove
one.)

Add the second, older account-name segment by hand if it differs from the
current one; `git log --all --format='%ae' | sort -u` and the paths listed under
`SHR-029-C5` in the manifest will tell you which files to look in.

Sanity-check the file before using it:

```bash
wc -l "$EXPR" && sed 's/==>.*/==> [replacement]/' "$EXPR"   # shape only, not values
```

## Step 5 — The rewrite

Run it on a **fresh clone of the mirror**, never on your working tree.

```bash
WORK="$OUT/rewrite"
git clone "$BACKUP.git" "$WORK"
cd "$WORK"

git filter-repo \
    --replace-text "$EXPR" \
    --replace-refs delete-no-add
```

Notes on the flags, because the wrong ones here are unrecoverable:

- `--replace-text` rewrites **blob content** wherever it appears, at any path,
  in any commit. It is content-scoped, not path-scoped — which is what you want:
  the URL moved between 14 paths over its life, and a `--path`-scoped run would
  miss the ones you forgot.
- Do **not** use `--invert-paths --path <file>` to "just delete the files". It
  deletes whole files from history, including their non-sensitive content, and
  it would silently drop `README.md` and `CHANGELOG.md` from every historical
  commit.
- `--replace-refs delete-no-add` keeps `refs/replace/` from filling with
  old→new mappings that would quietly resurrect the old objects on push.
- `filter-repo` removes the `origin` remote on purpose. Do not add it back until
  step 6 passes.

## Step 6 — Verify every ref

```bash
git for-each-ref --format='%(objectname) %(refname)' | sort > "$OUT/refs-after.txt"
git rev-list --all | sort                                   > "$OUT/commits-after.txt"
git tag --list                                              > "$OUT/tags-after.txt"

# Counts must match; SHAs must all differ.
diff <(wc -l < "$OUT/commits-before.txt") <(wc -l < "$OUT/commits-after.txt") \
  && echo "commit count preserved"
comm -12 "$OUT/commits-before.txt" "$OUT/commits-after.txt" \
  | tee "$OUT/unchanged-shas.txt" | wc -l
```

`unchanged-shas.txt` should contain only commits that predate the first
occurrence of every replaced string. If a commit *after* that point kept its
SHA, the rewrite did not touch it and your expressions are wrong.

Then re-run the scan and diff it against step 3:

```bash
bash scripts/scan-history-sensitive.sh --repo . | tee "$OUT/scan-after.txt"
diff "$OUT/scan-before.txt" "$OUT/scan-after.txt"
```

Every approved candidate must report `blobs=0 paths=0`. Any that does not is a
failed rewrite — **stop, do not push**, fix the expressions and re-run from a
fresh clone of the mirror.

Confirm all three tags survived and point at rewritten commits:

```bash
diff "$OUT/tags-before.txt" "$OUT/tags-after.txt" && echo "tag set preserved"
for t in $(git tag --list); do git rev-parse "$t"; done
```

Annotated tags are rewritten in place by `filter-repo`; lightweight tags follow
their commit. Neither needs manual re-creation, but both need checking.

## Step 7 — Fresh-clone check

Verification inside the rewritten repo can be fooled by leftover objects. Clone
it fresh and check there.

```bash
git clone "$WORK" "$OUT/fresh" && cd "$OUT/fresh"
bash scripts/scan-history-sensitive.sh --repo . | tee "$OUT/scan-fresh.txt"
```

A fresh clone carries no reflog and no unreachable objects, so this is also the
check that closes **SHR-029-C3**. If the fresh clone is clean and the rewritten
repo is not, the difference is unreachable objects — see step 8.

## Step 8 — Prune the local object store (closes SHR-029-C3)

Only in the rewritten repo, and only after step 7 passes. **This discards all
reflogs**, i.e. the undo history for recent local work.

```bash
cd "$WORK"
git reflog expire --expire=now --expire-unreachable=now --all
git gc --prune=now --aggressive
git fsck --unreachable --no-progress | awk '$2=="blob"{print $3}' | wc -l   # expect 0
```

Every collaborator must run the equivalent in their own clone, or re-clone —
which is simpler, and is required anyway by step 10.

## Step 9 — Push

Lift branch protection on `main` in GitHub Settings first, and write down what
it was set to so you can restore it exactly.

```bash
cd "$WORK"
git remote add origin https://github.com/kanadhiayash/shiroe.git
git push --force --all origin
git push --force --tags origin
```

Restore branch protection immediately afterwards.

Then re-verify against the remote, not against your local copy:

```bash
git clone https://github.com/kanadhiayash/shiroe.git "$OUT/remote-check"
bash scripts/scan-history-sensitive.sh --repo "$OUT/remote-check" | tee "$OUT/scan-remote.txt"
```

## Step 10 — The parts a rewrite does not reach

The force push does not end the exposure. All four of these are required to
finish the job, and none of them is a git command.

1. **GitHub cached views.** Old commits stay addressable by SHA through the web
   UI and API after a force push, and pull requests keep rendering them. Open a
   GitHub Support request asking them to purge cached views and stale refs for
   `kanadhiayash/shiroe`, quoting the approved manifest version. Until that
   completes, the strings are still fetchable from GitHub.
2. **Forks.** Any fork made before the rewrite keeps the full old history and is
   outside the owner's control. Check `gh api repos/kanadhiayash/shiroe/forks`
   and contact each fork owner. If a fork exists, treat removal as best-effort,
   not as achieved.
3. **Collaborator clones.** Every collaborator must delete their clone and
   re-clone. Rebasing or fetching will re-introduce the old objects on their next
   push, silently undoing the rewrite. Send the instruction explicitly; do not
   assume.
4. **CI caches and artifacts.** Purge Actions caches and any stored artifacts
   built from pre-rewrite commits.

## Step 11 — Close the loop

- Update `docs/security/HISTORY_REDACTION_MANIFEST.md`: set
  `rewrite_performed: true`, record the executing commit, and move the executed
  candidates' `approval` field from `NOT GRANTED` to the approval record.
- Re-run the repository's gates: `python -m pytest`,
  `python scripts/check-canon-consistency.py --root .`,
  `python scripts/check-active-identity.py --root .`.
- File the scan artifacts (`scan-before.txt`, `scan-after.txt`,
  `scan-fresh.txt`, `scan-remote.txt`, `refs-before.txt`, `refs-after.txt`) with
  the approval record.
- **Delete `expressions.txt`** and shred it if the filesystem supports it. It is
  the one artifact of this procedure that contains what you removed.
- Keep the mirror backup for at least 90 days.

---

## Rollback

Before step 9, rollback is free: delete `$WORK` and start again from the mirror.

After step 9, restore from the mirror backup:

```bash
git clone "$BACKUP.git" "$OUT/rollback" && cd "$OUT/rollback"
git remote set-url origin https://github.com/kanadhiayash/shiroe.git
git push --force --all origin && git push --force --tags origin
```

This restores the old SHAs, and with them the strings the rewrite removed. It
does not un-notify collaborators who already re-cloned. Rolling back is
therefore a decision of the same weight as rolling forward — treat it as one.
