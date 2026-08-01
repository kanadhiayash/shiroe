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
PINNED_VERSION = (
    "PersonaMem v1, 32k tier, HF bowen-upenn/PersonaMem rev "
    "73dfd752d477d0c466cd441f1669397f5726d7ab (2026-07-29); 589 tasks over "
    "37 shared contexts"
)
# Hash of the DERIVED personamem.json, not of an upstream file: the release
# ships questions_32k.csv + shared_contexts_32k.jsonl, and
# scripts/fetch-benchmark-data.py:fetch_personamem converts them into the flat
# shape this loader reads. The conversion is deterministic (CSV row order,
# json.dumps indent=2), so the hash is stable — but it pins the CONVERTER as
# well as the source. Changing fetch_personamem invalidates this pin, and it
# should: a different conversion is a different dataset.
PINNED_SHA256: str | None = "408c8d197fa84dfb73e0caacdffc4f1940cc8e70f2fa2d6c23ffc7239988df36"
LICENSE = 'CC-BY-4.0 (PersonaMem-v2) / MIT (PersonaMem-v1)'
LICENSE_NOTE = 'Verified 2026-07-29: HF bowen-upenn/PersonaMem-v2 is cc-by-4.0, PersonaMem-v1 is mit, and the GitHub code repo bowen-upenn/PersonaMem is MIT. Record WHICH version a run used — the terms differ between v1 and v2.'
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
