# EnergyAI Real Product Implementation Plan

This plan turns the current PFE platform from a strong thesis/demo app into a client-usable energy forecasting product. The goal is twofold:

1. Make the project excellent for a Master's PFE defense by proving academic rigor, engineering maturity, and market usefulness.
2. Make the product credible in a career portfolio by showing that real clients could onboard, connect data, forecast consumption, manage costs, and receive actionable alerts.

## Product Verdict

The current app is not a waste of time. It already has real foundations: FastAPI, Next.js, authentication, roles, subscription gates, model serving, WebSockets, dashboards, PDF export, Moroccan setup, and forecast history.

The gap is product reality. Today, some parts are simulated, some production paths are fragile, and the app does not yet solve a complete client workflow end to end with real data and reliable deployment.

The target product should be:

> A Moroccan-focused energy intelligence platform for homes, small businesses, and facilities that connects meter or uploaded consumption data, forecasts future usage, estimates bills in MAD, detects waste/peaks, and gives practical cost-saving recommendations.

## Success Definition

The project reaches "real product" quality when a real user can do all of this without developer help:

- Register and complete setup.
- Connect a real data source or upload historical meter CSVs.
- See current and historical consumption.
- Run 24h, 7-day, and 30-day forecasts.
- Understand forecast accuracy and uncertainty.
- Receive useful alerts before budget, tariff, or peak-load problems happen.
- Export useful reports for decision-making.
- Manage subscription, profile, settings, and notifications.
- Trust that their data is private and isolated from other users.
- Use the app reliably after deployment, not only on localhost.

## Phase 0: Stabilize The Existing App

Purpose: make the app build, run, and demo reliably before adding features.

### Tasks

- Fix frontend production build.
  - Remove `.next/dev/types/**/*.ts` from `frontend/tsconfig.json`.
  - Delete stale `.next` artifacts locally.
  - Run `npm run build` until it passes cleanly.

- Reduce frontend warnings.
  - Remove unused imports and variables.
  - Fix React hook dependency warnings.
  - Keep lint at zero errors and ideally under five warnings.

- Make Docker reliable.
  - Require real `JWT_SECRET_KEY`, `ADMIN_PASSWORD`, and database password in `.env`.
  - Remove insecure default admin password from `docker-compose.yml`.
  - Confirm `docker compose up --build` starts frontend, backend, and database.

- Create a clean demo seed flow.
  - Add a seed script for one admin, one analyst, one free viewer, and realistic demo forecasts.
  - Do not depend on a committed SQLite database.

### Acceptance Criteria

- `python -m pytest` passes.
- `npm run lint` has no errors.
- `npm run build` passes.
- Docker Compose starts from a fresh clone with documented `.env`.
- A tester can log in and use the app in under five minutes.

## Phase 1: Make The Product Honest

Purpose: remove academic/product credibility risks caused by overclaiming.

### Tasks

- Label every simulated feature clearly.
  - Smart meter stream: "simulated" unless real API mode is configured.
  - Billing checkout: "sandbox checkout" until Stripe or another provider exists.
  - Analytics fallback data: "demo data" when no real history exists.

- Split demo data from real data.
  - Add a `data_source` field where relevant: `real_meter`, `uploaded_csv`, `simulator`, `demo_seed`.
  - Show that source in dashboard, analytics, PDF reports, and forecast history.

- Replace fake "actuals" with real history where possible.
  - Use stored `SmartMeterReading` and uploaded datasets for actual consumption charts.
  - If no actual values exist, show an empty state instead of pretending.

- Add confidence/uncertainty language.
  - Do not present forecasts as guaranteed.
  - Add forecast bands or error ranges based on validation error, historical residuals, or model ensemble spread.

### Acceptance Criteria

- No chart presents simulated values as real measured values.
- PDF reports disclose whether data is real, uploaded, simulated, or seeded.
- The thesis story becomes stronger: "we criticize fake metrics, so our product labels uncertainty and simulation honestly."

## Phase 2: Real Client Data Ingestion

Purpose: make the platform useful without needing a developer or notebook.

### MVP Data Sources

- CSV upload.
  - Keep this as the first real-client path.
  - Support common formats: timestamp, active power, reactive power, voltage, current, sub-metering columns when available.
  - Add a mapping wizard so clients can map their column names to the platform schema.

- Manual meter readings.
  - Simple form for daily or hourly kWh readings.
  - Useful for small clients without smart meters.

- API connector mode.
  - Keep current sensor API URL support, but make it safe.
  - Add schema validation for returned readings.
  - Add allowlist controls and SSRF protection.

### Later Data Sources

- Shelly / Home Assistant / MQTT integration.
- Utility provider imports where legally and technically available.
- IoT gateways for businesses and facilities.

### Backend Tasks

- Add `Meter`, `MeterReading`, `Site`, and `DataImportJob` tables.
- Associate readings with `user_id` and optionally `site_id`.
- Store raw uploaded file metadata and parsed status.
- Add ingestion validation:
  - missing timestamp detection,
  - duplicate detection,
  - timezone handling,
  - unit conversion,
  - gap filling policy.

