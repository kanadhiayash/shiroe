"""PrivacyGuard command helpers built on the deterministic scrubber."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from shiroe.privacy import scrub


@dataclass(frozen=True)
class PrivacyFinding:
    path: str
    redacted: int
    classes_hit: list[str]
    suggestion: str

    def to_dict(self) -> dict:
        return asdict(self)


def classify_text(text: str, *, redact_md_path: Path) -> dict:
    cleaned, report = scrub(text, redact_md_path, provenance="privacy/classify")
    if "credentials" in report.classes_hit:
        privacy_class = "secret"
    elif report.classes_hit:
        privacy_class = "sensitive"
    else:
        privacy_class = "public"
    return {
        "privacy_class": privacy_class,
        "redacted": report.redacted,
        "classes_hit": report.classes_hit,
        "redacted_text": cleaned,
    }


def scan_path(path: Path, *, redact_md_path: Path) -> list[PrivacyFinding]:
    findings: list[PrivacyFinding] = []
    for file in _scan_files(path):
        _, report = scrub(file.read_text(errors="ignore"), redact_md_path, provenance=f"privacy/scan/{file}")
        if report.redacted:
            findings.append(
                PrivacyFinding(
                    path=str(file),
                    redacted=report.redacted,
                    classes_hit=report.classes_hit,
                    suggestion="Redact or abstract before public release.",
                )
            )
    return findings


def redact_file(path: Path, *, redact_md_path: Path) -> tuple[str, PrivacyFinding | None]:
    cleaned, report = scrub(path.read_text(errors="ignore"), redact_md_path, provenance=f"privacy/redact/{path}")
    finding = None
    if report.redacted:
        finding = PrivacyFinding(
            path=str(path),
            redacted=report.redacted,
            classes_hit=report.classes_hit,
            suggestion="Review suggested redactions before writing or publishing.",
        )
    return cleaned, finding


def format_findings(findings: list[PrivacyFinding], *, format: str = "text") -> str:
    if format == "json":
        return json.dumps([finding.to_dict() for finding in findings], indent=2, sort_keys=True) + "\n"
    if not findings:
        return "No PrivacyGuard findings.\n"
    lines = [
        f"HIGH {finding.path} redacted={finding.redacted} classes={','.join(finding.classes_hit)}"
        for finding in findings
    ]
    return "\n".join(lines) + "\n"


def _scan_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(
        file for file in path.rglob("*")
        if file.is_file() and file.suffix.lower() in {".md", ".txt", ".json", ".yml", ".yaml"}
    )
