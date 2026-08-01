"""Trust inspection (vNext §8.5).

Fast, deterministic, stdlib-only. Produces a ``TrustReport`` recording
digest, license (best-effort), executable-entrypoint hints, declared and
inferred permissions, and prompt-injection / outside-write heuristics.
Sandbox smoke test is intentionally left as an ``experimental`` stub
("not run" — never faked to a green).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path


_TEXT_EXTENSIONS = {".md", ".py", ".sh", ".js", ".ts", ".json", ".yaml",
                    ".yml", ".toml"}


@dataclass
class TrustReport:
    path: str
    digest: str
    file_count: int
    total_bytes: int
    license: str | None = None
    entrypoints: list[str] = field(default_factory=list)
    declared_permissions: dict | None = None
    inferred_permissions: dict = field(default_factory=dict)
    prompt_injection_hits: list[str] = field(default_factory=list)
    outside_writes: list[str] = field(default_factory=list)
    sandbox_smoke_test: str = "not-run"

    def to_dict(self) -> dict:
        return {
            "path": self.path, "digest": self.digest,
            "file_count": self.file_count, "total_bytes": self.total_bytes,
            "license": self.license, "entrypoints": self.entrypoints,
            "declared_permissions": self.declared_permissions,
            "inferred_permissions": self.inferred_permissions,
            "prompt_injection_hits": self.prompt_injection_hits,
            "outside_writes": self.outside_writes,
            "sandbox_smoke_test": self.sandbox_smoke_test,
        }


_LICENSE_PATTERN = re.compile(
    r"(MIT|Apache-?2\.0|BSD-?[23]|GPL-?[23]|MPL-?2\.0|ISC)", re.IGNORECASE,
)
_PROMPT_INJECTION_PATTERNS = (
    re.compile(r"ignore previous", re.IGNORECASE),
    re.compile(r"override .*instructions", re.IGNORECASE),
    re.compile(r"disregard the system prompt", re.IGNORECASE),
    re.compile(r"you are now (a|the) ", re.IGNORECASE),
)
_OUTSIDE_WRITE_PATTERNS = (
    re.compile(r"open\s*\(\s*['\"]/", re.IGNORECASE),   # absolute-path open
    re.compile(r"os\.remove|shutil\.rmtree|rm -rf"),
    re.compile(r"requests\.post|urllib.*urlopen"),
)


def _iter_text_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    out: list[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix in _TEXT_EXTENSIONS:
            out.append(p)
    return out


def _digest_directory(root: Path) -> tuple[str, int, int]:
    h = hashlib.sha256()
    files = sorted(_iter_text_files(root))
    total_bytes = 0
    for p in files:
        rel = str(p.relative_to(root)) if p != root else p.name
        try:
            data = p.read_bytes()
        except OSError:
            continue
        total_bytes += len(data)
        h.update(rel.encode("utf-8") + b"\0")
        h.update(hashlib.sha256(data).digest())
    return "sha256:" + h.hexdigest(), len(files), total_bytes


def _detect_license(root: Path) -> str | None:
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"):
        p = root / name if root.is_dir() else None
        if p and p.exists():
            text = p.read_text(encoding="utf-8", errors="ignore")[:2000]
            m = _LICENSE_PATTERN.search(text)
            return m.group(1) if m else "unknown"
    return None


def _entrypoints(root: Path) -> list[str]:
    if root.is_file():
        return [root.name]
    hits: list[str] = []
    for name in ("server.py", "run.sh", "main.py", "index.js", "index.ts",
                 "cli.py"):
        if (root / name).exists():
            hits.append(name)
    return hits


def _scan_patterns(text: str, patterns: tuple[re.Pattern, ...]) -> list[str]:
    hits: list[str] = []
    for pat in patterns:
        m = pat.search(text)
        if m:
            hits.append(m.group(0))
    return hits


def inspect_source(path: Path | str,
                   *,
                   declared_permissions: dict | None = None) -> TrustReport:
    path = Path(path)
    digest, count, total = _digest_directory(path)
    report = TrustReport(
        path=str(path),
        digest=digest,
        file_count=count,
        total_bytes=total,
        license=_detect_license(path) if path.is_dir() else None,
        entrypoints=_entrypoints(path),
        declared_permissions=declared_permissions,
    )
    for p in _iter_text_files(path)[:200]:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for hit in _scan_patterns(text, _PROMPT_INJECTION_PATTERNS):
            report.prompt_injection_hits.append(f"{p.name}: {hit}")
        for hit in _scan_patterns(text, _OUTSIDE_WRITE_PATTERNS):
            report.outside_writes.append(f"{p.name}: {hit}")
    report.inferred_permissions = {
        "subprocess": bool(report.entrypoints and any(
            e.endswith((".sh", ".py")) for e in report.entrypoints
        )),
        "external_write": bool(report.outside_writes),
    }
    return report
