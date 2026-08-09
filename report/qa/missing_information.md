# Missing and Unconfirmed Information

This file lists information that could not be established from the repository or verified institutional material and was therefore not invented. Only information that directly affects the submitted document is visibly marked in red.

## Institutional and administrative information

- Official Master PFE cover template applicable to SDIA. The public Faculty of Sciences cover model found during the institutional search is for doctoral theses; its official logo and visual motif were adapted without claiming that its doctoral wording governs a Master PFE.
- Supervisor laboratory affiliation, if required. Current faculty material supports the title `Pr.`, the name Ali Oubelkacem, and the Department of Computer Science affiliation.
- Host organization, if the PFE was conducted with an external organization.
- Official defense date. The earlier tentative 9 September 2026 value was removed because no official evidence is preserved locally.
- Jury members, grades, institutions, and roles.
- Official FS-UMI rules for citation style, margins, font, line spacing, binding, cover wording, and front-matter order for this Master programme.
- Exact institution-approved wording for the AI-tool usage declaration.
- Final personal dedication text.

## Scientific and documentary gaps

- No successful frozen metric artifact was found for TimePro.
- No successful frozen metric artifact was found for TimeMixer++.
- The exploratory TSMixer work has no frozen successful metric artifact.
- MultiCycleNet is represented by local experimental results; exact reproduction of a named published implementation is not claimed.
- The serving-normalization comparison validates the scaler and inverse-transform change on the exact frozen LCL cohort only. Site-specific calibration, conformal recalibration, time-zone transfer, and Moroccan household transfer remain unvalidated.
- Code-coverage evidence was not found and is not claimed.

## Deployment and operational gaps

- The Azure jury release is verified through public HTTPS web/API endpoints, managed PostgreSQL, a private registry, Key Vault secrets, model-readiness checks, email-worker health, and responsive browser smoke tests.
- Public email registration, verification delivery, SMTP capability, and a production Google Web identity origin are enabled and smoke-tested. Sustained provider delivery and recovery behavior have not been load-tested.
- Alert and avatar-cleanup workers are not deployed in Azure; uploaded avatars are not durably persisted.
- The deployment uses Azure-generated hostnames, registry credentials rather than workload identity, and no centralized Log Analytics retention.
- Backup retention is configured, but restoration, load testing, disaster recovery, formal accessibility testing, and multi-tenant penetration testing remain outside the verified evidence.

## Decisions requested before final submission

1. Confirm the final English title or provide the institutionally approved wording.
2. Supply the jury composition, any required host/laboratory information, and final defense-date confirmation.
3. Confirm the FS-UMI Master PFE cover and formatting rules.
4. Approve the neutral wording of the DEPM methodological audit.
5. Approve or replace the draft AI-tool declaration.
6. Decide whether interval recalibration or a Moroccan pilot study must be completed before defense.
7. Decide whether a custom domain, durable avatar storage, and the remaining Azure workers are required before the defense.
