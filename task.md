# Platform Improvements Tasks

This task list tracks the resolution of open improvements and hygiene tasks.

## Phase 1: Machine Learning & Cost Correctness
- [x] **ML-1: Standardize Month Encoding Inconsistency (1.1)**
  - [x] Implement shared helper `encode_month(dt: datetime) -> float`
  - [x] Update `predict_upload` path in `forecast.py` to use helper
  - [x] Update `smart-meter` sync path in `forecast.py` to use helper
  - [x] Update `_load_samples` in `forecast_service.py` to use helper
- [x] **ML-2: Persist Forecast Start Hour (1.2)**
  - [x] Save `input_start` and `input_end` datetimes during new predictions
- [x] **ML-3: Moroccan ONEE Pricing Wiring (1.3)**
  - [x] Update report generation in `analytics.py` to calculate costs using the start hour and ONEE tiered preset brackets
- [ ] **ML-4: Label Synthetic/Simulated Analytics Data (1.4)**
  - [ ] Add explicit "Demo / Simulated Data" indicators to frontend analytics charts
- [ ] **ML-5: Sandbox Retrain Flow (1.5)**
  - [ ] Write new model weights to a candidate directory instead of overwriting production `.pth` files
  - [ ] Remove the synthetic accuracy increment of `+0.0035`

## Phase 2: Security & Quality
- [ ] **SEC-1: Refresh Token Rotation (3.2)**
  - [ ] Store hashed refresh tokens in the database and invalidate them upon logout or rotation
- [ ] **TST-1: In-Memory SQLite for Tests (5.4)**
  - [ ] Refactor test setup to use `sqlite:///:memory:`
- [ ] **TST-2: Expand Test Coverage (5.1)**
  - [ ] Add `test_auth.py` and `test_billing.py`
- [ ] **LOG-1: Structured Logging (5.2)**
  - [ ] Implement Python logging module usage instead of `print()`

## Phase 3: UX & Interface Polish
- [ ] **UX-1: Admin Subscription Management (3.4)**
  - [ ] Add subscription tier selector dropdown in the admin user edit modal
- [ ] **UX-2: WebSocket Reconnect with Backoff (4.1)**
  - [ ] Implement backoff reconnect loop in frontend WebSocket consumer
- [ ] **HYG-1: Remove Committed SQLite Database (6.1)**
  - [ ] Add `backend/*.db` and `backend/energy_forecast.db` to `.gitignore`
  - [ ] Create schema/seed sql for easy database seeding
