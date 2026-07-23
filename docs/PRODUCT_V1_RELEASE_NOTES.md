# Product V1 release notes

## Release status

Product V1 completed functional automated validation from a clean detached worktree,
including PostgreSQL migrations, backend integration, CPU inference for both fixed
forecast horizons, frontend/browser coverage, Compose workers, dependency and secret
scans, and isolated backup/restore. No P0 or P1 software defect is open.

This is **not a releasable production candidate**. The final clean-source audit found
pre-existing tracked raw data, checkpoint files, and notebooks/output notebooks. That
is a P1 release-hygiene blocker and was preserved rather than removed because it is
outside the authorized Product V1 scope. SMTP/provider, Google OAuth, final public
URL/cookie-origin, legal identity, and durable backup-destination acceptance must
also be completed in staging before enabling those capabilities.

## Included Product V1 capabilities

- Truthful 24-hour forecast plus runtime-gated 168-hour Global TFT forecast with
  artifact integrity, provenance, fallback disclosure, and reports.
- Transactional multipart email outbox with PostgreSQL safe claiming, retries,
  dead-letter handling, and critical-alert opt-in.
- Email verification and secure password reset; refresh credentials remain HttpOnly
  and server-hashed.
- Server-validated Google identity/link/unlink protections, disabled until operator
  configuration is complete.
- Durable normalized WebP avatars, including correct `image/webp` public serving in
  minimal production containers.
- Owner-scoped archive/deletion, public policy/support pages, performance bounds,
  multi-browser journeys, vulnerability/secret gates, and restore operations.

## Evidence and deployment conditions

See `PRODUCT_V1_G7_VALIDATION_EVIDENCE.md` for exact automated results and the
test-double boundary, and `operations.md` for deploy, backup, recovery, rotation,
and release-handoff steps.

Before production enablement, first complete an approved repository-hygiene change
and rerun G7, then supply and test real legal identity, public origins, SMTP sender/
provider, Google OAuth configuration, and durable backup location. Keep
`EMAIL_DELIVERY_ENABLED=false` and `GOOGLE_AUTH_ENABLED=false` until those controlled
staging checks pass. No credential belongs in this repository or these release notes.
