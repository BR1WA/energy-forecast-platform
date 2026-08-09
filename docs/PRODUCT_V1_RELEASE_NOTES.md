# Product V1 release notes

## Release status

Product V1 completed functional automated validation from a clean detached worktree,
including PostgreSQL migrations, backend integration, CPU inference for both fixed
forecast horizons, frontend/browser coverage, Compose workers, dependency and secret
scans, and isolated backup/restore. No P0 or P1 software defect is open.

The jury release is deployed from commit
`af467989694322ef76a5402a367893ea01f5e1dd` to the existing Azure Italy North
architecture. The public web/API, managed PostgreSQL connection, email worker,
SMTP capability, 24-hour and 168-hour model readiness, and Google Web OAuth origin
are verified. The release remains a controlled PFE deployment rather than a claim
of complete production maturity.

## Included Product V1 capabilities

- Truthful 24-hour forecast plus runtime-gated 168-hour Global TFT forecast with
  artifact integrity, provenance, fallback disclosure, and reports.
- Transactional multipart email outbox with PostgreSQL safe claiming, retries,
  dead-letter handling, and critical-alert opt-in.
- Email verification and secure password reset; refresh credentials remain HttpOnly
  and server-hashed.
- Server-validated Google identity/link/unlink protections, with the Azure Web
  client configured as an external production application using basic identity.
- JPEG, PNG, WebP, HEIC, and HEIF avatar ingestion with bounded decoding and
  normalized WebP output. Azure avatar storage is still ephemeral.
- Administrative pending/active/disabled lifecycle presentation and mutually
  meaningful platform statistics.
- Calendar-correct Today, Week, Month, Year, and All usage views; deterministic
  Today/Week/Month estimates; previous-month comparison and actionable dashboard
  guidance.
- Owner-scoped archive/deletion, public policy/support pages, performance bounds,
  multi-browser journeys, vulnerability/secret gates, and restore operations.

## Evidence and deployment conditions

See `PRODUCT_V1_G7_VALIDATION_EVIDENCE.md` for exact automated results and the
test-double boundary, and `operations.md` for deploy, backup, recovery, rotation,
and release-handoff steps.

Deployment-specific evidence is recorded in
`../report/evidence/azure_deployment_evidence_2026-08-09.md`. The coordinated
rollback target is the retained `v1-8c519b6` web, API, and email-worker revision
set. Remaining hardening includes durable avatar storage, Azure alert/avatar
workers, centralized monitoring, workload identity, restore evidence, load and
disaster-recovery testing, formal accessibility review, and penetration testing.
No credential belongs in this repository or these release notes.
