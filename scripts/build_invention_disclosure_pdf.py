"""Build the completed DriftGuard-X technical draft in VIT IDF-B structure."""

from __future__ import annotations

import argparse
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

INK = colors.HexColor("#17233D")
VIT_BLUE = colors.HexColor("#253B80")
ACCENT = colors.HexColor("#0F766E")
PALE = colors.HexColor("#E8F2F1")
LINE = colors.HexColor("#AAB4C4")
MUTED = colors.HexColor("#4B5563")


class AdmissionFlow(Flowable):
    def __init__(self) -> None:
        super().__init__()
        self.width = 174 * mm
        self.height = 47 * mm

    def draw(self) -> None:
        canvas = self.canv
        labels = [
            "Canonicalize\nstate + policy",
            "Issue receipt\n+ reserve",
            "Worker recomputes\nbindings",
            "Execute or\nrefuse",
            "Consume / release\n+ audit",
        ]
        box_w = 31 * mm
        gap = 4.5 * mm
        y = 16 * mm
        for index, label in enumerate(labels):
            x = index * (box_w + gap)
            canvas.setFillColor(PALE if index not in {3, 4} else colors.HexColor("#E7EEF9"))
            canvas.setStrokeColor(ACCENT if index < 3 else VIT_BLUE)
            canvas.roundRect(x, y, box_w, 20 * mm, 2 * mm, fill=1, stroke=1)
            canvas.setFillColor(INK)
            canvas.setFont("Helvetica-Bold", 7.5)
            for line_no, line in enumerate(label.split("\n")):
                canvas.drawCentredString(x + box_w / 2, y + 12.5 * mm - line_no * 4 * mm, line)
            if index < len(labels) - 1:
                start = x + box_w
                end = x + box_w + gap
                canvas.setStrokeColor(MUTED)
                canvas.line(start + 1 * mm, y + 10 * mm, end - 1 * mm, y + 10 * mm)
                canvas.line(end - 3 * mm, y + 11.5 * mm, end - 1 * mm, y + 10 * mm)
                canvas.line(end - 3 * mm, y + 8.5 * mm, end - 1 * mm, y + 10 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(
            0, 5 * mm, "Mismatch, expiry, reuse, or evidence promotion -> refusal before dispatch"
        )


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=27,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=8 * mm,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=16,
            textColor=MUTED,
            spaceAfter=6 * mm,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=19,
            textColor=VIT_BLUE,
            spaceBefore=3 * mm,
            spaceAfter=4 * mm,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
            textColor=ACCENT,
            spaceBefore=3 * mm,
            spaceAfter=2 * mm,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=13.2,
            textColor=INK,
            spaceAfter=2.5 * mm,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=13.2,
            textColor=INK,
            leftIndent=5 * mm,
            firstLineIndent=-3 * mm,
            bulletIndent=0,
            spaceAfter=2 * mm,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.4,
            leading=10,
            textColor=INK,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.4,
            leading=10,
            textColor=colors.white,
        ),
        "note": ParagraphStyle(
            "Note",
            parent=base["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=8.2,
            leading=12,
            textColor=MUTED,
            borderColor=LINE,
            borderWidth=0.5,
            borderPadding=7,
            backColor=colors.HexColor("#F6F8FB"),
            spaceBefore=2 * mm,
            spaceAfter=4 * mm,
        ),
        "center": ParagraphStyle(
            "Center",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
            textColor=INK,
        ),
    }


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def _bullets(items: list[str], styles: dict[str, ParagraphStyle]) -> list[Paragraph]:
    return [Paragraph(item, styles["bullet"], bulletText="-") for item in items]


def _header_footer(canvas, document) -> None:  # type: ignore[no-untyped-def]
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.rect(18 * mm, height - 29 * mm, width - 36 * mm, 17 * mm, fill=0, stroke=1)
    canvas.setFont("Helvetica-Bold", 12)
    canvas.setFillColor(VIT_BLUE)
    canvas.drawString(22 * mm, height - 20 * mm, "VIT IPR&TTCELL")
    canvas.setFont("Helvetica-Bold", 10)
    canvas.setFillColor(INK)
    canvas.drawCentredString(width / 2, height - 20 * mm, "Invention Disclosure Format (IDF)-B")
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(width - 22 * mm, height - 17 * mm, "Document No. 02-IPR-R003")
    canvas.drawRightString(width - 22 * mm, height - 22 * mm, "Technical draft: 09.09.2026")
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, 15 * mm, width - 18 * mm, 15 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(
        18 * mm, 10 * mm, "CONFIDENTIAL - PRE-FILING TECHNICAL DRAFT - NOT A FILED SPECIFICATION"
    )
    canvas.drawRightString(width - 18 * mm, 10 * mm, f"Page {document.page}")
    canvas.restoreState()


