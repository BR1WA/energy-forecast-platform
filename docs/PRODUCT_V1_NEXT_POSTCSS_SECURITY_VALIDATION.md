# Product V1 Next.js/PostCSS security validation

## Scope

This focused change addresses the production-only npm audit findings on
`security/next-postcss-upgrade`, based on remote `release/product-v1` commit
`86bf66d607e18c05e7cbdf43be5d8a7189c6db2f`. Email delivery and Google
authentication remained disabled throughout validation:

```text
EMAIL_DELIVERY_ENABLED=false
GOOGLE_AUTH_ENABLED=false
```

## Advisory path and fix

The original production dependency path was:

```text
next@16.2.11 -> postcss@8.5.10
```

The two high-severity advisories were:

- GHSA-6g55-p6wh-862q: arbitrary file read and information disclosure via
  attacker-controlled `sourceMappingURL` in CSS comments.
- GHSA-r28c-9q8g-f849: path traversal in previous source-map auto-loading
  leading to arbitrary `.map` file disclosure.

Both advisories affect PostCSS versions through `8.5.17`. The existing narrow
PostCSS override was updated from `8.5.10` to patched `8.5.23`; the lockfile
updated PostCSS and its required `nanoid` floor from `3.3.12` to `3.3.16`.
Next.js remained on the current `16.2.11` major-compatible release.

## Validation evidence

- `npm audit --omit=dev --audit-level=high`: **passed; 0 vulnerabilities**.
- `npm ci --ignore-scripts --no-audit`: passed using the committed lockfile.
- Frontend lint: passed.
- Frontend TypeScript typecheck: passed.
- Frontend production build: passed.
- Complete Playwright matrix (`--workers=1`): **66 passed** across Chromium,
  Firefox, and WebKit projects.
- Backend suite: **92 passed, 4 skipped**.
- Model-contract tests: **10 passed**.
- Fresh SQLite Alembic upgrade: reached `c8f4a1b2d306`.
- CPU warm-up succeeded for both horizons.
- Runtime checkpoint hashes remained unchanged:

```text
24h:  60fedcdee375dc0b2973e55b9f4ec752da69c2a7e390e1f951ed5cbb7bc5a04d
168h: 80af16b25af9b912019c6e40cfdc491e2cf5173e5743144596801e28df695f93
```

- Fresh backend and frontend Docker images built successfully.
- Docker Compose started PostgreSQL, backend, frontend, and all workers;
  `/health`, `/api/v1/system/live`, `/api/v1/system/ready`,
  `/api/v1/system/health`, and the frontend root each returned HTTP 200.
- `pip-audit -r backend/requirements.txt`: no known vulnerabilities.
- Docker-backed Gitleaks history scan on clean committed checkout `5fa7078`:
  passed; 289 commits scanned, no leaks found.
- Docker-backed Gitleaks clean-directory scan on the same checkout: passed;
  no leaks found.

## Change and push scope

The dependency commit changes only `frontend/package.json` and
`frontend/package-lock.json`. This validation record is the only additional
file permitted for the focused branch. No secrets or environment-file values
were committed. The branch is not merged and is not pushed to `main` or
`release/product-v1`.

```text
Production dependency security validation: PASSED
Email delivery enabled: false
Google authentication enabled: false
```
