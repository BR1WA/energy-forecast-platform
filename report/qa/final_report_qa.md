# Final Report QA - Production Model Update Version 8

## Build identification

- Output: `output/pdf/PFE_ZOUITNI_Salah_Eddine_production_v8.pdf`.
- Previous draft and supervisor-review PDFs are retained and were not overwritten.
- Language: academic English with a French resume.
- Build date: 15 August 2026.
- Format: A4, 12 pt, one-sided PDF; 98 pages; 1,729,785 bytes.
- SHA-256: `5434F751FF9809127BB75584A92BD4C93702E81C176353A66AA7A428CBC1043F`.

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
The previously verified Azure revision predates this integration and is still
reported as a two-TFT deployment; no later Azure promotion is claimed.

## Current local quality gates

- Backend and training suite: 116 passed, 4 explicit PostgreSQL-only skips.
- Month real-wrapper smoke: exact base and adapter loaded; 30 finite ordered
  quantile outputs returned.
- Frontend ESLint and TypeScript: passed.
- Next.js production build: passed; 25 routes.
- Playwright six-project matrix: 198 passed, 0 failed.
- Simulator browser coverage: one-year hourly context, all-model readiness,
  synthetic provenance, reset isolation, and CSV handoff.
- Python compileall: passed.
- Docker Compose configuration: resolved successfully.
- Production Docker image build: intentionally stopped before completion at the
  user's request to avoid PyTorch/model downloads over limited cellular data.
  No later dependency, dataset, or container download was attempted.

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
- The production Dockerfile installs the separately pinned foundation runtime,
  copies only the exact release adapter, and defines a build-time base-prefetch
  step. Its full build was not rerun under the cellular-data constraint above.
- Hourly Chronos releases, frozen protocol, audit, hashes, and CPU benchmark are
  retained as production-eligible challengers rather than active models.

## Compilation and visual QA

- Build method: clean isolated MiKTeX pdfLaTeX, Biber, and two stabilizing
  pdfLaTeX passes.
- Fatal LaTeX errors: 0.
- Undefined references or citations: 0.
- Overfull horizontal or vertical boxes: 0.
- All 98 pages rendered with Poppler at 90 dpi.
- All pages inspected in nine numbered contact sheets.
- Full-page checks covered both abstracts, the new month/hourly model tables,
  current validation summary, evidence registry, requirement matrix, and final
  installation page.
- No clipped text, overlapping content, broken tables, unreadable glyphs,
  accidental blank pages, or content outside the margins was observed.

## Remaining boundaries

The report remains administratively incomplete until the official defense date
and jury composition are supplied. Model results remain dataset-specific rather
than a performance guarantee for an arbitrary Moroccan site. The new repository
release has not yet been promoted to Azure, and the target deployment still needs
its foundation-image memory/startup check when non-cellular bandwidth is
available.