### Frontend Tasks

- Build an onboarding "Connect Data" step.
- Add import progress and validation results.
- Show bad rows, missing columns, and accepted rows.
- Let users preview their imported consumption before saving.

### Acceptance Criteria

- A real client can upload a CSV and get a forecast without editing code.
- The app stores their readings and reuses them for dashboard and analytics.
- Import errors are understandable to non-technical users.

## Phase 3: Multi-Tenant Product Architecture

Purpose: make the app safe for more than one real client.

### Tasks

- Make settings per user or per organization.
  - Current global `SystemSettings` is acceptable for a demo, not for a SaaS.
  - Add `Organization` and `OrganizationMember` if targeting businesses.
  - Move tariffs, provider, sensor config, and setup state to user/org scope.

- Enforce ownership everywhere.
  - Every forecast, alert, meter, import job, budget, report, and setting must be filtered by authenticated user or organization.

- Add roles inside organizations.
  - Owner, admin, analyst, viewer.
  - Site-level access if supporting multi-site clients.

- Add audit logs.
  - Track subscription changes, settings changes, report exports, data imports, user invites, and model retraining.

### Acceptance Criteria

- User A cannot read, update, export, or infer User B's data.
- Admin actions are logged.
- Multi-site is backed by database records, not static arrays.

## Phase 4: Forecasting That Clients Can Trust

Purpose: improve model usefulness and make forecast outputs actionable.

### Tasks

- Standardize preprocessing.
  - One shared path for CSV, simulator, API, and smart-meter data.
  - Consistent timestamp handling, scaling, and calendar features.

- Fix model registry ownership.
  - Use `ModelRegistry` as the source of truth.
  - Store model version, artifact path, horizon, features, metrics, trained date, and status.

- Add model evaluation per client dataset.
  - After importing historical data, backtest the model on that client's data.
  - Show client-specific MAE, RMSE, MAPE, and R2 if enough history exists.

- Add forecast uncertainty.
  - MVP: use historical validation residuals or ensemble spread.
  - Better: quantile forecasting or conformal prediction.

- Make retraining safe.
  - Never overwrite production weights directly.
  - Train to candidate artifacts.
  - Evaluate candidate.
  - Promote only if metrics improve and admin confirms.

- Add recommendation engine.
  - Peak-shaving suggestions.
  - Off-peak scheduling suggestions.
  - Budget-risk alerts.
  - Abnormal consumption detection.

### Acceptance Criteria

- Forecast output includes predicted consumption, confidence range, expected cost, and top recommendations.
- Retraining cannot damage the active model.
- Forecast accuracy is shown honestly and can be explained during defense.

## Phase 5: Client-Useful Dashboard

Purpose: move from beautiful charts to decisions clients can act on.

### Core Screens

- Dashboard:
  - current consumption,
  - today's projected cost,
  - month-to-date cost,
  - budget progress,
  - forecast risk,
  - active alerts,
  - top recommendation.

- Forecast:
  - 24h, 7-day, and 30-day forecasts,
  - model comparison,
  - confidence bands,
  - export CSV/PDF.

- Analytics:
  - daily, weekly, monthly consumption,
  - peak hours,
  - appliance/sub-metering breakdown when available,
  - tariff impact,
  - savings opportunities.

- Alerts:
  - peak demand,
  - budget risk,
  - abnormal usage,
  - missing meter data,
  - power factor issues if supported by real data.

- Settings:
  - tariff,
  - provider,
  - budget,
  - notification preferences,
  - data source configuration.

### UX Tasks

- Add empty states that tell users what to do next.
- Replace generic spinners with skeletons.
- Add mobile audit for dashboard, forecast, setup, and reports.
- Make reports client-facing, not just academic.

### Acceptance Criteria

- A client can answer: "How much will I spend?", "When is my usage highest?", "What should I do?", and "How confident is this forecast?"

## Phase 6: Real Payments And Plans

Purpose: make SaaS monetization honest and production-safe.

### Tasks

- Integrate Stripe, Paddle, PayPal, or Moroccan-friendly payment provider.
- Move checkout confirmation to signed webhooks only.
- Keep subscription lifecycle:
  - pending,
  - active,
  - past_due,
  - cancelled,
  - expired.

- Add billing portal.
  - invoices,
  - renewal date,
  - cancellation,
  - plan changes.

- Define useful tiers.

### Suggested Tiers

- Free:
  - CSV upload,
  - 24h forecast,
  - basic dashboard,
  - limited history.

- Pro:
  - 7-day and 30-day forecasts,
  - alerts,
  - PDF/CSV exports,
  - budget tracking,
  - recommendations.

- Business:
  - multi-site,
  - team roles,
  - scheduled reports,
  - API connector,
  - priority support.

### Acceptance Criteria

- Users cannot self-confirm payment.
- Entitlements are driven by real subscription status.
- Plan limits are enforced server-side.

## Phase 7: Security, Privacy, And Compliance

Purpose: make clients trust the product.

### Tasks

