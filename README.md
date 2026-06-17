# 🏆 DEPM — Critical Analysis, Replication & Commercial SaaS Prediction Platform

> **Master's PFE (End of Studies Project)**: A rigorous replication, critical evaluation, and commercial SaaS-grade dashboard integration of the **Deep Energy Predictor Model (DEPM)** paper.

This project replicates the results of *"Prediction of electricity consumption using an innovative deep energy predictor model"* (Ragupathi et al., Energy Reports 12, 2024), exposes critical methodological flaws (specifically **data leakage** and **anomalous metric patterns**), and embeds the models in a premium full-stack real-time energy analytics SaaS platform.

---

## 📸 Platform Screenshots

### 1. Dashboard Overview & Analytics
![Dashboard Overview](docs/screenshots/dashboard_overview.png)

### 2. Admin Panel & Real-Time Presence Tracking
![Admin Presence Tracking](docs/screenshots/admin_avatars.png)

---

## 🌟 Key Features

### 🔒 Commercial SaaS Plan Gating
* **Feature Gating**: Standard users (Free/Pro plans) have academic ML tools (`/forecast`) hidden unless they have an `analyst` or `admin` role.
* **Premium Dashboard Metrics**: Gated Power Factor ($cos\ \phi$) and Current Draw metrics behind a blur overlay for Free users.
* **AI Forecast Curve Gating**: The dashed AI Forecast Curve on the dashboard charts is locked behind Pro/Enterprise tiers.
* **Enterprise Features**: Heatmap analytics and ReportLab-generated PDF report exports are exclusive to **Enterprise** plan subscribers.

### 🇲🇦 Moroccan Setup Wizard & Localization
* **Regional Preferences**: Country is locked to **Morocco** and currency to **MAD**.
* **Moroccan Utilities**: Built-in utility preset dropdown mapping regional providers (Lydec, Redal, Amendis, RADEEMA, RAMSA, RADEEF, RADEEJ, RADEECO, ONEE) across the 12 administrative regions.
* **Tariff Auto-Presets**: Automatically populates local peak/off-peak rates and schedules (e.g. 18:00 - 23:00 peak hours) dynamically based on the chosen utility.
* **Dynamic PDF Exporter**: Rewrote the PDF generator to fetch active user regional settings, compute exact consumption costs in MAD using Moroccan utility schedule rates, and export customized PDF reports.

### ⚡ Multi-Site Grid Manager (`/multi-site`)
* Exclusive portal for **Enterprise** subscribers.
* Powered by a FastAPI dynamic backend endpoint (`/api/v1/multi-site`).
* Renders real-time aggregate facility load curves, cross-site telemetry grids (Casablanca, Tangier, Marrakech, Agadir), sub-metered circuit telemetries, and simulated battery peak-shaving dispatch controls.

### 🧠 SQL Model Registry & Retraining Engine
* **ModelRegistry DB Table**: Recreated the database schema to store active models,Versions, status, parameters, and training metrics in SQL.
* **Startup Seeding**: Service startup auto-detects empty model registries and seeds configurations for:
  1. **SOTA Hybrid Model** (Recurrent-Attention + RevIN) — Validation $R^2$: `0.8407`
  2. **PatchTST Model** (Transformer-based Patching) — Validation $R^2$: `0.8142`
  3. **CNN-BiLSTM Baseline** — Validation $R^2$: `0.6914`
* **DB-Backed Retraining**: Model retraining triggers PyTorch backpropagation loops and saves live training progress directly to the SQL database.

---

## 🔍 Critical PFE Findings

1. **Data Leakage**: The paper includes `Global_intensity` as an input feature for predicting active power. `Global_intensity` is a mathematical proxy for active power ($P = V \times I$), creating data leakage. Removing it drops performance from ~99% to ~84%.
2. **Fabricated Metrics**: Metric outputs across the paper's tables follow an impossible mathematical pattern: $\text{Precision} = \text{Accuracy} - 0.01$ and $\text{Recall} = \text{Accuracy} + 0.01$, indicating manually typed or simulated metrics.
3. **Replication Proofs**: Our replication notebooks (`notebooks/`) verify the paper's claimed scores under leaked conditions and show the real-world performance drops when leakage is resolved.

---

## 📁 Repository Structure

```text
PFE2/
├── backend/                       # FastAPI Backend API
│   ├── app/
│   │   ├── main.py                # Server entry point, CORS, & startup seeding
│   │   ├── models/                # SQLAlchemy database models (User, ModelRegistry, Settings)
│   │   ├── schemas/               # Pydantic schemas (SystemHealth, UserResponse)
│   │   ├── services/              # Auth, alert_service (custom configurations) & forecast_service
│   │   └── routers/               # Endpoint controllers (auth, admin, settings, multi_site, forecast)
│   └── energy_forecast.db         # SQLite local database
├── frontend/                      # Next.js Frontend App
│   ├── src/
│   │   ├── app/                   # App Router pages (dashboard, profile, admin, settings, multi-site)
│   │   ├── components/            # Layout (Sidebar, Navbar) & UI components (SetupGuard, Error Boundary)
│   │   ├── lib/                   # API client fetching & state synchronization
│   │   └── types/                 # TypeScript interfaces (matching DB models)
├── notebooks/                     # Jupyter Notebooks for PFE evaluation
│   ├── EECP_CBL_Replication.ipynb # Replication of paper dataset
│   └── fair_comparison.ipynb      # Quantitative leakage analysis
└── docs/                          # Project diagrams & screenshots
```

---

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- Docker & Docker Compose (Optional)

### 1. Backend Setup (FastAPI)
```bash
cd backend
# Install dependencies
pip install -r requirements.txt
# Run database migrations and start the development server
python -m uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Setup (Next.js)
```bash
cd frontend
# Install dependencies
npm install
# Start dev server
npm run dev
```

---

## 🧪 Tech Stack

- **Backend**: FastAPI, SQLAlchemy (SQLite/PostgreSQL), PyTorch, ReportLab (PDF), psutil
- **Frontend**: Next.js 14+, React, Tailwind CSS, Recharts, Lucide React
- **Analysis**: Jupyter, pandas, scikit-learn, matplotlib
