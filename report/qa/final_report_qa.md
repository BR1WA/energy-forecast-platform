# Final Report QA — Jury Release Update

## Build identification

- Planned output: `report/exports/PFE_ZOUITNI_Salah_Eddine_supervisor_review_v4.pdf`.
- Previous supervisor-review and draft PDFs are retained and will not be overwritten.
- Language: professional academic English, with the required French résumé.
- Build date: 9 August 2026.

## Scientific-evidence boundary

No model was trained, fine-tuned, replaced, or downloaded during this update. No
frozen research metric, serving-normalization result, checkpoint, prepared
artifact, or production model artifact changed. The report continues to separate
the frozen research-normalization results from the inference-only production-
normalization re-evaluation.

The exact serving-normalization evaluation remains supported by preserved local
evidence under `models/lcl_global_forecasting/full_selected_v1/`; the original Low
Carbon London CSV files were neither required nor downloaded. Hashes, origins,
environment, parity checks, and result files remain recorded in
`report/evidence/lcl_tft_serving_normalization_manifest.json`.

## Current Azure deployment evidence

The report records the jury release verified on 9 August 2026:

- deployed source: exact `origin/main` commit
  `af467989694322ef76a5402a367893ea01f5e1dd`;
- frontend revision: `ca-energyai-web--v1-af46798`, healthy;
- API revision: `ca-energyai-api--v1-af46798`, healthy;
- email-worker revision: `ca-energyai-email-worker--v1-af46798`, one healthy replica;
- frontend digest: `sha256:085ca6ef85c7170da811c385d3a9647f3561a875724ebb96f8c5cb9d5612ce68`;
- backend digest: `sha256:b90e1d9a1939546a85318f959d52d4188adfeafb303b3e2a373c2e9009ac871b`;
- public pages: web, Login, Register, Privacy, and Terms returned HTTP 200;
- database: managed PostgreSQL 16 ready;
- models: both frozen 24-hour and 168-hour TFT artifacts available, enabled, and warmed;
- email: SMTP capability ready and the email worker healthy;
- Google: external application in production; live account chooser opened for the
  exact Azure origin without creating a user;
- responsive smoke: desktop and 390 x 844 registration views had no horizontal overflow;
- rollback: the coordinated `v1-8c519b6` web/API/email-worker revisions remain inactive,
  healthy, and available.

The evidence registry is
`report/evidence/azure_deployment_evidence_2026-08-09.md`. It records the resource
boundary, immutable image digests, Google project/client boundary, health evidence,
rollback target, and remaining limitations without storing secrets.

## Current quality gates

- Backend local suite: 106 passed, 4 explicit PostgreSQL-only skips.
- Historical isolated-PostgreSQL suite: 100 passed, 0 skipped; schema unchanged.
- Frontend ESLint and TypeScript: passed.
- Next.js production build: passed; 25 routes.
- Playwright six-project matrix: 180 passed, 0 failed.
- Populated DST-week tests: 167-hour and 169-hour cases passed.
- npm audit: zero known vulnerabilities.
- production Python requirements audit: zero known vulnerabilities.
- Docker-specific `npm ci`: passed after lockfile normalization.

## Explicit cloud limitations retained

The report does not claim full production maturity. Azure alert and avatar-cleanup
workers, durable avatar storage, centralized Log Analytics retention, a custom
domain, and workload-identity registry access remain absent. Backup restoration,
load, disaster-recovery, sustained provider, formal accessibility, and penetration
tests remain incomplete. The monthly budget is an alerting control, not an automatic
shutdown policy. Model evidence remains London-cohort evidence rather than a
Moroccan-site performance guarantee.

## Administrative placeholders

1. Official defense date.
2. Jury names, grades, institutions, and roles.
3. Exact Faculty/Master-approved AI-tool declaration.

The unsupported tentative 9 September 2026 date remains removed. The dedication
remains excluded because no dedication text was supplied.

## Exact files in this update

- `README.md`
- `docs/PRODUCT_V1_RELEASE_NOTES.md`
- `frontend/package-lock.json`
- `report/source/frontmatter/abstracts.tex`
- `report/source/generate_figures.py`
- `report/assets/diagrams/azure_deployment_topology.pdf`
- `report/source/chapters/chapter1.tex`
- `report/source/chapters/chapter6.tex`
- `report/source/chapters/chapter7.tex`
- `report/source/chapters/general_conclusion.tex`
- `report/source/appendices/appendix_a_traceability.tex`
- `report/source/appendices/appendix_c_technical.tex`
- `report/qa/missing_information.md`
- `report/qa/current_report_text.txt`
- `report/qa/final_report_qa.md`
- `report/evidence/azure_deployment_evidence_2026-08-09.md`
- `report/exports/PFE_ZOUITNI_Salah_Eddine_supervisor_review_v4.pdf`

## Compilation and textual QA

- Output: `report/exports/PFE_ZOUITNI_Salah_Eddine_supervisor_review_v4.pdf`.
- Format: A4, 12 pt, one-sided PDF; 97 pages; 1,711,087 bytes.
- SHA-256: `2690A92C2200C3ED71A29F4873DBD5E9DEDB36FBBB600D14CEE5669BB84558AC`.
- Build method: clean manual MiKTeX sequence in a fresh output directory using
  pdfLaTeX, Biber, and stabilizing pdfLaTeX passes. `latexmk` was unavailable
  because the installed MiKTeX has no Perl script engine.
- Fatal LaTeX errors: 0.
- Undefined references: 0.
- Undefined citations: 0.
- Overfull horizontal or vertical boxes: 0.
- Duplicate PDF destinations: 0.
- `TODO`: 0; `TBD`: 0; malformed `??` references: 0.
- Duplicated “Contents Contents” and “References References”: 0.
- “An Recurrent”: 0.
- Local Windows/Unix absolute paths: 0.
- Stale disabled-registration/Google/deployment claims: 0.
- `9 September 2026`: 0.
- `TO BE CONFIRMED`: exactly 3 intentional administrative markers.

## Visual QA

All 97 pages were rendered at 110 dpi and inspected in nine numbered contact
sheets. Full-resolution checks covered the revised Azure topology, Azure resource
table, validation summary, evidence registries, requirement matrix, rotated hash
table, cover, and AI-tool declaration. The evidence wording was shortened after
the first inspection to eliminate a nearly empty appendix continuation page.

Verified conditions:

- no accidental blank pages;
- no overlapping or duplicated running headers;
- no cropped or clipped text, figures, tables, captions, or screenshots;
- no class-diagram relationship labels or multiplicities overlapping boxes;
- no content outside page margins;
- no broken references or citations;
- long technical identifiers break only at meaningful separators;
- the landscape evidence table is rotated, bounded, and readable;
- administrative placeholders are visible and limited to their intended fields.

The report is ready for supervisor review as a technically finalized current-state
draft. It is not institutionally final until the three administrative items above
are confirmed.
