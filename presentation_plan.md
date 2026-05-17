# PFE2 Progress Presentation Plan

> **Title:** Replication & Critical Analysis of the Deep Energy Predictor Model (DEPM)
>
> **Context:** PFE2 builds on PFE1 (initial implementation). Everything below is **new work**.

---

## Slide 1 — Recap: Where PFE1 Left Off (2 min)

**Talking points:**
- PFE1: Implemented the DEPM architecture from the paper (Cascaded ResNet + DNN + XGBoost)
- Dataset: UCI Household Electric Power Consumption (2M+ rows, 47 months)
- Achieved initial results but noticed discrepancies with the paper's reported metrics
- **PFE2 goal:** Investigate why, validate properly, extend the architecture

---

## Slide 2 — Discovery: Data Leakage Problem (3 min)

**Key finding:** The paper's methodology has a critical flaw — **data leakage**

**What is it:**
- Target: `Global_active_power` (High vs Low, median split)
- Feature included: `Global_intensity`
- Physics: `P = V × I` → `Global_active_power = Voltage × Global_intensity / 1000`
- **The model is just learning arithmetic, not energy patterns**

**Evidence:**
- Simple models (Logistic Regression) achieve **99.4% accuracy** with leakage
- This is higher than the paper's complex DEPM at 98%

**Show:** Side-by-side results table — simple models vs paper claims

---

## Slide 3 — Data Preprocessing & Feature Engineering (3 min)

**Supervisor Request: Engineered Features Details**

To give the model more context beyond raw sensor readings, we implemented robust feature engineering (without introducing leakage).

**Key Formulas & Transformations:**
1. **Sub-Metering Aggregation:**
   - `SubTotal = Sub_metering_1 + Sub_metering_2 + Sub_metering_3`
2. **Sub-Metering Ratios (Proportional Usage):**
   - `SubRatio_1 = Sub_metering_1 / (SubTotal + 1)`
   - *(Same for SubRatio_2 and SubRatio_3)*
3. **Temporal Features:**
   - Extracted `Hour` (0-23), `DayOfWeek` (0-6), `Month` (1-12)
   - `Season = (Month % 12 // 3) + 1`
   - `IsWeekend = 1 if DayOfWeek >= 5 else 0`
   - `IsHoliday = 1 if Date is a public holiday else 0`

**Dimensionality Reduction:**
- Features scaled using `StandardScaler`
- `PCA (Principal Component Analysis)` applied to reduce feature dimensionality while retaining 95% of variance (reduced to 10 components).

**Show:** A snippet of the feature engineering pipeline/dataframe.

---

## Slide 4 — Paper Credibility Analysis (3 min)

**Suspicious patterns in the paper's Tables 1-6:**

| Every row in all 6 tables follows: |
|---|
| `Precision = Accuracy - 0.01` |
| `Recall = Accuracy + 0.01` |
| `F1-Score = Accuracy` |

**This is statistically impossible** — 40+ rows, all with identical pattern.

**Additional critical red flags:**
1. **The 54-Sample Confusion Matrix:** The paper claims to test on a 2M+ row dataset, but their Figure 14 confusion matrix sums to exactly 54 samples (26+1+1+26). This indicates fabricated or grossly mismanaged evaluation.
2. **Plagiarized Text (Paper-Mill signs):**
   - Page 12: Mentions predicting *"diagnosis values"* (copy-pasted from a medical paper).
   - Page 10: Justifies ResNet for *"image histogram data"* (copy-pasted from a computer vision paper).
3. **Problem Framing Mismatch:** Grid operators need continuous predictions (regression). Converting this to a simple binary "High/Low" classification task is practically useless for real-world energy forecasting.
4. **No code provided** ("Code availability: Not applicable")

**Show:** Pattern analysis output, screenshot of the 54-sample confusion matrix, and highlighted plagiarized text.

---

## Slide 5 — Full Replication: With vs Without Leakage (4 min)

**Two notebooks created:**

