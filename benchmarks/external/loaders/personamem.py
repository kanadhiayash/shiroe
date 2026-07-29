"""PersonaMem loader — persona-grounded multiple-choice memory questions.

Manual download (no auto-downloads):
    Official source: https://github.com/bowen-upenn/PersonaMem
    Download the released question/context files per the repository README
    (HuggingFace dataset links) and export them as ``personamem.json`` — a
    JSON list of question objects — in the local dataset directory.
"""

from __future__ import annotations

from pathlib import Path

from benchmarks.external.loaders import _common
from benchmarks.external.schema import DatasetCheck, Task, Turn, read_json

NAME = "personamem"
OFFICIAL_URL = "https://github.com/bowen-upenn/PersonaMem"
PINNED_VERSION = "PersonaMem v1 (pin HF dataset revision at download time)"
PINNED_SHA256: str | None = None  # record via check() after manual download
LICENSE = 'unverified'
LICENSE_NOTE = 'Licence not yet confirmed against the official release; verify before publishing numbers.'
DATA_FILENAME = "personamem.json"
DOWNLOAD_INSTRUCTIONS = (
    "Follow the official README to obtain the benchmark files and export a "
    f"JSON list of question objects as {DATA_FILENAME} in the dataset directory."
)


def load(data_dir: str | Path) -> list[Task]:
    path = _common.require_data_file(NAME, data_dir, DATA_FILENAME, OFFICIAL_URL, DOWNLOAD_INSTRUCTIONS)
    items = read_json(path)
    tasks: list[Task] = []
    for item in items:
        context = tuple(
            Turn(role=str(turn.get("role", "user")), content=str(turn.get("content", "")))
            for turn in item.get("context", [])
        )
        tasks.append(Task(
            task_id=str(item["question_id"]),
            benchmark=NAME,
            question=str(item["question"]),
            answers=(str(item["correct_answer"]),),
            sessions=(context,) if context else (),
            metric="choice_accuracy",
            options=tuple(str(option) for option in item.get("options", [])),
            metadata={"persona_id": item.get("persona_id")},
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
