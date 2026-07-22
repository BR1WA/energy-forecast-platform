# Product V1 Implementation Plan

**Branch:** `release/product-v1`  
**Base revision:** `102f8cd` (`main`, merged PFE pull request #2)  
**Plan date:** 2026-07-22  
**Target:** client-ready Product V1  
**Status:** Ready for implementation  
**Timebox:** approximately one focused week, followed by release review  
**Scope owner:** this document supersedes the short Product V1 outline in
`docs/PRODUCT_IMPLEMENTATION_PLAN_2026-07-20.md` where details conflict.

## Implementation progress

| Gate | Status | Evidence |
|---|---|---|
| G0 - Baseline and contracts | Complete | Baseline frozen, flags default off, enabled integration configuration validated, typed forecast capability errors added |
| G1 - 168-hour forecast | Complete | Independent artifact packaged, strict CPU warm-up passed, horizon-aware API/UI/reporting delivered, regression and Docker gates passed |
| G2-G7 | Pending | Not started on this implementation slice |

## 1. Outcome

Product V1 extends the truthful, single-user/single-site PFE release with:

1. An independently packaged and gated 168-hour Global TFT forecast.
2. Reliable transactional email delivery with retries and deduplication.
3. Email verification and secure password recovery.
4. Google authentication with server-side validation and explicit, safe linking.
5. HttpOnly refresh-cookie sessions instead of browser-readable refresh tokens.
6. Critical-alert email controlled by verified user preferences.
7. Durable avatar handling, self-service account export/deletion, and public
   privacy, terms, and support information.
8. Wider automated browser, dependency, backup/restore, and measured-performance
   release evidence.

Product V1 remains a focused residential energy product. It does not introduce
multi-site tenancy, organizations, billing, device control, model selection,
application retraining, Gemini, or 30-day forecasting.

## 2. Non-negotiable product rules

The following rules remain release blockers throughout this branch:

- A normal user owns exactly one Site and one primary Meter.
- Every reading, forecast, alert, recommendation, export, and account action is
  owner-scoped on the server.
- Measured, simulated, forecast, fallback, and unavailable states remain visibly
  distinct.
- The existing 24-hour forecast remains the stable default and cannot regress.
- The 168-hour forecast is invisible when its operator flag or artifact gate is
  disabled. When the artifact is available but client history is insufficient,
  the UI may show the feature with the precise data-readiness reason.
- No email-dependent control is enabled unless the mail subsystem is configured.
- Provider failure never rolls back a committed alert, account, or forecast.
- Raw verification, reset, refresh, Google, or provider tokens are never stored
  in the database or application logs.
- A password-reset request always returns the same public response whether the
  account exists or not.
- Google email alone is not sufficient to silently attach a Google identity to
  an existing account.
- New visible behavior must include loading, empty, disabled, failure, retry, and
  success states before it is considered complete.

## 3. Merged PFE baseline and confirmed gaps

| Area | Current baseline | Product V1 gap |
|---|---|---|
| Forecasting | Packaged 24-hour Global TFT, SHA-256 manifest check, 336-hour input gate, seasonal fallback | No packaged or runtime-gated 168-hour artifact; API/UI assume 24 hours |
| Research candidate | `week_168h` checkpoint and metrics exist in local research output | Output is untracked, not independently reproduced, packaged, or covered by product tests |
| Sessions | Hashed, persisted, rotating refresh JWTs with replay prevention | Refresh token is returned in JSON and handled by browser JavaScript |
| Email | `AlertConfig.email_enabled` exists in the database | API forces it off; no provider, outbox, templates, worker, or delivery evidence |
| Account identity | Local email/password accounts | No verification, recovery-token model, or Google identity model |
| Alerts | Evidence-backed persisted alerts; critical severity exists | No transactional critical-alert notification path |
| Avatars | Local `static/avatars` upload/delete | No durable container volume/storage abstraction or cleanup contract |
| Account rights | Consumption CSV and forecast PDF; admin can delete users | No complete account export or user-owned deletion flow; no public legal/support pages |
| Quality gates | Backend tests, lint, typecheck, build, migrations, Docker smoke | No automated multi-browser/mobile suite or dependency vulnerability gate |
| Operations | PostgreSQL and documented manual restore evidence | No repeatable Product V1 restore rehearsal or email-worker health/runbook |

The current recorded 168-hour Global TFT result is a promising candidate, not
release evidence:

- Cold-start macro MAE: `0.1973218019 kWh`
- Cold-start seasonal-naive macro MAE: `0.2490550040 kWh`
- Improvement over seasonal naive: `20.7718%`
- Cold-start households beating seasonal naive: `98.3968%`
- Horizon/lookback: `168/336` hourly steps

These values must be reproduced from immutable evaluation files and copied into a
production manifest before the product advertises a week forecast.

## 4. Delivery strategy

Work proceeds through the gates below in order. A gate is merged into the branch
only when its tests pass and incomplete UI is hidden. Keep commits small enough
to revert one gate without reverting the others.

| Gate | Deliverable | Depends on | Release blocking |
|---|---|---|---|
| G0 | Baseline freeze and contracts | Merged PFE | Yes |
| G1 | 168-hour artifact and forecast path | G0 | Yes |
| G2 | Transactional email foundation | G0 | Yes |
| G3 | Verification and password recovery | G2 | Yes |
| G4 | Cookie sessions and Google identity | G3 | Yes |
| G5 | Critical-alert email | G2, G3 | Yes |
| G6 | Account, legal, storage, performance, and operational hardening | G1-G5 | Yes |
| G7 | Full release validation | All gates | Yes |

G1 and G2 may be implemented in parallel after G0, but their database migrations
must remain in one linear Alembic history before integration.

## 5. Gate G0 - Freeze baseline and define contracts

### Implementation

- Record the exact PFE baseline revision, artifact fingerprint, database head,
  backend count, frontend routes, Docker readiness, and manual browser journey.
- Add Product V1 feature settings with safe defaults:
  - `FORECAST_168H_ENABLED=false`
  - `EMAIL_DELIVERY_ENABLED=false`
  - `GOOGLE_AUTH_ENABLED=false`
- Extend startup validation so enabled integrations require all corresponding
  secrets and public URLs; disabled integrations must still allow local startup.
- Define a single public error-code envelope for verification, recovery, Google,
  forecast capability, and mail-unavailable states. UI logic must not parse human
  error strings.
- Preserve the existing PFE endpoints while introducing Product V1 contracts.

### Acceptance gate

- Existing backend, frontend, migration, and Docker smoke gates pass unchanged.
- Default Product V1 configuration exposes no new non-functional controls.
- Production startup refuses partially configured enabled integrations and names
  only the missing setting, never its value.

## 6. Gate G1 - Promote the 168-hour Global TFT

### 6.1 Research promotion gate

Before copying the checkpoint into the application:

- Preserve the experiment manifest, seed, code revision, dataset identity/split,
  preprocessing, cohort definitions, and evaluation metrics.
- Recompute the checkpoint SHA-256 and verify that the checkpoint loads strictly
  into the declared architecture.
- Re-run inference on a fixed evaluation fixture and compare output to a stored
  tolerance, including shape `(168, 3)`, finite values, non-negative kWh, ordered
  `p10 <= p50 <= p90`, and stable timestamps.
- Confirm no training or evaluation household leakage across the declared known
  and cold-start cohorts.
- Compare against weekly seasonal naive on the same windows. Promotion requires:
  - positive macro-MAE improvement;
  - at least 75% of cold-start households beating seasonal naive;
  - no undocumented preprocessing difference between evaluation and product;
  - successful CPU inference inside the production backend image.
- Write `docs/FORECAST_168H_ARTIFACT.md` with metrics, limitations, fingerprint,
  runtime measurement, and explicit non-guarantee for a new client site.

The existing recorded result exceeds the numerical promotion thresholds, but
release remains blocked until the reproducibility and product-runtime checks pass.

### 6.2 Artifact contract

Create `backend/model_artifacts/global_tft_168h/` containing only the deployable
checkpoint and manifest. The manifest must declare at least:

- contract version, model name/display name, version, and checkpoint filename;
- checkpoint SHA-256 and byte size;
- input/output units, hourly resolution, 336-hour lookback, and 168-hour horizon;
- exact architecture parameters and calendar feature order;
- normalization and missing-data policy;
- quantiles and evaluation cohort metrics;
- training dataset identity and seed;
- limitations and fallback behavior.

Do not commit raw datasets, notebook output folders, cloned third-party repositories,
caches, or full experiment runs as application artifacts. Add ignore rules or an
artifact-publication script so research output cannot accidentally enter a release.

### 6.3 Backend contract

- Refactor fixed forecast definitions into a horizon-indexed artifact catalog; do
  not duplicate the full 24-hour service.
- Keep separate model instances, manifests, fingerprints, readiness, and warm-up
  status for 24 and 168 hours.
- Extend the API using an explicit `horizon_hours` value restricted to `24 | 168`:
  - `GET /api/v1/forecast/capabilities`
  - `GET /api/v1/forecast/readiness?horizon_hours=...`
  - `POST /api/v1/forecast/run` with a typed request body
  - history/latest filters by horizon without changing ownership rules.
- Preserve body-less 24-hour execution temporarily if needed for compatibility,
  but mark it as the 24-hour default in tests.
- Persist horizon, artifact fingerprint, input snapshot, preprocessing, source,
  fallback reason, confidence method, timestamps, and all 168 prediction points.
- Use the previous 168 hours as the deterministic weekly seasonal fallback only
  when a complete 336-hour prepared window passes the existing data gates.
- Prevent a failed 168-hour load or inference from changing 24-hour readiness.
- Update health/readiness output to report each fixed artifact independently.

### 6.4 Frontend contract

- Add a Day/Week horizon selector only when the server advertises the 168-hour
  capability as operator-enabled and artifact-ready.
- Keep Day as the default and show the selected horizon in totals, charts, history,
  report metadata, loading text, empty states, and limitations.
- Render 168 points readably through daily grouping/summary with an optional hourly
  drill-down; do not draw an unreadable 168-label axis.
- Clearly label Global TFT versus weekly seasonal fallback and show why fallback
  occurred.
- Update Dashboard and Reports without implying that a persisted 24-hour forecast
  is a week forecast.

### 6.5 Tests

- Manifest missing, hash mismatch, architecture mismatch, Torch missing, and flag
  disabled.
- 24/168 readiness isolation and 24-hour regression coverage.
- Insufficient coverage, maximum gap, non-finite input, timezone/DST timestamps,
  output shape/order, fallback, persistence, history filtering, and ownership.
- Fixed CPU inference fixture in the ML-enabled image.
- Frontend selector visibility, disabled/readiness reasons, 168-point rendering,
  fallback disclosure, history, and report metadata.

### Acceptance gate

- The 168-hour option cannot appear without a valid, warmed artifact and enabled
  feature flag.
- The same persisted input produces the expected fixed-fixture output within the
  declared tolerance.
- A broken 168-hour artifact leaves 24-hour forecast and global readiness healthy.
- Forecast PDF and UI identify horizon, method, version, fingerprint, uncertainty,
  source, and limitations.

## 7. Gate G2 - Transactional email foundation

### 7.1 Persistence

Add an `email_outbox` table through Alembic with:

- immutable message type, recipient, template version, and JSON payload;
- unique deterministic `deduplication_key`;
- `pending | processing | sent | retry | dead` status;
- attempt count, next-attempt timestamp, lease/lock timestamp, sent timestamp;
- provider message ID and a bounded/sanitized last-error field;
- created/updated timestamps and indexes for due-message polling.

Application code enqueues the outbox row in the same database transaction as the
business event. It never calls SMTP/provider APIs inside that transaction.

### 7.2 Delivery worker

- Add a provider-neutral mail interface and an SMTP implementation using TLS,
  timeouts, an authenticated sender, and plain-text plus HTML multipart templates.
- Add a dedicated worker command/service. Claim rows safely with a lease and
  `FOR UPDATE SKIP LOCKED` on PostgreSQL so duplicate workers do not double-send.
- Retry transient errors using bounded exponential backoff with jitter. Mark a
  message dead after the configured maximum and keep it available for an explicit
  audited retry; never loop forever.
- Treat provider acceptance as delivery success while documenting that acceptance
  is not proof of inbox delivery.
- Log outbox ID/type/status/attempt/latency only. Never log recipient tokens,
  template secrets, SMTP credentials, or complete provider responses.
- Add readiness details that distinguish API health from optional mail delivery.
  A provider outage must not make forecast or ingestion endpoints unavailable.

### 7.3 Configuration

Add documented settings without defaults that could accidentally send mail:

- `EMAIL_DELIVERY_ENABLED`
- `EMAIL_FROM_ADDRESS`, `EMAIL_FROM_NAME`, `EMAIL_REPLY_TO`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`
- `SMTP_USE_TLS`, `EMAIL_WORKER_POLL_SECONDS`, `EMAIL_MAX_ATTEMPTS`
- `PUBLIC_FRONTEND_URL`

Use a local capture server in development/test; never use a real recipient in CI.

### Acceptance gate

- Transaction rollback removes both the business change and unsent outbox row.
- Transaction commit survives provider outage and the message retries later.
- Repeated enqueue with the same key produces one logical message.
- Two workers cannot deliver the same claimed row concurrently.
- Secret scanning and log assertions find no raw credentials or action tokens.

## 8. Gate G3 - Email verification and password recovery

### 8.1 Data model

- Add `users.email_verified_at`.
- Add a general one-time `account_action_tokens` table with user, purpose,
  SHA-256 token hash, expiry, used/revoked timestamp, created timestamp, and
  indexes. Purposes are restricted to `verify_email` and `reset_password`.
- Store only a cryptographically random token hash. Tokens are single-use, scoped
  to one purpose, short-lived, and invalidated when replaced or consumed.
- Mark existing PFE users verified during migration to avoid locking out already
  accepted accounts; document this compatibility decision in the migration.

### 8.2 Verification flow

- New local registrations create an unverified account and enqueue one verification
  message. Do not issue normal access/refresh credentials until verification.
- Verification consumes the token atomically, marks the account verified, and
  redirects to a frontend result page without putting tokens in browser storage.
- Resend uses both IP and normalized-account rate limits and returns a neutral
  response. It rotates outstanding verification tokens and honors cooldown.
- Login with correct credentials for an unverified account returns a stable
  `email_verification_required` code; incorrect credentials retain the existing
  generic response.

### 8.3 Password recovery flow

- Request always returns `202` with the same message and comparable work whether
  the email is unknown, Google-only, inactive, or local.
- Reset confirmation validates purpose, hash, expiry, unused status, and password
  policy inside one transaction.
- Successful reset changes the password, consumes the token, revokes every refresh
  token for that user, and records a sanitized audit event.
- Reuse, expiry, racing submissions, and cross-purpose tokens fail safely.
- Email links use only `PUBLIC_FRONTEND_URL`; request headers cannot select the host.

### 8.4 Frontend

- Add verification-pending/result, forgot-password, and reset-password routes.
- Add resend cooldown and explicit expired/used/invalid states without revealing
  whether an arbitrary email belongs to an account.
- Update registration and login journeys while retaining the one-site setup after
  first verified sign-in.

### Acceptance gate

- Token values never appear in database rows, application logs, analytics, or
  frontend persistent storage.
- Enumeration, expiry, replay, race, rate-limit, password-policy, and session
  revocation tests pass.
- Mail outage leaves the account and outbox in a recoverable state and gives the
  user truthful retry guidance.

## 9. Gate G4 - Refresh-cookie migration and Google identity

### 9.1 Session migration

- Return access tokens in the response, but set refresh tokens only in an
  `HttpOnly` cookie. Remove `refresh_token` from public response schemas.
- Configure the cookie with `Secure` outside local development, `HttpOnly`, a
  narrow auth path, an explicit SameSite policy, bounded lifetime, and optional
  production domain. Never put it in `localStorage` or expose it to JavaScript.
- Read and rotate the cookie at refresh; clear it at logout and on invalid/replayed
  refresh. Keep the existing database hash and replay-prevention behavior.
- Hold the access token in memory and bootstrap a page reload through the refresh
  endpoint. Retry a failed API request at most once after refresh.
- Enforce the configured Origin on cookie-authenticated state-changing endpoints,
  keep CORS allowlists exact, and never combine wildcard origins with credentials.
- Support a short, documented compatibility window only if required for migration;
  remove legacy JSON refresh-token acceptance before the Product V1 release tag.

### 9.2 Google identity model

- Add `auth_identities` with `user_id`, provider, immutable provider subject,
  normalized provider email snapshot, timestamps, and unique constraints on
  `(provider, subject)` and `(user_id, provider)`.
- Allow `password_hash` to be null only for a Google-only account and update all
  local-password paths accordingly.
- Validate Google credentials on the backend: signature, issuer, audience,
  expiration, nonce/state, and `email_verified`. Client claims are never trusted
  without provider verification.
- New Google identities create a normal user that must still complete the same
  one-site setup.
- If a Google email matches an existing account but no identity is linked, refuse
  silent linking. Require an authenticated session plus recent local-password
  confirmation before linking.
- Prevent linking a Google subject already owned by another user.
- Unlink only when another usable sign-in method remains. Revocation/unlink must
  revoke active sessions and create an audit event.
- Keep the Google button hidden unless server capability and frontend client
  configuration are both enabled.

### 9.3 Tests

- Cookie flags, refresh rotation, replay, logout, logout-all, password-change/reset
  revocation, Origin/CSRF checks, and absence of browser-readable refresh tokens.
- Invalid issuer/audience/signature/nonce, expired credential, unverified Google
  email, duplicate subject, matching-email collision, explicit link/unlink, last
  login-method protection, deactivated user, and one-site ownership.
- Browser tests covering reload, concurrent refresh, expired access token, local
  login, Google login in a controlled test double, and logout.

### Acceptance gate

- Browser storage and API JSON contain no refresh token.
- A stolen/replayed old refresh token cannot create a new session.
- Google cannot silently take over or merge an existing local account.
- Local and Google users enter the identical ownership/setup workflow.

## 10. Gate G5 - Critical-alert email

### Implementation

- Re-enable `email_enabled` in alert API schemas and settings only when mail is
  configured and the current email is verified.
- Default existing and new users to opt-out until they explicitly enable email.
- When a new `critical` alert is persisted, enqueue a notification in the same
  transaction using `critical-alert:{alert_id}:{user_id}` as the logical dedup key.
- Template content includes the persisted evidence, observed time/timezone,
  threshold, source label, and a link to the owned alert. It must not invent device
  state, savings, cause, or control capability.
- Acknowledge/reopen actions do not resend the creation email. Any future reminder
  policy requires its own explicit dedup key and is outside this phase.
- Provider failures update only outbox delivery state. They do not change alert
  lifecycle or ingestion responses.
- Show preference status and verified-email prerequisite truthfully in Settings.

### Acceptance gate

- One critical alert creates at most one logical email; high/medium alerts do not.
- Opt-out, unverified email, disabled subsystem, duplicate evaluation, cooldown,
  provider failure, retry, and ownership tests pass.
- Alert ingestion/worker transactions remain successful while SMTP is unavailable.

## 11. Gate G6 - Product and operational hardening

### 11.1 Avatar storage

- Introduce a storage interface and configure a durable local volume for the
  single-instance deployment. Keep an S3-compatible implementation deferred until
  horizontal deployment is actually selected.
- Validate decoded image type, dimensions, and byte limit; generate an opaque
  server filename; never trust filename extensions or user paths.
- Remove replaced/deleted avatar objects after the database change is durable, with
  retryable cleanup for failures.
- Include the avatar volume in backup/restore documentation and verify restored
  files through the public endpoint.

### 11.2 Privacy, terms, support, export, and deletion

- Add public Privacy, Terms, and Support pages linked from registration/login and
  the authenticated layout. Content must contain owner/contact/effective-date
  placeholders that block production release until configured.
- Add an authenticated account export containing user/profile/preferences, site,
  meter metadata, readings, forecasts, alerts, recommendations, and audit-relevant
  user events in a documented machine-readable archive. Never export token hashes,
  ingestion secrets, password hashes, or other users' data.
- Add user-owned account deletion with recent-auth/password confirmation for local
  users and recent provider re-authentication for Google-only users.
- Deletion revokes sessions, removes owned database data and avatar objects, and
  returns a clear irreversible-action confirmation. Define which minimal security
  audit record, if any, is retained and anonymize it.
- Test export/deletion isolation and cascade behavior on PostgreSQL, not SQLite only.

### 11.3 Performance

- Establish fixtures and measure p50/p95 API latency and query counts for Dashboard,
  Consumption ranges, raw pagination, Reports, forecast history, alert worker, and
  account export.
- Capture `EXPLAIN (ANALYZE, BUFFERS)` for slow PostgreSQL queries and add only
  evidence-backed composite indexes/aggregations.
- Verify pagination and memory bounds on large reading/forecast sets. A 168-point
  forecast must not materially slow Dashboard when only summary data is needed.
- Record before/after numbers and the dataset size; do not claim performance gains
  without measurements.

### 11.4 CI, browsers, dependencies, and restore

- Add automated Playwright journeys for Chromium, Firefox, and WebKit at desktop
  and representative 360/390/768 px widths. At minimum cover local auth,
  verification/recovery states, setup, monitoring, 24/168 forecast states, alerts,
  settings, export, deletion confirmation, refresh, and logout.
- Add Python and npm dependency vulnerability scanning. Fail on unresolved
  high/critical findings; any temporary exception requires package, advisory,
  reason, owner, and expiry.
- Add secret scanning and ensure model/data output directories cannot be committed
  accidentally.
- Rehearse a PostgreSQL custom-format backup plus avatar volume backup into isolated
  targets. Verify row counts, representative ownership, forecast fingerprints,
  outbox statuses, and avatar content after restore.
- Document mail-worker deploy, drain, retry, rollback, key rotation, provider outage,
  Google credential rotation, backup, restore, and feature-disable procedures.

### Acceptance gate

- Public legal/support links are reachable and production placeholders are gone.
- Account export is complete and owner-scoped; deletion is confirmed, audited as
  designed, and irreversible.
- Performance evidence shows no material PFE regression and no unbounded query.
- Browser matrix, dependency/secret scans, fresh migration, Docker smoke, backup,
  and isolated restore all pass.

## 12. Gate G7 - Product V1 release validation

Run the final gate from a clean clone at the proposed release commit.

### Automated evidence

- Backend unit/integration tests against PostgreSQL.
- Alembic upgrade from the PFE head and from an empty database; downgrade only where
  the project explicitly supports it.
- ML artifact hash/contract tests and CPU inference for both horizons.
- Frontend lint, TypeScript, production build, component tests, and browser matrix.
- Dependency and secret scans.
- Docker Compose configuration, build, liveness, readiness, mail worker, alert
  worker, and frontend smoke.
- Provider-outage tests proving business transactions remain committed.

### Manual/staging evidence

1. Register, receive captured verification mail, verify, sign in, and complete setup.
2. Exercise expired/resend verification and password reset; confirm old sessions die.
3. Sign in with Google using approved staging origins; link/unlink an existing local
   account and verify takeover protection.
4. Import or push data, run 24-hour and 168-hour forecasts, inspect provenance and
   fallback/unavailable states, then export both reports.
5. Trigger a critical alert, observe one outbox delivery, simulate provider outage,
   recover delivery, and confirm the alert never rolled back or duplicated.
6. Upload/replace/delete an avatar, restart containers, and confirm persistence.
7. Export an account, inspect contents for ownership and secret exclusion, then
   delete a disposable account and confirm session/data/avatar removal.
8. Complete desktop/mobile journeys in the supported browser matrix.
9. Restore database and avatar backups into isolated targets and verify the recorded
   restore checklist.

### Release artifacts

- `docs/PRODUCT_V1_IMPLEMENTATION_LOG.md`
- `docs/PRODUCT_V1_RELEASE_NOTES.md`
- `docs/FORECAST_168H_ARTIFACT.md`
- updated environment example and deployment/operations documentation
- browser, performance, security-scan, backup/restore, and migration evidence

## 13. Planned code and migration map

Exact names may change during implementation, but responsibilities must remain
separated as follows:

| Area | Existing files to extend | New responsibility/files |
|---|---|---|
| Configuration | `backend/app/config.py`, `backend/.env.example`, `docker-compose.yml` | Feature flags, SMTP, Google, cookies, public URLs, worker settings |
| Models/migrations | `backend/app/models/models.py`, `backend/alembic/versions/` | Email verification timestamp, action tokens, identities, outbox, indexes |
| Forecast | `backend/app/services/product_forecast_service.py`, `backend/app/routers/forecast.py`, `backend/app/routers/system.py` | Horizon catalog, 168 artifact/service path, capabilities, isolated readiness |
| Email | `backend/app/cli.py`, worker deployment | Provider interface, templates, outbox service/worker |
| Authentication | `backend/app/routers/auth.py`, `backend/app/services/auth_service.py`, `backend/app/schemas/schemas.py` | Verification, reset, cookie rotation, Google validation/linking |
| Alerts | `backend/app/services/alert_service.py`, `backend/app/routers/alerts.py`, `backend/app/alert_worker.py` | Critical-alert enqueue and truthful preferences |
| Account/storage | auth/settings routers and avatar endpoints | Storage abstraction, account archive, self-deletion |
| Frontend auth | `frontend/src/lib/auth.tsx`, `frontend/src/services/api-client.ts`, login/register pages | Cookie bootstrap, verification/reset, Google, link/unlink states |
| Frontend forecast | forecast, dashboard, reports pages and shared types/API | Horizon selection, grouping, provenance, capability/readiness states |
| Frontend policy | root/authenticated layouts | Privacy, terms, support, export/deletion surfaces |
| Tests/CI | `backend/tests/`, `.github/workflows/ci.yml` | New API, worker, ML, PostgreSQL, Playwright, scan, and restore gates |

Migration order should be linear:

1. Identity and account-action fields/tables, including existing-user verification.
2. Email outbox.
3. Performance indexes proven necessary by measurements.

Each migration must work on a copy of the PFE schema/data and on an empty database.

## 14. Environment and secret inventory

Product V1 production deployment is blocked until the operator supplies and tests:

- strong JWT/admin/database secrets;
- exact frontend/API public URLs and CORS/cookie policy;
- verified sender address/name/reply-to and SMTP credentials;
- Google client ID/secret or credential configuration plus approved origins;
- legal owner/contact/support values;
- durable avatar and backup paths;
- feature flags explicitly enabled only after their readiness checks pass.

Secrets remain in the deployment secret store or local ignored `.env`, never in
Git, model manifests, frontend `NEXT_PUBLIC_*` variables (except the public Google
client ID/API URL), screenshots, logs, or release notes.

## 15. Suggested one-week sequence

| Day | Focus | Exit condition |
|---|---|---|
| 1 | G0 contracts; G1 artifact reproducibility/package | Clean baseline and valid 168 manifest/inference fixture |
| 2 | G1 backend/frontend; G2 outbox/provider/worker | Gated week forecast and provider-independent durable mail queue |
| 3 | G3 verification/reset | Secure single-use flows with captured-mail tests |
| 4 | G4 cookies/Google | No browser refresh token; safe Google create/link/unlink |
| 5 | G5 alerts; G6 account/storage/legal | Critical email isolation and complete account surfaces |
| 6 | Performance, browser matrix, scans, Docker, migrations | Automated Product V1 gates green |
| 7 | Staging journeys, outage tests, backup/restore, docs | Release evidence complete; no P0/P1 defect |

If external SMTP, sender-domain, Google console, or public-domain credentials are
not available, implementation and captured-provider tests may continue, but Product
V1 cannot be declared production-ready. Keep the affected capability disabled and
record the external dependency rather than simulating success.

## 16. Definition of done

Product V1 is complete only when all items below are true:

- [ ] PFE behavior and truth/ownership rules remain green.
- [ ] 24-hour forecast remains stable and independently ready.
- [ ] 168-hour candidate is reproducible, packaged, fingerprinted, runtime-tested,
      feature-gated, and truthfully represented in UI/reports.
- [ ] Email outbox is transactional, deduplicated, retryable, and safe with multiple
      workers and provider outages.
- [ ] Verification and reset tokens are hashed, expiring, single-use, rate-limited,
      non-enumerating, and session-revoking where required.
- [ ] Refresh tokens exist only as hashes server-side and HttpOnly cookies client-side.
- [ ] Google validation/linking/unlinking prevents silent takeover and preserves the
      one-site model.
- [ ] Critical email honors verified opt-in and cannot roll back or duplicate alerts.
- [ ] Avatars survive container replacement and participate in backup/restore.
- [ ] Privacy, terms, support, account export, and account deletion are complete.
- [ ] Performance changes have recorded before/after evidence.
- [ ] Backend, frontend, PostgreSQL migrations, ML inference, Docker, browser matrix,
      dependency/secret scans, provider outage, backup, and restore gates pass.
- [ ] Environment/deployment/runbook/release documentation is current.
- [ ] A clean source audit finds no raw dataset, credential, token, cache, cloned
      repository, or notebook-output leakage.
- [ ] No open P0/P1 issue remains and every visible control has working behavior.

## 17. Explicitly deferred to Product V2 or later

- 30-day detailed or aggregate forecasting.
- Gemini/chatbot or generated recommendations.
- Multi-site, organization, tenant administration, billing, or payments.
- Pull-based energy-provider connectors and device control.
- Application retraining, client model selection, or model comparison UI.
- Horizontal worker/API scaling beyond correctness-safe outbox locking.
- S3-compatible avatar storage unless deployment topology requires it.
- Prometheus/Grafana unless measured operations create a concrete need.

Deferred work must not leave routes, controls, feature claims, or partially connected
schemas visible in Product V1.
