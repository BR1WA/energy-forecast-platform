# Final Report QA — Persistent Demo and Account-Control Update

## Build identification

- Planned output: `report/exports/PFE_ZOUITNI_Salah_Eddine_supervisor_review_v5.pdf`.
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

The report records the latest split revision set verified on 9 August 2026:

- verified `origin/main` head:
  `6796b1ec7360f9c05cb804fbd8be29ba1ea78ef8`;
- frontend revision: `ca-energyai-web--v1-f807316`, healthy with 100% traffic;
- API revision: `ca-energyai-api--v1-6796b1e`, healthy with 100% traffic;
- email-worker revision: `ca-energyai-email-worker--v1-6796b1e`, one healthy replica;
- frontend digest: `sha256:6f136232457e877611b98b59c32440eaa5f141b120026fc604adafb41022d5a1`;
- backend digest: `sha256:44bc79966e03a04d906895047fb189d3bfb12617544dcc59cfbd83f66cf8f299`;
- public pages: web, Login, Register, Privacy, and Terms returned HTTP 200;
- database: managed PostgreSQL 16 ready;
- models: both frozen 24-hour and 168-hour TFT artifacts available, enabled, and warmed;
- email: SMTP capability ready and the email worker healthy;
- Google: external application in production; live account chooser opened for the
  exact Azure origin without creating a user;
- responsive smoke: desktop and 390 x 844 registration views had no horizontal overflow;
- rollback: older revisions remain inactive; compatible web/API pairs must be selected.

The evidence registry is
`report/evidence/azure_deployment_evidence_2026-08-09.md`. It records the resource
boundary, immutable image digests, Google project/client boundary, health evidence,
rollback target, and remaining limitations without storing secrets.

## Current quality gates

- Backend local suite: 112 passed, 4 explicit PostgreSQL-only skips.
- Historical isolated-PostgreSQL suite: 100 passed, 0 skipped; schema unchanged.
- Current CI PostgreSQL migrations, tests, backend test-image build/rerun: passed.
- Frontend ESLint and TypeScript: passed.
- Next.js production build: passed; 25 routes.
- Playwright six-project matrix: 192 passed, 0 failed.
- Populated DST-week tests: 167-hour and 169-hour cases passed.
- npm audit: zero known vulnerabilities.
- production Python requirements audit: zero known vulnerabilities.
- Docker-specific `npm ci`: passed after lockfile normalization.
- Full-history secret scan and Docker Compose CI smoke: passed.
- GitHub Actions run `31328212332`: green at commit `6796b1e`.

## Latest implementation evidence

- Persistent simulator: deterministic 30-day/2,881-point bootstrap for an empty
  meter, forward-only scale-to-zero catch-up, coarser exceptional intervals,
  5,000-point cap, and idempotent meter/timestamp storage.
- Data integrity: every generated row is `source="simulation"`; CSV, push,
  pre-existing, and deliberately stopped gaps are never backfilled.
- Explicit reset: regenerates only simulator-owned readings and batches.
- Dashboard: plain-language energy, cost, peak, comparison, provenance, coverage,
  and next-action narratives complement the quantitative charts.
- CSV handoff: preview remains available; confirmed import stops a running
  simulator after consent and preserves historical source labels.
- Account deletion: recent reauthentication plus ordered set-based ownership-graph
  deletion; focused PostgreSQL verification removed a full simulator account in
  0.272 seconds.

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
- `report/source/frontmatter/abstracts.tex`
- `report/source/chapters/chapter1.tex`
- `report/source/chapters/chapter6.tex`
- `report/source/chapters/chapter7.tex`
- `report/source/chapters/general_conclusion.tex`
- `report/source/appendices/appendix_a_traceability.tex`
- `report/source/appendices/appendix_c_technical.tex`
- `report/qa/current_report_text.txt`
- `report/qa/final_report_qa.md`
- `report/evidence/azure_deployment_evidence_2026-08-09.md`
- `report/evidence/commit_timeline.csv`
- `report/evidence/requirements_traceability.csv`
- `report/evidence/test_evidence_summary.csv`
- `report/exports/PFE_ZOUITNI_Salah_Eddine_supervisor_review_v5.pdf`

## Compilation and textual QA

- Output: `report/exports/PFE_ZOUITNI_Salah_Eddine_supervisor_review_v5.pdf`.
- Format: A4, 12 pt, one-sided PDF; 98 pages; 1,720,721 bytes.
- SHA-256: `84B98108632FDD62B55062CAD9A31ABC9A067CE2D25C8C1366B64F32928687C0`.
- Build method: clean manual MiKTeX sequence in a fresh output directory using
  pdfLaTeX, Biber, and stabilizing pdfLaTeX passes.
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

All 98 pages were rendered at 90 dpi and inspected in nine numbered contact
sheets. Full-resolution checks additionally covered the English and French
abstracts, persistent-simulation section, dashboard narrative, Azure topology
and resource table, validation summary, conclusion, evidence registries,
requirement matrix, API/test tables, cover, and AI-tool declaration. The
abstracts were tightened after the first inspection to remove nearly empty
keyword-only continuation pages.

Verified conditions:

- no accidental blank pages; one intentional recto separator remains before the
  contents;
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
