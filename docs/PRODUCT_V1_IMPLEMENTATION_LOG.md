# Product V1 Implementation Log

**Branch:** `release/product-v1`  
**Base:** `102f8cd`  
**Started:** 2026-07-22

## G0 - Baseline and capability contracts

**Status:** Complete

- Frozen the merged PFE contract and evidence in `docs/PRODUCT_V1_BASELINE.md`.
- Added disabled-by-default `FORECAST_168H_ENABLED`,
  `EMAIL_DELIVERY_ENABLED`, and `GOOGLE_AUTH_ENABLED` settings.
- Added startup validation that rejects enabled email/Google integrations with
  incomplete configuration without printing secret values.
- Documented all flags in backend/root environment examples and wired them into
  the backend Compose service.
- Added stable forecast capability error codes and frontend support for structured
  `{code, message}` error details.
- Kept database and primary 24-hour artifact readiness as the global readiness
  gate; optional week failure is reported independently.

## G1 - 168-hour Global TFT

**Status:** Complete

### Research promotion

- Source experiment: `full_selected_v1`, seed `2026`.
- Verified 2,000 unique known and 500 unique cold-start household identifiers
  with zero split overlap; 499 cold-start households supplied valid evaluation
  windows.
- Verified strict loading of all 186 checkpoint tensors into the shared
  horizon-dynamic `GlobalTFT` architecture.
- Verified deterministic repeated CPU output within `1e-5`, finite `(1, 168, 3)`
  output, and fixed reference values at the start, middle, and end of the horizon.
- Packaged only `model.pt` and `manifest.json` under
  `backend/model_artifacts/global_tft_168h/`.
- Checkpoint SHA-256:
  `80af16b25af9b912019c6e40cfdc491e2cf5173e5743144596801e28df695f93`.

### Backend

- Replaced the single model cache with a fixed 24/168 artifact catalog while
  retaining PFE compatibility constants and body-less 24-hour execution.
- Isolated manifests, hashes, model instances, warm-up, feature visibility, and
  failure state by horizon.
- Added authenticated capabilities and horizon-aware readiness, execution,
  latest, and history contracts.
- Persisted horizon, fixed artifact fingerprint, forecast window, method,
  preprocessing, inference time, and all target points.
- Added a 168-hour seasonal fallback based on the previous complete 168-hour
  window, available only after the week artifact has first passed its visibility
  gate.
- Extended analytics summaries and PDF reports to preserve the actual horizon.
- Added per-artifact system readiness plus a read-only admin view for both fixed
  artifacts. A failed optional week artifact cannot take the day service offline.

### Frontend

- Kept Day/24h as the default.
- Added the Week/168h selector only when returned by server capabilities.
- Filtered readiness, latest forecast, and history by the selected horizon.
- Added dynamic horizon labels to Dashboard, Forecast, history, Reports, and PDF
  descriptions.
- Grouped 168 stored hourly targets into readable local-day chart totals while
  retaining every hourly value for peak, provenance, persistence, and export.
- Added horizon-specific model evidence, forecast windows, target counts,
  fingerprints, fallback disclosure, and empty states.

### Source safeguards

- Added ignore rules for research data, checkpoints, NumPy arrays, logs, caches,
  experiment runs, and cloned repositories under `models/`.
- Kept research/training folders separate from deployable model artifacts.
- Updated README, operations, baseline, artifact, and execution-plan documents.

## G0-G1 validation evidence

| Gate | Result |
|---|---|
| Backend full suite | `53 passed` |
| Torch-free Docker backend suite | `50 passed, 3 skipped` (ML inference tests intentionally skipped) |
| 24-hour ML inference | Passed with ordered quantiles and deterministic repeated output |
| 168-hour ML inference | Passed with 168 ordered quantiles and deterministic repeated output |
| Production image warm-up | Both 24h and 168h available and warmed with independent fingerprints |
| Frontend ESLint | Passed |
| Frontend TypeScript | Passed |
| Next.js production build | Passed |
| Docker Compose configuration | Passed |
| Alembic graph | Single unchanged head `d3a9f6c1b208` |

The isolated production image check used `FORECAST_168H_ENABLED=true` and loaded
both checkpoints with Torch without starting or changing the local database stack.

## G2 - Transactional email

**Status:** Complete

- Added a caller-transaction-owned, deterministically deduplicated outbox.
- Added PostgreSQL `FOR UPDATE SKIP LOCKED` claiming, expiring leases, bounded
  retry/backoff, dead-letter state, and audited manual retry.
- Added provider-neutral SMTP/test delivery, multipart templates, sanitized
  logging, and optional mail readiness.

## G3 - Verification and recovery

**Status:** Complete

- New local registrations remain unverified and receive no session.
- Action-token SHA-256 hashes are stored separately from sealed render-time mail
  payloads; raw tokens are not persisted.
- Verification and reset are atomic and single-use, resend/reset requests are
  neutral and rate-limited, and password reset revokes all sessions.
- Added verification, resend, forgot-password, and reset-password browser states.

## G4 - Cookie sessions and Google identity

**Status:** Complete

- Refresh credentials remain in HttpOnly cookies and server-side hashes with
  rotation, replay prevention, Origin enforcement, logout, and logout-all.
- Google credentials and one-time state/nonce challenges are validated server-side.
- Linking requires an authenticated session and recent local-password
  confirmation; unlinking protects the final usable login method and revokes
  sessions.

## G5 - Critical-alert email

**Status:** Complete

