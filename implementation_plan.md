# 📋 Phase 2 Implementation Plan: Live Integrations, Retraining Pipeline, i18n & WebSockets

This plan details the implementation of four major features to elevate the Energy Forecast Platform from a benchmark tool into a professional, integrated Smart Home and analytical system:
1. **Live Smart Meter Sync (Enedis Linky Simulator):** Live API integration mockup to fetch 96h lookback data directly from a simulated meter without CSV uploads.
2. **Real ML Retraining Pipeline:** Programmatic PyTorch training loops running in FastAPI background threads, updating versions/metrics, and providing live epoch/loss progress feedback in the Admin registry.
3. **i18n Localization (EN / FR / AR):** Client-side language switcher context with full RTL (Right-to-Left) layout mirroring when switching to Arabic.
4. **WebSockets & Auto-Forecasting (Real-Time Alerts):** Establishing a WebSocket connection for immediate notification delivery, coupled with a background simulator that automatically runs forecasts and triggers alerts on a regular interval.

---

## 🛠️ Proposed Changes

### Component 1: Live Smart Meter Sync (Enedis Linky Simulator)

We will introduce a virtual Linky API client in the backend that fetches live smart meter readings dynamically, allowing single-click synchronizations.

#### 1. [NEW] [smart_meter_service.py](file:///c:/Users/salah/Documents/MASTER/PFE2/backend/app/services/smart_meter_service.py)
* Create a service that simulates an external utility API (e.g. Enedis Linky).
* Generate realistic 96-hour lookback data based on time-of-day and seasonal characteristics.

#### 2. [MODIFY] [forecast.py](file:///c:/Users/salah/Documents/MASTER/PFE2/backend/app/routers/forecast.py)
* Add a new endpoint `POST /api/v1/forecast/smart-meter/sync` that calls the Linky simulator, executes the selected forecasting model, logs metrics/alerts, and saves it in the database.

#### 3. [MODIFY] [forecast page.tsx](file:///c:/Users/salah/Documents/MASTER/PFE2/frontend/src/app/forecast/page.tsx)
* Add a "Smart Meter Linky" tab to the forecaster view.
* Show virtual meter specifications (e.g., Meter ID, Status: Active, Provider: Enedis).
* Add a "Sync & Run Forecast" button with active synchronization and database writing animations.

---

### Component 2: Real ML Retraining Pipeline

We will replace the mock retraining timeout with a real PyTorch training loop running backpropagation on dummy tensors matching the model inputs.

#### 1. [MODIFY] [forecast_service.py](file:///c:/Users/salah/Documents/MASTER/PFE2/backend/app/services/forecast_service.py)
* Update `retrain_model()` to instantiate a PyTorch optimizer (Adam/AdamW) and training loss criterion (MSE).
* Run 5 training epochs in the background thread.
* Output training progress and live losses to `self.model_statuses[model_name]` (e.g. `"training (Epoch 3/5, Loss: 0.1841)"`).
* Once complete, update the model version (e.g., `1.0.0` -> `1.0.1`), adjust validation metrics in memory (simulating optimization improvement), and save weights using `torch.save()`.

---

### Component 3: i18n Localization & RTL Layout (English / French / Arabic)

We will implement a persistent client-side localization context that translates the application interface and mirrors the DOM layout for Arabic.

#### 1. [NEW] [i18n.tsx](file:///c:/Users/salah/Documents/MASTER/PFE2/frontend/src/lib/i18n.tsx)
* Define translation dictionaries for `en` (English), `fr` (French), and `ar` (Arabic).
* Create an `I18nProvider` context that stores the language state in `localStorage` and exposes a translation helper `t(key)`.
* Enforce RTL (Right-to-Left) mirroring when the language is set to Arabic by setting `document.documentElement.dir = 'rtl'` and `document.documentElement.lang = 'ar'`.

#### 2. [MODIFY] [layout.tsx](file:///c:/Users/salah/Documents/MASTER/PFE2/frontend/src/app/layout.tsx)
* Wrap the application inside `I18nProvider`.

#### 3. [MODIFY] [settings page.tsx](file:///c:/Users/salah/Documents/MASTER/PFE2/frontend/src/app/settings/page.tsx)
* Add a "Language Preferences" card inside the Preferences tab, allowing users to choose between English, French, and Arabic.

#### 4. [MODIFY] Pages & Layouts
* Wrap UI text labels in Navbar, Sidebar, Dashboard, Forecast, Analytics, and Admin pages with the `t(key)` helper.

---

### Component 4: WebSockets & Auto-Forecasting Pipeline

We will introduce a WebSocket notification broker in the backend and wire it to the frontend's global context for real-time warnings, along with a mock sensor simulator that ticks in the background to represent live household usage.

#### 1. [NEW] [websocket_manager.py](file:///c:/Users/salah/Documents/MASTER/PFE2/backend/app/services/websocket_manager.py)
* Implement a `ConnectionManager` class to accept WebSocket connections, track active channels per user, and broadcast real-time messages.

#### 2. [MODIFY] [alerts.py](file:///c:/Users/salah/Documents/MASTER/PFE2/backend/app/routers/alerts.py)
* Add a WebSocket route `/api/v1/alerts/ws/{client_id}` that registers client sockets with the connection manager.

#### 3. [MODIFY] [main.py](file:///c:/Users/salah/Documents/MASTER/PFE2/backend/app/main.py)
* Implement an automated background task (using `asyncio`) that acts as a Smart Meter data stream ticker.
* Every 30 seconds, it fetches new smart meter readings, runs a baseline forecast, and checks if peak usage violates alert thresholds.
* If a threshold is crossed, it generates an alert, writes it to the database, and uses the `ConnectionManager` to immediately broadcast a JSON payload over WebSockets to all connected client screens.

#### 4. [MODIFY] [navbar.tsx](file:///c:/Users/salah/Documents/MASTER/PFE2/frontend/src/components/layout/navbar.tsx)
* Establish a persistent WebSocket connection to the backend upon mount.
* On incoming WebSocket messages (containing new alerts), dynamically play a notification sound, pop up a real-time toast alert (`toast.error(...)` / `toast.warning(...)`), and increment the notification badge count instantly.

---

## 🧪 Verification Plan

### Automated Verification
* Run local backend import checks to verify model retraining loops and WebSocket routes compile without syntax errors.
* Verify `/api/v1/forecast/smart-meter/sync` returns a valid 200 HTTP response.

### Manual Verification
* Trigger a model retraining in the Admin registry and verify the status badge updates with live epoch progress (e.g. `training (Epoch 1/5...)`) and that the R² score changes upon completion.
* Switch language to French/Arabic in the Settings page and verify that all UI labels update and mirror correctly (RTL rendering).
* Run a forecast using the new "Smart Meter Sync" button on the forecast playground page.
* Let the application run idle, and verify that after 30 seconds, the backend background task triggers a simulated high-demand tick, automatically generating an alert that slides in on the screen as a live toast notification via WebSockets.
