# Azure deployment evidence - 15 August 2026

## Evidence boundary

This record documents the in-place promotion of EnergyAI's three-horizon release
to the existing Microsoft Azure deployment in Italy North. The operation did not
reset or recreate PostgreSQL, alter model research metrics, or record any secret
value. Existing data, Key Vault-backed settings, SMTP configuration, and the
previous known-good API revision were preserved.

## Verified source and immutable images

- Source commit: `d25295bdc19816f535e520d9ce434bf0e9a2c1c8`
- Full CI run: [31893388429](https://github.com/BR1WA/energy-forecast-platform/actions/runs/31893388429)
- Remote release-image run: [31894053504](https://github.com/BR1WA/energy-forecast-platform/actions/runs/31894053504)
- Backend repository: `acrenergyaipfe2691.azurecr.io/energyai-backend`
- Backend digest: `sha256:12144be4f7b628d1d3ff3e6c8238f320f19f36171ac13a3f7a324e67950c8d92`
- Frontend repository: `acrenergyaipfe2691.azurecr.io/energyai-frontend`
- Frontend digest: `sha256:253f4be29d5b66adf352bb5c69176767178810e2efa9f8b06c91bad0d54655e4`

The release images were built and pushed by GitHub-hosted runners. This avoided
local PyTorch, browser-engine, and foundation-model downloads while the developer
was on a limited cellular connection. Azure deployments reference the immutable
digests rather than mutable tags.

## Azure resources and active release

- Subscription: Azure for Students
- Resource group: `rg-energyai-pfe`
- Container Apps environment: `cae-energyai-pfe`
- Registry: `acrenergyaipfe2691`, private Basic ACR
- PostgreSQL: `psql-energyai-br1wa-2691`, PostgreSQL 16, Burstable B1ms,
  32 GiB, seven-day backup retention
- Web: `ca-energyai-web--v4-d25295b`, healthy, 100% traffic
- API: `ca-energyai-api--v4-d25295b`, healthy, 100% traffic, one ready replica,
  two vCPU and 4 GiB
- Email worker: `ca-energyai-email-worker--v4-d25295b`, healthy, one ready replica

Public endpoints:

- Web: `https://ca-energyai-web.calmtree-b020e00c.italynorth.azurecontainerapps.io`
- API: `https://ca-energyai-api.calmtree-b020e00c.italynorth.azurecontainerapps.io`

## Quality gates before promotion

GitHub Actions run `31893388429` passed:

- full-history secret scanning;
- migration of an empty PostgreSQL database;
- backend tests, dependency audit, backend image build, and in-image test rerun;
- frontend lint, type checking, production build, dependency audit, and the full
  six-project browser matrix;
- model-enabled Docker Compose startup and core health smoke checks.

The first candidate image built from commit `4fc6165` exposed a future
`transformers` compatibility break while warming Chronos-2. Production traffic
was immediately kept on `ca-energyai-api--v1-6796b1e`. Commit `a9da635` pinned
the compatible runtime and added a production-image import guard; commit
`d25295b` made that guard conditional for intentionally ML-free CI images. The
failed candidate `ca-energyai-api--v3-4fc6165` received no production traffic and
was deactivated after the corrected release passed.

## Model and subsystem readiness

The corrected API revision was first tested through its direct revision hostname
while the prior API still received 100% production traffic. Before cutover, and
again through the normal public API hostname after cutover, `/api/v1/system/ready`
reported:

| Horizon | Release | Available | Enabled | Warmed | Error |
|---|---|---:|---:|---:|---|
| 24 hours | Global TFT 24-hour `1.0.0` | true | true | true | null |
| 168 hours | Global TFT 168-hour `1.0.0` | true | true | true | null |
| 720 hours | Chronos-2 LoRA 30-day daily `3.0.0` | true | true | true | null |

The same readiness response reported PostgreSQL ready, email processing ready,
and zero processing, retry, or dead email-outbox entries. Authentication
capabilities reported email delivery and Google authentication enabled.

## Public smoke results

The following checks passed after the final traffic update:

- web `/`, `/login`, `/register`, `/privacy`, and `/terms`: HTTP 200;
- API liveness, readiness, and authentication capabilities: HTTP 200;
- unauthenticated `/api/v1/alerts` and `/api/v1/alerts/`: HTTP 401;
- web, API, and worker revisions: Azure health state `Healthy`.

No production test account was created. The new-account, 365-day simulator and
all-model readiness flows were exercised by the green browser and backend suites
before promotion.

## Rollback and remaining limitations

The previous API revision `ca-energyai-api--v1-6796b1e` remains active at zero
replicas and zero traffic as the immediate rollback target. The known-failed
candidate was deactivated. Rollback must keep compatible web, API, and worker
revisions together.

This remains a controlled academic deployment, not a claim of universal model
accuracy or complete production hardening. The negative southern-Morocco month
diagnostic remains valid. Hourly Chronos-2 challengers remain inactive. The site
still uses Azure-managed hostnames and registry deployment credentials; durable
avatar storage, centralized log retention, cloud alert/avatar-cleanup workers,
tested restoration, sustained load/provider testing, formal accessibility, and
multi-tenant penetration testing remain outside the verified boundary.
