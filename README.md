# DEPM — Critical Analysis & Replication

> Master's PFE project: Replicating and critically evaluating the **Deep Energy Predictor Model (DEPM)** paper.

## Objective

Reproduce the results from *"Prediction of electricity consumption using an innovative deep energy predictor model"* (Ragupathi et al., Energy Reports 12, 2024) and identify methodological flaws including **data leakage** and **suspicious metric patterns**.

## Project Structure

```
PFE2/
├── app/                          # FastAPI prediction dashboard
│   ├── main.py                   # Backend API
│   ├── models.py                 # PyTorch model definitions
│   └── static/index.html         # Dashboard UI
├── data/
│   ├── household_power_consumption.txt  # UCI dataset (not tracked)
│   └── steel_industry_energy.csv        # UCI Steel dataset
├── models/                       # Trained model weights (not tracked)
├── notebooks/
│   ├── depm_proposed.ipynb       # Initial DEPM implementation
│   ├── fair_comparison.ipynb     # Data leakage investigation
│   ├── depm_final.ipynb          # Full paper replication (with leakage)
│   ├── depm_final_noleak.ipynb   # Full replication (leakage removed)
│   ├── depm-variants.ipynb       # 10 model variants (Kaggle)
│   └── depm-on-steel-*.ipynb     # Cross-dataset validation (Kaggle)
├── extracted_paper.txt           # Paper text for reference
└── presentation_plan.md          # Defense presentation outline
```

## Key Findings

1. **Data Leakage**: The paper includes `Global_intensity` as a feature, which is a direct mathematical proxy for the target (`P = V × I`).
2. **Fabricated Metrics**: All 40+ rows across 6 tables follow an impossible pattern: `Precision = Accuracy - 0.01`, `Recall = Accuracy + 0.01`.
3. **Real Performance**: Without leakage, accuracy drops from ~99% to ~89%, consistent across DEPM variants.

## Models

- **Standalone**: DNN, LSTM, BiLSTM, GRU, BiGRU
- **DEPM Hybrid**: Each DL model + XGBoost (paper's proposed architecture)
- **Architecture**: Cascaded ResNet → PCA → DL → XGBoost

## Tech Stack

- PyTorch, XGBoost, scikit-learn, FastAPI
- Trained on Kaggle (GPU)
