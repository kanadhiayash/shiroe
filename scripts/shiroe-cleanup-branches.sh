#!/usr/bin/env bash
# Zeref local cleanup: remove worktrees and branches whose work is already on dev.
#
# Safety model — a branch is deleted only if BOTH are true:
#   1. it is not dev or main, and
#   2. either its PR is MERGED, or `git diff origin/dev <branch>` shows no file
#      with content unique to the branch.
# Squash merges leave branch tips unreachable from dev, so `git branch -d`
# refuses them. This checks content instead, then uses -D.
#
# Dry run by default. Pass --apply to actually delete.

set -euo pipefail

REPO="$HOME/Desktop/ZEREF/zeref"
APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1

cd "$REPO"

echo "==> repo: $REPO"
echo "==> fetching and pruning remote refs"
git fetch --all --prune --quiet

# Refuse to touch a dirty tree. An earlier version switched to dev
# unconditionally, which silently carried uncommitted work off the branch it
# was made on — a cleanup tool must never move your changes for you.
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "!! working tree has uncommitted changes. Commit or stash first." >&2
  git status --short --untracked-files=no >&2
  exit 1
fi

CUR=$(git rev-parse --abbrev-ref HEAD)
if [ "$CUR" != "dev" ]; then
  echo "==> switching to dev (was on $CUR)"
  git checkout dev --quiet
fi
git pull --ff-only --quiet
echo "==> dev is at $(git rev-parse --short HEAD)"

echo
echo "==> collecting merged PR head branches"
MERGED_PR=$(gh pr list --state merged --limit 100 --json headRefName -q '.[].headRefName' | sort -u)

SAFE=()
KEEP=()
for b in $(git for-each-ref --format='%(refname:short)' refs/heads); do
  case "$b" in dev|main) continue;; esac
  if echo "$MERGED_PR" | grep -qx "$b"; then
    SAFE+=("$b"); continue
  fi
  # No merged PR record. Safe only if every file this branch touched already
  # has the branch's content on dev.
  #
  # Two wrong tests were tried first, both worth avoiding:
  #   * "files with additions and zero deletions" cleared any branch that
  #     MODIFIES lines (a CI pin bump is 16 added / 16 removed in one file),
  #     which would have deleted unmerged work.
  #   * plain `git diff --quiet origin/dev <branch>` cannot tell "behind" from
  #     "ahead", so it flagged every stale-but-fully-landed branch as unsafe.
  #
  # Correct test: take the files the branch changed since it forked (three-dot),
  # then compare the branch's version of just those files against dev. If they
  # match, dev already has everything the branch carries.
  files=$(git diff --name-only "origin/dev...$b" 2>/dev/null)
  if [ -z "$files" ]; then
    SAFE+=("$b")
  elif git diff --quiet origin/dev "$b" -- $files 2>/dev/null; then
    SAFE+=("$b")
  else
    n=$(git diff --name-only origin/dev "$b" -- $files 2>/dev/null | wc -l | tr -d ' ')
    KEEP+=("$b ($n file(s) whose content is NOT on dev)")
  fi
done

echo
echo "==> SAFE TO DELETE (${#SAFE[@]}):"
printf '    %s\n' "${SAFE[@]}"

if [ ${#KEEP[@]} -gt 0 ]; then
  echo
  echo "==> KEEPING — has content not on dev:"
  printf '    %s\n' "${KEEP[@]}"
fi

if [ "$APPLY" -eq 0 ]; then
  echo
  echo "==> DRY RUN. Nothing changed. Re-run with:  scripts/shiroe-cleanup-branches.sh --apply"
  exit 0
fi

echo
echo "==> removing worktrees for those branches"
# Parse worktree list into path+branch pairs, remove any whose branch is safe.
git worktree list --porcelain | awk '
  /^worktree /{p=$2}
  /^branch /{gsub("refs/heads/","",$2); print p"\t"$2}
' | while IFS=$'\t' read -r path branch; do
  for s in "${SAFE[@]}"; do
    if [ "$branch" = "$s" ]; then
      echo "    removing worktree $path"
      git worktree remove --force "$path" || echo "      (skipped: $path)"
      break
    fi
  done
done
git worktree prune

echo
echo "==> deleting local branches"
for b in "${SAFE[@]}"; do
  git branch -D "$b" >/dev/null 2>&1 && echo "    deleted $b" || echo "    skipped $b (in use or already gone)"
done

echo
echo "==> deleting merged remote branches"
for b in "${SAFE[@]}"; do
  if git ls-remote --exit-code --heads origin "$b" >/dev/null 2>&1; then
    git push origin --delete "$b" >/dev/null 2>&1 && echo "    deleted origin/$b" || echo "    skipped origin/$b"
  fi
done

echo
echo "==> final state"
git worktree list
echo
git branch -vv
echo
echo "==> done. dev at $(git rev-parse --short HEAD)"
