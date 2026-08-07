# Final Report QA — Current-State Azure Update

## Build identification

- Output: `report/exports/PFE_ZOUITNI_Salah_Eddine_supervisor_review_v3.pdf`.
- Previous supervisor-review and draft PDFs are retained and were not overwritten.
- Language: professional academic English, with the required French résumé.
- Format: A4, 12 pt, one-sided PDF; 99 pages; 1,711,157 bytes.
- SHA-256: `DB7DBB7BB9EA69FBE84E916533B99850F19C7B1DF27B6D05354CBDB6210DC37A`.
- Build date: 7 August 2026.
- Build method: clean manual MiKTeX sequence in a fresh output directory using pdfLaTeX, Biber, and stabilizing pdfLaTeX passes. The final URL-layout correction was followed by two successful pdfLaTeX passes.

## Scientific-evidence boundary

No model was trained, fine-tuned, replaced, or downloaded during this update. No frozen research metric, serving-normalization result, checkpoint, prepared artifact, or production model artifact was changed. The report continues to separate the frozen research-normalization results from the inference-only production-normalization re-evaluation.

The exact serving-normalization evaluation remains supported by preserved local evidence under `models/lcl_global_forecasting/full_selected_v1/`; the original Low Carbon London CSV files were neither required nor downloaded. The detailed hashes, origins, environment, parity checks, and result files remain recorded in `report/evidence/lcl_tft_serving_normalization_manifest.json` and the associated CSV evidence files.

## Current Azure deployment evidence

The report now records the controlled public PFE deployment verified on 7 August 2026:

- deployed source: exact `origin/main` commit `00a5592a4e84e0547ba56495ee00b551226f1db9`;
- region and resource group: Italy North, `rg-energyai-pfe`;
- frontend: Azure Container App `ca-energyai-web`, external HTTPS, HTTP 200;
- API: Azure Container App `ca-energyai-api`, external HTTPS, liveness and readiness green;
- models: both frozen 24-hour and 168-hour TFT artifacts reported available, enabled, and warmed;
- persistence: PostgreSQL 16 server ready, 32 GiB storage, seven-day backup retention;
- supporting services: private Azure Container Registry and Azure Key Vault;
- end-to-end smoke test: real administrator authentication succeeded and the role-gated admin page reported database healthy, forecast ready, and process operational with no browser-console warning;
- observed first API cold start: approximately 22 seconds, consistent with the configured zero-to-one replica range.

The evidence registry is `report/evidence/azure_deployment_evidence_2026-08-07.md`. It records public endpoints, container-image digests, resource configuration, smoke-test observations, cost controls, firewall cleanup, and the exact evidence boundary without storing secrets.

## Explicit cloud limitations retained

The report does not claim full production maturity. It states that public registration, verification email, password-reset delivery, Google authentication, cloud background workers, durable avatar storage, centralized Log Analytics retention, custom-domain configuration, and workload-identity registry access are not configured. Backup restoration, load, disaster-recovery, formal accessibility, and penetration tests remain incomplete. The monthly budget is an alerting control, not an automatic shutdown policy.

## Current-state report corrections

- English and French abstracts now distinguish the verified Azure core from incomplete cloud features.
- Chapters 1, 6, and 7 now describe the local Compose profile and the public Azure topology separately.
- Chapter 6 includes the verified Azure resource boundary, public endpoints, health evidence, administrator smoke test, cold-start observation, and deployment limitations.
- Chapter 7 separates the 7 August deployment validation from the frozen scientific evaluation and updates product limitations and operational threats.
- The general conclusion and Appendices A and C now reflect the actual deployed state and remaining hardening work.
- The local Docker wording was clarified so it cannot be read as contradicting the public Azure deployment.
- The two public Azure endpoints are now printed in full as well as embedded as clickable links.
- A deployment-topology figure now separates the public browser path, Container Apps environment, API/database traffic, registry image supply, Key Vault secret supply, and subscription-level budget alerts.
- The budget row now states that 25 is in the subscription billing currency rather than implying an unsupported currency.
- The Docker test row now explicitly directs readers to the separate public-Azure validation result.
- The French abstract now uses formal Azure scale-to-zero terminology instead of the ambiguous phrase “passer à zéro instance.”
- The unsupported 9 September 2026 date remains removed. Defense date, jury information, and the institution-approved AI-tool declaration remain unresolved rather than invented.
- The dedication remains excluded because no dedication text has been supplied.

## Compilation and textual QA

- Fatal LaTeX errors: 0.
- Undefined references: 0.
- Undefined citations: 0.
- Bibliography-rerun warnings: 0.
- Overfull horizontal or vertical boxes: 0.
- Duplicate PDF destinations: 0.
- Informational underfull horizontal boxes: 100; visual inspection found no objectionable spacing or clipping.
- Dense-table glue-shrink diagnostics: 3; all affected tables remain bounded and readable.
- Search results: `TODO` 0; `TBD` 0; malformed `??` references 0; duplicated “Contents Contents” 0; duplicated “References References” 0; “An Recurrent” 0; local Windows/Unix absolute paths 0; stale no-public-deployment claims 0; `9 September 2026` 0.
- `TO BE CONFIRMED`: exactly 3 intentional administrative markers.

## Visual QA

All 99 pages were rendered at 110 dpi and inspected in nine numbered contact sheets. Full-resolution checks covered the printed deployment endpoints, new Azure topology, revised deployment table, deployment-limitations continuation, product-limitations page, and rotated full-hash evidence table.

Verified conditions:

- no accidental blank pages;
- no overlapping or duplicated running headers;
- no cropped or clipped text, figures, tables, captions, or screenshots;
- no class-diagram relationship labels or multiplicities overlapping boxes;
- no content outside page margins;
- no broken references or citations;
- no inconsistent defense-date claim;
- long technical identifiers break only at meaningful separators;
- the landscape evidence table is correctly rotated, bounded, and readable;
- administrative placeholders are visible and limited to their intended fields.

## Remaining administrative placeholders

1. Official defense date.
2. Jury names, grades, institutions, and roles.
3. Exact Faculty/Master-approved AI-tool declaration.

The report is ready for supervisor review as a technically finalized current-state draft. It is not an institutionally final submission until the three administrative items above are confirmed.

## Exact files modified or generated in this update

- `report/source/frontmatter/abstracts.tex`
- `report/source/generate_figures.py`
- `report/assets/diagrams/azure_deployment_topology.pdf`
- `report/source/chapters/chapter1.tex`
- `report/source/chapters/chapter6.tex`
- `report/source/chapters/chapter7.tex`
- `report/source/chapters/general_conclusion.tex`
- `report/source/appendices/appendix_a_traceability.tex`
- `report/source/appendices/appendix_c_technical.tex`
- `report/qa/missing_information.md`
- `report/qa/current_report_text.txt`
- `report/qa/final_report_qa.md`
- `report/evidence/azure_deployment_evidence_2026-08-07.md`
- `report/exports/PFE_ZOUITNI_Salah_Eddine_supervisor_review_v3.pdf`

No push, checkpoint replacement, model training, or external-dataset download was performed.
