"""HELMET loader — holistic long-context evaluation (QA subset).

Manual download (no auto-downloads):
    Official source: https://github.com/princeton-nlp/HELMET
    Follow the repository's data download instructions (data hosted per its
    README) and place the QA-style JSONL as ``helmet.jsonl`` in the local
    dataset directory.
"""

from __future__ import annotations

from pathlib import Path

from benchmarks.external.loaders import _common
from benchmarks.external.schema import DatasetCheck, Task, Turn, read_jsonl

NAME = "helmet"
OFFICIAL_URL = "https://github.com/princeton-nlp/HELMET"
PINNED_VERSION = "HELMET v1 QA subset (pin release/commit at download time)"
PINNED_SHA256: str | None = None  # record via check() after manual download
LICENSE = 'unverified'
LICENSE_NOTE = 'Licence not yet confirmed against the official release; verify before publishing numbers.'
DATA_FILENAME = "helmet.jsonl"
DOWNLOAD_INSTRUCTIONS = (
    "Follow the official README data instructions and save the QA subset as "
    f"{DATA_FILENAME} in the dataset directory."
)


def load(data_dir: str | Path) -> list[Task]:
    path = _common.require_data_file(NAME, data_dir, DATA_FILENAME, OFFICIAL_URL, DOWNLOAD_INSTRUCTIONS)
    tasks: list[Task] = []
    for item in read_jsonl(path):
        tasks.append(Task(
            task_id=str(item.get("id", len(tasks))),
            benchmark=NAME,
            question=str(item["question"]),
            answers=tuple(str(answer) for answer in item.get("answers", [])),
            sessions=((Turn(role="context", content=str(item.get("context", ""))),),),
            metric="token_f1",
            metadata={},
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
