# Master's PFE Expansion: Third Model + Full-Stack Energy Management Platform

This plan covers two major workstreams:
1. **Add a third SOTA model (PatchTST)** — a fundamentally different architecture to strengthen the comparative analysis
2. **Expand into a full Master's-grade project** — production web app, UML, authentication, security, containerization

---

## Part 1: Third SOTA Model — PatchTST

### Research Summary

The model research evaluated **8 candidate architectures** from top venues (ICLR, NeurIPS, AAAI, TMLR). Here are the top 3:

| Rank | Model | Venue | Architecture Type | Key Differentiator |
|:---|:---|:---|:---|:---|
| 🥇 | **PatchTST** | ICLR 2023 | Pure Transformer | Channel-independent patching, no RNN |
| 🥈 | **iTransformer** | ICLR 2024 Spotlight | Inverted Transformer | Variates-as-tokens, cross-variable attention |
| 🥉 | **TimesNet** | ICLR 2023 | 2D CNN (Inception) | FFT periodicity → reshape to 2D → vision CNN |

### Why PatchTST?

> [!IMPORTANT]
> **PatchTST creates a clean 3-way architectural comparison for your thesis:**
> | Model | Architecture Family | Temporal Backbone | Variable Strategy |
> |:---|:---|:---|:---|
> | **CNN-BiLSTM** | Convolutional + Recurrent | BiLSTM | Channel-Mixed |
> | **Our SOTA** | Hybrid Recurrent-Attention | BiGRU + Transformer | CI + Cross-Variable Attention |
> | **PatchTST** | Pure Transformer | Self-Attention only | Channel-Independent |
>
> This gives you **three fundamentally different paradigms** to compare — exactly what a thesis committee wants to see.

