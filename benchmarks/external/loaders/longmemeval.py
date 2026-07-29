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
PINNED_VERSION = "longmemeval_s v1 (pin release/commit at download time)"
PINNED_SHA256: str | None = None  # record via check() after manual download
LICENSE = 'MIT'
LICENSE_NOTE = 'MIT-licensed dataset and code (xiaowu0162/LongMemEval).'
DATA_FILENAME = "longmemeval_s.json"
DOWNLOAD_INSTRUCTIONS = (
    "Follow the official README download links and save the file as "
    f"{DATA_FILENAME} in the dataset directory."
)


def load(data_dir: str | Path) -> list[Task]:
    path = _common.require_data_file(NAME, data_dir, DATA_FILENAME, OFFICIAL_URL, DOWNLOAD_INSTRUCTIONS)
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
    return _common.run_check(
        name=NAME, data_dir=data_dir, data_filename=DATA_FILENAME,
        official_url=OFFICIAL_URL, instructions=DOWNLOAD_INSTRUCTIONS,
        pinned_sha256=PINNED_SHA256, load=load,
    )


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(_common.check_cli(_sys.modules[__name__]))