def build(output: Path) -> None:
    styles = _styles()
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(
        str(output),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=36 * mm,
        bottomMargin=20 * mm,
        title="DriftGuard-X Invention Disclosure Format (IDF)-B",
        author="DriftGuard-X technical team",
        subject="State-bound admission control of autonomous recovery operations",
    )
    frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        id="body",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    doc.addPageTemplates([PageTemplate(id="idf-b", frames=[frame], onPage=_header_footer)])
    story: list[Flowable] = []

    story.extend(
        [
            Spacer(1, 25 * mm),
            _p("DriftGuard-X", styles["title"]),
            _p(
                "Technical system and method for state-bound admission control of autonomous recovery operations",
                styles["subtitle"],
            ),
            Table(
                [
                    ["Target jurisdiction", "India"],
                    [
                        "Disclosure type",
                        "IDF-B technical draft for institutional and patent-agent review",
                    ],
                    ["Implementation status", "Working reference prototype; hosted CI green"],
                    [
                        "Suggested TRL",
                        "TRL 5 - technology validated in a relevant controlled environment",
                    ],
                ],
                colWidths=[45 * mm, 125 * mm],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (0, -1), PALE),
                        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
                        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                        ("LEADING", (0, 0), (-1, -1), 12),
                        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 7),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                ),
            ),
            Spacer(1, 8 * mm),
            _p(
                "This document completes the technical sections of the supplied IDF-B form. It deliberately does not identify inventors, applicants, ownership, priority, or public-disclosure dates because those facts were not supplied and must not be inferred from source-control history.",
                styles["note"],
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            _p("1. Title of the invention", styles["h1"]),
            _p(
                "Technical System and Method for State-Bound Admission Control of Autonomous Recovery Operations",
                styles["body"],
            ),
            _p("2. Field / Area of invention", styles["h1"]),
            _p(
                "Distributed computing, autonomous software recovery, dependable AI systems, replay-based fault diagnosis, resource admission control, execution provenance, and computer-system security.",
                styles["body"],
            ),
            _p("3. Prior patents and publications from literature", styles["h1"]),
            _p(
                "The review below is bounded and preliminary. Publication dates must be compared with the actual conception, disclosure, and priority chronology by a registered Indian patent professional.",
                styles["note"],
            ),
        ]
    )
    prior_rows = [
        ["Ref.", "Reference", "Relevant teaching", "Draft consequence"],
        [
            "P1",
            "CN121681201A (2026)",
            "Topology, counterfactual intervention, isolated replay repair",
            "Broad diagnosis plus replay repair is crowded",
        ],
        [
            "R1",
            "Bandits with Knapsacks (2013)",
            "Exploration under resource budgets",
            "Budgeted bandit selection is established",
        ],
        [
            "R2",
            "Graph Attention Networks (2017/2018)",
            "Attention over graph neighborhoods",
            "GAT architecture is not the novelty",
        ],
        [
            "R3",
            "Counterfactual RCA for Dynamical Systems (2024)",
            "Counterfactual reasoning for root cause",
            "Counterfactual attribution needs narrower scope",
        ],
        [
            "R4",
            "Conformal Prediction (2021)",
            "Finite-sample calibrated uncertainty",
            "Statistical bounds are implementation detail",
        ],
        [
            "R5",
            "in-toto (USENIX Security 2019)",
            "Cryptographically verified software provenance",
            "Signing and provenance alone are established",
        ],
        [
            "P6",
            "US20260134155A1 (2026)",
            "Integrity baselines, interception, isolation/recovery, append-only records",
            "Hash-bound audit records alone are insufficient",
        ],
        [
            "P7",
            "US20210271998A1 (2021)",
            "Distributed provenance, replay, rollback, execution ordering",
            "Generic provenance plus replay/rollback is crowded",
        ],
        [
            "P8",
            "CN120612066A (2025)",
            "Task/terminal binding, state receipts and rollback treatment",
            "Receipt lifecycle alone is insufficient",
        ],
        [
            "P9",
            "CN121187728A (2026)",
            "Versioned execution plan, resource lock, rollback and audit digest",
            "Focus on recovery-specific recomputation/refusal",
        ],
        [
            "P10",
            "EP4369195A1 (2024)",
            "Audited privileged actions across worker nodes",
            "Worker execution and audit metadata are established",
        ],
    ]
    prior_table = Table(
        [
            [
                _p(str(cell), styles["table_header"] if row_index == 0 else styles["small"])
                for cell in row
            ]
            for row_index, row in enumerate(prior_rows)
        ],
        colWidths=[10 * mm, 39 * mm, 63 * mm, 58 * mm],
        repeatRows=1,
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), VIT_BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F8FB")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        ),
    )
    story.extend(
        [
            prior_table,
            Spacer(1, 3 * mm),
            _p(
                "Primary links and a fuller overlap analysis are maintained in docs/prior_art_worksheet.md. This table is not an exhaustive patent search, freedom-to-operate analysis, or novelty opinion.",
                styles["note"],
            ),
            PageBreak(),
            _p("4. Summary and background of the invention", styles["h1"]),
            _p(
                "Autonomous recovery pipelines commonly make an admission decision in one process and execute later in another process. Between those points, the replay manifest, trace, component version, policy, rollback conditions, available capacity, or authority of the evidence can change. A queued operation may therefore execute against state different from the state that was approved. Generic signatures or audit logs can detect some tampering after the fact, but do not by themselves prevent this time-of-check/time-of-use failure before resource allocation and state change.",
                styles["body"],
            ),
            _p("Candidate technical distinction", styles["h2"]),
            _p(
                "DriftGuard-X issues a durable, single-use admission receipt before dispatch. Its canonical digest binds tenant, replay-manifest digest, trace-root digest, intervention identity, current and candidate component versions, policy digest, rollback-capsule digest, reserved predicted cost, uncertainty margin, rollback reserve, evidence ceiling, and expiry. The worker independently recomputes mandatory bindings from its current durable records. Missing, changed, expired, reused, or over-promoted evidence causes refusal before the replay or remediation executor is constructed. Terminal state transitions consume or release the reservation once and append a hash-linked lifecycle event.",
                styles["body"],
            ),
            _p("Technical effect", styles["h2"]),
        ]
    )
    story.extend(
        _bullets(
            [
                "Prevents an operation admitted for stale or incomplete distributed state from crossing the worker dispatch boundary.",
                "Bounds capacity committed to an admitted operation while preserving a rollback reserve and releasing it on refusal or failure.",
                "Automatically refuses evidence promotion, such as treating controlled or simulated evidence as production authority.",
                "Produces a recomputable, ordered event chain for issue, verify, mismatch refusal, consume, release, and void transitions.",
            ],
            styles,
        )
    )
    story.extend(
        [
            _p(
                "India framing: the contribution is presented as a technical solution to distributed state drift and unsafe resource dispatch, implemented through cooperating stores, coordinators, queues, and worker/executor boundaries. It is not presented as an algorithm per se. Eligibility, novelty, and inventive step remain matters for professional examination.",
                styles["note"],
            ),
            _p("5. Objective(s) of invention", styles["h1"]),
        ]
    )
    story.extend(
        _bullets(
            [
                "Bind each autonomous recovery authorization to the exact distributed state and authority evaluated at admission time.",
                "Refuse execution when mandatory state is omitted, changed, expired, reused, or outside the admitted evidence class.",
                "Reserve bounded execution capacity together with rollback capacity before dispatch and reconcile it exactly once.",
                "Provide durable, independently verifiable lifecycle evidence across coordinator and worker process boundaries.",
                "Reduce unsafe dispatch and uncontrolled resource consumption during replay and remediation under state drift.",
            ],
            styles,
        )
    )
    story.extend(
        [PageBreak(), _p("6. Working principle of the invention", styles["h1"]), AdmissionFlow()]
    )
    working = [
        "The coordinator reads tenant-scoped trace, manifest, component, policy, capsule, evidence, and resource records.",
        "It canonicalizes the values, reserves predicted cost plus uncertainty and rollback reserve, and atomically persists an ISSUED receipt and ISSUE event.",
        "The receipt identifier is carried with the queued replay or remediation request; the worker loads current state from durable records rather than trusting the request payload alone.",
        "The worker supplies every mandatory binding to a transactional verifier. Any mismatch or omission appends MISMATCH_REFUSAL and VOID events and prevents executor allocation.",
        "A valid, unexpired ISSUED receipt is atomically changed to VERIFIED. Concurrent claims observe the changed state and are refused.",
        "Success changes VERIFIED to CONSUMED. Failure, timeout, cancellation, or expiry changes the receipt to RELEASED or VOIDED. Only one terminal transition is recorded.",
        "Audit verification recomputes each event hash and predecessor reference to detect persisted event mutation or ordering gaps.",
    ]
    for index, text in enumerate(working, start=1):
        story.append(_p(f"<b>{index}.</b> {text}", styles["body"]))

    story.extend(
        [
            PageBreak(),
            _p("7. Description of the invention in detail", styles["h1"]),
            _p("7.1 Canonical receipt data structure", styles["h2"]),
            _p(
                "A receipt has a unique identifier, canonical payload, binding digest, lifecycle status, reserved-cost amount, issue time, expiry time, and optional terminal time. The canonical digest uses deterministic key ordering and domain separation. Identity and execution-state bindings are mandatory at verification; numeric reservation and expiry values remain part of the sealed receipt and cannot be rewritten by the worker.",
                styles["body"],
            ),
            _p("7.2 Transactional lifecycle", styles["h2"]),
            _p(
                "The reference store uses SQLite BEGIN IMMEDIATE transactions to serialize receipt transitions across processes. The permitted success path is ISSUED -> VERIFIED -> CONSUMED. ISSUED or VERIFIED may move to RELEASED or VOIDED according to failure handling. Repeated terminal calls are idempotent and do not append duplicate terminal events.",
                styles["body"],
            ),
            _p("7.3 Worker and remediation boundary", styles["h2"]),
            _p(
                "The replay worker reconstructs manifest, trace root, intervention identity, component versions, policy, capsule, tenant, and evidence class from stored execution records before constructing the replay engine. The remediation executor applies the same admission service before preparing a rollback capsule or applying an action. This places refusal before material resource allocation or state mutation.",
                styles["body"],
            ),
            _p("7.4 Append-only audit sequence", styles["h2"]),
            _p(
                "Each lifecycle event stores receipt identifier, sequence number, event type, predecessor hash, reason, details, timestamp, and event hash. The event hash covers all those values with a domain-separated SHA-256 input. Verification detects content changes, predecessor substitution, and sequence gaps. Database-level immutability against an administrator is not claimed for the portable reference backend.",
                styles["body"],
            ),
            _p("7.5 Deployment embodiment", styles["h2"]),
            _p(
                "For multi-host deployment, the same transition contract is intended for a shared transactional database with row locking or compare-and-swap semantics. External state attestation, worker-loss leasing, production metering, and multi-host expiry races remain validation items and are not represented as completed capabilities.",
                styles["body"],
            ),
            PageBreak(),
            _p("8. Experimental validation results", styles["h1"]),
        ]
    )
    validation_rows = [
        ["Validation", "Observed result", "Interpretation / limitation"],
        [
            "Focused admission, receipt, and worker tests",
            "22 passed locally on 09.09.2026",
            "Includes strict omission refusal and process contention",
        ],
        [
            "Cross-process claim contention",
            "1 of 6 processes admitted",
            "Portable SQLite reference; not multi-host PostgreSQL",
        ],
        [
            "Concurrent finalization",
            "Exactly 1 terminal event",
            "Single-use transition under tested contention",
        ],
        [
            "Drift refusal cases",
            "Changed state, policy, trace, expiry, and evidence promotion refused",
            "Fixture-backed behavior, not production performance",
        ],
        [
            "Audit mutation",
            "Recomputed chain reports hash mismatch",
            "Detects stored content mutation in tested chain",
        ],
        [
            "Hosted CI",
            "Green on main; Python, PostgreSQL migrations, web E2E, containers, security/SBOM",
            "Engineering gate, not patent or safety certification",
        ],
        [
            "Controlled retrieval experiment",
            "Two seeds; 30 SciFact queries each; 75 and 72 measurable query/fault pairs",
            "Four attempted fault families; real public data with controlled faults",
        ],
        [
            "Neutral BCRB ordering",
            "Mean replays 2.680 vs 2.680 fixed (seed 42); 2.681 vs 2.681 fixed (seed 7)",
            "No scheduler advantage observed in this controlled study",
        ],
        [
            "Oracle upper-reference ordering",
            "Mean replays 1.000 in both seeds",
            "Receives injected correct repair; not autonomous diagnosis evidence",
        ],
    ]
    validation_table = Table(
        [
            [
                _p(str(cell), styles["table_header"] if row_index == 0 else styles["small"])
                for cell in row
            ]
            for row_index, row in enumerate(validation_rows)
        ],
        colWidths=[47 * mm, 52 * mm, 71 * mm],
        repeatRows=1,
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), VIT_BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F8FB")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        ),
    )
    story.extend(
        [
            validation_table,
            Spacer(1, 4 * mm),
            _p(
                "The controlled retrieval study does not show a neutral-scheduler advantage over fixed ordering. Only the oracle upper reference improves replay count, and it receives the injected correct repair. It must not be used to claim learned diagnosis, general scheduler superiority, or production safety. The admission-control tests establish deterministic refusal and single-use invariants but do not yet measure production latency or cost overrun.",
                styles["note"],
            ),
            _p("9. Aspects of the invention needing protection", styles["h1"]),
        ]
    )
    story.extend(
        _bullets(
            [
                "The system combination that durably binds recovery state, resource reservation, rollback reserve, evidence authority, and expiry before asynchronous dispatch.",
                "Mandatory independent recomputation at the worker/executor boundary and refusal on omitted or changed bindings before executor construction.",
                "The single-use transactional lifecycle that couples claim, execution outcome, capacity consumption/release, and hash-linked audit transitions.",
                "Refusal of upward evidence-class promotion between admission and recovery authorization.",
                "Recovery-specific use of the same receipt across replay execution and remediation authorization to control distributed time-of-check/time-of-use drift.",
            ],
            styles,
        )
    )
    story.extend(
        [
            _p(
                "Do not center protection on generic GATs, conformal prediction, budgeted bandits, signatures, hash chains, dashboards, counterfactual replay, or rollback in isolation. Those areas have material prior-art overlap.",
                styles["note"],
            ),
            PageBreak(),
            _p("10. Technology readiness level", styles["h1"]),
            _p(
                "Suggested selection: <b>TRL 5 - technology validated in a relevant environment.</b>",
                styles["body"],
            ),
        ]
    )
    trl = [[f"TRL {i}" for i in range(1, 10)], ["", "", "", "", "SELECTED", "", "", "", ""]]
    trl_table = Table(trl, colWidths=[18.8 * mm] * 9, rowHeights=[11 * mm, 11 * mm])
    trl_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("BACKGROUND", (4, 0), (4, 1), PALE),
                ("TEXTCOLOR", (4, 0), (4, 1), ACCENT),
            ]
        )
    )
    story.extend(
        [
            trl_table,
            Spacer(1, 5 * mm),
            _p("Rationale", styles["h2"]),
            _p(
                "The system has an integrated implementation, durable reference storage, process-boundary enforcement, controlled real-data experiments, a service-backed golden path, and green hosted CI. It has not been demonstrated as a complete production deployment with a shared multi-host admission database, external state attestation, independent security validation, or operational canaries. TRL 6 or above would therefore overstate the present evidence.",
                styles["body"],
            ),
            _p("Required applicant inputs before filing", styles["h1"]),
        ]
    )
    story.extend(
        _bullets(
            [
                "Human inventor names and each person's specific technical contribution.",
                "Applicant legal name, address, ownership basis, assignments, and employment/university/sponsor obligations.",
                "Any existing Indian or foreign filing, application number, filing date, and claimed priority.",
                "Earliest public GitHub visibility, demo, paper, pitch, sale, offer, submission, or other disclosure date.",
                "Dated conception records and corroboration for the state-bound receipt embodiment.",
            ],
            styles,
        )
    )
    story.extend(
        [
            _p("Source and legal-status note", styles["h1"]),
            _p(
                "Prepared from the DriftGuard-X repository at main and the user-supplied VIT IDF-B template. Relevant official guidance: Indian Patent Office, Guidelines for Examination of Computer Related Inventions (2025), especially the assessment of technical problem, technical means, and technical effect under Section 3(k). No application has been submitted by this work. This document is a technical disclosure draft, not legal advice, a novelty conclusion, a freedom-to-operate opinion, or a completed Form 2 specification.",
                styles["note"],
            ),
        ]
    )

    doc.build(story)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/pdf/DriftGuardX_Invention_Disclosure_IDF_B.pdf"),
    )
    args = parser.parse_args()
    build(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
