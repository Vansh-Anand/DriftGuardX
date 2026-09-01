from __future__ import annotations

import json

from scripts.enforce_trivy_report import load_findings


def test_load_findings_flattens_targets(tmp_path) -> None:
    report = tmp_path / "trivy.json"
    report.write_text(
        json.dumps(
            {
                "Results": [
                    {
                        "Target": "requirements.lock",
                        "Vulnerabilities": [
                            {
                                "VulnerabilityID": "CVE-test",
                                "PkgName": "example",
                                "InstalledVersion": "1",
                                "FixedVersion": "2",
                                "Severity": "HIGH",
                            }
                        ],
                    },
                    {"Target": "clean.lock", "Vulnerabilities": None},
                ]
            }
        ),
        encoding="utf-8",
    )

    assert load_findings(report) == [
        {
            "VulnerabilityID": "CVE-test",
            "PkgName": "example",
            "InstalledVersion": "1",
            "FixedVersion": "2",
            "Severity": "HIGH",
            "Target": "requirements.lock",
        }
    ]
