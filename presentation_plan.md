# State Defense Presentation Plan (Progress Report)

**Project:** Intelligent Energy Forecasting Platform
**Presenter:** Zouitni Salah Eddine
**Program:** Master SDIA
**Supervisor:** M. Ali Oubelkacem
**Focus:** Shift from Classification to Regression, Advanced Model Performance, and the Web Application

---

## Slide 1: Title Slide
*   **Title:** Progress Report: Developing a Real-Time Energy Forecasting Platform
*   **Details:** Presenter Name, Program, Supervisor Name, Date.

## Slide 2: Progress Since Last Presentation
*   **Goal from Last Defense:** Transition the platform from classification-based telemetry to continuous regression forecasting.
*   **Model Shift:** Replaced basic classification classifiers with regression architectures to predict exact future power consumption (kW).
*   **Model Progression:** Upgraded from baseline sequential models (CNN-BiLSTM) to modern Transformers (PatchTST, iTransformer, SOTA Hybrid).

## Slide 3: The Challenge: Predicting Long-Term Horizons
*   **Short-Term vs. Long-Term:** Predict 24-hour patterns vs. 1-week (168h) and 1-month (720h) horizons.
*   **Limitation of Historical Telemetry:** Energy consumption over weeks/months is highly dependent on exogenous factors (weather, seasonal changes, temperature).
*   **Current Feature Set:** Models currently only trained on multivariate historical load telemetry (Active Power, Reactive Power, Voltage, Intensity, Sub-metering).

## Slide 4: Real Model Evaluation Metrics (Scientific Accuracy)
*   **24-Hour Horizon (Short-Term):**
    *   *CNN-BiLSTM (Baseline):* $R^2 \approx 0.6914$ | MAE $\approx 0.5335$ kW
    *   *PatchTST:* $R^2 \approx 0.8142$ | MAE $\approx 0.4519$ kW
    *   *SOTA Hybrid:* $R^2 \approx 0.8407$ | MAE $\approx 0.4614$ kW
*   **1-Week Horizon (168h):**
    *   *PatchTST:* $R^2 \approx 0.2945$ | MAE $\approx 0.4630$ kW
    *   *iTransformer:* $R^2 \approx 0.3082$ | MAE $\approx 0.4454$ kW
*   **1-Month Horizon (720h):**
    *   *PatchTST:* $R^2 \approx 0.1697$ | MAE $\approx 0.4950$ kW
    *   *iTransformer:* $R^2 \approx 0.2417$ | MAE $\approx 0.4579$ kW
*   *Key Takeaway:* Long-term model performance suffers (low $R^2$ values) due to the absence of weather variables.

## Slide 5: The Full-Stack Web Application Architecture
*   **Challenge:** Developing a functional platform to serve, configure, and monitor these models in real time.
*   **Backend:** FastAPI (Python), SQLite database, and PyTorch (for model inference).
*   **Communication:** WebSockets for streaming simulated/live real-time energy telemetry.
*   **Frontend:** Next.js (React) + Recharts for interactive visualization.

## Slide 6: Key Application Feature: The ML Sandbox
*   **Model Comparison:** Allows operators to compare model forecasts side-by-side.
*   **Dynamic Horizon Selection:** Supports choosing different models for short-term (24h), medium-term (168h), and long-term (720h) predictions.
*   **Unified Model Registry:** Central database to track parameters (epochs, lookback windows, layers) and true training metrics.

## Slide 7: Key Application Feature: Real-Time Alerts & Budgeting
*   **WebSocket Stream:** Telemetry data feeds live charts in the dashboard.
*   **Trigger Logic:** Instantly checks power consumption against defined thresholds.
*   **Alert Panel:** Real-time visual warnings (prepended via WebSockets without page reload) to notify users of high consumption or budget overruns.

## Slide 8: Next Steps: Model Performance Enhancements
*   **Exogenous Weather Features:** Train long-horizon models using a supplementary weather dataset (temperature, humidity, solar radiation).
*   **Calendar Features:** Enhancing time embeddings to better capture weekend/weekday cycles and public holidays.
*   **Model Optimization:** Quantizing PyTorch models for faster CPU-based inference in production.

## Slide 9: Next Steps: Application Improvements & Issue Resolution
*   **User & Operator Roles:** Resolve permission boundaries and UI flows for users (inspecting consumption/budgets) and operators (configuring models).
*   **Alert System Stability:** Finalize triggers and clean up threshold settings.
*   **ML Sandbox Fixes:** Ensure predictions match the selected model for the current horizon correctly on the dashboard.

## Slide 10: Conclusion & Q&A
*   Summary of current progress and opening for jury feedback.
