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
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_ROOT = Path(os.environ.get("ZEREF_BENCHMARK_DATA", Path.home() / "zeref-benchmark-data"))
USER_AGENT = "zeref-benchmark-fetch/1.0 (+https://github.com/kanadhiayash/zeref-memory-engine)"
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


def _download(url: str, dest: Path, timeout: int = 300) -> bool:
    """Download to `dest`. Returns True if fetched, False if already present.

    Writes via a .part file and renames, so an interrupted run never leaves a
    truncated file that looks complete on the next pass.
    """
    if dest.exists() and dest.stat().st_size > 0:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout, **_opener_kwargs()) as response, part.open("wb") as handle:
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            handle.write(chunk)
    part.rename(dest)
    return True


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
        "~925 MB",
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
