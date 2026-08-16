# Final Report QA - Audit-Remediated Version 10

## Build identification

- Output: `output/pdf/PFE_ZOUITNI_Salah_Eddine_production_v10.pdf`.
- Previous draft and supervisor-review PDFs are retained and were not overwritten.
- Language: academic English with a French resume.
- Build date: 16 August 2026.
- Format: A4, 12 pt, one-sided PDF; 98 pages; 1,732,542 bytes.
- SHA-256: `1E6C094D30A0AE23BA86FC67C694629D553212402A02E1EFC9C4B7F1EB2F9283`.

## Scientific-evidence boundary

This update records new model work rather than reusing the prior negative month
conclusion. The production month release is Chronos-2 120M plus a rank-8 LoRA
adapter trained for 600 updates under a frozen protocol. The strongest frozen
Tetouan selection baseline is improved by 49.82%, macro R2 is 0.4498, and
central-80% coverage is 88.15%. Portugal transfers positively; the southern
Morocco diagnostic is 7.27% worse than its comparator and remains an explicit
limitation.

The same architecture was tested for 24 and 168 hourly targets. Both challengers
pass their frozen London accuracy and reload gates, improving the packaged TFTs
by 2.90% and 2.62%. They remain undeployed because the gains do not yet justify
doubling the required history to 672 hours, adding the foundation-base memory
cost, and changing the current serving contract without a geographic audit.

The repository release exposes the month model through the backend and frontend.
Azure revision `v4-d25295b` now serves this integration. The public readiness
payload reports the 24-hour, 168-hour, and 720-hour artifacts available, enabled,
and warmed, including the 30-day daily Chronos-2 model.

## Current source quality gates

- Backend and training suite on SQLite: 142 passed, 4 explicit
  PostgreSQL-only skips; 82.38% application coverage against a 70% CI floor.
- Fresh PostgreSQL 16 database: all 18 migrations applied; 146 passed, 0
  skipped; `alembic check` reported no schema drift.
- ML-enabled backend test image: 117 passed, 4 skipped; UID 10001; no compiler;
  exact Chronos-2 revision prefetched.
- Month real-wrapper smoke: exact base and adapter loaded; 30 finite ordered
  quantile outputs returned.
- Frontend ESLint and TypeScript: passed.
- Next.js production build: passed; 25 routes.
- Playwright six-project matrix: 204 passed, 0 failed. The final password and
  production-documentation policy change was additionally rechecked in a
  36-case six-project authentication matrix.
- Simulator browser coverage: one-year hourly context, all-model readiness,
  synthetic provenance, reset isolation, and CSV handoff.
- Python compileall: passed.
- Docker Compose configuration: resolved successfully.
- Backend and frontend production/test images: built and smoke-tested as
  non-root runtimes. The backend foundation image installed only hash-locked
  dependencies and prefetched the exact base revision.
- Dependency audits: npm and Python runtime/development/foundation locks report
  zero known vulnerabilities. The custom CPU Torch wheel is explicitly outside
  PyPI's advisory database.
- Full-history secret scan: 407 commits scanned; no leaks found.

## Release implementation evidence

- Backend supports horizon identifiers 24, 168, and 720 while returning the
  authoritative target count, interval, and resolution. The 720 identifier means
  30 daily targets, never 720 hourly values.
- Month input preparation integrates meter intervals into rolling 24-hour totals,
  requires at least 270 valid days in a maximum 365-day context, and permits only
  bounded causal interpolation.
- A new empty account can bootstrap 365 days of deterministic hourly simulation
  history (8,761 boundary-inclusive readings). This makes all three active model
  contracts ready without lowering the month gate or changing TFT inputs.
- The month runtime is offline-only and verifies pinned base and adapter checksums.
- Forecast persistence, history serialization, charts, readiness, and PDF export
  preserve daily cadence.
- The production Dockerfile installs the transitively hash-locked foundation runtime,
  copies only the exact release adapter, and defines a build-time base-prefetch
  step. The full model-enabled image was built and tested on GitHub runners,
  preserving the local cellular-data constraint.
- Hourly Chronos releases, frozen protocol, audit, hashes, and CPU benchmark are
  retained as production-eligible challengers rather than active models.

## Compilation and visual QA

- Build method: MiKTeX pdfLaTeX, Biber, and two stabilizing pdfLaTeX passes.
  `latexmk` was unavailable because its local wrapper requires Perl; the direct
  equivalent sequence completed without an added dependency.
- Fatal LaTeX errors: 0.
- Undefined references or citations: 0.
- Overfull horizontal or vertical boxes: 0.
- All 98 final pages rendered with Poppler at 90 dpi.
- All pages inspected in nine numbered contact sheets after the final figure
  update; changed architecture, simulation, security, validation, and appendix
  pages were also reviewed at full-page resolution.
- Full-page checks covered both abstracts, the new month/hourly model tables,
  current validation summary, evidence registry, requirement matrix, and final
  installation page.
- No clipped text, overlapping content, broken tables, unreadable glyphs,
  accidental blank pages, or content outside the margins was observed.
- The reopened PDF has 98 readable pages, is not encrypted, contains no local
  Windows path or tool token, and retains only the two approved visible
  administrative placeholders on the cover.

## Remaining boundaries

The report remains administratively incomplete until the official defense date,
jury composition, any required host/laboratory line, and approved AI-tool
disclosure are supplied. Model results remain dataset-specific rather than a
performance guarantee for an arbitrary Moroccan site. The existing Azure
release passed foundation-image startup, 2-vCPU/4-GiB readiness, and public
endpoint checks, but the remediated source images and dedicated simulation
worker have not yet been promoted. It remains a controlled academic deployment,
not a claim of universal accuracy or full production maturity.
