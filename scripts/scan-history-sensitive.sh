#!/usr/bin/env bash
# scan-history-sensitive.sh — read-only sensitive-data scan over the whole
# object store (SHR-029/031).
#
# Produces the evidence behind docs/security/HISTORY_REDACTION_MANIFEST.md and
# is the command a reviewer re-runs to check that manifest is still true.
#
# READ-ONLY. It runs `git cat-file`, `git rev-list`, `git for-each-ref` and
# `git fsck` only. It never writes a ref, never rewrites history, never pushes.
#
# Why blob-level and not `git grep <every commit>`: grepping each commit's tree
# re-counts an unchanged file once per commit, so a string that sat still for
# 200 commits reports as 200 hits and the number means nothing. Scanning each
# *blob* once gives "how many distinct file versions carry this", which is the
# number a redaction decision actually needs. It also reaches objects no commit
# points at any more — amends, discarded index writes, dropped stashes — which
# `rev-list --all` cannot see and which survive a naive history rewrite.
#
# Output is deliberately front-loaded with what was scanned (ref count, commit
# count, object count, blob count). An empty finding list is only meaningful
# next to the size of the haystack it came from.
#
# Usage:
#   bash scripts/scan-history-sensitive.sh [--repo <path>] [--quiet]
#
# Exit codes:
#   0  scan completed (findings are printed; findings are not an error — this
#      script reports, the manifest decides)
#   2  not a git repository, or git is unavailable

set -uo pipefail

REPO="."
QUIET=0
while [ $# -gt 0 ]; do
    case "$1" in
        --repo) REPO="${2:?--repo needs a path}"; shift 2 ;;
        --quiet) QUIET=1; shift ;;
        -h|--help) sed -n '2,28p' "$0"; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

command -v git >/dev/null 2>&1 || { echo "ERROR: git not found" >&2; exit 2; }
cd "$REPO" 2>/dev/null || { echo "ERROR: no such directory: $REPO" >&2; exit 2; }
git rev-parse --git-dir >/dev/null 2>&1 || { echo "ERROR: not a git repository: $REPO" >&2; exit 2; }

# --------------------------------------------------------------------------- #
# Pattern classes.
#
# `name|extended-regex`, one per line. The names are the manifest's
# `pattern_class` values and tests/test_redaction_manifest.py reads them from
# right here, so adding a class below forces a manifest row for it.
#
# Every regex is a *strict shape*, not a substring. `AKIA` alone matches base64
# image bytes and the word "AKIA" in redaction documentation; `AKIA` plus the
# 16 uppercase-alphanumerics an AWS key ID actually has does not. Substring
# scanning is what produced the four-figure false-positive counts in the PR 01
# inventory; the difference is the whole point of re-running this.
#
# This file spells the shapes it hunts for, so it excludes itself from the scan
# below — otherwise the scanner is permanently its own top finding.
# --------------------------------------------------------------------------- #
PATTERNS='
aws-access-key-id|AKIA[0-9A-Z]{16}
pem-private-key|-----BEGIN (RSA |OPENSSH |EC |DSA |PGP )?PRIVATE KEY-----
github-token|gh[pousr]_[A-Za-z0-9]{36}
provider-api-key|sk-(ant-)?[A-Za-z0-9_-]{20,}
private-notion-workspace|[A-Za-z0-9][A-Za-z0-9-]*[.]notion[.]site
home-rooted-absolute-path|/(Users|home)/[A-Za-z0-9._-]+/
operator-working-copy-path|(~|\$HOME)/(Desktop|Documents|Downloads|Dropbox|OneDrive)/[^[:space:]]+
personal-cloud-sync-path|com~apple~CloudDocs|Library/Mobile Documents
'

# Home/host segments that stand for "whoever runs this" rather than a person.
# Kept in step with tests/test_no_private_operational_references.py, which
# guards the current tree against the same shapes.
PLACEHOLDER='^(<.*|\{.*|\[.*|\$.*|%.*|.|example|user|username|name|you|me|someone|somebody|youruser|yourname|placeholder|redacted|home|runner|root|ubuntu|x|redacted-notion-host)$'

SELF="scripts/scan-history-sensitive.sh"
MANIFEST="docs/security/HISTORY_REDACTION_MANIFEST.md"
RUNBOOK="docs/security/HISTORY_REWRITE_RUNBOOK.md"
GUARD="tests/test_no_private_operational_references.py"

# --------------------------------------------------------------------------- #
# What we are about to scan. Printed before any finding, on purpose.
# --------------------------------------------------------------------------- #
REF_COUNT=$(git for-each-ref --format='%(refname)' | wc -l | tr -d ' ')
COMMIT_COUNT=$(git rev-list --all | wc -l | tr -d ' ')
OBJECT_COUNT=$(git cat-file --batch-all-objects --batch-check='%(objectname)' | wc -l | tr -d ' ')

BLOBS=$(mktemp); PATHMAP=$(mktemp); UNREACH=$(mktemp)
trap 'rm -f "$BLOBS" "$PATHMAP" "$UNREACH"' EXIT

git cat-file --batch-all-objects --batch-check='%(objectname) %(objecttype)' \
    | awk '$2=="blob"{print $1}' > "$BLOBS"
BLOB_COUNT=$(wc -l < "$BLOBS" | tr -d ' ')