| Notebook | Leakage | Features | Accuracy |
|---|---|---|---|
| `depm_final.ipynb` | ✅ Yes (paper's method) | ~40+ incl. `Global_intensity` | ~95-99% |
| `depm_final_noleak.ipynb` | ❌ Removed | ~15 clean features | ~85-93% |

**Both replicate ALL 6 paper experiments:**
- Table 1: 9 activation functions
- Table 2: Hyperparameter tuning (layers, neurons, optimizer)
- Table 3: 11 model comparison (LR → DEPM)
- Table 4: 9 optimizers
- Table 5: 10 XGBoost learning rates
- Table 6: 8 DNN batch sizes

**Show:** Comparison bar charts, confusion matrices, ROC curves

---

## Slide 6 — DEPM Architecture Variants (4 min)

**Extended the paper's architecture** by replacing DNN with other DL models:

| Standalone | DEPM Hybrid (DL + XGBoost) |
|---|---|
| DNN | DEPM-DNN (paper's proposed) |
| LSTM | DEPM-LSTM |
| BiLSTM | DEPM-BiLSTM |
| GRU | DEPM-GRU |
| BiGRU | DEPM-BiGRU |

**Total: 10 models trained and compared**

**Key question answered:** Does the DEPM hybrid (adding XGBoost) actually improve over standalone DL models?

**Show:**
- Paired comparison chart (Standalone vs DEPM for each architecture)
- 10 confusion matrices
- ROC curves (standalone panel + DEPM panel)
- Full metrics table

---

## Slide 7 — Cross-Dataset Validation (3 min)

**The paper only tested on ONE dataset.** We tested on a second:

| | Household Power | Steel Industry |
|---|---|---|
| **Source** | UCI | UCI (#851) |
| **Samples** | 2M+ (minute-level) | 35,040 |
| **Domain** | Residential | Industrial |
| **Target** | GAP median split | Load type (Light vs Med+Max) |

**Same DEPM pipeline applied:**
- Median imputation → IQR → Feature engineering → PCA → ResNet → DNN + XGBoost
- Compared against baselines (LR, RF, XGBoost)

**Show:** Steel industry results table, confusion matrices, ROC curves

**Key finding:** DEPM generalizes to different energy domains

---

## Slide 8 — FastAPI Prediction Dashboard (2 min)

**Built a production-ready web application:**

**Features:**
- Model selector: Choose from all 10 trained models
- Custom Input mode: Enter all features manually
- Quick Hour mode: Slider to select hour → instant prediction
- Daily Profile mode: 24-hour consumption prediction visualization
- Stats Dashboard: Interactive charts comparing all models
- Detailed metrics table with accuracy, precision, recall, F1, AUC

**Tech stack:** FastAPI + PyTorch + XGBoost + Chart.js

**Show:** Live demo or screenshots of the dashboard

---

## Slide 9 — Conclusions & Future Work (2 min)

### What PFE2 Adds Over PFE1:

1. **Critical Analysis** — Identified data leakage, impossible metrics (54 samples), and plagiarized text in the paper.
2. **Rigorous Replication** — Full reproduction of all 6 experiments (with and without leakage).
3. **Architecture Extension** — 5 new DL variants (LSTM, BiLSTM, GRU, BiGRU) × 2 modes (standalone + DEPM).
4. **Cross-Dataset Validation** — Tested on Steel Industry dataset (paper only used one).
5. **Deployment** — FastAPI dashboard for real-time prediction with all models.
6. **Reproducibility** — All code open, documented, and runnable on Kaggle.

### Key Takeaway:

> *The DEPM paper's classification results are not reproducible as reported due to data leakage and fabricated metrics. A proper approach requires framing this as a Time-Series Regression problem to forecast continuous power usage.*

### Future Work:
- Implementing Short-Term Load Forecasting (STLF) using **Regression** (LSTM / XGBoost Regressor) with strict chronological splitting and evaluating via MAE, RMSE, and MAPE.

---

## File Inventory (What to Prepare)

| File | Purpose | Show During |
|---|---|---|
| `notebooks/depm_final.ipynb` | Full replication WITH leakage | Slide 5 |
| `notebooks/depm_final_noleak.ipynb` | Full replication WITHOUT leakage | Slide 5 |
| `notebooks/depm_variants_train.ipynb` | 10 model variants training | Slide 6 |
| `notebooks/depm_steel_industry.ipynb` | Cross-dataset validation | Slide 7 |
| `notebooks/fair_comparison.ipynb` | Initial leak investigation | Slide 2 |
| `app/` | FastAPI dashboard | Slide 8 |

---

## Timing

| Slide | Topic | Duration |
|---|---|---|
| 1 | Recap | 2 min |
| 2 | Data Leakage | 3 min |
| 3 | Preprocessing & Features | 3 min |
| 4 | Paper Credibility | 3 min |
| 5 | Full Replication | 4 min |
| 6 | Architecture Variants | 4 min |
| 7 | Cross-Dataset | 3 min |
| 8 | FastAPI Demo | 2 min |
| 9 | Conclusions | 2 min |
| | **Total** | **~26 min** |
