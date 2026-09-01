"""Fail CI on actionable Trivy findings and expose reproducible annotations."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _escape(value: object) -> str:
    return str(value).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def load_findings(report_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    findings: list[dict[str, Any]] = []
    for result in payload.get("Results", []):
        target = str(result.get("Target", report_path))
        for vulnerability in result.get("Vulnerabilities") or []:
            finding = dict(vulnerability)
            finding["Target"] = target
            findings.append(finding)
    return findings


def main() -> int:
    if len(sys.argv) != 2:
        print("::error title=Trivy policy error::Expected exactly one JSON report path")
        return 2

    report_path = Path(sys.argv[1])
    if not report_path.is_file():
        print(
            "::error title=Trivy scan failed::The scanner did not produce its required JSON report"
        )
        return 2

    try:
        findings = load_findings(report_path)
    except (OSError, ValueError, TypeError) as exc:
        print(f"::error title=Invalid Trivy report::{_escape(exc)}")
        return 2

    for finding in findings:
        vulnerability_id = _escape(finding.get("VulnerabilityID", "unknown"))
        package = _escape(finding.get("PkgName", "unknown-package"))
        installed = _escape(finding.get("InstalledVersion", "unknown"))
        fixed = _escape(finding.get("FixedVersion", "not-published"))
        target = _escape(finding.get("Target", report_path))
        severity = _escape(finding.get("Severity", "UNKNOWN"))
        print(
            f"::error title={severity} {vulnerability_id}::{package} {installed} -> "
            f"{fixed} in {target}"
        )

    if findings:
        print(f"Trivy policy rejected {len(findings)} actionable HIGH/CRITICAL finding(s).")
        return 1

    print("Trivy policy passed: no actionable HIGH/CRITICAL findings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
