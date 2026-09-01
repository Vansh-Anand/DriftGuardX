# Template execution contract: Invention Disclosure Format (IDF)-B

## Reference

- Retained source: `C:\Users\aniru\Downloads\driftguardx\artifacts\invention-disclosure\reference-format-b.docx`
- SHA-256: `0d6e34afe12b996a1820ebc0244ef843732406e4504f2d8d59d44011dbc54266`
- Source size: 3,564,140 bytes
- Visual evidence: `reference-render/pages/page-1.png` through `page-18.png`; all 18 pages inspected.
- Structural evidence: `reference-structure.json`, `reference-style-evidence.json`.
- Source section count: 2.

## Page system

- A4 portrait: 8.271 x 11.694 inches.
- Margins for both source sections: left 0.689 in, right 0.393 in, top 0.667 in, bottom 0.194 in.
- Header distance 0.501 in; footer distance 0 in.
- Section 1 is continuous. Section 2 starts on a new page and repeats the form-identification table before the TRL matrix.
- The source uses a small recurring top-left ownership line (`©VIT IPR&TTCELL`) on intermediate pages. Preserve this line and the VIT form header/table because the requested document is to follow the supplied institutional format.

## Typography and paragraph rhythm

- Primary body type: Arial, 11-12 pt, near-black (`1A1A1A`), justified.
- Numbered principal prompts: source `List Paragraph` style, bold 12 pt, real numbering definition `numId=1`, level 0.
- Subsection labels: bold 12 pt using source `Normal` or `Body Text` styles.
- Figure captions: centered italic, near-black.
- Opening invention title answer: Arial body type, justified, separated from the prompt by one paragraph.
- The source is dense and formal; maintain short paragraph gaps and keep headings with following content. Avoid the original's crowded image walkthrough by allocating figures to architecture only.

## Tables and lists

- Form table: 3 x 3, source `Normal Table`, grid widths 7146/1260/1454 DXA; contains VIT logo/title, document number, issue/date, and amendment/date. Preserve its image relationship and geometry.
- Prior-art table: source pattern is a five-column `Table Grid`. Rebuild with explicit widths optimized for Category / Reference / Relevant disclosure / Difference from this invention / Date.
- TRL matrix: source pattern is a 9-level matrix. Rebuild in landscape-like density within A4 portrait using explicit widths, repeating header rows, and a selected TRL 4 cell.
- Principal lists use real Word numbering. Wrapped lines align under their item text.

## Components and content flow

1. Institutional form header.
2. Title of invention.
3. Field/area of invention.
4. Preliminary prior-art landscape.
5. Summary, technical problem, background, gap, and novelty statement.
6. Objectives.
7. Working principle in brief.
8. Detailed architecture and operational sequence.
9. Architecture figure walkthrough (black-and-white line figures, not marketing screenshots).
10. Technical effects, supported evidence, limitations, and variants.
11. Aspects for protection and claim-direction handoff.
12. Inventorship/disclosure record placeholders.
13. New-page institutional header and TRL selection.
14. End-of-document marker.

## Slot map

- All source invention-specific prose, prior-art rows, figures, screenshots, captions, claims, and TRL narrative are rewriteable and must be replaced.
- The institutional form title, VIT logo, document number, issue/date, amendment/date, and recurring ownership line are preserve-only unless the user later supplies institution-specific replacements.
- The final TRL selection is rewriteable but must remain evidence-bounded; use TRL 4 for the implemented laboratory prototype and explicitly state that production validation is incomplete.
- Inventor names, conception dates, assignments, funding, and pre-filing disclosure dates are unresolved user-owned facts. Use clearly labeled blanks; do not invent them.

## Package preservation

- Preserve the source theme, style, numbering, font table, and image relationships needed by the institutional header.
- Body screenshots and source-invention media are removable.
- Preserve opaque/custom package parts unless python-docx necessarily rewrites them; compare the retained reference hash before and after authoring to confirm the retained file remains unchanged.
- New architecture images are editable task assets. Their source is generated locally and not imported from the prior invention.

## Fidelity and quality gates

- The new document must remain recognizably derived from the supplied IDF-B form: A4 geometry, institutional header, dense Arial drafting, numbered prompts, compact prior-art table, architecture figures with italic captions, protection section, and final TRL page.
- Every reference and final page must be visually inspected. Microsoft Word PDF export plus PDF rasterization is the accepted renderer because LibreOffice is not installed.
- No source-invention content, screenshots, or unsupported performance claims may survive.
- No guarantee of patentability may appear. Novelty is characterized as a candidate distinction subject to professional search and counsel review.
- The source DOCX must remain byte-for-byte unchanged at the recorded SHA-256.
