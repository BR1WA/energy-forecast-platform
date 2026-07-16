# Application Status Audit Report

**Date of Audit**: 2026-07-16  
**Time of Audit**: 19:27 (UTC+1 / WAT)  
**Audited by**: Antigravity  
**Overall Status**: 🟢 All Systems Operational

---

## 1. Container Status

| Service | Container | Image | State | Uptime | Port Mapping |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **Database** | `energy_db` | `postgres:16-alpine` | 🟢 Running | ~35 hours | `0.0.0.0:5432→5432` |
| **Backend** | `energy_backend` | `pfe2-backend` | 🟢 Running | ~1 hour | `0.0.0.0:8000→8000` |
| **Frontend** | `energy_frontend` | `pfe2-frontend` | 🟢 Running | ~1 hour | `0.0.0.0:3000→3000` |

> **Note**: Backend and frontend were last restarted during the Docker sync troubleshooting session (`58dad948`). The database has been continuously running for ~35 hours.

---

## 2. Health Check Probe Results

### Backend API — `GET /api/v1/system/health`

| Check | Result |
| :--- | :--- |
| **URL** | `http://localhost:8000/api/v1/system/health` |
| **HTTP Status** | `200 OK` |
| **Backend subsystem** | ✅ `healthy` |
| **Database subsystem** | ✅ `healthy` |
| **Forecast subsystem** | ⚠️ `placeholder` |
| **Weather subsystem** | ✅ `healthy` |
| **Uptime** | 3,173 seconds (~52 min) |

```json
{
  "backend": "healthy",
  "database": "healthy",
  "forecast": "placeholder",
  "weather": "healthy",
  "uptime": 3173
}
```

### Frontend — `GET http://localhost:3000`

| Check | Result |
| :--- | :--- |
| **HTTP Status** | `200 OK` |
| **Next.js Version** | `16.2.6` |
| **Server State** | ✅ Ready (264ms startup) |

---

## 3. Resource Utilisation

| Container | CPU % | Memory Used | Memory % | Net I/O (In/Out) |
| :--- | :--- | :--- | :--- | :--- |
| `energy_backend` | 0.17% | 432.5 MiB / 7.43 GiB | 5.69% | 9.07 MB / 4.96 MB |
| `energy_frontend` | 0.00% | 63.38 MiB / 7.43 GiB | 0.83% | 179 kB / 1.05 MB |
| `energy_db` | 0.00% | 58.9 MiB / 7.43 GiB | 0.77% | 12.3 MB / 26.3 MB |

The backend's ~432 MiB footprint is expected (ML model held in memory for real-time inference).

---

## 4. Database & Data Audit

### 4a. Migration Status

| Check | Result |
| :--- | :--- |
| **Current revision** | `bf09bfef2e1e` |
| **Alembic status** | ✅ `(head)` — up-to-date |

### 4b. Table Row Counts

| Table | Row Count | Δ Since Last Audit |
| :--- | ---: | :--- |
| `smart_meter_readings` | **58,101** | +600 *(live telemetry active)* |
| `model_registry` | **3** | ±0 |
| `forecasts` | **221** | ±0 |
| `alerts` | **2,628** | +37 |

### 4c. Smart Meter Telemetry Range

| Field | Value |
| :--- | :--- |
| **Earliest record** | `2026-06-14 19:52:13 UTC` |
| **Latest record** | `2026-07-16 18:24:39 UTC` |
| **Coverage span** | ~32 days |

### 4d. Model Registry

| ID | Model Name | Active | Registered |
| :--- | :--- | :---: | :--- |
| 1 | `24h_hybrid_v2_baseline_1782856150` | ✅ Yes | 2026-07-08 13:41 UTC |
| 2 | `24h_hybrid_v2_baseline_1782856368` | ❌ No | 2026-07-08 13:41 UTC |
| 3 | `24h_hybrid_v2_baseline_1782855695` | ❌ No | 2026-07-08 14:09 UTC |

---

## 5. Log Analysis

### Backend Logs (Last 50 Lines)
- **Errors / Exceptions**: ✅ None detected
- **Warnings**:
  - `InconsistentVersionWarning`: `StandardScaler` pickled with `sklearn 1.8.0`, runtime is `1.9.0`. Minor risk — consider re-serializing the scaler artifact.
  - `UserWarning`: Pydantic field `model_name` conflicts with protected `model_` namespace. Cosmetic only.
- **WebSocket activity**: Active live telemetry stream connections — normal behavior.

### Frontend Logs (Last 20 Lines)
- **Errors detected**: ✅ None
- Next.js production server started cleanly.

---

## 6. Known Issues & Recommendations

| # | Severity | Issue | Recommendation |
| :-- | :--- | :--- | :--- |
| 1 | ⚠️ Medium | `sklearn` version mismatch (`1.8.0` pickle vs `1.9.0` runtime) | Re-serialize the `StandardScaler` artifact using `sklearn 1.9.0`. |
| 2 | ⚠️ Medium | `forecast` health check returns `"placeholder"` | Implement an active model smoke-test in the health endpoint. |
| 3 | ℹ️ Low | Insecure `ADMIN_PASSWORD` default in use | Override via `.env` before any non-local deployment. |
| 4 | ℹ️ Low | Pydantic `model_` namespace conflict warning | Add `model_config = {'protected_namespaces': ()}` to the schema. |
| 5 | ℹ️ Low | Frontend container has no volume mounts | Code changes require full rebuild; consider adding source volume for dev loop. |

---

## 7. Audit History

| Audit Date | Status | Key Events |
| :--- | :--- | :--- |
| 2026-07-16 19:27 WAT | 🟢 Healthy | Full audit — no errors in logs; DB growing via live telemetry; all services operational. |
| 2026-07-16 (earlier) | 🟢 Healthy | Fixed `seed_db.py` AttributeError & `DashboardService` "need 96 rows, got 1" failure. |

---
*Audit completed by Antigravity at 19:27 WAT (2026-07-16).*
