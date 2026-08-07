# Azure deployment evidence - 7 August 2026

## Release identity

- Repository: BR1WA/energy-forecast-platform
- Source branch: origin/main
- Deployed Git commit: 00a5592a4e84e0547ba56495ee00b551226f1db9
- Azure subscription: Azure for Students
- Resource group: rg-energyai-pfe
- Deployment region: Italy North

The deployment used an isolated detached worktree at the exact commit above. Existing uncommitted local research and report files were not included in either container image.

## Public endpoints

- Web: https://ca-energyai-web.calmtree-b020e00c.italynorth.azurecontainerapps.io
- API: https://ca-energyai-api.calmtree-b020e00c.italynorth.azurecontainerapps.io

Both endpoints use Azure-managed HTTPS ingress. No custom domain was configured.

## Resource boundary

| Layer | Resource | Configuration |
|---|---|---|
| Frontend | ca-energyai-web | Azure Container App, external ingress, target port 3000, 0.5 vCPU, 1 GiB, minimum 0 and maximum 1 replica |
| Backend | ca-energyai-api | Azure Container App, external ingress, target port 8000, 2 vCPU, 4 GiB, minimum 0 and maximum 1 replica |
| Database | psql-energyai-br1wa-2691 | Azure Database for PostgreSQL 16, Burstable Standard_B1ms, 32 GiB, seven-day backup retention |
| Registry | acrenergyaipfe2691 | Private Azure Container Registry, Basic SKU |
| Secrets | kv-energyai-pfe-2691 | Azure Key Vault containing database, JWT, and administrator secrets |
| Environment | cae-energyai-pfe | Azure Container Apps environment with centralized log destination disabled |

Final resource inventory contained exactly the six resources above. The failed VM path, public IP, NIC, virtual network, network security group, and delayed duplicate PostgreSQL server were removed after dependency checks.

## Image identity

- Backend image digest: sha256:fb092d267b9dc7f871e8d793b5981f169ff9b52896caf301a3e74f3d1526ec00
- Frontend image digest: sha256:d636916a13ca72469bc97c088542f5a64f26a317ccbd10583ea3434020cf4372

The frontend was built with the public API URL embedded. Google authentication was disabled. The backend was configured with production secret validation, both forecasting horizons enabled, email delivery disabled, and the final frontend origin allowed by CORS.

## Final verification

- Frontend root returned HTTP 200.
- /api/v1/system/live returned status=alive.
- /api/v1/system/ready returned ready=true.
- Database readiness returned ready.
- The 24-hour artifact was available, enabled, and warmed.
- The 168-hour artifact was available, enabled, and warmed.
- The 24-hour and 168-hour checkpoint fingerprints remained `60fedcdee375dc0b2973e55b9f4ec752da69c2a7e390e1f951ed5cbb7bc5a04d` and `80af16b25af9b912019c6e40cfdc491e2cf5173e5743144596801e28df695f93`.
- A real administrator login succeeded after bootstrap verification and redirected to /admin.
- The administration page displayed database healthy, forecast runtime ready, and process operational.
- Browser inspection found no console warnings or errors on the final administration view.
- The first observed API cold start was approximately 22 seconds.

The generated administrator credential was rotated before final validation. No credential value is recorded in this evidence file or the report.

## Cost and access controls

- A subscription-level monthly budget of 25 was created for 1 August 2026 through 1 August 2027.
- Notifications are configured at 80% actual spend and 100% forecast spend.
- The budget is an alerting mechanism, not an automatic resource shutdown.
- Temporary owner-IP PostgreSQL firewall rules used for bootstrap corrections were removed.
- The remaining PostgreSQL firewall rule permits Azure-originated services; it does not preserve a developer-IP exception.

## Explicitly unverified or disabled

- Public registration and email verification are disabled because SMTP delivery and the email worker are not configured.
- Password-reset email delivery is disabled.
- Google OAuth is disabled.
- Alert, email, and avatar-cleanup workers are not deployed in Azure.
- Avatar storage is ephemeral in the cloud backend.
- Centralized Log Analytics retention is disabled.
- ACR access uses deployment credentials rather than a managed workload identity.
- No custom domain is configured.
- No backup restoration, load test, disaster-recovery exercise, formal accessibility audit, or penetration test was performed.
- Public deployment does not validate forecast accuracy for Moroccan or other new-site data.

No model was trained, fine-tuned, replaced, or re-evaluated during deployment. No scientific metric was changed.
