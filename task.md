# 📋 Execution Checklist

- `[x]` **Component 1: Live Smart Meter Sync**
  - `[x]` Create `backend/app/services/smart_meter_service.py` to simulate Enedis Linky API readings
  - `[x]` Add `/api/v1/forecast/smart-meter/sync` endpoint in `backend/app/routers/forecast.py`
  - `[x]` Add "Smart Meter Linky" sync interface in `frontend/src/app/forecast/page.tsx`
  - `[x]` Verify API connectivity and commit changes

- `[x]` **Component 2: Real ML Retraining Pipeline**
  - `[x]` Implement real PyTorch training loop (Adam + MSELoss) in `backend/app/services/forecast_service.py`
  - `[x]` Update training stats, version increments, and metrics on completion
  - `[x]` Verify registry details update and commit changes

- `[x]` **Component 3: i18n Localization & RTL**
  - `[x]` Create `frontend/src/lib/i18n.tsx` translation context (EN / FR / AR)
  - `[x]` Setup RTL layout mirroring when Arabic is active
  - `[x]` Integrate translation helper `t()` across Navbar, Sidebar, Dashboard, Forecast, Analytics, Admin pages
  - `[x]` Add Language Selection settings card in `frontend/src/app/settings/page.tsx`
  - `[x]` Verify translations work and commit changes

- `[x]` **Component 4: WebSockets & Auto-Forecasting**
  - `[x]` Create `backend/app/services/websocket_manager.py` ConnectionManager class
  - `[x]` Add WebSocket router `/api/v1/alerts/ws/{client_id}` in `backend/app/routers/alerts.py`
  - `[x]` Setup background task ticker in `backend/app/main.py` that automatically runs forecasts and broadcasts alerts
  - `[x]` Establish WebSocket receiver in `frontend/src/components/layout/navbar.tsx` to slide in alert toasts
  - `[x]` Verify live alert broadcasting and commit changes
