#!/usr/bin/env python3
"""Fetch external benchmark datasets to a local directory.

Standard library only — no huggingface_hub, no git-lfs, no new dependency of
any kind. Downloads land OUTSIDE the repository by default so a dataset can
never be committed by accident.

Nothing here runs during tests or CI. The harness itself never fetches; this
script is the deliberate, explicit download step.

    python3 scripts/fetch-benchmark-data.py --list
    python3 scripts/fetch-benchmark-data.py --dataset locomo
    python3 scripts/fetch-benchmark-data.py --all

Licences differ per dataset and some are restrictive — ConvoMem is
CC-BY-NC-4.0 (non-commercial). Each dataset's terms are printed before its
download starts. You are responsible for complying with them.
"""

from __future__ import annotations

import argparse
import ast
import csv
import http.client
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_ROOT = Path(os.environ.get("ZEREF_BENCHMARK_DATA", Path.home() / "shiroe-benchmark-data"))
USER_AGENT = "shiroe-benchmark-fetch/1.0 (+https://github.com/kanadhiayash/shiroe)"
HF = "https://huggingface.co"


def _ssl_context() -> "ssl.SSLContext":
    """A verifying TLS context, with an explicit CA bundle if one is needed.

    Some python.org macOS builds ship without a configured trust store, so
    the default context fails CERTIFICATE_VERIFY_FAILED on every host. Fall
    back to certifi's bundle, then the system bundle. Verification is never
    disabled — an unverified download of benchmark data would undermine the
    provenance hashes this whole pipeline depends on.
    """
    context = ssl.create_default_context()
    if context.cert_store_stats().get("x509_ca", 0):
        return context
    for candidate in (_certifi_path(), "/etc/ssl/cert.pem"):
        if candidate and Path(candidate).exists():
            return ssl.create_default_context(cafile=candidate)
    return context


def _certifi_path() -> str | None:
    try:
        import certifi
    except ImportError:
        return None
    return certifi.where()


_SSL = None


def _opener_kwargs() -> dict:
    global _SSL
    if _SSL is None:
        _SSL = _ssl_context()
    return {"context": _SSL}


def _get(url: str, timeout: int = 120) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout, **_opener_kwargs()) as response:
        return response.read()


# A multi-thousand-file dataset pull will meet at least one dropped
# connection. Retrying here, in the one function every fetcher calls, keeps
# a single transient failure from aborting the remaining files — which is
# what happened to a ConvoMem pull that died at 1890/2500 on
# "[Errno 54] Connection reset by peer" and lost the rest of the run.
DOWNLOAD_RETRIES = 4
RETRY_BACKOFF_S = 2.0
# 429 and 5xx are transient. 401/403/404 are not, and retrying them just
# burns time on a request that will never succeed.
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
_TRANSIENT = (
    urllib.error.URLError,
    TimeoutError,
    ConnectionError,          # covers ConnectionResetError (Errno 54)
    http.client.IncompleteRead,
)


def _download(url: str, dest: Path, timeout: int = 300) -> bool:
    """Download to `dest`. Returns True if fetched, False if already present.

    Writes via a .part file and renames, so an interrupted run never leaves a
    truncated file that looks complete on the next pass. Transient network
    failures are retried with backoff; the partial .part is discarded between
    attempts so a resumed byte stream can never be spliced onto a stale one.
    """
    if dest.exists() and dest.stat().st_size > 0:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")

    last_error: Exception | None = None
    for attempt in range(DOWNLOAD_RETRIES):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout, **_opener_kwargs()) as response, part.open("wb") as handle:
                while True:
                    chunk = response.read(1 << 20)
                    if not chunk:
                        break
                    handle.write(chunk)
            part.rename(dest)
            return True
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in RETRYABLE_STATUS:
                part.unlink(missing_ok=True)
                raise
        except _TRANSIENT as exc:
            last_error = exc
        part.unlink(missing_ok=True)
        if attempt < DOWNLOAD_RETRIES - 1:
            time.sleep(RETRY_BACKOFF_S * (2 ** attempt))

    raise RuntimeError(
        f"failed to download {dest.name} after {DOWNLOAD_RETRIES} attempts: {last_error}"
    )


