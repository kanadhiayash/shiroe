"""ConvoMem loader — conversational long-term memory QA.

The field names below were verified against the real Salesforce/ConvoMem
release, not inferred. An earlier version of this loader guessed the schema
and every key it guessed was wrong; the superseded guesses are recorded at
the bottom of this module so the same mistake is not made twice.

DATA and CODE are two different repositories under two different licences:

    data:  https://huggingface.co/datasets/Salesforce/ConvoMem   CC-BY-NC-4.0
    code:  https://github.com/SalesforceAIResearch/ConvoMem      Apache-2.0

The GitHub repository is a Scala/Gradle evaluation harness and holds no
benchmark data. The dataset licence is NON-COMMERCIAL — see LICENSE_NOTE.

Manual download only (the harness never fetches). The release is ~2,500 JSON
files under ``core_benchmark/`` and ``legacy_benchmarks/``, not a single
file, so ``--data`` takes a directory and every ``*.json`` beneath it is read.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from benchmarks.external.loaders import _common
from benchmarks.external.schema import DatasetCheck, DatasetMissingError, Task, Turn, read_json

NAME = "convomem"
OFFICIAL_URL = "https://huggingface.co/datasets/Salesforce/ConvoMem"
CODE_URL = "https://github.com/SalesforceAIResearch/ConvoMem"
PINNED_VERSION = "Salesforce/ConvoMem (HF revision e3e9b39, 2025-11-18)"
PINNED_SHA256: str | None = None  # set to a tree_sha256() value to pin
LICENSE = "CC-BY-NC-4.0"
LICENSE_NOTE = (
    "NON-COMMERCIAL. The dataset is CC-BY-NC-4.0 even though the evaluation "
    f"code at {CODE_URL} is Apache-2.0. Published numbers must attribute "
    "Salesforce/ConvoMem, and commercial use of the data is not granted."
)
DATA_FILENAME = "."  # directory tree, not one file
DOWNLOAD_INSTRUCTIONS = (
    "Download from https://huggingface.co/datasets/Salesforce/ConvoMem "
    "(e.g. `huggingface-cli download Salesforce/ConvoMem --repo-type dataset "
    "--local-dir <dir>`) and pass that directory as --data. Any subset of the "
    "*.json files works; the loader walks the tree."
)


def _tasks_from_file(path: Path) -> list[Task]:
    """Parse one ConvoMem JSON file.

    Real shape, confirmed against the release::

        {"evidence_items": [{"question", "answer", "message_evidences",
                             "conversations": [{"messages": [{"speaker","text"}],
                                                "id", "containsEvidence"}],
                             "category", "scenario_description", "personId"}],
         "checkpoint": "<sha>"}
    """
    payload = read_json(path)
    if not isinstance(payload, dict):
        return []
    items = payload.get("evidence_items")
    if not isinstance(items, list):
        return []

    # The evidence condition (abstention, changing, user, assistant_facts,
    # preference, implicit_connection) is carried by the directory layout.
    # The item's own `category` is the persona's topic — a different axis —
    # so both are recorded rather than conflated.
    evidence_type = path.parent.parent.name or path.parent.name

    tasks: list[Task] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        question = item.get("question")
        answer = item.get("answer")
        if not question or answer is None:
            continue
        sessions = tuple(
            tuple(
                Turn(role=str(msg.get("speaker", "user")), content=str(msg.get("text", "")))
                for msg in conversation.get("messages", [])
                if isinstance(msg, dict)
            )
            for conversation in item.get("conversations", [])
            if isinstance(conversation, dict)
        )
        person_id = str(item.get("personId", path.stem))
        tasks.append(Task(
            task_id=f"{person_id}:{evidence_type}:{index}",
            benchmark=NAME,
            question=str(question),
            answers=(str(answer),),
            sessions=sessions,
            # ConvoMem is built for LLM-as-judge scoring. Abstention gold
            # answers are full sentences ("There is no information in prior
            # conversations to answer this question"), which token overlap
            # scores badly, so token_f1 is a cheap secondary signal here and
            # never the official metric.
            metric="token_f1",
            metadata={
                "evidence_type": evidence_type,
                "topic_category": item.get("category"),
                "person_id": person_id,
                "checkpoint": payload.get("checkpoint"),
                "source_file": path.name,
            },
        ))
    return tasks


def load(data_dir: str | Path) -> list[Task]:
    directory = Path(data_dir)
    files = sorted(p for p in directory.rglob("*.json") if p.is_file()) if directory.exists() else []
    if not files:
        raise DatasetMissingError(
            _common.missing_dataset_message(
                NAME, directory, OFFICIAL_URL, DOWNLOAD_INSTRUCTIONS
            )
        )
    tasks: list[Task] = []
    for path in files:
        tasks.extend(_tasks_from_file(path))
    return tasks


def tree_sha256(data_dir: str | Path) -> str | None:
    """Deterministic digest over the whole dataset tree.

    ConvoMem ships as thousands of files, so there is no single file to hash
    — but a scored run still needs one reproducible number identifying
    exactly which data produced it. Digest of the sorted
    (relative path, file digest) pairs: stable across machines, and it
    changes if any file is added, removed, or edited.
    """
    directory = Path(data_dir)
    files = sorted(p for p in directory.rglob("*.json") if p.is_file())
    if not files:
        return None
    accumulator = hashlib.sha256()
    for path in files:
        accumulator.update(path.relative_to(directory).as_posix().encode("utf-8"))
        accumulator.update(b"\0")
        accumulator.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii"))
        accumulator.update(b"\n")
    return accumulator.hexdigest()


def check(data_dir: str | Path) -> DatasetCheck:
    directory = Path(data_dir)
    errors: list[str] = []
    task_count = 0
    try:
        task_count = len(load(directory))
    except DatasetMissingError as exc:
        errors.append(str(exc))
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"parse error: {exc}")
    if not errors and task_count == 0:
        errors.append(
            "no tasks parsed — the directory has *.json files but none matched "
            "the ConvoMem evidence_items shape"
        )
    return DatasetCheck(
        ok=not errors,
        dataset=NAME,
        path=str(directory),
        errors=tuple(errors),
        task_count=task_count,
        sha256_actual=tree_sha256(directory),
        sha256_pinned=PINNED_SHA256,
    )


# Superseded guesses, kept deliberately. NONE of these keys exist in the real
# release: conversation_id, sessions, turns, questions, qid. The real release
# nests question/answer on each evidence_item, groups turns under
# conversations[].messages[], and identifies a record by personId.
_SUPERSEDED_GUESSES = ("conversation_id", "sessions", "turns", "questions", "qid")


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(_common.check_cli(_sys.modules[__name__]))
