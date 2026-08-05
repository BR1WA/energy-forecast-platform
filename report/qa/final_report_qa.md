# Final Report QA — Targeted Finalization Pass

## Build identification

- Output: `report/exports/PFE_ZOUITNI_Salah_Eddine_supervisor_review_v1.pdf` (verified local deliverable; intentionally not versioned in Git).
- Previous draft retained: `report/exports/PFE_ZOUITNI_Salah_Eddine_draft.pdf` was not overwritten.
- Language: professional academic English, with the required French résumé.
- Format: A4, 12 pt, one-sided PDF; 91 pages; 1,669,108 bytes.
- SHA-256: `44394F66214A6805FDD28BB653B5EFF66835DA68F553034E924A081165E2599A`.
- Build date: 1 August 2026.
- Clean build: a fresh source-and-assets copy was compiled with MiKTeX pdfLaTeX, Biber, and the required stabilizing pdfLaTeX passes. The final figure correction was followed by two additional successful pdfLaTeX passes.

## Serving-normalization evaluation decision

The exact inference-only evaluation was possible from preserved local evidence. The original Low Carbon London CSV files were not needed and were not downloaded. No model was trained, fine-tuned, or replaced, and no research metric, checkpoint, or production artifact was overwritten.

The following files under `models/lcl_global_forecasting/full_selected_v1/` supplied the required evidence:

- `data/hourly_raw.npy`: exact hourly values for 2,500 households over 8,760 hourly positions;
- `data/hourly_calendar.npy`: preserved calendar features for the same 8,760 positions;
- `data/households.json`: ordered household identities;
- `data/known_households.npy` and `data/cold_households.npy`: disjoint, complete known/cold-start assignments;
- `data/prepared.json`: shared train, validation, and test boundaries at 6,132, 7,008, and 8,760;
- the frozen 24-origin protocol recoverable from the preserved training worker;
- `runs/global_tft/day_24h/best.pt` and `runs/global_tft/week_168h/best.pt`: frozen checkpoints whose hashes match the packaged backend checkpoints.

These artifacts permit exact reconstruction of the 336-hour histories, future targets, fixed origins, cold-start cohort, calendar inputs, and seasonal-naive targets. There is therefore no missing-artifact blocker for this evaluation.

## Serving-normalization results

The new results use the exact production rolling-history rule implemented by `backend/app/services/product_forecast_service.py::ProductForecastService._predict_tft`: compute the mean and population standard deviation over the latest 336 accepted hourly values, clamp the standard deviation to at least `1e-6`, normalize the history, inverse-transform the quantiles, clamp predictions at zero, and sort q10/q50/q90 independently at every lead time. A vectorized evaluation implementation passed CPU production-method parity checks at both horizons within 0.001 kWh.

| Metric | 24 h serving | 168 h serving |
|---|---:|---:|
| Evaluated households | 500 | 499 |
| Evaluation windows | 11,871 | 11,830 |
| Macro MAE (kWh) | 0.181945 | 0.194138 |
| Median household MAE (kWh) | 0.142769 | 0.150560 |
| p90 household MAE (kWh) | 0.362684 | 0.387758 |
| Macro RMSE (kWh) | 0.322854 | 0.335025 |
| Bias (kWh) | -0.061638 | -0.053130 |
| Macro R² | 0.285221 | 0.244525 |
| Global R² | 0.638839 | 0.581186 |
| Seasonal-naive macro MAE (kWh) | 0.251540 | 0.249055 |
| Households beating seasonal naive | 498/500 (99.60%) | 496/499 (99.40%) |
| q10 pinball loss (kWh) | 0.029440 | 0.031123 |
| q50 pinball loss (kWh) | 0.091103 | 0.096999 |
| q90 pinball loss (kWh) | 0.061746 | 0.066166 |
| Central-80% empirical coverage | 81.011% | 78.056% |
| Mean interval width (kWh) | 0.571945 | 0.598749 |
| Quantile-crossing rate | 0.000% | 0.000% |

The report keeps these results clearly separated from the frozen research-normalization results. The verified research headlines remain unchanged at macro MAE 0.184928 with 495/500 wins for 24 h and macro MAE 0.197322 with 491/499 wins for 168 h.

## Evaluation provenance

- Execution Git commit: `f6679d4b5f759511dcd8bec26745bb894633f66a`; the manifest records that the working tree was dirty because the evaluation script and report revision were uncommitted.
- Environment: Windows 11; Python 3.13.11; NumPy 2.2.6; PyTorch 2.6.0+cu124; CUDA 12.4; NVIDIA GeForce RTX 3070 Laptop GPU; float16 autocast disabled.
- Evaluation script SHA-256: `ffdd74c33a7403e6f3636104efbaf44c558dea6cd5de6fc2204af39e8f81f7f7`.
- Production preprocessing source SHA-256: `312baaf589c5314cdfb747c99002a6203d2f6d9358f46476a12cb8aa1147dae3`.
- Frozen checkpoint SHA-256 values: 24 h `60fedcdee375dc0b2973e55b9f4ec752da69c2a7e390e1f951ed5cbb7bc5a04d`; 168 h `80af16b25af9b912019c6e40cfdc491e2cf5173e5743144596801e28df695f93`.
- Prepared-data hashes, exact origins, CPU/GPU parity checks, inference timings, and output paths are recorded in `report/evidence/lcl_tft_serving_normalization_manifest.json`.
- New evidence outputs: the manifest above, `lcl_tft_serving_normalization_comparison.csv`, `lcl_tft_serving_day_24h_households.csv`, and `lcl_tft_serving_week_168h_households.csv` in `report/evidence/`.