- Move auth tokens from localStorage to secure HTTP-only cookies if possible.
- Add CSRF protection if using cookies.
- Add strict CORS config per environment.
- Add rate limits to all sensitive endpoints.
- Validate all uploads and API connector URLs.
- Add file size limits and malware-safe handling for uploads.
- Add privacy policy and terms.
- Add data deletion/export features.
- Encrypt sensitive connector credentials.
- Add structured logging without leaking secrets.

### Acceptance Criteria

- Basic security review does not find obvious account/data leakage.
- A user can delete their account data.
- Production secrets are never committed or defaulted.

## Phase 8: Deployment And Operations

Purpose: make the app reliable outside your laptop.

### Tasks

- Choose deployment target:
  - Render/Fly.io/Railway for simple PFE demo,
  - VPS with Docker Compose for control,
  - AWS/GCP/Azure for professional scale.

- Use PostgreSQL in production.
- Store model artifacts outside the container or as versioned releases.
- Add object storage for uploads and reports.
- Add CI pipeline:
  - backend tests,
  - frontend lint,
  - frontend build,
  - Docker build.

- Add monitoring:
  - uptime,
  - API errors,
  - background jobs,
  - model inference latency,
  - failed imports,
  - WebSocket connections.

- Add backups.
  - Database daily backup.
  - Artifact backup.
  - Restore procedure.

### Acceptance Criteria

- A fresh deployment can be built from Git.
- CI blocks broken builds.
- You can recover from database failure using backups.
- You can see errors without opening the server terminal.

## Phase 9: PFE Defense Excellence

Purpose: make the project score as high as possible academically.

### Defense Deliverables

- Clear problem statement:
  - energy forecasting,
  - tariff optimization,
  - Moroccan localization,
  - critique of flawed paper methodology.

- Research proof:
  - notebooks showing leakage issue,
  - fair model comparison,
  - metrics table,
  - explanation of why corrected performance is more honest.

- Engineering proof:
  - architecture diagram,
  - database diagram,
  - API endpoint list,
  - security model,
  - deployment diagram.

- Product proof:
  - live demo,
  - user journey,
  - imported real or realistic dataset,
  - PDF report,
  - alert scenario,
  - subscription gating.

- Honesty proof:
  - slide that explicitly separates real features from simulated integrations.
  - explain why simulations exist and how the plan replaces them.

### Demo Script

1. Register or log in as a client.
2. Complete Moroccan setup.
3. Upload real historical consumption CSV.
4. Validate and import readings.
5. View dashboard.
6. Run 24h forecast.
7. Show cost projection and recommendation.
8. Trigger budget/peak alert.
9. Export PDF report.
10. Show admin model registry and system health.
11. Explain academic contribution and leakage correction.

### Acceptance Criteria

- The jury sees research, software engineering, and product thinking.
- You can confidently say what is real, what is simulated, and how each simulation becomes real.

## Priority Backlog

### P0: Must Fix Before Calling It A Product

- Frontend production build failure.
- Docker production env/secrets.
- Per-user or per-organization settings.
- Real CSV import pipeline with validation and stored readings.
- Honest labeling of simulated/demo data.
- Real dashboard based on stored readings.
- Server-side ownership checks everywhere.

### P1: Needed For Client Usefulness

- Forecast uncertainty bands.
- Budget and tariff recommendations.
- Real alert engine based on user readings.
- Report export with source labels and useful insights.
- Model registry backed by database.
- Safe retraining candidate/promote flow.
- Mobile responsive audit.

### P2: Needed For SaaS Maturity

- Real payment provider and signed webhooks.
- Organization/team management.
- Scheduled reports.
- Production monitoring and backups.
- Secure cookie auth.
- Data deletion/export.

### P3: Portfolio Differentiators

- Home Assistant/MQTT integration.
- Appliance-level insights.
- Explainability view for forecasts.
- Carbon emissions estimate.
- Recommendation impact tracking: "you saved X MAD".

## Suggested Timeline

### Week 1: Stabilization

- Fix build.
- Clean warnings.
- Fix Docker/env.
- Create seed data.
- Update README with reliable setup.

### Week 2: Real Data MVP

- Add meter/import tables.
- Build CSV mapping/import wizard.
- Store readings.
- Dashboard reads from stored data.

### Week 3: Forecast Productization

- Standardize preprocessing.
- Add backtesting.
- Add confidence bands.
- Add cost projection and recommendations.

### Week 4: Multi-Tenant And Security

- Per-user/org settings.
- Ownership enforcement audit.
- Upload/API connector hardening.
- Add audit logs.

### Week 5: Reports, Alerts, Polish

- Client-ready PDF.
- Alert rules based on real readings.
- Better empty states.
- Mobile audit.

### Week 6: Deployment And Defense

- CI/CD.
- Production deploy.
- Monitoring/backups.
- Final demo script.
- Defense slides and diagrams.

## Final Product North Star

Do not optimize only for "more features." Optimize for this:

> A client imports or connects their consumption data, understands their future bill risk, receives clear recommendations, and can prove savings over time.

That is what turns the app from a beautiful PFE dashboard into a real product.