def _hf_tree(repo: str) -> list[dict]:
    """List every file in a HuggingFace dataset repo, following pagination."""
    out: list[dict] = []
    url = f"{HF}/api/datasets/{repo}/tree/main?recursive=1"
    seen_cursors: set[str] = set()
    while url:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=120, **_opener_kwargs()) as response:
            payload = json.loads(response.read())
            link = response.headers.get("Link", "")
        out.extend(item for item in payload if item.get("type") == "file")
        url = ""
        # HF paginates via a Link: <...>; rel="next" header.
        for part in link.split(","):
            if 'rel="next"' in part:
                candidate = part.split(";")[0].strip().strip("<>")
                if candidate and candidate not in seen_cursors:
                    seen_cursors.add(candidate)
                    url = candidate
                break
    return out


def _hf_revision(repo: str) -> str | None:
    try:
        return json.loads(_get(f"{HF}/api/datasets/{repo}")).get("sha")
    except (urllib.error.URLError, ValueError):
        return None


def fetch_locomo(root: Path) -> dict:
    target = root / "locomo"
    url = "https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json"
    fetched = _download(url, target / "locomo10.json")
    return {"dataset": "locomo", "path": str(target), "new_files": int(fetched)}


def fetch_longmemeval(root: Path) -> dict:
    """The cleaned release, not the original.

    The maintainers re-released in Sept 2025 after finding that history
    sessions could interfere with answer correctness. Scoring against the
    pre-cleanup files would produce numbers that are not comparable to
    anything published after that date, in either direction.
    """
    target = root / "longmemeval"
    repo = "xiaowu0162/longmemeval-cleaned"
    wanted = ("longmemeval_s_cleaned.json", "longmemeval_oracle.json")
    new = 0
    for name in wanted:
        new += int(_download(f"{HF}/datasets/{repo}/resolve/main/{name}", target / name))
    # The loader expects longmemeval_s.json; point it at the cleaned file
    # rather than silently loading the superseded one.
    canonical = target / "longmemeval_s.json"
    if not canonical.exists() and (target / "longmemeval_s_cleaned.json").exists():
        canonical.write_bytes((target / "longmemeval_s_cleaned.json").read_bytes())
    return {
        "dataset": "longmemeval",
        "path": str(target),
        "new_files": new,
        "revision": _hf_revision(repo),
        "note": "cleaned release (Sept 2025); not comparable to pre-cleanup numbers",
    }


def fetch_convomem(root: Path) -> dict:
    target = root / "convomem"
    repo = "Salesforce/ConvoMem"
    files = [f for f in _hf_tree(repo) if f["path"].endswith(".json")]
    new = 0
    for index, item in enumerate(files, 1):
        rel = item["path"]
        if _download(f"{HF}/datasets/{repo}/resolve/main/{rel}", target / rel):
            new += 1
        if index % 100 == 0:
            print(f"    convomem {index}/{len(files)} files", flush=True)
    return {
        "dataset": "convomem",
        "path": str(target),
        "new_files": new,
        "total_files": len(files),
        "revision": _hf_revision(repo),
    }


