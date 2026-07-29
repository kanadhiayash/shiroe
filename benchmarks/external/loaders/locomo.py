"""LoCoMo loader — long-term conversational memory QA.

Manual download (no auto-downloads):
    Official source: https://github.com/snap-research/locomo
    Fetch data/locomo10.json from the repository release and place it in the
    local dataset directory as ``locomo10.json``.
"""

from __future__ import annotations

from pathlib import Path

from benchmarks.external.loaders import _common
from benchmarks.external.schema import DatasetCheck, Task, Turn, read_json

NAME = "locomo"
OFFICIAL_URL = "https://github.com/snap-research/locomo"
PINNED_VERSION = "locomo10 (repo snapshot, pin commit at download time)"
# Pin the sha256 of the downloaded locomo10.json here after the manual
# download; None means "not yet pinned" and check() will report the actual
# hash so it can be recorded before any published run.
PINNED_SHA256: str | None = None
LICENSE = 'see LICENSE.txt in snap-research/locomo (no SPDX identifier declared)'
LICENSE_NOTE = "GitHub reports NOASSERTION; confirm terms in the repo's LICENSE.txt before publishing numbers."
DATA_FILENAME = "locomo10.json"
DOWNLOAD_INSTRUCTIONS = (
    "From the official repository, download data/locomo10.json and save it as "
    f"{DATA_FILENAME} in the dataset directory."
)


def load(data_dir: str | Path) -> list[Task]:
    path = _common.require_data_file(NAME, data_dir, DATA_FILENAME, OFFICIAL_URL, DOWNLOAD_INSTRUCTIONS)
    samples = read_json(path)
    tasks: list[Task] = []
    for sample in samples:
        sample_id = str(sample["sample_id"])
        conversation = sample.get("conversation", {})
        sessions = []
        for key in sorted(k for k in conversation if k.startswith("session_")):
            turns = conversation[key]
            if not isinstance(turns, list):
                continue
            sessions.append(tuple(
                Turn(role=str(turn.get("speaker", "user")), content=str(turn.get("text", "")))
                for turn in turns
            ))
        for idx, qa in enumerate(sample.get("qa", [])):
            answer = qa.get("answer")
            if answer is None:
                continue
            tasks.append(Task(
                task_id=f"{sample_id}:qa{idx}",
                benchmark=NAME,
                question=str(qa["question"]),
                answers=(str(answer),),
                sessions=tuple(sessions),
                metric="token_f1",
                metadata={"category": qa.get("category")},
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
