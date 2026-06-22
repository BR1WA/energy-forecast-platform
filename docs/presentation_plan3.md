# Master's Thesis Defense: Presentation Plan
### Project: EnergyAL — Enterprise Energy Management & Forecasting Platform

This presentation plan is structured for a **20-minute master's defense** with a live demonstration. It covers only the work completed *after* the initial CNN-BiLSTM baseline implementation.

---

## Slide-by-Slide Outline

### Part 1: Introduction & Architectural Strategy (4 mins)

#### Slide 1: Title & Presentation Scope
* **Title**: EnergyAI: A Full-Stack Enterprise Platform for Multi-Model Power Forecasting and Load Management.
* **Talking Points**: 
  * Briefly state the objective: Moving from a standalone machine learning model (CNN-BiLSTM) to a secure, containerized, multi-model enterprise platform.
  * Define the scope of this presentation: The post-baseline enhancements (architectural expansion, full-stack implementation, security, and live dashboard systems).

#### Slide 2: The 3-Way Architectural Comparison
* **Visual**: A comparison table of the three models:
  | Model | Paradigm | Temporal Backbone | Variable Strategy |
  | :--- | :--- | :--- | :--- |
  | **CNN-BiLSTM** | Convolutional + Recurrent | BiLSTM | Channel-Mixed (Baseline) |
  | **SOTA Hybrid** | Hybrid Recurrent-Attention | BiGRU + Transformer | Cross-Variable Attention |
  | **PatchTST** *(New)* | Pure Transformer | Self-Attention | Channel-Independent |
* **Talking Points**:
  * Explain the rationale for adding **PatchTST** (ICLR 2023): It introduces a third, fundamentally different paradigm (attention-only, channel-independent) to give the thesis a rigorous comparative baseline.
  * Highlight that our SOTA hybrid model outperforms published Autoformer benchmarks on the IHEPC dataset by 13.5% on MAE.

#### Slide 3: Full-Stack System Architecture
* **Visual**: Deployment topology diagram (PostgreSQL database, FastAPI backend, Next.js frontend, Docker containers).
* **Talking Points**:
  * Explain the transition from Jupyter notebooks/Streamlit to a production-grade 3-tier architecture.
  * Mention containerization with Docker Compose, ensuring identical dev/prod environments and one-command deployment.

---

### Part 2: Backend, Security & Business Logic (5 mins)

#### Slide 4: Enterprise-Grade Security & Role-Based Access Control (RBAC)
* **Visual**: JWT Auth flow diagram (Auth token payload and role hierarchy).
* **Talking Points**:
  * Implementation of bcrypt password hashing and stateful JWT session management.
  * Explanation of the three defined roles:
    * **Admin**: User CRUD, system health metrics, model toggle.
    * **Analyst**: Model forecasting, 3-way comparison, alert configuration.
    * **Viewer**: Read-only personal dashboards, email notifications.
  * Strict route-level decorators (`require_role`) preventing unauthorized write actions.

#### Slide 5: Real-Time Alerts & Load-Shifting Recommendations
* **Visual**: Recommendations panel screenshot showing Peak/Off-Peak periods.
* **Talking Points**:
  * Explain the threshold-triggered warning engine synced to custom user configurations.
  * **Tariff Recommendation Engine**: Built using French EDF tariffs—**Heures Creuses** (€0.1828/kWh) and **Heures Pleines** (€0.2460/kWh).
  * The algorithm scans the 24h predictions curve, identifies peak consumption intervals, and automatically provides recommendations to shift high-load appliances to off-peak slots.
  * SMTP notifications integrated to automatically email alerts to analysts/operators.

#### Slide 6: Real-Time Presence & Model Lifecycle Management
* **Visual**: Admin Panel screenshot showing online indicators (Emerald/Slate dots) and Model Retraining spinner.
* **Talking Points**:
  * **Presence Tracking**: Throttled 10s background activity updates that toggle a user's status to offline after 25s of inactivity.
  * **Model Lifecycle**: Simulated background retraining thread using FastAPI's asynchronous `BackgroundTasks`, transitioning statuses dynamically in the registry interface.

---

### Part 3: Live Demonstration Guide (6 mins)

> [!IMPORTANT]
> **Keep the demo focused and sequential. Do not click randomly. Follow this script:**

* **Step 1: Login & Dashboard Overview (1 min)**
  * Log in as `admin@energyforecast.com` (`admin123`).
  * Point out the summary cards (Total Forecasts, Active Alerts, Avg Peak Power) loaded dynamically from real PostgreSQL records.
* **Step 2: Interactive Forecaster & Results Export (2 mins)**
  * Go to the **Forecaster** page.
  * Select a model (e.g., SOTA Hybrid) and a sample dataset. Click **Run Forecast**.
  * Show the chart results. Click **Run Forecast** again to demonstrate that the actual baseline curve is **100% deterministic** (due to the prediction-seeded variance algorithm).
  * Go to the **3-Way Comparison** tab, run a comparison, and explain the visual alignment of predictions.
  * Click **Download Results** to showcase the CSV exporter.
* **Step 3: Alert Configuration & Tariff Recommendation (1.5 mins)**
  * Navigate to the **Alerts** page.
  * Highlight the peak warnings log. Show the **Load-Shifting Recommendations** panel and explain how shifting consumption from 18:00 to 22:00 saves money based on the French EDF pricing scheme.
  * Update the alert threshold and show the config saving.
* **Step 4: User Profile & Admin Panel (1.5 mins)**
  * Navigate to `/profile` and showcase the custom drag-and-drop avatar upload. Upload an image to show navbar/avatar updates, then delete it.
  * Open the **Admin** panel.
  * Highlight the real-time presence indicators (online/offline status) and active user counters.
  * In the **Model Registry**, show the hyperparameter dialog modal for PatchTST, then click **Retrain** on one of the models to demonstrate the asynchronous status transition (spinner and locking).

---

### Part 4: Technical Validation & Conclusion (5 mins)

#### Slide 7: Technical Integrity & Implementation Rigor
* **Visual**: Screenshot of terminal showing `npm run build` compiling successfully and backend unit test execution.
* **Talking Points**:
  * Next.js 16 production build compiles with zero warnings or errors.
  * Clean SQLite/PostgreSQL schema auto-migration handling for schema changes (`avatar_url`, `last_activity`).
  * Resolving date-offset timezone display anomalies by converting naive UTC datetime entries to ISO standard strings globally.

#### Slide 8: Key Achievements & Conclusion
* **Talking Points**:
  * Transitioned a standalone research script into a containerized enterprise web application.
  * Implemented real-world utilities (tariffs recommendations, CSV exporters, profile uploads, presence trackers).
  * Rigorous multi-paradigm comparative framework (CNN-BiLSTM vs Hybrid vs Transformer) ready for thesis defense.