def fetch_personamem(root: Path) -> dict:
    """PersonaMem v1, 32k tier, converted to the shape the loader reads.

    v1 (MIT) rather than v2 (CC-BY-4.0, multimodal, ~400 MB of CSV): the
    loader's PINNED_VERSION names v1, and the two releases carry different
    terms, so mixing them would make the recorded licence wrong.

    The release ships `questions_<tier>.csv` plus `shared_contexts_<tier>.jsonl`,
    NOT the flat `personamem.json` the loader expects, so this converts. Field
    names below were read off the real download, not inferred — the sibling
    ConvoMem loader records what guessing a schema cost last time.

    Two details the conversion must not get wrong:

    * `correct_answer` is a LABEL ("(c)"), not answer prose. It is passed
      through verbatim because the axis metric is `choice_accuracy`, which
      normalises "(c)" to "c" and compares against the model's choice.
    * `end_index_in_shared_context` truncates the haystack. Every row's index
      lands strictly inside its context, and the turn at that index is the
      response being asked about — so the slice is `[:end_index]`. Ingesting
      the whole context would feed the answer back as retrievable memory and
      silently inflate every arm.

    Only the 32k tier is fetched. It is a complete released condition of the
    benchmark (589 questions over 37 contexts), not a sample of one. The 128k
    and 1M tiers are separate context-length conditions; add them when a run
    needs them rather than pulling 240 MB nothing reads yet.
    """
    target = root / "personamem"
    repo = "bowen-upenn/PersonaMem"
    tier = "32k"
    questions_csv = f"questions_{tier}.csv"
    contexts_jsonl = f"shared_contexts_{tier}.jsonl"

    new = 0
    for name in (questions_csv, contexts_jsonl):
        new += int(_download(f"{HF}/datasets/{repo}/resolve/main/{name}", target / name))

    def parse_options(raw: str) -> list:
        """`all_options` is not consistently JSON in the release.

        286 of the 589 rows in the 32k tier are JSON-quoted; the other 303 are
        Python reprs with single quotes. `ast.literal_eval` reads both and,
        unlike `eval`, evaluates literals only — no code can run from dataset
        text. Anything neither parser accepts raises rather than degrading to
        an empty option list, which would turn a parse bug into a
        model-looking failure.
        """
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        try:
            parsed = ast.literal_eval(raw)
        except (ValueError, SyntaxError) as exc:
            raise RuntimeError(f"personamem: unparseable all_options: {raw[:120]!r}") from exc
        if not isinstance(parsed, list):
            raise RuntimeError(f"personamem: all_options is not a list: {raw[:120]!r}")
        return parsed

    shared: dict[str, list] = {}
    with (target / contexts_jsonl).open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                shared.update(json.loads(line))

    items, unresolved = [], 0
    with (target / questions_csv).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            context = shared.get(row["shared_context_id"])
            if context is None:
                # Never silently drop to an empty haystack: that would score as
                # a retrieval miss and read as a model failure, not a data bug.
                unresolved += 1
                continue
            end = int(row["end_index_in_shared_context"])
            items.append({
                "question_id": row["question_id"],
                "persona_id": row["persona_id"],
                "question": row["user_question_or_message"],
                "correct_answer": row["correct_answer"],
                "options": parse_options(row["all_options"]),
                "context": context[:end],
                "question_type": row["question_type"],
                "topic": row["topic"],
            })

    if unresolved:
        raise RuntimeError(
            f"personamem: {unresolved} question row(s) reference a shared_context_id "
            f"absent from {contexts_jsonl}; refusing to write a partial dataset"
        )

    (target / "personamem.json").write_text(
        json.dumps(items, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "dataset": "personamem",
        "path": str(target),
        "new_files": new,
        "tier": tier,
        "questions": len(items),
        "shared_contexts": len(shared),
        "revision": _hf_revision(repo),
        "note": f"v1 {tier} tier converted to personamem.json; licence MIT (v1), NOT v2's CC-BY-4.0",
    }


DATASETS = {
    "locomo": (
        fetch_locomo,
        "see LICENSE.txt in snap-research/locomo (no SPDX identifier declared)",
        "~3 MB",
    ),
    "longmemeval": (fetch_longmemeval, "MIT", "~300 MB"),
    "convomem": (
        fetch_convomem,
        "CC-BY-NC-4.0 — NON-COMMERCIAL; attribute Salesforce/ConvoMem",
        # Measured, not estimated: ~1,890 of ~2,500 files already occupy 18 GB
        # on disk, most of it core_benchmark/pre_mixed_testcases (individual
        # files exceed 50 MB). The previous "~925 MB" understated this by more
        # than an order of magnitude and would strand a fetch part-way on a
        # machine provisioned against it.
        "~25 GB",
    ),
    "personamem": (
        fetch_personamem,
        "MIT (PersonaMem v1). NOT the v2 release, which is CC-BY-4.0 — "
        "record which version a run used; the terms differ",
        "~7 MB (32k tier)",
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", action="append", choices=sorted(DATASETS), default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    args = parser.parse_args()

    if args.list:
        for name, (_, licence, size) in sorted(DATASETS.items()):
            print(f"{name:14s} {size:>10s}  {licence}")
        return 0

    names = sorted(DATASETS) if args.all else (args.dataset or [])
    if not names:
        parser.error("pass --dataset NAME, --all, or --list")

    root = Path(args.root).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    print(f"destination: {root}\n")

    results = []
    for name in names:
        fetch, licence, size = DATASETS[name]
        print(f"[{name}] licence: {licence}")
        print(f"[{name}] approx size: {size} — downloading...", flush=True)
        try:
            result = fetch(root)
        except (urllib.error.URLError, OSError) as exc:
            print(f"[{name}] FAILED: {exc}", file=sys.stderr)
            results.append({"dataset": name, "error": str(exc)})
            continue
        print(f"[{name}] done: {json.dumps(result, sort_keys=True)}\n", flush=True)
        results.append(result)

    manifest = root / "download-manifest.json"
    manifest.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"manifest: {manifest}")
    return 0 if all("error" not in r for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
