# Product V1 G7 validation evidence

**Validation scope:** detached clean worktree at `6a298b6`, followed by the focused
WebP response-content-type repair described below.
**Date:** 2026-07-23
**Database:** isolated PostgreSQL 16 containers.
**External capabilities:** SMTP and Google remained disabled unless exercised by a
captured provider or controlled test double.

## Automated results

| Validation | Command or environment | Result |
|---|---|---|
| Empty database migration | `python -m app.cli migrate` | Reached `c8f4a1b2d306` |
| PFE-head migration | `102f8cd` worktree upgraded to `d3a9f6c1b208`, then current worktree `python -m alembic upgrade head` | Reached `c8f4a1b2d306` |
| Backend integration suite | `python -m pytest -q` with isolated PostgreSQL | `96 passed` |
| Auth/mail/Google focused suite | Recovery, outbox, PostgreSQL locking, critical-alert, auth, and Google identity tests | `42 passed` |
| CPU ML contract | ML-enabled Docker test image: `tests/test_model_contract.py` | `10 passed`; both 24h and 168h artifact hash/contract/inference checks ran |
| Frontend dependencies | `npm ci` | Succeeded; npm reported zero vulnerabilities |
| Frontend quality | `npm run lint`, `npm run typecheck`, `npm run build` | Passed; 23 routes generated |
| Browser matrix | `npx playwright test` | `66 passed` across Chromium, Firefox, WebKit, and 360/390/768 px projects |
| Python dependency scan | `python -m pip_audit -r requirements.txt` | No known vulnerabilities |
| npm dependency scan | `npm audit --audit-level=high` | Zero vulnerabilities |
| Secret scan | Gitleaks full committed history | `336 commits`, 127.62 MB, no leaks |
| Clean source audit | Tracked-file allowlist audit | **Failed:** 26 pre-existing tracked CSV data/checkpoint/notebook artifacts remain |
| Compose validation | `docker compose ... config --quiet` and isolated `up --detach` | Passed after replacing disposable port mappings |
| Compose smoke | liveness, readiness, frontend, alert/email/avatar workers | HTTP 200; 24h and 168h artifacts available and warmed |
| Provider outage | Capturing provider failure in the isolated Compose database | committed outbox row moved to `retry`; no business rollback |
| Backup/restore | PostgreSQL custom dump plus avatar tar into isolated targets | user/site/reading/forecast counts, fingerprint, dead outbox status, decoded avatar, SHA-256, and public endpoint all matched |

The disposable Compose override initially appended the base port list, which collided
with the user's running stack. It was corrected with Compose `!override`; no product
configuration was weakened and the final isolated stack used dedicated ports.

## G7 repair

The restored avatar was publicly reachable but the Debian-slim production image
returned `application/octet-stream` for `.webp`. `backend/app/main.py` now
registers `image/webp` explicitly before mounting static avatars. The targeted
account-controls suite passed (`7 passed`), the complete PostgreSQL suite passed
again (`96 passed`), and the restored endpoint returned `200 image/webp`.

## Real-provider boundary

The following evidence is automated or test-double only:

- verification and password-reset mail use the captured provider;
- alert provider outage uses a deterministic failing capture provider;
- Google login/link/unlink uses the controlled credential verifier/test double;
- browser tests mock API responses where a real external identity or mail provider
  would otherwise be required.

The following production prerequisites were unavailable and were deliberately not
claimed as validated: SMTP sender-domain acceptance and inbox delivery, Google OAuth
console/client setup and approved origins, final public API/frontend URLs and cookie
origin policy, durable production backup destination, and production legal owner/
contact/support values. Email and Google remain disabled until those staging checks
are performed by the operator.

## Defects and release status

No P0 defect remains from automated G7 validation. The WebP MIME response issue was
repaired and regression-tested. A P1 release-hygiene blocker remains: the required
clean-source audit found pre-existing tracked raw data, checkpoints, and notebooks/
output notebooks. They were not modified because they are outside Product V1 scope
and the validation instruction requires preserving unrelated files. Product V1 is
therefore **not releasable** until an approved repository-hygiene change removes or
relocates those artifacts, followed by a fresh G7 audit. Real-provider prerequisites
above remain additional operator-owned release blockers.
