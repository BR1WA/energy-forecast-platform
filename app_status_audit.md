# Application Status Audit

**Audit date:** 7 August 2026

**Release commit:** `732812fd2d374502961fe6df759aeb32433abd81`

**Overall status:** Operational PFE release with verified Azure hosting

## Release state

The application is available on Microsoft Azure in the Italy North region:

- Web application: <https://ca-energyai-web.calmtree-b020e00c.italynorth.azurecontainerapps.io>
- API: <https://ca-energyai-api.calmtree-b020e00c.italynorth.azurecontainerapps.io>
- Frontend revision: `ca-energyai-web--v1-732812f`
- API revision: `ca-energyai-api--v1-email`
- Email-worker revision: `ca-energyai-email-worker--v1-email`

The deployed web image is pinned to digest
`sha256:e97d4ee0244bbbfd0bef949ace93f5b3a8c401182ef6ad4ab5a832d6ea8cc3c3`.
The API and email worker use the frozen backend image
`sha256:fb092d267b9dc7f871e8d793b5981f169ff9b52896caf301a3e74f3d1526ec00`.

## Verified capabilities

| Capability | Status | Evidence |
| --- | --- | --- |
| Next.js web application | Ready | Public login and registration pages return HTTP 200 |
| FastAPI service | Ready | `/api/v1/system/ready` returns `ready: true` |
| PostgreSQL | Ready | Readiness probe reports `database.status: ready` |
| 24-hour forecasting | Ready | Frozen Global TFT artifact is available and warmed |
| 168-hour forecasting | Ready | Frozen Global TFT artifact is available and warmed |
| Public registration | Enabled | Authentication capability reports `email_delivery_enabled: true` |
| Verification email | Ready | Gmail SMTP TLS authentication succeeded; worker has one healthy replica |
| Google authentication | Disabled | No production Google OAuth configuration is advertised |

Public registration requires email verification before the first login. The
SMTP password is stored as an Azure secret and is not committed to this
repository. The worker has no public ingress.

## Consumption-chart release

The current frontend release replaces the earlier consumption curve with a
time-aware power and energy visualization. It preserves real timestamp spacing,
shows missing intervals as gaps, supports power/energy modes, displays observed
min-max ranges, and provides timezone, coverage, sample-count, average, and peak
context.

Validation completed for this release:

- TypeScript type checking passed.
- ESLint passed without warnings.
- The production Next.js image built successfully with all 25 routes.
- The focused consumption-chart test passed on six targets: Chromium, Firefox,
  and WebKit across desktop and mobile viewports.
- The deployed desktop and 390-pixel layouts have no horizontal overflow.
- The live browser review produced no console errors.

## Local development services

The Docker Compose environment contains PostgreSQL, FastAPI, Next.js, the alert
worker, email worker, and avatar-cleanup worker. At the time of this audit the
database, backend, and frontend containers were healthy and all three workers
were running.

## Deliberate limitations

- The public cloud account initially has no configured site or meter readings;
  it therefore presents an honest empty state until setup/import is completed.
- Email delivery depends on the configured Gmail SMTP account.
- Google OAuth remains disabled.
- Avatar storage remains ephemeral in the current Container Apps deployment.
- Local report renders and third-party paper PDFs remain outside version control.
- Scientific metrics and frozen checkpoints were not changed by the UI or cloud
  deployment work.

## Repository state

The release source is tracked on `main`. Research leaderboards, manifests,
training workers, notebooks, report plans, and CSV-builder utilities are retained
as reproducibility and project-history artifacts. Large datasets, checkpoints,
generated report renders, secrets, and third-party PDFs remain excluded.