## Targeted report corrections

- Running headers now use one controlled chapter mark; overlapping Chapter 5 and Chapter 6 headers and duplicated list/reference headings are removed.
- The class diagram was re-laid out so relationship names and multiplicities occupy whitespace rather than boxes or attributes.
- URL-style line breaking is restricted to meaningful separators, preventing long notebook, tag, route, CSV, and registry names from breaking character by character.
- “An Recurrent Neural Network” was corrected to “A recurrent neural network.”
- Model-name capitalization was checked and normalized in the touched text.
- The unsupported 9 September 2026 date was removed. The defense date is consistently pending official confirmation; jury information remains unresolved.
- The dedication page is excluded from this supervisor-review build because no dedication text was supplied.
- The public-deployment section remains explicitly incomplete: there is no public URL, ingress, TLS termination, or verified cloud deployment.
- The serving-normalization evidence and comparison table were added without changing the frozen research metrics.

## Compilation and textual QA

- Fatal LaTeX errors: 0.
- Undefined references: 0.
- Undefined citations: 0.
- Bibliography rerun warnings: 0.
- Overfull boxes: 0.
- Duplicate PDF destinations: 0.
- Informational underfull-box warnings: 93; page inspection found no clipping or objectionable spacing.
- Ignored glue-shrink diagnostics from dense tables: 4; all affected tables remain bounded and readable.
- Search results: `TODO` 0; `TBD` 0; malformed `??` references 0; duplicated “Contents Contents” 0; duplicated “References References” 0; “An Recurrent” 0; local Windows/Unix absolute paths 0; repository placeholders 0; `9 September 2026` 0.
- `TO BE CONFIRMED`: exactly 3 intentional administrative markers.

## Visual QA

All 91 pages were rendered at 110 dpi and inspected in ten numbered contact sheets. Original-resolution or higher-resolution checks covered the cover, chapter openings, Chapter 5 research/serving tables, Chapter 5 and 6 running headers, application screenshots, the class diagram, the layered architecture, the rotated full-hash table, references, Docker instructions, and the AI-tool declaration. A persistence-layer text collision found during the first high-resolution pass was corrected, rebuilt, and re-inspected at 160 dpi.

Final verified conditions:

- no accidental blank pages;
- no overlapping or duplicated running headers;
- no cropped or clipped text, figures, tables, captions, or screenshots;
- no relationship labels or multiplicities overlapping class boxes;
- no content outside page margins;
- no broken references or citations;
- no inconsistent defense-date claim;
- long technical identifiers break only at meaningful separators;
- administrative placeholders are visible and confined to the intended fields.

## Remaining administrative placeholders

1. Official defense date.
2. Jury names, grades, institutions, and roles.
3. Exact Faculty/Master-approved AI-tool declaration.

The dedication is not a placeholder in this draft; it has been removed. The report is technically ready for supervisor review but is not an institutionally final submission until the three items above are supplied or confirmed.

## Exact files modified or generated in this pass

- `report/source/evaluate_lcl_serving_normalization.py`
- `report/evidence/lcl_tft_serving_normalization_manifest.json`
- `report/evidence/lcl_tft_serving_normalization_comparison.csv`
- `report/evidence/lcl_tft_serving_day_24h_households.csv`
- `report/evidence/lcl_tft_serving_week_168h_households.csv`
- `report/source/main.tex`
- `report/source/config/preamble.tex`
- `report/source/frontmatter/cover.tex`
- `report/source/chapters/general_introduction.tex`
- `report/source/chapters/chapter1.tex`
- `report/source/chapters/chapter2.tex`
- `report/source/chapters/chapter4.tex`
- `report/source/chapters/chapter5.tex`
- `report/source/chapters/chapter6.tex`
- `report/source/chapters/chapter7.tex`
- `report/source/chapters/general_conclusion.tex`
- `report/source/appendices/appendix_a_traceability.tex`
- `report/source/appendices/appendix_b_research_assets.tex`
- `report/source/generate_figures.py`
- `report/assets/diagrams/class_domain.pdf`
- `report/assets/figures/energyai_layered_architecture.pdf`
- `report/qa/missing_information.md`
- `report/qa/final_report_qa.md`
- `report/exports/PFE_ZOUITNI_Salah_Eddine_supervisor_review_v1.pdf` (local deliverable; excluded from Git)

No commit, push, checkpoint replacement, model training, or external dataset download was performed.
