"""FactGuard: deterministic public-claim safety checks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


BLOCKED_PATTERNS = {
    "unsupported_superlative": ["best memory engine", "best-in-class", "beats every", "beats all"],
    "benchmark_claim": ["10/10 on all benchmarks", "scores 10/10", "leaderboard"],
    "production_ready": ["production-ready", "production proven", "production-proven"],
    "success_without_evidence": ["all gates pass", "all checks pass", "fully verified", "unsupported claim"],
}


@dataclass(frozen=True)
class FactFinding:
    path: str
    line: int
    category: str
    severity: str
    claim: str
    suggestion: str

    def to_dict(self) -> dict:
        return asdict(self)


def classify_claim(claim: str, *, source_refs: list[str] | None = None) -> str:
    lowered = claim.lower()
    if _matched_category(lowered):
        return "unsupported_claim"
    if "unknown" in lowered:
        return "unknown"
    if any(word in lowered for word in ("assume", "assumption", "likely", "maybe")):
        return "assumption"
    if source_refs:
        return "verified_fact"
    return "user_provided_fact"


def check_claim(claim: str, *, source_refs: list[str] | None = None, path: str = "<claim>") -> list[FactFinding]:
    category = _matched_category(claim.lower())
    if not category:
        if classify_claim(claim, source_refs=source_refs) == "user_provided_fact" and _looks_factual(claim):
            return [
                FactFinding(
                    path=path,
                    line=1,
                    category="missing_source_ref",
                    severity="medium",
                    claim=claim,
                    suggestion="Add a source reference or reclassify this as an assumption.",
                )
            ]
        return []
    return [
        FactFinding(
            path=path,
            line=1,
            category=category,
            severity="high",
            claim=claim,
            suggestion=suggest_rewrite(claim),
        )
    ]


def scan_path(path: Path) -> list[FactFinding]:
    files = _markdown_files(path)
    findings: list[FactFinding] = []
    for file in files:
        for line_no, line in enumerate(file.read_text(errors="ignore").splitlines(), start=1):
            category = _matched_category(line.lower())
            if category:
                findings.append(
                    FactFinding(
                        path=str(file),
                        line=line_no,
                        category=category,
                        severity="high",
                        claim=line.strip(),
                        suggestion=suggest_rewrite(line),
                    )
                )
    return findings


def report(findings: list[FactFinding], *, format: str = "text") -> str:
    if format == "md":
        lines = ["# FactGuard Report", "", f"Findings: {len(findings)}", ""]
        for finding in findings:
            lines.append(f"- **{finding.severity}** `{finding.category}` {finding.path}:{finding.line} - {finding.suggestion}")
        return "\n".join(lines) + "\n"
    if not findings:
        return "No FactGuard findings.\n"
    lines = [
        f"{finding.severity.upper()} {finding.category} {finding.path}:{finding.line} {finding.suggestion}"
        for finding in findings
    ]
    return "\n".join(lines) + "\n"


def suggest_rewrite(claim: str) -> str:
    lowered = claim.lower()
    if "best" in lowered or "beats" in lowered:
        return "Use: Zeref is designed as a local-first memory hardening layer for AI agents."
    if "benchmark" in lowered or "10/10" in lowered or "leaderboard" in lowered:
        return "State benchmark status only with a dated, reproducible source."
    if "production" in lowered:
        return "Use: Zeref is being hardened for local-first AI memory workflows."
    return "Rewrite as a sourced, bounded claim."


def matched_claim_category(claim: str) -> str:
    """Public entry point: the BLOCKED_PATTERNS category `claim` trips, or "".

    Callers that need "does FactGuard reject this text?" must use this rather
    than restating phrases, so every guard shares one pattern table.
    """
    return _matched_category(claim.lower())


def _matched_category(lowered: str) -> str:
    for category, phrases in BLOCKED_PATTERNS.items():
        if any(phrase in lowered for phrase in phrases):
            return category
    return ""


def _looks_factual(claim: str) -> bool:
    lowered = claim.lower()
    return any(token in lowered for token in (" is ", " has ", " supports ", " ships ", " passes "))


def _markdown_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*.md") if p.is_file())
