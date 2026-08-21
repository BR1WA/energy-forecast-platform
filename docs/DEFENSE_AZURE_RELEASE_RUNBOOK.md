# Defense Azure release runbook

This runbook is a release procedure, not an approval to modify Azure. It applies only after a tested commit has passed GitHub CI and an operator has supplied the existing application and registry secrets through a secure channel.

1. Build immutable backend and frontend images with the `Build Azure Release Images` workflow, using the exact green commit SHA.
2. Deploy the API and web revisions from those image digests. Set the defense-window scale floor to one replica and the ceiling to one replica for each; this avoids cold starts without adding a parallel scaling design.
3. Use `scripts/prepare_azure_defense_workers.ps1` with the immutable backend image, a release suffix, `-Apply`, and the existing secrets. It updates the existing email worker to that backend image and creates/updates one always-on simulation worker and one always-on alert worker. The script does nothing unless `-Apply` is present.
4. Do not deploy the avatar-cleanup worker to Azure yet. The deployed avatar storage is local to a container app; the Compose named volume is not shared across Azure apps. A separate cleanup worker would therefore not reliably see API-created files. First move avatars to shared durable object storage, then deploy this existing worker pattern.
5. Confirm all five desired apps use the intended image digest/revision: web, API, email worker, simulation worker, and alert worker. Confirm the workers have no ingress and have `minReplicas=1`, `maxReplicas=1`.
6. Check `/api/v1/system/ready` and `/api/v1/system/health`. `workers.simulation`, `workers.alerts`, and `workers.email` must be `operational`; the response includes last successful loop time and the staleness threshold.

## Jury smoke journey

Sign in, then visit Dashboard, Usage, Demo simulator, the 24-hour forecast, 168-hour forecast, 30-day forecast, and Actions. Confirm the simulator worker advances a deliberately started session, all forecast windows show actual start/end dates and are not expired, the input-history coverage/provenance/model evidence and quantile interval are visible, and Actions reports missing-data and email capability accurately. Generate fresh forecasts from current meter history immediately before the defense; never alter historic timestamps or data to make an old forecast appear current.
