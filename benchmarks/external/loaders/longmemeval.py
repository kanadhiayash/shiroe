"""LongMemEval loader — long-term interactive memory QA over haystack sessions.

Manual download (no auto-downloads):
    Official source: https://github.com/xiaowu0162/LongMemEval
    Download longmemeval_s.json (or longmemeval_m.json) per the repository's
    instructions (HuggingFace/Drive links in its README) and place it in the
    local dataset directory as ``longmemeval_s.json``.
"""

from __future__ import annotations

from pathlib import Path

from benchmarks.external.loaders import _common
from benchmarks.external.schema import DatasetCheck, Task, Turn, read_json

NAME = "longmemeval"
OFFICIAL_URL = "https://github.com/xiaowu0162/LongMemEval"
PINNED_VERSION = 'longmemeval_s_cleaned.json, HF xiaowu0162/longmemeval-cleaned rev 98d7416 (2026-07-29); 500 tasks. CLEANED release - not comparable to pre-Sept-2025 numbers'
PINNED_SHA256: str | None = "d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442"
LICENSE = 'MIT'
LICENSE_NOTE = 'MIT-licensed dataset and code (xiaowu0162/LongMemEval).'
# The cleaned release ships as longmemeval_s_cleaned.json. PINNED_VERSION and
# PINNED_SHA256 above both describe that file, so it is what a run should
# actually load — accept its real name first and fall back to the historical
# one. Requiring the old name forced anyone following the official download
# instructions to rename the file, and renaming it discards the one signal
# that says which release they have.
DATA_FILENAME = "longmemeval_s_cleaned.json"
ACCEPTED_FILENAMES = (DATA_FILENAME, "longmemeval_s.json")
DOWNLOAD_INSTRUCTIONS = (
    "Download longmemeval_s_cleaned.json from "
    "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned into the "
    "dataset directory (the pre-Sept-2025 longmemeval_s.json is also accepted, "
    "but its numbers are NOT comparable to the cleaned release)."
)


def _present_data_file(data_dir: str | Path) -> Path | None:
    """First accepted filename that exists, or None. Never raises."""
    directory = Path(data_dir)
    for filename in ACCEPTED_FILENAMES:
        candidate = directory / filename
        if candidate.exists():
            return candidate
    return None


def _resolve_data_file(data_dir: str | Path) -> Path:
    """First accepted filename that exists, else the standard missing-data error."""
    found = _present_data_file(data_dir)
    if found is not None:
        return found
    return _common.require_data_file(
        NAME, Path(data_dir), DATA_FILENAME, OFFICIAL_URL, DOWNLOAD_INSTRUCTIONS
    )


def load(data_dir: str | Path) -> list[Task]:
    path = _resolve_data_file(data_dir)
    items = read_json(path)
    tasks: list[Task] = []
    for item in items:
        sessions = tuple(
            tuple(
                Turn(role=str(turn.get("role", "user")), content=str(turn.get("content", "")))
                for turn in session
            )
            for session in item.get("haystack_sessions", [])
            if isinstance(session, list)
        )
        tasks.append(Task(
            task_id=str(item["question_id"]),
            benchmark=NAME,
            question=str(item["question"]),
            answers=(str(item["answer"]),),
            sessions=sessions,
            metric="token_f1",
            metadata={
                "question_type": item.get("question_type"),
                "haystack_dates": item.get("haystack_dates", []),
            },
        ))
    return tasks


def check(data_dir: str | Path) -> DatasetCheck:
    # Hash whichever accepted file is actually present, so the digest matches
    # what load() read rather than a name that may not exist on disk. When
    # nothing is present, fall back to the canonical name so run_check reports
    # a missing dataset with download instructions instead of raising.
    present = _present_data_file(data_dir)
    return _common.run_check(
        name=NAME, data_dir=data_dir,
        data_filename=present.name if present else DATA_FILENAME,
        official_url=OFFICIAL_URL, instructions=DOWNLOAD_INSTRUCTIONS,
        pinned_sha256=PINNED_SHA256, load=load,
    )


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(_common.check_cli(_sys.modules[__name__]))
