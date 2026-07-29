"""ConvoMem loader — conversational long-term memory QA (Wave 4).

Manual download (no auto-downloads):
    Official source: https://github.com/convomem/convomem (verify before use —
    this loader's field names were built to the common Task shape used by the
    other loaders in this directory and have NOT been checked against a live
    download under the WS5 no-network-fetch constraint on this task. Confirm
    the real release's JSON keys match ``load()`` below before pinning
    PINNED_SHA256 or running Phase B; adjust the parsing here if they differ.
    Download the dataset's conversations file per the repository's README and
    place it in the local dataset directory as ``convomem.json``.
"""

from __future__ import annotations

from pathlib import Path

from benchmarks.external.loaders import _common
from benchmarks.external.schema import DatasetCheck, Task, Turn, read_json

NAME = "convomem"
OFFICIAL_URL = "https://github.com/convomem/convomem"
PINNED_VERSION = "convomem (pin release/commit at download time)"
PINNED_SHA256: str | None = None  # record via check() after manual download
DATA_FILENAME = "convomem.json"
DOWNLOAD_INSTRUCTIONS = (
    "Follow the official repository's download instructions and save the "
    f"conversations file as {DATA_FILENAME} in the dataset directory."
)


def load(data_dir: str | Path) -> list[Task]:
    path = _common.require_data_file(NAME, data_dir, DATA_FILENAME, OFFICIAL_URL, DOWNLOAD_INSTRUCTIONS)
    conversations = read_json(path)
    tasks: list[Task] = []
    for conv in conversations:
        conv_id = str(conv["conversation_id"])
        sessions = tuple(
            tuple(
                Turn(role=str(turn.get("speaker", "user")), content=str(turn.get("text", "")))
                for turn in session.get("turns", [])
            )
            for session in conv.get("sessions", [])
            if isinstance(session, dict)
        )
        for question in conv.get("questions", []):
            answer = question.get("answer")
            if answer is None:
                continue
            tasks.append(Task(
                task_id=f"{conv_id}:{question.get('qid', len(tasks))}",
                benchmark=NAME,
                question=str(question["question"]),
                answers=(str(answer),),
                sessions=sessions,
                metric="token_f1",
                metadata={"category": question.get("category")},
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
