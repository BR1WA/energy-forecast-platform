# PFE Audit Remediation Record

**Date:** 16 August 2026

**Scope:** Complete repository audit findings, implementation, and local verification

**Evidence boundary:** Source and local/container validation only unless an Azure result is explicitly identified as the preceding `v4-d25295b` release.

## Implemented remediation

| Area | Implemented change | Verification |
|---|---|---|
| Database integrity | Added the 18th Alembic revision to reject orphan readings and enforce non-null meter ownership; aligned ORM indexes, constraints, and model-registry uniqueness. | Fresh PostgreSQL migration, 146 tests with no skips, and zero Alembic drift. |
| Migration concurrency | Serialized PostgreSQL migrations with an advisory lock. | Fresh database startup and migration checks passed. |
| WebSockets | Replaced socket-lifetime ORM sessions with short-lived sessions and moved blocking ORM work off the event loop. | WebSocket/backend suites passed. |
| Background work | Removed the simulator loop from the API lifecycle and added a dedicated `simulation-worker` service and CLI command. | Seven-service Compose configuration resolves; worker tests passed. |
| Resource controls | Added limits to forecast, simulation, CSV import, PDF/export, and account-export/deletion operations. | Backend route suites passed. |
| HTTP security | Added frontend CSP/HSTS/frame/MIME/referrer/permissions/COOP policy and backend API headers. | API tests and live frontend-container header smoke passed. |
| API exposure | Disabled OpenAPI, Swagger UI, and ReDoc outside debug mode. | Policy assertion included in system tests. |
| Password policy | Raised new, reset, and changed passwords to a consistent 12-character minimum while preserving existing-login compatibility. | Backend auth tests and 36-case six-project auth browser matrix passed. |
| Containers | Added pinned base-image digests, multi-stage builds, non-root UID 10001, compiler-free runtimes, Next.js standalone output, and a private-only PostgreSQL host binding. | Backend and frontend images built; UID/compiler/import/header checks passed. |
| Python supply chain | Added transitive hash locks for runtime, development, CPU Torch, and foundation-model stacks; upgraded vulnerable packages. | Hash-enforced installs, `pip check`, and audits passed. Custom CPU Torch is outside PyPI audit data and remains explicitly identified. |
| JavaScript supply chain | Regenerated the Linux-valid npm lock and retained the safe Sharp override. | Clean Linux `npm ci` and `npm audit` passed with zero known vulnerabilities. |
| Model loading/training | Removed unsafe Torch deserialization fallback, fixed causal window preparation and validation construction, and made optional model dependencies explicit. | Training/backend tests and exact Chronos-2 load/prefetch checks passed. |
| Frontend correctness | Fixed zero-budget handling, durable language preferences, refresh-token typing, i18n subscription behavior, and stale effect-derived state. | ESLint, TypeScript, build, and 204-case browser matrix passed. |
| CI | Pinned actions and service images by digest; added PostgreSQL migration/drift, coverage, hash-install, audit, image-test, secret-scan, and Compose smoke gates. | Workflow syntax/config reviewed; equivalent local gates passed. |
| Repository hygiene | Removed tracked runtime avatars, stale database/output files, duplicate scratch scripts, unused frontend clients, and stale registry tests; added precise ignores and reviewed gitleaks fingerprints. | `git diff --check` clean; 407-commit gitleaks scan found no leaks. |
| Report | Updated topology, security, validation counts, residual boundaries, and QA evidence; generated production v10. | 98 pages, zero fatal/undefined/overfull findings, all pages rendered and visually inspected. |

## Verified final gates

- SQLite backend/training: 142 passed, 4 PostgreSQL-only skips, 82.38% application coverage.
- PostgreSQL backend/training: 146 passed, 0 skipped; 18 migrations; zero schema drift.
- ML-enabled backend container: 117 passed, 4 skipped; non-root; compiler absent.
- Frontend: ESLint, TypeScript, and 25-route production build passed.
- Browser: 204/204 full matrix passed; final auth-policy subset 36/36 passed.
- Dependency audits: zero known npm or auditable Python vulnerabilities.
- Secret scan: 407 commits, no leaks.
- Report: 98 pages, final visual QA passed.

## Residual actions requiring owner authority or external systems

- Supply the official defense date, jury composition, any required
  host/laboratory line, and approved AI-tool disclosure. These are not invented.
- Promote the remediated web/API images and provision the dedicated simulation,
  alert, and avatar-cleanup workers in Azure, then capture new remote evidence.
- Configure durable avatar object storage, centralized logs, restore evidence,
  load/accessibility/penetration tests, and a shared rate-limit backend before
  claiming horizontally scaled production maturity.
- Rewrite the 1.21 GiB historical Git object store only with explicit approval;
  history rewriting can invalidate existing clones and commit references.
