# India Filing Handoff

Prepared: 2026-09-08. Target: India, confirmed by the user.
Filing status: unknown. This is review material for a registered Indian patent agent.

## What needs assessment

India's Section 3(k) excludes the categories stated there, including computer
programmes per se and algorithms. Naming software as a system does not by itself
resolve eligibility. The agent should evaluate the substance of this implementation
and the technical contribution under the current CRI guidance.
Sources: [Section 3](https://www.ipindia.gov.in/acts/patent-act-1970/section-3),
[2025 CRI Guidelines, sections 4 and 5](https://ipindia.gov.in/frontend/pdf/patents/guidelines/GUIDELINES%20FOR%20EXAMINATION%20OF%20COMPUTER%20RELATED%20INVENTIONS%20%28CRIs%29%20-%202025.pdf).

The proposed technical effects to assess are rejection of mismatched replay state,
bounded worker output/time, resource admission before execution, and detection of
changed rollback conditions. Existing tests support specific behaviors; they do
not establish novelty or the inventive step of their combination. Material overlap
is recorded in prior_art_worksheet.md, particularly CN121681201A.

## Application preparation

The official filing process uses Form 1 and a provisional or complete specification
in Form 2. The agent must select the appropriate route, verify other applicable
forms, applicant category, fees, signatures and examination requirements.
Sources: [Filing process](https://www.ipindia.gov.in/filing-process),
[Forms and fees](https://www.ipindia.gov.in/pages/patents/learn/forms-and-official-fees).

Where a provisional specification is filed, Section 9 requires the complete
specification within twelve months. No deadline has been calculated here because
no filing date was supplied.
Source: [Section 9](https://www.ipindia.gov.in/acts/patent-act-1970/section-9).

## Inputs required from the applicant

| Required fact | Current record |
|---|---|
| Applicant legal name, address and ownership basis | Not supplied |
| Human inventors and each person's technical contribution | Not supplied; do not infer from Git authors |
| Existing filing or priority application and dates | Not supplied |
| Earliest public GitHub visibility, demo, paper, sale or submission | Not supplied |
| Employment, university, sponsor or assignment obligations | Not supplied |
| Supporting dated conception and experiment records | Repository available; authorship and dates need corroboration |

Prior GitHub pushes are known, but public visibility at the time has not been
established. The agent must assess any disclosure against the actual chronology
and applicable provisions. A CONFIDENTIAL header on a repository file does not
establish that the file was kept private.

## Concrete review decisions

1. Compare candidate elements with the cited patent and literature, expand the
   Indian and international family search, and assess inventive step.
2. Select a supported embodiment, trace the integrated execution path, and remove
   any optional or simulated mechanism that the chosen claim requires to be real.
3. Confirm inventorship, ownership and disclosure chronology with the applicant.
4. Prepare and approve the formal specification, drawings and applicable forms,
   then file using the authorized applicant or agent.

No application has been submitted by this work. No filing number, priority date,
eligibility conclusion, novelty conclusion or grant is asserted.
