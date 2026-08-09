# Azure deployment evidence — 9 August 2026

## Evidence boundary

This record documents an in-place, non-destructive update of the existing
EnergyAI PFE deployment in Azure Italy North. No database was reset or recreated,
no migration was added or run, no model was trained or replaced, and no secret
value is recorded here. The deployment preserves the existing PostgreSQL data,
Key Vault-backed settings, SMTP configuration, model checkpoints, and inactive
Container Apps revisions.

## Source and images

- Deployed Git commit: `af467989694322ef76a5402a367893ea01f5e1dd`
- Remote branch at deployment: `origin/main`
- Backend image: `acrenergyaipfe2691.azurecr.io/energyai-backend:af46798`
- Backend image-list digest: `sha256:b90e1d9a1939546a85318f959d52d4188adfeafb303b3e2a373c2e9009ac871b`
- Frontend image: `acrenergyaipfe2691.azurecr.io/energyai-frontend:af46798`
- Frontend image-list digest: `sha256:085ca6ef85c7170da811c385d3a9647f3561a875724ebb96f8c5cb9d5612ce68`

The backend digest is shared with tag `1e4d004` because commit `af46798` changes
only the frontend lockfile required for reproducible `npm ci` inside the Node 20
Docker image. The frontend image was built with the public Azure API URL and the
public Google Web client ID. No Google client secret is required by EnergyAI or
stored in Azure.

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

After deployment, the active and healthy revisions are:

- API: `ca-energyai-api--v1-af46798`
- Web: `ca-energyai-web--v1-af46798`
- Email worker: `ca-energyai-email-worker--v1-af46798`

The three `v1-8c519b6` revisions remain inactive, healthy, and available as the
exact coordinated rollback target. Earlier inactive revisions were also retained.

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

Automated release evidence immediately preceding deployment comprised 106 passing
backend tests with four explicit PostgreSQL-only skips in the local SQLite profile,
180/180 Playwright tests across six desktop/responsive browser projects, successful
ESLint, TypeScript, and 25-route production compilation, populated 167-hour and
169-hour DST projection tests, and zero known vulnerabilities in the production
npm and Python dependency audits. The historical isolated-PostgreSQL result remains
100 passed and zero skipped; it was not rerun during this deployment.

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