**Key facts:**
- **2000+ citations** since ICLR 2023 — one of the most influential recent time-series papers
- **Official code:** [github.com/yuqinie98/PatchTST](https://github.com/yuqinie98/PatchTST) (MIT license)
- **Best ECL benchmark:** MSE 0.130 / MAE 0.223 at horizon 96 (electricity dataset)
- **No recurrent components** — pure attention, architecturally distinct from our SOTA

### IHEPC-Specific Benchmark Context

The research found published IHEPC benchmarks:

| Model | MAE (kW) | RMSE (kW) | Source |
|:---|:---|:---|:---|
| LSTM+GRU Hybrid | ~0.83 | ~2.70 | MDPI 2025 |
| Autoformer | 0.540 | 0.764 | J. Adv. Inf. Tech. 2025 |
| **Our SOTA (current)** | **0.4669** | **0.6679** | Ours |
| **PatchTST (target)** | **TBD** | **TBD** | To be trained |

> [!TIP]
> Our current SOTA already **outperforms the published Autoformer benchmark on IHEPC** by 13.5% on MAE. Adding PatchTST as a third model will either (a) beat our SOTA (proving attention-only is sufficient) or (b) validate our hybrid approach as superior — both are valuable thesis findings.

### PatchTST Architecture

```
Input (96h × 7 variables)
    ↓
RevIN Normalization
    ↓
Channel Independence (process each variable separately)
    ↓
Patching: Split into N patches of length P with stride S
    ↓
Patch Embedding (Linear projection + Positional Encoding)
    ↓
Transformer Encoder (L layers × H heads)
    ↓
Flatten + Linear Projection → Forecast (24h)
    ↓
RevIN Denormalization
    ↓
Output (24h × 7 variables)
```

**Hyperparameters for IHEPC:**
- Patch length $P = 16$, Stride $S = 8$
- $d_{model} = 128$, $n_{heads} = 8$, $n_{layers} = 3$
- Dropout = 0.2, FFN dim = 256
- Lookback = 96, Horizon = 24

### Kaggle Notebook Plan

#### [NEW] `generate_patchtst_notebook.py`
Generates a self-contained Kaggle notebook with:

1. **Data Loading & Preprocessing** — identical pipeline to existing notebooks
2. **PatchTST Model Definition** — pure PyTorch (no external dependencies)
3. **Training Loop** — AdamW + OneCycleLR + Huber loss, 15 epochs
4. **Three-Way Evaluation** — loads all 3 models' weights, computes MAE/RMSE/MAPE
5. **Visualization** — comparison plots for the thesis
6. **Model Save** — exports `patchtst_weights.pth`

### App Integration

#### [MODIFY] `app_forecast/sota_model.py`
Add `PatchTST` class definition.

#### [MODIFY] `app_forecast/predictor.py`
Add PatchTST loading + `predict_patchtst()` method.

#### [MODIFY] `app_forecast/app.py`
PatchTST auto-appears in sidebar selector and playground comparisons.

---

## Part 2: Full-Stack Enterprise Energy Management Platform

### Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                     FRONTEND (Next.js 14 + TypeScript)           │
│   Login │ Dashboard │ Forecaster │ Analytics │ Alerts │ Admin    │
│                     shadcn/ui + Tailwind + Recharts              │
└──────────────────────────────┬───────────────────────────────────┘
                               │ REST API + WebSocket
┌──────────────────────────────┴───────────────────────────────────┐
│                      BACKEND (FastAPI)                            │
│   Auth (JWT+bcrypt) │ RBAC │ Forecast API │ Alert Engine │ Admin │
│                     Auto Swagger/OpenAPI docs                     │
└────────┬──────────────┬──────────────┬───────────────────────────┘
         │              │              │
   ┌─────┴─────┐  ┌─────┴─────┐  ┌────┴──────┐
   │ PostgreSQL │  │  PyTorch  │  │   Redis   │
   │ + Timescale│  │  Models   │  │  (Cache + │
   │ (Users,    │  │  (SOTA,   │  │   Celery  │
   │  Forecasts,│  │  PatchTST,│  │   Broker) │
   │  Alerts)   │  │  CNN-BiLSTM│ │           │
   └───────────┘  └───────────┘  └───────────┘
```

### Tech Stack

| Layer | Technology | Rationale |
|:---|:---|:---|
| **Frontend** | Next.js 14 + TypeScript | SSR, file-based routing, enterprise-grade |
| **UI** | shadcn/ui + Tailwind CSS | Premium dark components, consistent design |
| **Charts** | Recharts or Plotly.js | Interactive time-series visualization |
| **Backend** | FastAPI (Python) | Async, auto Swagger docs, ML-native |
| **Auth** | JWT + bcrypt (passlib) | Industry standard, stateless |
| **Database** | PostgreSQL (SQLite for dev) | Users, forecasts, alerts |
| **Cache** | Redis | Session cache, Celery broker |
| **ML Inference** | PyTorch (CPU) | Direct model loading |
| **Containerization** | Docker + Docker Compose | One-command deployment |
| **API Docs** | Swagger/OpenAPI (auto from FastAPI) | Zero-effort documentation |

---

### Module Breakdown

#### 🔐 Module 1: Authentication & RBAC

**JWT Flow:**
```
POST /api/v1/auth/login {email, password}
  → Server validates bcrypt hash
  → Returns {access_token (15min), refresh_token (7d)}
  → Client stores → sends Authorization: Bearer <token>
  → Protected endpoints use Depends(get_current_user)
```

**Three Roles:**

| Role | Access Level |
|:---|:---|
| **Admin** | Full: user CRUD, model deployment, system config, all data |
| **Analyst** | Forecasting, analytics, export, model comparison, alert config |
| **Viewer/Homeowner** | Read-only: own dashboard, personal forecasts, receive alerts |

#### 📊 Module 2: Forecasting Dashboard (Port from Streamlit)
- All 4 existing modules ported to React components
- **Three-way model comparison** (SOTA vs PatchTST vs CNN-BiLSTM)
- Forecast history saved to database per user
- CSV upload + sample data selection
- Interactive Plotly.js / Recharts charts

#### 📈 Module 3: Analytics & Reporting
- Historical forecast accuracy tracking (rolling MAE/RMSE over time)
- Seasonal consumption heatmaps
- Model performance comparison dashboard
- Exportable PDF reports (WeasyPrint)

#### 🔔 Module 4: Alert System
- Configurable peak demand thresholds per user
- Email notifications via SMTP (SendGrid)
- Alert history log with acknowledgment
- Cost-saving recommendation engine

#### ⚙️ Module 5: Admin Panel
- User CRUD operations
- Model version management (upload new weights, toggle active/inactive)
- System health monitoring
- Audit logs (who forecasted what, when)

---

### Security Features

| Feature | Implementation |
|:---|:---|
| Password Hashing | bcrypt with salt rounds (passlib) |
| JWT Tokens | Access (15min) + Refresh (7d), python-jose |
| CORS | Whitelist frontend origin only |
| Rate Limiting | SlowAPI middleware on auth endpoints |
| Input Validation | Pydantic models on all API inputs |
| SQL Injection | SQLAlchemy ORM (parameterized queries) |
| HTTPS | TLS enforcement in production |
| GDPR | Data export/deletion endpoints (French energy data) |
| Audit Logging | Log all forecast requests with user ID + timestamp |

---

### Database Schema

```sql
-- Users & Auth
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    role VARCHAR(20) DEFAULT 'viewer',  -- admin, analyst, viewer
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ
);

-- Forecast History
CREATE TABLE forecasts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    model_name VARCHAR(50) NOT NULL,
    input_start TIMESTAMPTZ,
    input_end TIMESTAMPTZ,
    predictions JSONB NOT NULL,
    metrics JSONB,  -- {mae, rmse, mape} if actuals available
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Alert Configuration
CREATE TABLE alert_configs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    threshold_kw FLOAT NOT NULL DEFAULT 3.0,
    email_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Alert History
CREATE TABLE alerts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    forecast_id INTEGER REFERENCES forecasts(id),
    alert_type VARCHAR(30),  -- peak_demand, cost_threshold
    severity VARCHAR(10),     -- low, medium, high
    message TEXT,
    peak_kw FLOAT,
    is_acknowledged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Model Registry
CREATE TABLE models (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    version VARCHAR(20),
    weights_path VARCHAR(500),
    architecture_summary TEXT,
    training_metrics JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    deployed_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

### UML Diagrams Required (6 minimum)

| # | Diagram | Purpose | Tool |
|:---|:---|:---|:---|
| 1 | **Use Case** | Actor-system interactions (Admin, Analyst, Viewer, System) | draw.io |
| 2 | **Class Diagram** | Backend models (User, Forecast, Alert, Model) | Mermaid / PlantUML |
| 3 | **Sequence Diagrams** | Login flow, Forecast flow, Alert trigger flow | Mermaid |
| 4 | **Activity Diagram** | ML pipeline (upload → preprocess → inference → display) | draw.io |
| 5 | **Deployment Diagram** | Docker containers, DB, frontend, backend topology | draw.io |
| 6 | **ER Diagram** | Database schema relationships | dbdiagram.io |
| 7 | **Component Diagram** | System modules and dependencies | PlantUML |

I can generate all Mermaid-based diagrams directly in the project docs.

---

### Directory Structure

```
PFE2/
├── backend/                        # FastAPI application
│   ├── app/
│   │   ├── main.py                 # FastAPI app entry
│   │   ├── config.py               # Settings (JWT secret, DB URL)
│   │   ├── database.py             # SQLAlchemy setup
│   │   ├── models/                 # ORM models
│   │   ├── schemas/                # Pydantic schemas
│   │   ├── routers/                # API route handlers
│   │   │   ├── auth.py
│   │   │   ├── forecast.py
│   │   │   ├── analytics.py
│   │   │   ├── alerts.py
│   │   │   └── admin.py
│   │   ├── services/               # Business logic
│   │   │   ├── auth_service.py
│   │   │   ├── forecast_service.py
│   │   │   └── alert_service.py
│   │   ├── ml/                     # Model inference
│   │   │   ├── architectures.py    # Model classes
│   │   │   ├── predictor.py        # Inference wrapper
│   │   │   └── weights/            # .pth files
│   │   └── middleware/
│   │       ├── auth.py             # JWT dependency
│   │       └── rate_limit.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                       # Next.js application
│   ├── src/
│   │   ├── app/                    # Pages (file-based routing)
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx            # Landing / Login
│   │   │   ├── dashboard/
│   │   │   ├── forecast/
│   │   │   ├── analytics/
│   │   │   ├── alerts/
│   │   │   └── admin/
│   │   ├── components/
│   │   │   ├── ui/                 # shadcn components
│   │   │   ├── charts/             # Plotly/Recharts wrappers
│   │   │   └── layout/             # Sidebar, Navbar
│   │   ├── lib/
│   │   │   ├── api.ts              # API client (fetch wrapper)
│   │   │   ├── auth.ts             # Auth context + hooks
│   │   │   └── utils.ts
│   │   └── types/                  # TypeScript interfaces
│   ├── package.json
│   └── Dockerfile
│
├── docker-compose.yml              # Full stack orchestration
├── docs/
│   ├── uml/                        # Diagram source files
│   └── architecture.md             # System design doc
│
├── app_forecast/                   # Streamlit (keep as prototype)
├── notebooks/                      # Training notebooks
├── models/                         # Model weights
└── data/                           # Dataset
```

---

### Docker Compose

```yaml
services:
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on: [backend]

  backend:
    build: ./backend
    ports: ["8000:8000"]
    depends_on: [db]
    volumes:
      - ./models:/app/ml/weights

  db:
    image: postgres:16
    environment:
      POSTGRES_DB: energy_forecast
      POSTGRES_USER: pfe
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

volumes:
  pgdata:
```

---

## What Makes This "Excellent" vs "Good"

| Feature | Good Thesis | Your Project (Excellent) |
|:---|:---|:---|
| Model | Single LSTM | **3 models**: CNN-BiLSTM + Hybrid SOTA + PatchTST |
| Evaluation | MAE only | MAE + RMSE + MAPE + multi-horizon + ablation |
| App | Jupyter/Streamlit | **Full-stack** web app with auth + RBAC |
| Infrastructure | Run locally | **Docker** + CI/CD |
| Security | None | **JWT + RBAC + HTTPS + GDPR** |
| Diagrams | 2-3 basic UML | **7 UML** + ER diagram + architecture |
| Novelty | Replication | **Critical DEPM analysis** + improved architecture |

---

## Open Questions

> [!IMPORTANT]
> 1. **Web app stack?**
>    - **Option A (Recommended):** FastAPI + Next.js — enterprise-grade, most impressive
>    - **Option B:** FastAPI + vanilla HTML/CSS/JS — simpler, like existing DEPM app
>    - **Option C:** Django full-stack
>
> 2. **Database?** SQLite (zero setup) or PostgreSQL (production-ready, thesis credibility)?
>
> 3. **Keep Streamlit app** as prototype alongside the new app, or replace it?
>
> 4. **Start with PatchTST notebook now** so you can train on Kaggle while I build the backend?

---

## Suggested Execution Order

| Phase | Task | Duration |
|:---|:---|:---|
| **Phase 1** | Generate PatchTST notebook → you train on Kaggle | 1 day |
| **Phase 2** | FastAPI backend (auth + forecast API + DB) | 3-4 days |
| **Phase 3** | Next.js frontend (login + dashboard + forecast) | 3-4 days |
| **Phase 4** | Integrate PatchTST weights + 3-way playground | 1 day |
| **Phase 5** | Alert system + analytics + admin panel | 2-3 days |
| **Phase 6** | UML diagrams + documentation | 1-2 days |
| **Phase 7** | Docker Compose + final polish | 1 day |
| **Phase 8** | Testing + walkthrough | 1 day |

---

## Verification Plan

### Automated Tests
- Auth: JWT generation, password hashing, role checks
- Forecast API: all 3 models produce valid 24-step outputs
- Alert: threshold triggers correctly

### Manual Verification
- Login/register flow end-to-end
- Three-way model comparison renders correctly
- Docker Compose brings up the full stack
- PDF report export works
