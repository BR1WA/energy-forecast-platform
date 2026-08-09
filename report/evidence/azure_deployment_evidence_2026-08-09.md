# Azure deployment evidence — 9 August 2026

## Evidence boundary

This record documents the in-place, non-destructive updates of the existing
EnergyAI PFE deployment in Azure Italy North through commit `6796b1e`. No
database was reset or recreated, no schema migration was required, no model was
trained or replaced, and no secret value is recorded here. The deployments
preserved existing PostgreSQL data, Key Vault-backed settings, SMTP
configuration, model checkpoints, and inactive Container Apps revisions.

## Source and images

- Verified remote head: `6796b1ec7360f9c05cb804fbd8be29ba1ea78ef8`
- Frontend source commit: `f807316`
- Frontend image digest:
  `sha256:6f136232457e877611b98b59c32440eaa5f141b120026fc604adafb41022d5a1`
- Backend and email-worker source commit: `6796b1e`
- Backend image digest:
  `sha256:44bc79966e03a04d906895047fb189d3bfb12617544dcc59cfbd83f66cf8f299`

The frontend image was built with the public Azure API URL and the public Google
Web client ID. No Google client secret is required by EnergyAI or stored in
Azure. The backend image continues to contain the same frozen forecast
artifacts; the current changes affect simulator continuity and bounded account
deletion rather than model weights or manifests.

## Azure resources

- Subscription: Azure for Students
- Resource group: `rg-energyai-pfe`
- Container Apps environment: `cae-energyai-pfe`
- Web app: `ca-energyai-web`
- API app: `ca-energyai-api`
- Email worker: `ca-energyai-email-worker`
- PostgreSQL: `psql-energyai-br1wa-2691`, PostgreSQL 16, Standard B1ms,
  32 GiB, seven-day backup retention
- Registry: `acrenergyaipfe2691`
- Key Vault: `kv-energyai-pfe-2691`

## Revisions

Before deployment, the active revisions were:

- API: `ca-energyai-api--v1-8c519b6`
- Web: `ca-energyai-web--v1-8c519b6`
- Email worker: `ca-energyai-email-worker--v1-8c519b6`

After the latest deployments, the active and healthy revisions are:

- Web: `ca-energyai-web--v1-f807316`, 100% traffic
- API: `ca-energyai-api--v1-6796b1e`, 100% traffic
- Email worker: `ca-energyai-email-worker--v1-6796b1e`, one ready replica

The web revision contains the communicative dashboard and confirmed
simulator-to-CSV handoff. The API and worker revision contains deterministic
persistent simulation and bounded permanent account deletion. Older revisions
remain inactive. A rollback must select compatible web and API revisions rather
than assume that one historical suffix applies to all components.

## Google identity configuration

- Google Cloud project name: `EnergyAI PFE`
- Google Cloud project ID: `energyai-pfe`
- Google Cloud project number: `693762459304`
- OAuth application: external, publishing status `In production`
- Web client name: `EnergyAI Azure Web`
- Authorized JavaScript origin:
  `https://ca-energyai-web.calmtree-b020e00c.italynorth.azurecontainerapps.io`
- Branding links: deployed homepage, `/privacy`, and `/terms`
- Scopes used by the application: basic Google identity only

The live Register page rendered `Continue with Google`, and invoking it opened
Google's account chooser for the Azure domain. The chooser was closed without
selecting an account, so this smoke test created no production user.

## Health and capability observations

- Public web `/`, `/login`, `/register`, `/privacy`, and `/terms`: HTTP 200
- API liveness: `status=alive`
- API readiness: `ready=true`
- PostgreSQL connectivity: `status=ready`
- 24-hour artifact: available, enabled, warmed
- 168-hour artifact: available, enabled, warmed
- Email subsystem: enabled and ready; outbox processing/retry/dead counts were zero
- Email worker: one running healthy replica
- Auth capability response: email delivery enabled and Google auth enabled
- Alerts canonical and trailing-slash requests: HTTP 401 when unauthenticated,
  with no HTTP downgrade redirect
- Desktop Register page: no horizontal overflow; Google control present
- 390 x 844 mobile Register page: no horizontal overflow; Google control visible
- Persistent simulation: an empty meter receives 2,881 labelled readings spanning
  30 days at 15-minute cadence; running sessions catch up forward after API sleep
  with idempotent timestamps and a 5,000-point hard limit
- Data integrity: CSV, push, pre-existing, and deliberately stopped gaps are not
  backfilled; reset replaces simulator-owned rows only
- CSV handoff: preview remains available, confirmation stops a running simulator
  before import, cancellation writes nothing, and historical simulation rows are
  preserved
- Account deletion: the API uses ordered set-based removal of the complete owned
  graph and preserves only an anonymized deletion audit event

The latest local suite comprised 112 passing backend tests with four explicit
PostgreSQL-only skips. A focused PostgreSQL test deleted an account after a full
2,881-point simulator bootstrap in 0.272 seconds. The six-project Playwright
inventory now contains 192 tests, including the dashboard narrative, simulator
reset/status, and simulator-to-CSV handoff. GitHub Actions run
`31328212332` passed frontend lint, TypeScript, production build, and the complete
browser matrix; backend migration, tests, dependency audit, image build, and
containerized rerun; full-history secret scanning; and Docker Compose smoke
testing. The historical isolated-PostgreSQL result remains 100 passed and zero
skipped and is retained as a separate earlier audit.

## Preserved limitations

This remains a controlled public PFE deployment, not a claim of complete production
maturity. Azure alert and avatar-cleanup workers are not deployed. Uploaded avatars
are not backed by durable object storage. The site uses Azure-generated hostnames,
registry credentials rather than workload identity, and no centralized Log
Analytics retention. Backup restoration, load, disaster-recovery, formal
accessibility, and multi-tenant penetration tests remain incomplete. The annual and
All-history views intentionally do not extrapolate deterministic end-of-period
costs, and model efficacy is not established for Moroccan sites.

## Deployment warning

ACR Tasks refused a remote build because Tasks operations are unavailable for this
student registry. The images were therefore built deterministically with local
Docker from the clean release commit, pushed to the existing private registry, and
deployed by immutable digest. This did not require an architecture change.
