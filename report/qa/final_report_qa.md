# Final Report QA

## Build identification

- Report: `PFE_ZOUITNI_Salah_Eddine_draft.pdf`.
- Language: professional academic English, with the required French résumé and retained French source correspondence where relevant.
- Format: A4, 12 pt, one-sided PDF; 90 pages; 1,656,671 bytes.
- SHA-256 of the verified source build: `68AF8C068C92AC85FD1445EFC3E1E08A670DBA3DCBB5D011E7F4DD71514119F9`.
- Build date: 2026-08-01.
- Compiler: MiKTeX pdfLaTeX with Biber bibliography processing.

## Completion checklist

- Institutional cover adaptation, dedication placeholder, acknowledgements, English abstract, French résumé, keywords, contents, lists of figures/tables/acronyms, general introduction, seven chapters, conclusion, references, and Appendices A-D: complete.
- Cover identity: official combined UMI/FSM logo and the blue-orange Faculty of Sciences motif; Department of Computer Science, Master SDIA wording, supervisor title, and the scheduled 9 September 2026 defense date are present.
- Research questions and demonstrated contributions are stated explicitly in the general introduction.
- Chapter 2 now contains a paper-level primary-source synthesis and covers recurrent, tree-based, convolutional, Transformer, global, normalization, probabilistic, leakage, drift, conformal, and privacy literature.
- Chapter 5 now reports exact frozen day-ahead and week-ahead results, training configuration, hardware, elapsed times, cohort/window counts, inference timing scope, post-hoc checkpoint diagnostics, and selection caveats.
- The central narrative includes the supervisor-supplied DEPM paper, its replication, the leakage audit, corrected historical variants, the forecasting pivot, completed and incomplete deep-model attempts, the ECL benchmark, the Low Carbon London cold-start study, and EnergyAI integration.
- Active 24-hour and 168-hour frozen metrics were retained without alteration. Historical classification scores remain labelled diagnostic or invalidated rather than forecast evidence.
- The research/serving normalization mismatch is stated consistently: frozen LCL evaluation uses per-household training-segment statistics, while product serving uses the latest accepted 336-hour window. The report does not transfer frozen MAE or coverage to the serving transform.
- Incomplete TimePro, TimeMixer++, and TSMixer work is reported as incomplete and excluded from successful-comparison claims. Monthly forecasting remains experimental and outside Product V1.
- Product routes, redirects, ownership boundary, six-service Compose architecture, 80 method-path operations across 74 unique OpenAPI paths, analytics PDF export, and the absence of a separate reports workspace are aligned with the audited source.
- Bibliography: 26 cited primary or authoritative entries processed by Biber with no unresolved citations.
- Evidence registries cover models, figures, commits, notebooks, artifact hashes, tests, requirements, OpenAPI inventory, and post-hoc TFT reanalysis.
- Visual assets: 21 programmatic figures/diagrams plus five live application screenshots registered with source, method, date, and status.
- Application screenshots: five 1280 × 720 captures from a non-administrative demonstration account. They cover Dashboard, Usage, ready 24-hour and 168-hour Global TFT forecasts, and an Actions view created by a labelled 0.500 kW push sample crossing a configured 0.400 kW threshold. No token, meter key, password, local path, or personal identifier is visible.

## Scientific evidence controls

- Frozen 24-hour cold-start headline: macro MAE 0.184928 kWh per hourly interval, 26.48% below the seasonal-naive baseline, with 495/500 household wins.
- Frozen 168-hour cold-start headline: macro MAE 0.197322 kWh per hourly interval, 20.77% below the seasonal-naive baseline, with 491/499 household wins.
- The reanalysis script strictly loads the frozen checkpoints and aborts if recomputed macro MAE or exact win counts differ from the frozen results beyond the declared numerical tolerance.
- Post-hoc empirical central-80% interval coverage is reported as 80.796% at 24 hours and 78.352% at 168 hours. These are frozen-cohort diagnostics, not claims of calibrated client-site coverage.
- Checkpoint, raw-array, calendar-array, scaler, and reanalysis-script hashes are recorded in the reanalysis manifest and Appendix B.
- Full-cohort batched research inference times are explicitly distinguished from request latency.
- The dynamic-window worker's clock-derived randomness and cuDNN benchmark setting are disclosed; seed 2026 is not represented as bitwise reproducibility.
- No code-coverage percentage is claimed because no coverage artifact was found.

## Software and deployment evidence

- Frozen application audit: 96 backend tests passed with four expected SQLite skips; 100 passed and zero skipped on disposable PostgreSQL; frontend lint, type check, and production build passed; 107 Playwright tests passed, with one isolated WebKit reload interruption passing on rerun.
- Docker was rechecked on 2026-08-01 after Docker Desktop started: PostgreSQL, backend, and frontend were healthy; alert, email, and avatar-cleanup workers were running.
- The deployment claim remains local Compose only. No public URL, TLS termination, cloud deployment, external provider validation, or production-load evidence is asserted.
- Nine high-severity npm findings remain documented as development-tool advisories; the production npm audit is recorded as clean.

## Compilation checks

- Fatal LaTeX errors: 0.
- Undefined references: 0.
- Undefined citations: 0.
- Bibliography rerun warnings: 0.
- Overfull boxes: 0.
- Duplicate PDF destinations: 0.
- Appendix numbering: A-D, with corresponding table and section numbers.
- Search for unintended `TODO`, `TBD`, local Windows paths, `file://`, malformed cross-references, and unsupported metrics: no unintended matches.
- Administrative placeholders: exactly three approved red `TO BE CONFIRMED` fields remain, on physical pages 1, 2, and 90.
- pdfTeX reports three ignored glue-shrink diagnostics while splitting dense longtables. Targeted page inspection confirms that the affected tables are fully visible, bounded, and readable.

## Visual inspection

All 90 pages were rendered at 110 dpi under `report/qa/rendered_verified_20260801` and inspected in eight numbered contact sheets. Targeted original-resolution checks covered the cover, both abstracts, all chapter openings, benchmark and traceability tables, the rotated full-hash table, diagrams, screenshots, references, Docker instructions, and AI-tool declaration.

Verified conditions:

- no accidental blank pages;
- no cropped text, tables, captions, figures, or screenshots;
- no content outside page margins;
- no distorted diagrams or application captures;
- no broken, loading, or administrative application state in the five report screenshots;
- readable grayscale-compatible academic figures;
- controlled title wrapping and consistent headers/page numbers;
- no duplicated captions or orphaned chapter headings.

## Remaining approved placeholders and decisions

- Personal dedication.
- Jury composition.
- Exact institution-approved AI-tool declaration.
- Final administrative confirmation of the scheduled 9 September 2026 defense date.
- Confirmation that the Faculty's public doctoral cover model may be adapted for this Master PFE, or replacement with a programme-supplied Master template.

## Final status

The draft is technically complete, reproducible, evidence-backed, and ready for supervisor review. It is not yet an institutionally final submission because the three approved placeholders, Master-specific formatting confirmation, and defense-date confirmation remain administrative dependencies.
