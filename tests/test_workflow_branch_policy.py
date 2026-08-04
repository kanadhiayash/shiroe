"""SHR-025 — one branch model: protected `main` plus short-lived topic branches.

`origin` carries exactly one branch, `main`. Nothing in CI and nothing a
contributor is told to do may assume a permanent integration branch (`dev`)
still exists. That assumption fails quietly rather than loudly: a workflow
filtered to `branches: [dev, main]` still runs, a PR retargeted at a missing
base is simply never opened, and the operator finds out weeks later that a
gate never fired.

**Why the YAML is parsed by regex and not by `pyyaml`.** `pyyaml` is an
*optional* extra in `pyproject.toml` (`[project.optional-dependencies].yaml`);
the project ships zero mandatory dependencies. A guard that imported it would
skip on exactly the install path most contributors use, which is the same as
not having the guard. So this file uses a **minimal targeted parser**: one
regex recognises the only YAML shapes a branch filter can take — `branches:`,
`branches-ignore:` and `target-branch:` in flow form (`[a, b]`) and in block
form (`- a`) — and a second, cruder raw-text scan catches a `dev` reference
anywhere else in the file. The raw scan is not redundant: branch names also
appear inside `if:` expressions and `run:` shell blocks, which a real YAML
loader hands back as one opaque scalar.

The synthetic-injection tests at the bottom are the point of the file. A guard
nobody has watched fail is a guard nobody knows works.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The branch name that must not come back.
RETIRED_BRANCH = "dev"

#: `dev` as a standalone token. Word characters, `/` and `-` are excluded on
#: both sides so "development", "developer", "devices", "/dev/null" and
#: "dev-only" never match — only `dev` used as a name in its own right.
DEV_TOKEN_RE = re.compile(r"(?<![\w/-])dev(?![\w/-])")

#: Every YAML key whose value is a branch name or a list of them. The optional
#: `- ` prefix matters: Dependabot writes `target-branch` inside a sequence item
#: (`updates:\n  - target-branch: dev`), so the key is not always line-initial.
BRANCH_KEY_RE = re.compile(
    r"^(?P<indent>[ \t]*(?:-[ \t]+)?)"
    r"(?P<key>branches|branches-ignore|target-branch)[ \t]*:[ \t]*(?P<inline>.*)$"
)

#: Docs a contributor is expected to follow. Anything here that names a `dev`
#: branch is an instruction to do something impossible.
CONTRIBUTOR_DOCS = (
    "CONTRIBUTING.md",
    "GITHUB_OS.md",
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "docs/BRANCHING.md",
    "docs/RELEASE_PROCESS.md",
    "docs/RELEASE_GATES.md",
    "docs/GETTING_STARTED.md",
    "docs/wiki/Architecture.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
)


# --------------------------------------------------------------------------- #
# The minimal targeted parser
# --------------------------------------------------------------------------- #

def branch_filters(text: str) -> list[str]:
    """Every branch name a CI file filters on. No YAML library involved."""
    names: list[str] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = BRANCH_KEY_RE.match(line)
        if match is None:
            continue
        inline = match.group("inline").split("#", 1)[0].strip()
        if inline.startswith("["):
            names += [item.strip().strip("'\"") for item in inline.strip("[]").split(",")]
            continue
        if inline:
            names.append(inline.strip("'\""))
            continue
        # Block form: consume the `- name` items that follow, deeper-indented.
        indent = len(match.group("indent"))
        for following in lines[index + 1:]:
            stripped = following.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if not stripped.startswith("- ") or (len(following) - len(following.lstrip())) <= indent:
                break
            names.append(stripped[2:].split("#", 1)[0].strip().strip("'\""))
    return [name for name in names if name]


def ci_files(root: Path) -> list[Path]:
    """Every GitHub Actions / Dependabot config file in the tree."""
    base = root / ".github"
    if not base.is_dir():
        return []
    return sorted(p for p in base.rglob("*") if p.suffix in {".yml", ".yaml"})


def scan(root: Path) -> list[str]:
    """Every place in `root` that assumes a permanent `dev` branch."""
    hits: list[str] = []
    for path in ci_files(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        for name in branch_filters(text):
            if name == RETIRED_BRANCH:
                hits.append(f"{rel}: branch filter names {name!r}")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if DEV_TOKEN_RE.search(line):
                hits.append(f"{rel}:{lineno}: {line.strip()}")
    for rel in CONTRIBUTOR_DOCS:
        path = root / rel
        if not path.is_file():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if DEV_TOKEN_RE.search(line):
                hits.append(f"{rel}:{lineno}: {line.strip()}")
    return hits


# --------------------------------------------------------------------------- #
# The real tree
# --------------------------------------------------------------------------- #

def test_no_ci_file_filters_on_a_dev_branch() -> None:
    offenders = [
        f"{path.relative_to(REPO_ROOT).as_posix()}: {branch_filters(path.read_text(encoding='utf-8'))}"
        for path in ci_files(REPO_ROOT)
        if RETIRED_BRANCH in branch_filters(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, (
        "CI branch filters still name a branch that does not exist on origin:\n"
        + "\n".join(offenders)
    )


def test_no_ci_file_mentions_a_dev_branch_anywhere() -> None:
    offenders = [hit for hit in scan(REPO_ROOT) if hit.startswith(".github/")]
    assert not offenders, "CI still references a `dev` branch:\n" + "\n".join(offenders)


def test_contributor_docs_do_not_name_a_dev_branch() -> None:
    offenders = [hit for hit in scan(REPO_ROOT) if not hit.startswith(".github/")]
    assert not offenders, (
        "Contributor instructions still name a `dev` branch:\n" + "\n".join(offenders)
    )


def test_branching_doc_states_the_main_only_model() -> None:
    doc = REPO_ROOT / "docs" / "BRANCHING.md"
    assert doc.is_file(), "docs/BRANCHING.md is the branch model of record and must exist"
    text = doc.read_text(encoding="utf-8")
    assert "`main`" in text, "docs/BRANCHING.md must name `main` as the trunk"
    assert "short-lived" in text, "docs/BRANCHING.md must say topic branches are short-lived"


def test_ci_files_were_actually_found() -> None:
    """A scan that reads nothing passes for the wrong reason."""
    assert len(ci_files(REPO_ROOT)) >= 2


# --------------------------------------------------------------------------- #
# Synthetic injection — the guard must actually bite
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "body, expected",
    [
        ("on:\n  push:\n    branches: [dev, main]\n", ["dev", "main"]),
        ("on:\n  push:\n    branches: ['dev', \"main\"]\n", ["dev", "main"]),
        ("on:\n  push:\n    branches:\n      - dev\n      - main\n", ["dev", "main"]),
        ("updates:\n  - target-branch: dev\n", ["dev"]),
        ("on:\n  pull_request:\n    branches-ignore: [dev]  # comment\n", ["dev"]),
        ("on:\n  push:\n    branches: [main]\n", ["main"]),
    ],
)
def test_parser_reads_every_branch_filter_shape(body: str, expected: list[str]) -> None:
    assert branch_filters(body) == expected


@pytest.mark.parametrize(
    "rel, body",
    [
        (".github/workflows/injected.yml", "on:\n  push:\n    branches: [dev, main]\n"),
        (".github/workflows/injected.yml", "on:\n  push:\n    branches:\n      - dev\n"),
        (".github/dependabot.yml", "updates:\n  - target-branch: dev\n"),
        (".github/workflows/injected.yml", "jobs:\n  a:\n    if: github.ref == 'dev'\n"),
        (".github/workflows/injected.yml", "# merged into dev before main\non: push\n"),
        ("CONTRIBUTING.md", "Open your PR against dev, not main.\n"),
        ("docs/BRANCHING.md", "Long-running `dev` collects features.\n"),
    ],
)
def test_injected_dev_reference_is_caught(tmp_path: Path, rel: str, body: str) -> None:
    target = tmp_path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    assert scan(tmp_path), f"injected {rel} was not caught: {body!r}"


@pytest.mark.parametrize(
    "body",
    [
        "# development notes for the developer\n",
        "run: cat /dev/null\n",
        "# dev-only linter pin\n",
        "# multi-device sync\n",
    ],
)
def test_english_words_are_not_mistaken_for_the_branch(tmp_path: Path, body: str) -> None:
    target = tmp_path / ".github" / "workflows" / "prose.yml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    assert not scan(tmp_path), f"false positive on {body!r}"


def test_clean_tree_scans_clean(tmp_path: Path) -> None:
    target = tmp_path / ".github" / "workflows" / "ok.yml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("on:\n  push:\n    branches: [main]\n", encoding="utf-8")
    assert scan(tmp_path) == []