- Critical-alert mail is an explicit opt-in available only when delivery is
  configured and the current account email is verified. Existing and new alert
  configurations default to opt-out at the database layer.
- Each newly persisted critical alert enqueues at most one logical message in the
  alert transaction with dedup key `critical-alert:{alert_id}:{user_id}`.
- Messages contain only persisted meter evidence, observed local time/timezone,
  configured threshold, source label, and an owner-scoped alert link.
- High/medium alerts and acknowledge/resolve/reopen actions do not enqueue mail.
  SMTP failures affect only outbox delivery state, never alert or ingestion state.
- Alert settings expose active, opted-out, unverified, and mail-unavailable states
  truthfully.

### G2-G5 validation evidence

| Gate | Result |
|---|---|
| Backend full suite on PostgreSQL | `87 passed` |
| G5 focused backend suite | `26 passed` after the final cooldown/medium additions |
| Fresh Alembic upgrade | Reached `a8d4c6e2f105` |
| PFE-head Alembic upgrade | Reached `a8d4c6e2f105`; legacy preference normalized to false/non-null |
| Frontend ESLint | Passed |
| Frontend TypeScript | Passed |
| Next.js production build | Passed as part of the browser web-server gate |
| Controlled Chromium journeys | `6 passed` |

External SMTP and Google credentials remain operator-provisioned feature flags.

## G6 - Product and operational hardening

**Status:** Complete

- Added decoded-image validation, WebP normalization, opaque object names, a
  configured durable avatar volume, and retryable post-commit object cleanup.
- Added configured public Privacy, Terms, and Support content, plus a complete
  owner-scoped machine-readable account archive and recent-authenticated account
  deletion with anonymized retained security evidence.
- Bounded large reading/forecast paths and recorded repeatable PostgreSQL p50/p95,
  query-count, and `EXPLAIN (ANALYZE, BUFFERS)` evidence without claiming an
  unsupported latency gain.
- Expanded the Playwright matrix to Chromium, Firefox, and WebKit across desktop
  and 360/390/768 px viewports; covered policy, setup, monitoring, both forecast
  horizons, account export/deletion, refresh, and logout journeys.
- Added Python/npm dependency and full-history secret gates, strengthened generated
  model/data ignores, and upgraded vulnerable dependencies.
- Added repeatable PostgreSQL custom-format and avatar archive scripts. An isolated
  restore verified ownership, counts, a forecast fingerprint, a dead outbox record,
  avatar decoding, and the restored avatar's public response hash.
- Expanded operations guidance for backup/restore, mail-worker lifecycle and
  outage recovery, feature disablement, credential rotation, and avatar cleanup.

### G6 validation evidence

| Gate | Result |
|---|---|
| Backend host suite | `91 passed, 4 skipped` |
| Torch-free backend test image against PostgreSQL | `92 passed, 3 skipped` |
| PostgreSQL locking/ownership suite | `4 passed` |
| Fresh and PFE-head Alembic upgrades | Both reached `c8f4a1b2d306` |
| Frontend lint, typecheck, and production build | Passed; 23 routes generated |
| Full browser matrix | `66 passed` across six desktop/mobile projects |
| Backend/frontend Docker images and HTTP smoke | Built; backend `/health` and frontend `/login` returned 200 |
| Python dependency audit | No known vulnerabilities |
| npm dependency audit | No vulnerabilities |
| Full-history secret scan | 336 commits scanned; no leaks after documented exact historical test-fixture baseline |
| Isolated PostgreSQL/avatar restore | Counts, ownership, fingerprint, outbox status, decoded image, and public SHA-256 all matched |

## G7 - Product V1 release validation

**Status:** Blocked after automated clean-worktree validation.

- Validated the detached clean worktree at `6a298b6`, then repaired an
  image-specific avatar MIME issue discovered during restored-file serving. WebP
  avatars are now explicitly served as `image/webp` even when the base image has
  no OS MIME database.
- Ran the complete backend suite against isolated PostgreSQL, empty-database and
  PFE-head upgrades, Docker CPU model-contract tests for both 24h and 168h,
  frontend lint/typecheck/build, and the six-project browser matrix.
- Ran captured-provider verification/reset and provider-outage/retry coverage,
  cookie-session/revocation coverage, and controlled Google test-double coverage.
- Built an isolated Compose stack with both forecast artifacts enabled and email
  and Google features disabled. Liveness, readiness, frontend, alert worker,
  email worker, avatar worker, and an in-stack provider-outage retry check passed.
- Rehearsed custom-format database plus avatar restore again into isolated targets,
  including public restored-avatar serving with the correct WebP MIME type.
- Recorded exact validation scope, outcomes, and external staging limits in
  `docs/PRODUCT_V1_G7_VALIDATION_EVIDENCE.md` and release handoff conditions in
  `docs/PRODUCT_V1_RELEASE_NOTES.md`.

No P0 product defect was found in the automated release validation. However, the
required clean-source audit found pre-existing tracked raw data, checkpoints, and
notebooks/output notebooks. They are outside Product V1 scope and were preserved as
instructed, but this is a P1 release-hygiene blocker under the plan's definition of
done. Real SMTP delivery, sender-domain acceptance, Google console/OAuth journeys,
production legal identity, and production public URL/cookie-origin acceptance were
also unavailable and were not simulated as real-provider evidence. Those capabilities
remain disabled until the operator completes the documented staging checklist.

## Release handoff

Product V1 functional source validation is complete, but the release remains blocked
on the tracked-source audit finding and on external operator configuration/real-
provider staging acceptance listed in the release notes. No Product V2 work is part
of this branch.