# blob -> the path(s) it was ever committed at. Blobs absent from this map are
# unreachable: real objects in the store that no commit references.
git rev-list --all --objects | awk 'NF>1{print $1" "substr($0, index($0," ")+1)}' | sort -u > "$PATHMAP"

git fsck --unreachable --no-progress 2>/dev/null | awk '$2=="blob"{print $3}' | sort -u > "$UNREACH"
UNREACH_COUNT=$(wc -l < "$UNREACH" | tr -d ' ')

echo "scan-history-sensitive — $(git rev-parse --show-toplevel)"
echo "HEAD:            $(git rev-parse HEAD)"
echo "scanned at:      $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo
echo "Coverage"
echo "  ref count:            $REF_COUNT   (all local, remote-tracking, tag and stash refs)"
echo "  commit count:         $COMMIT_COUNT   (reachable from --all)"
echo "  object count:         $OBJECT_COUNT   (every object in the store)"
echo "  blob count:           $BLOB_COUNT   (scanned individually, once each)"
echo "  unreachable blobs:    $UNREACH_COUNT   (included above; invisible to rev-list --all)"
echo "  excluded from hits:   $SELF, $GUARD, $MANIFEST, $RUNBOOK"
echo "                        (they spell the shapes on purpose)"
echo

# --------------------------------------------------------------------------- #
# The scan. One `git cat-file` per blob, every pattern applied in one grep.
#
# ponytail: one fork per blob — ~25s for ~3k objects here. If this repo ever
# grows an order of magnitude, replace the loop with a single `git cat-file
# --batch` stream and a length-prefixed reader; not worth the parser today.
# --------------------------------------------------------------------------- #
ALL_RE=$(printf '%s\n' "$PATTERNS" | sed '/^[[:space:]]*$/d' | cut -d'|' -f2- | paste -sd'|' -)

HITS=$(mktemp); trap 'rm -f "$BLOBS" "$PATHMAP" "$UNREACH" "$HITS"' EXIT
: > "$HITS"

while read -r blob; do
    [ -n "$blob" ] || continue
    content=$(git cat-file blob "$blob" 2>/dev/null) || continue
    printf '%s' "$content" | grep -aqE "$ALL_RE" || continue

    paths=$(awk -v b="$blob" '$1==b{print substr($0, index($0," ")+1)}' "$PATHMAP")
    [ -n "$paths" ] || paths="<unreachable blob>"

    printf '%s\n' "$PATTERNS" | sed '/^[[:space:]]*$/d' | while IFS='|' read -r name rest; do
        re="$rest"
        # `-e` is required, not stylistic: the PEM shape starts with `-----`
        # and grep would read it as a bundle of short options.
        matches=$(printf '%s' "$content" | grep -aoE -e "$re" | sort -u)
        [ -n "$matches" ] || continue
        while IFS= read -r m; do
            # Second stage: drop placeholder-shaped segments so the redaction
            # pipeline's own documentation is not reported as a leak.
            seg=$(printf '%s' "$m" | sed -E 's#^/(Users|home)/##; s#/.*$##; s#[.]notion[.]site$##')
            printf '%s' "$seg" | grep -qiE "$PLACEHOLDER" && continue
            while IFS= read -r p; do
                case "$p" in
                    "$SELF"|"$GUARD"|"$MANIFEST"|"$RUNBOOK") continue ;;
                esac
                printf '%s\t%s\t%s\n' "$name" "$p" "$blob" >> "$HITS"
            done <<EOF
$paths
EOF
        done <<EOF
$matches
EOF
    done
done < "$BLOBS"

# --------------------------------------------------------------------------- #
# Commit metadata is not a blob. Author and committer identities live in the
# commit objects themselves and no blob scan can see them.
# --------------------------------------------------------------------------- #
IDENTITIES=$(git log --all --format='%an <%ae>%n%cn <%ce>' | sort -u | grep -v 'users[.]noreply[.]github[.]com' || true)
IDENT_COUNT=$(printf '%s\n' "$IDENTITIES" | sed '/^$/d' | wc -l | tr -d ' ')

# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
echo "Findings by pattern class (distinct blobs / distinct paths)"
printf '%s\n' "$PATTERNS" | sed '/^[[:space:]]*$/d' | while IFS='|' read -r name _; do
    b=$(awk -F'\t' -v n="$name" '$1==n{print $3}' "$HITS" | sort -u | wc -l | tr -d ' ')
    p=$(awk -F'\t' -v n="$name" '$1==n{print $2}' "$HITS" | sort -u | wc -l | tr -d ' ')
    printf '  %-28s blobs=%-5s paths=%s\n' "$name" "$b" "$p"
done
echo
echo "  non-noreply commit identit(ies): $IDENT_COUNT"
echo

if [ "$QUIET" -eq 0 ]; then
    echo "Paths per pattern class"
    printf '%s\n' "$PATTERNS" | sed '/^[[:space:]]*$/d' | while IFS='|' read -r name _; do
        paths=$(awk -F'\t' -v n="$name" '$1==n{print $2}' "$HITS" | sort -u)
        [ -n "$paths" ] || continue
        echo "  [$name]"
        printf '%s\n' "$paths" | sed 's/^/    /'
    done
    echo
    echo "Commit identities (excluding GitHub noreply aliases)"
    printf '%s\n' "$IDENTITIES" | sed '/^$/d;s/^/    /'
    echo
fi

echo "Nothing was rewritten. Classify each pattern class above in $MANIFEST."
exit 0
