from __future__ import annotations

import csv
from pathlib import Path

from shiroe.lineage.importer import SourceIdentity, import_lineage, inventory_tree
from shiroe.lineage.intake import REQUIRED_COLUMNS


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _row(row_id: int, repo: str = "owner/repo", url: str | None = None) -> dict[str, str]:
    return {
        "id": str(row_id),
        "section": "A",
        "repo_name": repo,
        "source_link_raw": repo,
        "repo_url": url or f"https://github.com/{repo}",
        "owner": repo.split("/")[0],
        "source_type": "repository",
        "category": "memory",
        "decision_from_lineage": "test",
        "shiroe_adoption": "Adapt",
        "priority": "high",
        "council_lens": "Memory Architect",
        "why_it_matters_to_shiroe": "test",
        "guardrail": "Do not bloat core.",
        "implementation_route": "test route",
        "next_analysis_question": "What is missing?",
    }


def test_import_lineage_dedupes_repositories_in_dry_run(tmp_path: Path) -> None:
    csv_path = tmp_path / "lineage.csv"
    _write_csv(csv_path, [_row(1), _row(2)])

    def resolver(row):
        return SourceIdentity(
            repo_url=f"https://github.com/{row.github_repo}",
            owner_name=row.github_repo,
            default_branch="main",
            commit_sha="abc123",
            archived=False,
            private=False,
            updated_at="2026-01-01T00:00:00Z",
            license="MIT",
            subdirectory=row.subdirectory,
            row_ids=[row.id],
            source_kind=row.source_kind,
            notes=[],
        )

    result = import_lineage(csv_path, root=tmp_path, sandbox=True, latest_default=True, dry_run=True, resolver=resolver)

    assert result["passed"] is True
    assert result["source_count"] == 1
    assert result["sources"][0]["identity"]["row_ids"] == [1, 2]
    assert result["sources"][0]["planned_action"] == "resolve_only"
    assert not (tmp_path / ".shiroe-sandbox").exists()


def test_inventory_tree_records_lines_hashes_and_exclusions(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "a.py").write_text("one\ntwo\n", encoding="utf-8")
    (root / "vendor").mkdir()
    (root / "vendor" / "bundle.py").write_text("ignored\n", encoding="utf-8")
    (root / "image.png").write_bytes(b"\x89PNG\r\n")

    result = inventory_tree(root)

    assert result["file_count"] == 1
    assert result["line_count"] == 2
    assert result["files"][0]["path"] == "src/a.py"
    assert result["files"][0]["sha256"]
    assert {"path": "vendor/bundle.py", "reason": "excluded_path"} in result["exclusions"]
    assert {"path": "image.png", "reason": "non_text_extension"} in result["exclusions"]
