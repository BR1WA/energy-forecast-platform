"""
⚡ SOTA Residential Energy Forecast System
Main Streamlit application with 4 interactive modules:
  1. 24-Hour Load Forecaster
  2. Sub-Metering Breakdown
  3. Smart Grid Alerts & Cost Estimation
  4. Model Playground
"""
import os
import sys
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from sklearn.metrics import mean_absolute_error, mean_squared_error

# Add app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from predictor import AppPredictor, TARGET_COLS, LOOKBACK, HORIZON

# ─────────────────────────────────────────────
# Page Configuration
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="⚡ SOTA Energy Forecast",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# Custom CSS — Premium Dark UI
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

:root {
    --bg-primary: #0a0b10;
    --bg-card: #131520;
    --bg-card-hover: #1a1d2e;
    --bg-elevated: #1e2235;
    --border: #2a2d42;
    --text-primary: #e2e8f0;
    --text-secondary: #8892b0;
    --text-muted: #5a6178;
    --accent: #6366f1;
    --accent-light: #818cf8;
    --accent-glow: rgba(99, 102, 241, 0.15);
    --green: #10b981;
    --green-glow: rgba(16, 185, 129, 0.15);
    --red: #ef4444;
    --red-glow: rgba(239, 68, 68, 0.15);
    --amber: #f59e0b;
    --amber-glow: rgba(245, 158, 11, 0.15);
    --blue: #3b82f6;
    --purple: #8b5cf6;
    --gradient: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a78bfa 100%);
    --gradient-green: linear-gradient(135deg, #10b981, #34d399);
    --gradient-amber: linear-gradient(135deg, #f59e0b, #fbbf24);
    --gradient-red: linear-gradient(135deg, #ef4444, #f87171);
}

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, sans-serif !important;
}

/* Hide Streamlit branding */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header[data-testid="stHeader"] {
    background: rgba(10, 11, 16, 0.8);
    backdrop-filter: blur(20px);
    border-bottom: 1px solid var(--border);
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: var(--bg-card);
    border-right: 1px solid var(--border);
}
section[data-testid="stSidebar"] .stRadio > label {
    color: var(--text-secondary) !important;
    font-weight: 600 !important;
    font-size: 0.75rem !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

/* Main content */
.main .block-container {
    padding: 2rem 2.5rem;
    max-width: 1400px;
}

/* Hero header */
.hero-title {
    font-size: 2.2rem;
    font-weight: 800;
    background: var(--gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 0.2rem;
    line-height: 1.2;
}
.hero-subtitle {
    color: var(--text-secondary);
    font-size: 0.95rem;
    font-weight: 400;
    margin-bottom: 1.8rem;
}

/* KPI Metric Cards */
.kpi-container {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
}
.kpi-card {
    flex: 1;
    min-width: 180px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 1.2rem 1.4rem;
    position: relative;
    overflow: hidden;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.kpi-card:hover {
    border-color: var(--accent);
    box-shadow: 0 0 20px var(--accent-glow);
    transform: translateY(-2px);
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    border-radius: 14px 14px 0 0;
}
.kpi-card.accent::before { background: var(--gradient); }
.kpi-card.green::before { background: var(--gradient-green); }
.kpi-card.amber::before { background: var(--gradient-amber); }
.kpi-card.red::before { background: var(--gradient-red); }

.kpi-label {
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    margin-bottom: 0.4rem;
}
.kpi-value {
    font-size: 1.8rem;
    font-weight: 800;
    color: var(--text-primary);
    line-height: 1.1;
}
.kpi-unit {
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--text-secondary);
    margin-left: 0.2rem;
}
.kpi-delta {
    font-size: 0.75rem;
    font-weight: 600;
    margin-top: 0.3rem;
}
.kpi-delta.positive { color: var(--green); }
.kpi-delta.negative { color: var(--red); }

/* Glass Card */
.glass-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 1.5rem;
    margin-bottom: 1.2rem;
    transition: all 0.3s ease;
}
.glass-card:hover {
    border-color: rgba(99, 102, 241, 0.3);
    box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2);
}
.glass-card h3 {
    font-size: 1rem;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 0.8rem;
}

/* Alert Banners */
.alert-banner {
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: 1rem;
    display: flex;
    align-items: flex-start;
    gap: 0.8rem;
    animation: slideIn 0.4s ease-out;
}
.alert-banner.peak {
    background: var(--red-glow);
    border: 1px solid rgba(239, 68, 68, 0.3);
}
.alert-banner.savings {
    background: var(--green-glow);
    border: 1px solid rgba(16, 185, 129, 0.3);
}
.alert-banner.info {
    background: var(--accent-glow);
    border: 1px solid rgba(99, 102, 241, 0.3);
}
.alert-icon {
    font-size: 1.4rem;
    flex-shrink: 0;
    margin-top: 0.1rem;
}
.alert-content { flex: 1; }
.alert-title {
    font-weight: 700;
    font-size: 0.85rem;
    margin-bottom: 0.2rem;
}
.alert-text {
    font-size: 0.8rem;
    color: var(--text-secondary);
    line-height: 1.5;
}
.alert-banner.peak .alert-title { color: var(--red); }
.alert-banner.savings .alert-title { color: var(--green); }
.alert-banner.info .alert-title { color: var(--accent-light); }

/* Sub-metering Legend */
.sub-legend {
    display: flex;
    gap: 1.2rem;
    flex-wrap: wrap;
    margin-bottom: 1rem;
}
.sub-legend-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.8rem;
    color: var(--text-secondary);
}
.sub-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
}

/* Metrics comparison table */
.metrics-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
}
.metrics-table th {
    text-align: left;
    padding: 0.7rem 1rem;
    background: var(--bg-elevated);
    color: var(--text-secondary);
    font-weight: 600;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 2px solid var(--border);
}
.metrics-table td {
    padding: 0.7rem 1rem;
    border-bottom: 1px solid var(--border);
    color: var(--text-primary);
}
.metrics-table tr:hover td {
    background: rgba(99, 102, 241, 0.05);
}
.metrics-table .winner {
    color: var(--green);
    font-weight: 700;
}

/* Status badge */
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.2rem 0.6rem;
    border-radius: 20px;
    font-size: 0.7rem;
    font-weight: 600;
}
.status-badge.ready { background: var(--green-glow); color: var(--green); }
.status-badge.missing { background: var(--red-glow); color: var(--red); }

/* Animations */
@keyframes slideIn {
    from { opacity: 0; transform: translateY(-10px); }
    to { opacity: 1; transform: translateY(0); }
}
@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--bg-primary); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

/* Streamlit overrides */
.stSelectbox > div > div {
    background: var(--bg-elevated) !important;
    border-color: var(--border) !important;
}
div[data-testid="stFileUploader"] {
    background: var(--bg-card);
    border: 2px dashed var(--border);
    border-radius: 12px;
    padding: 1rem;
}
div[data-testid="stFileUploader"]:hover {
    border-color: var(--accent);
}
button[kind="primary"] {
    background: var(--gradient) !important;
    border: none !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    padding: 0.6rem 1.5rem !important;
    transition: all 0.3s ease !important;
}
button[kind="primary"]:hover {
    box-shadow: 0 4px 20px var(--accent-glow) !important;
    transform: translateY(-1px);
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.5rem;
    background: var(--bg-card);
    padding: 0.3rem;
    border-radius: 10px;
    border: 1px solid var(--border);
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    padding: 0.5rem 1rem;
    font-weight: 600;
    font-size: 0.85rem;
}
.stTabs [aria-selected="true"] {
    background: var(--accent) !important;
}

/* Download button */
.stDownloadButton > button {
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-primary) !important;
    border-radius: 8px !important;
}
.stDownloadButton > button:hover {
    border-color: var(--accent) !important;
    box-shadow: 0 0 15px var(--accent-glow) !important;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Plotly Theme
# ─────────────────────────────────────────────
PLOTLY_LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(family='Inter, sans-serif', color='#e2e8f0', size=12),
    xaxis=dict(gridcolor='rgba(42,45,66,0.5)', zerolinecolor='rgba(42,45,66,0.5)'),
    yaxis=dict(gridcolor='rgba(42,45,66,0.5)', zerolinecolor='rgba(42,45,66,0.5)'),
    margin=dict(l=20, r=20, t=50, b=20),
    hoverlabel=dict(bgcolor='#1e2235', font_size=12, font_family='Inter'),
    legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(size=11)),
)

def get_layout(**kwargs):
    """Helper to merge layout overrides without duplicate keyword arguments."""
    layout = PLOTLY_LAYOUT.copy()
    for k, v in kwargs.items():
        if isinstance(v, dict) and k in layout and isinstance(layout[k], dict):
            item_copy = layout[k].copy()
            item_copy.update(v)
            layout[k] = item_copy
        else:
            layout[k] = v
    return layout


COLORS = {
    'actual': '#e2e8f0',
    'sota': '#10b981',
    'baseline': '#3b82f6',
    'patchtst': '#e63946',
    'historical': '#6366f1',
    'peak': '#ef4444',
    'off_peak': '#10b981',
    'kitchen': '#f59e0b',
    'laundry': '#3b82f6',
    'climate': '#10b981',
    'other': '#8b5cf6',
}


# ─────────────────────────────────────────────
# Model Loading (Cached)
# ─────────────────────────────────────────────
@st.cache_resource
def load_predictor():
    weights_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'weights')
    return AppPredictor(weights_dir)


def load_sample_options():
    """Load available sample CSVs."""
    samples_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'samples')
    if not os.path.exists(samples_dir):
        return {}

    meta_path = os.path.join(samples_dir, 'sample_metadata.csv')
    if os.path.exists(meta_path):
        meta = pd.read_csv(meta_path)
        return {row['name']: row['description'] for _, row in meta.iterrows()}
    else:
        files = [f for f in os.listdir(samples_dir) if f.endswith('.csv') and f != 'sample_metadata.csv']
        return {f.replace('sample_', '').replace('.csv', ''): f for f in files}


def load_sample_data(sample_name):
    """Load a sample CSV."""
    samples_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'samples')
    csv_path = os.path.join(samples_dir, f'sample_{sample_name}.csv')
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        return df
    return None


# ─────────────────────────────────────────────
# HTML Helpers
# ─────────────────────────────────────────────
def render_kpi_cards(metrics):
    """Render a row of KPI metric cards."""
    html = '<div class="kpi-container">'
    for m in metrics:
        delta_html = ''
        if 'delta' in m and m['delta'] is not None:
            cls = 'positive' if m.get('delta_positive', True) else 'negative'
            sign = '+' if m.get('delta_positive', True) else ''
            delta_html = f'<div class="kpi-delta {cls}">{sign}{m["delta"]}</div>'

        html += f'''
        <div class="kpi-card {m.get('color', 'accent')}">
            <div class="kpi-label">{m['label']}</div>
            <div class="kpi-value">{m['value']}<span class="kpi-unit">{m.get('unit', '')}</span></div>
            {delta_html}
        </div>'''
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def render_alert(alert_type, icon, title, text):
    """Render a styled alert banner."""
    st.markdown(f'''
    <div class="alert-banner {alert_type}">
        <div class="alert-icon">{icon}</div>
        <div class="alert-content">
            <div class="alert-title">{title}</div>
            <div class="alert-text">{text}</div>
        </div>
    </div>
    ''', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 1rem 0 0.5rem;">
        <div style="font-size: 2.5rem; margin-bottom: 0.3rem;">⚡</div>
        <div style="font-size: 1.1rem; font-weight: 800; background: linear-gradient(135deg, #6366f1, #a78bfa);
             -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
            Energy Forecast
        </div>
        <div style="font-size: 0.7rem; color: #5a6178; margin-top: 0.2rem;">
            SOTA Recurrent-Attention Model
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Navigation
    page = st.radio(
        "NAVIGATION",
        ["🔮 Load Forecaster", "📊 Sub-Metering", "⚡ Smart Grid Alerts", "🧪 Model Playground"],
        index=0,
        label_visibility="visible",
    )

    st.divider()

    # Model selector
    predictor = load_predictor()
    available_models = predictor.get_available_models()

    if available_models:
        selected_model = st.selectbox(
            "Active Model",
            available_models,
            index=0,
            help="Select the model to use for forecasting."
        )
    else:
        selected_model = None
        st.error("No model weights found!")

    # Model status
    st.markdown("#### Model Status")
    for model_name, loaded in predictor.models_loaded.items():
        badge = 'ready' if loaded else 'missing'
        icon = '●' if loaded else '○'
        label = 'Ready' if loaded else 'Missing'
        st.markdown(
            f'<span class="status-badge {badge}">{icon} {model_name}: {label}</span>',
            unsafe_allow_html=True
        )

    st.divider()

    st.markdown("""
    <div style="font-size: 0.7rem; color: #5a6178; padding: 0.5rem 0;">
        <strong>Architecture:</strong> Multi-Scale Patching + RevIN + Calendar Embeddings +
        Cross-Variable Attention<br><br>
        <strong>Dataset:</strong> IHEPC (Clamart, France)<br>
        <strong>Horizon:</strong> 24 hours ahead<br>
        <strong>Lookback:</strong> 96 hours (4 days)
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Helper: Data Loading Widget
# ─────────────────────────────────────────────
def data_input_widget(key_prefix="main", require_actuals=False):
    """Reusable widget for loading sample data or uploading CSV."""
    samples = load_sample_options()

    input_method = st.radio(
        "Data Source",
        ["📁 Sample Data", "📤 Upload CSV"],
        horizontal=True,
        key=f"{key_prefix}_input_method",
        label_visibility="collapsed",
    )

    df = None

    if input_method == "📁 Sample Data":
        if samples:
            sample_options = {f"{name}: {desc}": name for name, desc in samples.items()}
            selected = st.selectbox(
                "Select a sample window",
                list(sample_options.keys()),
                key=f"{key_prefix}_sample_select"
            )
            sample_name = sample_options[selected]
            df = load_sample_data(sample_name)
            if df is not None:
                st.success(f"Loaded **{len(df)} hours** — {df.index[0].strftime('%b %d %Y')} to {df.index[-1].strftime('%b %d %Y')}")
        else:
            st.warning("No sample data found. Run `generate_samples.py` first.")
    else:
        uploaded = st.file_uploader(
            f"Upload CSV ({LOOKBACK}+ hourly rows, 7 target columns)",
            type=["csv"],
            key=f"{key_prefix}_upload"
        )
        if uploaded is not None:
            try:
                df = pd.read_csv(uploaded, index_col=0, parse_dates=True)
                if not isinstance(df.index, pd.DatetimeIndex):
                    st.error("First column must be a parseable datetime index.")
                    df = None
                elif len(df) < LOOKBACK:
                    st.error(f"Need at least {LOOKBACK} rows. Got {len(df)}.")
                    df = None
                else:
                    missing = [c for c in TARGET_COLS if c not in df.columns]
                    if missing:
                        st.error(f"Missing columns: {missing}")
                        df = None
                    else:
                        st.success(f"Uploaded **{len(df)} hours** of data.")
            except Exception as e:
                st.error(f"Error reading CSV: {e}")

    return df


# ═════════════════════════════════════════════
# MODULE 1: 24-Hour Load Forecaster
# ═════════════════════════════════════════════
if page == "🔮 Load Forecaster":
    st.markdown('<div class="hero-title">24-Hour Load Forecaster</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-subtitle">Select a historical 4-day window and generate a 24-hour demand forecast using the SOTA model.</div>',
        unsafe_allow_html=True
    )

    if selected_model is None:
        render_alert('info', '📥', 'Model Weights Required',
                     'Please download the model weights from Kaggle and place them in <code>app_forecast/weights/</code>.')
        st.stop()

    # Data input
    df_full = data_input_widget("forecaster")

    if df_full is not None:
        # Split into input (96h) and any remaining actuals
        df_input = df_full.iloc[:LOOKBACK][TARGET_COLS]
        has_actuals = len(df_full) >= LOOKBACK + HORIZON
        df_actuals = df_full.iloc[LOOKBACK:LOOKBACK + HORIZON][TARGET_COLS] if has_actuals else None

        col_btn, col_info = st.columns([1, 3])
        with col_btn:
            run_forecast = st.button("🚀 Generate Forecast", type="primary", use_container_width=True)

        if run_forecast or st.session_state.get('forecast_result') is not None:
            if run_forecast:
                with st.spinner("Running model inference..."):
                    forecast_df = predictor.predict(df_input, selected_model)
                    st.session_state['forecast_result'] = forecast_df
                    st.session_state['forecast_input'] = df_input
                    st.session_state['forecast_actuals'] = df_actuals
                    st.session_state['forecast_model'] = selected_model

            forecast_df = st.session_state['forecast_result']
            df_input = st.session_state['forecast_input']
            df_actuals = st.session_state.get('forecast_actuals')
            used_model = st.session_state.get('forecast_model', selected_model)

            gap_forecast = forecast_df['Global_active_power'].values

            # KPI cards
            peak_kw = gap_forecast.max()
            avg_kw = gap_forecast.mean()
            total_kwh = gap_forecast.sum()
            min_kw = gap_forecast.min()

            kpis = [
                {'label': 'Peak Demand', 'value': f'{peak_kw:.2f}', 'unit': 'kW', 'color': 'red'},
                {'label': 'Average Load', 'value': f'{avg_kw:.2f}', 'unit': 'kW', 'color': 'accent'},
                {'label': 'Total Energy', 'value': f'{total_kwh:.1f}', 'unit': 'kWh', 'color': 'amber'},
                {'label': 'Min Load', 'value': f'{min_kw:.2f}', 'unit': 'kW', 'color': 'green'},
            ]

            if df_actuals is not None:
                actual_gap = df_actuals['Global_active_power'].values
                mae = mean_absolute_error(actual_gap, gap_forecast)
                kpis.append({'label': 'Forecast MAE', 'value': f'{mae:.3f}', 'unit': 'kW', 'color': 'accent'})

            render_kpi_cards(kpis)

            # Main forecast chart
            fig = go.Figure()

            # Historical context
            fig.add_trace(go.Scatter(
                x=df_input.index, y=df_input['Global_active_power'],
                name='Historical Context (96h)',
                line=dict(color=COLORS['historical'], width=1.5),
                fill='tozeroy',
                fillcolor='rgba(99, 102, 241, 0.08)',
                hovertemplate='<b>%{x}</b><br>Power: %{y:.3f} kW<extra>Historical</extra>'
            ))

            # Forecast
            forecast_color = COLORS['patchtst'] if 'PatchTST' in used_model else (COLORS['sota'] if 'SOTA' in used_model else COLORS['baseline'])
            fig.add_trace(go.Scatter(
                x=forecast_df.index, y=gap_forecast,
                name=f'{used_model} Forecast (24h)',
                line=dict(color=forecast_color, width=2.5),
                fill='tozeroy',
                fillcolor=f'rgba({",".join(str(int(forecast_color.lstrip("#")[i:i+2], 16)) for i in (0,2,4))}, 0.12)',
                hovertemplate='<b>%{x}</b><br>Predicted: %{y:.3f} kW<extra>Forecast</extra>'
            ))

            # Actuals overlay
            if df_actuals is not None:
                fig.add_trace(go.Scatter(
                    x=df_actuals.index, y=actual_gap,
                    name='Actual (Ground Truth)',
                    line=dict(color=COLORS['actual'], width=2, dash='dot'),
                    hovertemplate='<b>%{x}</b><br>Actual: %{y:.3f} kW<extra>Ground Truth</extra>'
                ))

            # Forecast boundary
            boundary_time = df_input.index[-1]
            fig.add_vline(
                x=boundary_time, line=dict(color='rgba(255,255,255,0.2)', width=1, dash='dash'),
            )
            fig.add_annotation(
                x=boundary_time, y=1.05, yref='paper',
                text='Forecast Start ▶', showarrow=False,
                font=dict(size=10, color='#8892b0'),
            )

            fig.update_layout(
                **get_layout(
                    title=dict(text='Global Active Power: Historical + Forecast', font=dict(size=16)),
                    xaxis_title='Time',
                    yaxis_title='Power (kW)',
                    height=450,
                    hovermode='x unified',
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                )
            )

            st.plotly_chart(fig, use_container_width=True)

            # Hourly bar chart
            with st.expander("📊 Hourly Forecast Breakdown", expanded=False):
                fig_bar = go.Figure()
                bar_colors = [COLORS['peak'] if h >= 6 and h < 22 else COLORS['off_peak']
                              for h in forecast_df.index.hour]
                fig_bar.add_trace(go.Bar(
                    x=[h.strftime('%H:%M') for h in forecast_df.index],
                    y=gap_forecast,
                    marker_color=bar_colors,
                    hovertemplate='<b>%{x}</b><br>%{y:.3f} kW<extra></extra>',
                ))
                fig_bar.update_layout(
                    **get_layout(
                        title='Hourly Predicted Load (Red = Peak Tariff, Green = Off-Peak)',
                        height=300,
                        xaxis_title='Hour', yaxis_title='Power (kW)',
                        showlegend=False,
                    )
                )
                st.plotly_chart(fig_bar, use_container_width=True)

            # Download
            csv_data = forecast_df.to_csv()
            st.download_button(
                "📥 Download Forecast CSV",
                csv_data,
                file_name="forecast_24h.csv",
                mime="text/csv",
            )


# ═════════════════════════════════════════════
# MODULE 2: Sub-Metering Breakdown
# ═════════════════════════════════════════════
elif page == "📊 Sub-Metering":
    st.markdown('<div class="hero-title">Sub-Metering Breakdown</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-subtitle">See exactly <em>where</em> your forecasted energy will be consumed — kitchen, laundry, climate control, or unmetered devices.</div>',
        unsafe_allow_html=True
    )

    forecast_df = st.session_state.get('forecast_result')

    if forecast_df is None:
        render_alert('info', '🔮', 'Generate a Forecast First',
                     'Go to the <strong>Load Forecaster</strong> module and generate a 24-hour forecast before viewing the breakdown.')
        st.stop()

    breakdown, total_wh = AppPredictor.compute_sub_metering_breakdown(forecast_df)

    # Compute "other" per hour safely in main module scope to prevent NameError in heatmap
    gap_wh_per_hour = forecast_df['Global_active_power'].clip(lower=0).values * 1000.0
    sub_total_per_hour = (
        forecast_df['Sub_metering_1'].clip(lower=0).values +
        forecast_df['Sub_metering_2'].clip(lower=0).values +
        forecast_df['Sub_metering_3'].clip(lower=0).values
    )
    other_per_hour = np.maximum(0, gap_wh_per_hour - sub_total_per_hour)

    # KPI cards
    kpis = []
    for name, data in breakdown.items():
        kpis.append({
            'label': f'{data["icon"]} {name}',
            'value': f'{data["wh"]:.0f}',
            'unit': 'Wh',
            'color': 'amber' if 'Kitchen' in name else ('accent' if 'Laundry' in name else
                     ('green' if 'Climate' in name else 'accent')),
        })
    render_kpi_cards(kpis)

    col_donut, col_bar = st.columns([1, 2])

    with col_donut:
        # Donut chart
        fig_donut = go.Figure(data=[go.Pie(
            labels=[f'{d["icon"]} {n}' for n, d in breakdown.items()],
            values=[d['wh'] for d in breakdown.values()],
            hole=0.6,
            marker=dict(colors=[d['color'] for d in breakdown.values()],
                        line=dict(color='#131520', width=2)),
            textposition='outside',
            textinfo='label+percent',
            textfont=dict(size=11),
            hovertemplate='<b>%{label}</b><br>%{value:.0f} Wh (%{percent})<extra></extra>',
        )])
        fig_donut.update_layout(
            **get_layout(
                title=dict(text='24h Energy Distribution', font=dict(size=14)),
                height=380,
                showlegend=False,
                annotations=[dict(text=f'{total_wh:.0f}<br>Wh', x=0.5, y=0.5, font_size=18,
                                  font_color='#e2e8f0', showarrow=False, font_family='Inter')],
            )
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    with col_bar:
        # Hourly stacked bar
        fig_stack = go.Figure()

        sub_cols = {
            'Sub_metering_1': ('Kitchen', COLORS['kitchen']),
            'Sub_metering_2': ('Laundry', COLORS['laundry']),
            'Sub_metering_3': ('Climate', COLORS['climate']),
        }

        hours_str = [h.strftime('%H:%M') for h in forecast_df.index]

        for col_name, (label, color) in sub_cols.items():
            fig_stack.add_trace(go.Bar(
                x=hours_str,
                y=forecast_df[col_name].clip(lower=0).values,
                name=label,
                marker_color=color,
                hovertemplate=f'<b>{label}</b><br>%{{x}}: %{{y:.1f}} Wh<extra></extra>',
            ))

        # Use other_per_hour calculated in main scope

        fig_stack.add_trace(go.Bar(
            x=hours_str, y=other_per_hour,
            name='Other', marker_color=COLORS['other'],
            hovertemplate='<b>Other</b><br>%{x}: %{y:.1f} Wh<extra></extra>',
        ))

        fig_stack.update_layout(
            **get_layout(
                barmode='stack',
                title=dict(text='Hourly Sub-Metering Breakdown', font=dict(size=14)),
                height=380,
                xaxis_title='Hour', yaxis_title='Energy (Wh)',
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            )
        )
        st.plotly_chart(fig_stack, use_container_width=True)

    # Heatmap
    with st.expander("🗺️ Hourly Dominance Heatmap", expanded=False):
        categories = ['Kitchen', 'Laundry', 'Climate', 'Other']
        heatmap_data = np.array([
            forecast_df['Sub_metering_1'].clip(lower=0).values,
            forecast_df['Sub_metering_2'].clip(lower=0).values,
            forecast_df['Sub_metering_3'].clip(lower=0).values,
            other_per_hour,
        ])

        fig_heat = go.Figure(data=go.Heatmap(
            z=heatmap_data,
            x=hours_str,
            y=categories,
            colorscale=[[0, '#131520'], [0.5, '#6366f1'], [1, '#a78bfa']],
            hovertemplate='<b>%{y}</b> at %{x}<br>%{z:.1f} Wh<extra></extra>',
        ))
        fig_heat.update_layout(
            **get_layout(
                title='Consumption Intensity by Category & Hour',
                height=250,
            )
        )
        st.plotly_chart(fig_heat, use_container_width=True)


# ═════════════════════════════════════════════
# MODULE 3: Smart Grid Alerts & Cost
# ═════════════════════════════════════════════
elif page == "⚡ Smart Grid Alerts":
    st.markdown('<div class="hero-title">Smart Grid Alerts & Cost</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-subtitle">Identify peak demand hours, estimate costs using French EDF tariffs, and get actionable recommendations to reduce your bill.</div>',
        unsafe_allow_html=True
    )

    forecast_df = st.session_state.get('forecast_result')

    if forecast_df is None:
        render_alert('info', '🔮', 'Generate a Forecast First',
                     'Go to the <strong>Load Forecaster</strong> module and generate a 24-hour forecast before viewing alerts.')
        st.stop()

    cost_data = AppPredictor.compute_cost_estimate(forecast_df)
    alerts = AppPredictor.detect_peak_alerts(forecast_df)

    # Cost KPIs
    render_kpi_cards([
        {'label': 'Estimated Daily Cost', 'value': f'€{cost_data["total_cost"]:.2f}', 'unit': '', 'color': 'amber'},
        {'label': 'Total Consumption', 'value': f'{cost_data["total_kwh"]:.1f}', 'unit': 'kWh', 'color': 'accent'},
        {'label': 'Peak Hours Cost', 'value': f'€{cost_data["peak_cost"]:.2f}', 'unit': '', 'color': 'red'},
        {'label': 'Off-Peak Cost', 'value': f'€{cost_data["off_peak_cost"]:.2f}', 'unit': '', 'color': 'green'},
    ])

    # Alerts
    for alert in alerts:
        render_alert(
            'peak', '🔴', 'Peak Load Alert',
            alert['message']
        )

    # Savings recommendation
    if cost_data['peak_kwh'] > 0:
        potential_savings = cost_data['peak_kwh'] * 0.15 * cost_data['savings_per_kwh']
        render_alert(
            'savings', '💡', f'Potential Savings: €{potential_savings:.2f}/day',
            f'By shifting ~15% of your peak-hour consumption ({cost_data["peak_kwh"]*0.15:.1f} kWh) '
            f'to off-peak hours (after 22:00), you could save approximately '
            f'€{potential_savings:.2f} per day (€{potential_savings*30:.1f}/month). '
            f'Consider running washing machines, dishwashers, and dryers during off-peak windows.'
        )

    # Cost breakdown chart
    col_cost, col_tariff = st.columns([2, 1])

    with col_cost:
        fig_cost = go.Figure()

        hours_str = [h.strftime('%H:%M') for h in forecast_df.index]
        bar_colors = [COLORS['peak'] if p else COLORS['off_peak'] for p in cost_data['is_peak']]

        fig_cost.add_trace(go.Bar(
            x=hours_str, y=cost_data['hourly_costs'],
            marker_color=bar_colors,
            name='Hourly Cost',
            hovertemplate='<b>%{x}</b><br>Cost: €%{y:.4f}<br>%{customdata[0]:.3f} kWh<extra></extra>',
            customdata=np.array([cost_data['hourly_kwh']]).T,
        ))

        # Peak threshold line
        if len(alerts) > 0:
            peak_kw = alerts[0]['max_kw']
            peak_cost = peak_kw * max(0.1369, 0.1056)
            fig_cost.add_hline(
                y=peak_cost * 0.5, line=dict(color='rgba(239,68,68,0.4)', width=1, dash='dash'),
                annotation_text='High cost zone', annotation_font_color='#ef4444',
            )

        fig_cost.update_layout(
            **get_layout(
                title=dict(text='Hourly Electricity Cost (€)', font=dict(size=14)),
                height=350,
                xaxis_title='Hour', yaxis_title='Cost (€)',
                showlegend=False,
            )
        )
        st.plotly_chart(fig_cost, use_container_width=True)

    with col_tariff:
        # Peak vs Off-Peak pie
        fig_pie = go.Figure(data=[go.Pie(
            labels=['Peak (06-22h)', 'Off-Peak (22-06h)'],
            values=[cost_data['peak_kwh'], cost_data['off_peak_kwh']],
            hole=0.5,
            marker=dict(colors=[COLORS['peak'], COLORS['off_peak']],
                        line=dict(color='#131520', width=2)),
            textinfo='label+percent',
            textfont=dict(size=10),
            hovertemplate='<b>%{label}</b><br>%{value:.1f} kWh<extra></extra>',
        )])
        fig_pie.update_layout(
            **get_layout(
                title=dict(text='Peak vs Off-Peak', font=dict(size=14)),
                height=350,
                showlegend=False,
            )
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # Tariff info
    with st.expander("ℹ️ Tariff Information (EDF France)", expanded=False):
        st.markdown("""
        | Tariff Period | Hours | Rate (€/kWh) |
        |:---|:---|:---|
        | **Heures Pleines** (Peak) | 06:00 – 22:00 | €0.1369 |
        | **Heures Creuses** (Off-Peak) | 22:00 – 06:00 | €0.1056 |

        *Based on standard EDF residential "Heures Creuses" contract pricing.*
        """)


# ═════════════════════════════════════════════
# MODULE 4: Model Playground
# ═════════════════════════════════════════════
elif page == "🧪 Model Playground":
    st.markdown('<div class="hero-title">Model Playground</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-subtitle">Compare SOTA vs CNN-BiLSTM predictions against ground truth. Upload any test window or select a sample to evaluate both models live.</div>',
        unsafe_allow_html=True
    )

    if len(predictor.get_available_models()) == 0:
        render_alert('info', '📥', 'Model Weights Required',
                     'Download model weights and place them in <code>app_forecast/weights/</code>.')
        st.stop()

    df_full = data_input_widget("playground", require_actuals=True)

    if df_full is not None:
        if len(df_full) < LOOKBACK + HORIZON:
            render_alert('info', '📏', 'Need More Data',
                         f'The playground requires at least {LOOKBACK + HORIZON} rows '
                         f'({LOOKBACK}h lookback + {HORIZON}h actuals). You provided {len(df_full)} rows.')
            st.stop()

        df_input = df_full.iloc[:LOOKBACK][TARGET_COLS]
        df_actuals = df_full.iloc[LOOKBACK:LOOKBACK + HORIZON][TARGET_COLS]

        run_playground = st.button("🔬 Run Comparison", type="primary", use_container_width=False)

        if run_playground:
            results = {}

            with st.spinner("Running inference on all available models..."):
                for model_name in predictor.get_available_models():
                    try:
                        pred = predictor.predict(df_input, model_name)
                        pred_gap = pred['Global_active_power'].values
                        actual_gap = df_actuals['Global_active_power'].values

                        mae = mean_absolute_error(actual_gap, pred_gap)
                        rmse = np.sqrt(mean_squared_error(actual_gap, pred_gap))
                        epsilon = 1e-8
                        mape = np.mean(np.abs((actual_gap - pred_gap) / (actual_gap + epsilon))) * 100

                        results[model_name] = {
                            'forecast': pred,
                            'mae': mae,
                            'rmse': rmse,
                            'mape': mape,
                            'predictions': pred_gap,
                        }
                    except Exception as e:
                        st.warning(f"Error running {model_name}: {e}")

            if results:
                st.session_state['playground_results'] = results
                st.session_state['playground_actuals'] = df_actuals
                st.session_state['playground_input'] = df_input

        results = st.session_state.get('playground_results')
        df_actuals = st.session_state.get('playground_actuals')
        df_input_pg = st.session_state.get('playground_input')

        if results and df_actuals is not None:
            actual_gap = df_actuals['Global_active_power'].values

            # Metrics comparison KPIs
            best_model = min(results, key=lambda m: results[m]['mae'])
            kpis = []
            for model_name, res in results.items():
                is_best = model_name == best_model
                kpis.append({
                    'label': f'{"🏆 " if is_best else ""}{model_name} MAE',
                    'value': f'{res["mae"]:.4f}',
                    'unit': 'kW',
                    'color': 'green' if is_best else 'accent',
                })
            render_kpi_cards(kpis)

            # Main comparison chart
            fig_compare = go.Figure()

            # Historical
            fig_compare.add_trace(go.Scatter(
                x=df_input_pg.index, y=df_input_pg['Global_active_power'],
                name='Historical Input',
                line=dict(color=COLORS['historical'], width=1.2),
                fill='tozeroy',
                fillcolor='rgba(99, 102, 241, 0.06)',
                hovertemplate='<b>%{x}</b><br>%{y:.3f} kW<extra>Input</extra>'
            ))

            # Actuals
            fig_compare.add_trace(go.Scatter(
                x=df_actuals.index, y=actual_gap,
                name='Actual (Ground Truth)',
                line=dict(color=COLORS['actual'], width=2.5),
                hovertemplate='<b>%{x}</b><br>Actual: %{y:.3f} kW<extra>Truth</extra>'
            ))

            # Model predictions
            model_colors = {'SOTA Model': COLORS['sota'], 'CNN-BiLSTM': COLORS['baseline'], 'PatchTST': COLORS['patchtst']}
            for model_name, res in results.items():
                color = model_colors.get(model_name, '#f59e0b')
                fig_compare.add_trace(go.Scatter(
                    x=res['forecast'].index, y=res['predictions'],
                    name=f'{model_name} (MAE: {res["mae"]:.3f})',
                    line=dict(color=color, width=2, dash='solid' if 'SOTA' in model_name else 'dashdot'),
                    hovertemplate=f'<b>%{{x}}</b><br>{model_name}: %{{y:.3f}} kW<extra></extra>'
                ))

            # Forecast boundary
            boundary = df_input_pg.index[-1]
            fig_compare.add_vline(x=boundary, line=dict(color='rgba(255,255,255,0.15)', width=1, dash='dash'))
            fig_compare.add_annotation(
                x=boundary, y=1.05, yref='paper',
                text='Forecast Start ▶', showarrow=False,
                font=dict(size=10, color='#8892b0'),
            )

            fig_compare.update_layout(
                **get_layout(
                    title=dict(text='Model Comparison: Actual vs Predicted', font=dict(size=16)),
                    height=480,
                    xaxis_title='Time', yaxis_title='Power (kW)',
                    hovermode='x unified',
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                )
            )
            st.plotly_chart(fig_compare, use_container_width=True)

            # Metrics table
            st.markdown('<div class="glass-card"><h3>📋 Detailed Metrics Comparison</h3>', unsafe_allow_html=True)

            table_html = '''
            <table class="metrics-table">
            <thead><tr>
                <th>Model</th><th>MAE (kW)</th><th>RMSE (kW)</th><th>MAPE (%)</th><th>Peak Error (kW)</th>
            </tr></thead><tbody>'''

            for model_name, res in results.items():
                is_best = model_name == best_model
                peak_err = abs(actual_gap.max() - res['predictions'].max())
                cls = ' class="winner"' if is_best else ''
                badge = ' 🏆' if is_best else ''
                table_html += f'''
                <tr>
                    <td{cls}>{model_name}{badge}</td>
                    <td{cls}>{res["mae"]:.4f}</td>
                    <td{cls}>{res["rmse"]:.4f}</td>
                    <td{cls}>{res["mape"]:.2f}%</td>
                    <td{cls}>{peak_err:.4f}</td>
                </tr>'''

            table_html += '</tbody></table>'
            st.markdown(table_html, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # Improvement summary
            if len(results) >= 2 and 'SOTA Model' in results and 'CNN-BiLSTM' in results:
                sota_mae = results['SOTA Model']['mae']
                cnn_mae = results['CNN-BiLSTM']['mae']
                improvement = (cnn_mae - sota_mae) / cnn_mae * 100

                if improvement > 0:
                    render_alert(
                        'savings', '📈', f'SOTA outperforms CNN-BiLSTM by {improvement:.1f}%',
                        f'On this window, the SOTA model achieves an MAE of {sota_mae:.4f} kW compared to '
                        f'{cnn_mae:.4f} kW for CNN-BiLSTM — a <strong>{improvement:.1f}% reduction</strong> in prediction error.'
                    )
                else:
                    render_alert(
                        'info', '📊', 'CNN-BiLSTM edges ahead on this window',
                        f'On this specific window, CNN-BiLSTM achieves MAE {cnn_mae:.4f} kW vs SOTA {sota_mae:.4f} kW. '
                        f'This can happen on low-variance sequences where the simpler model suffices.'
                    )

            # Error distribution
            with st.expander("📉 Hourly Prediction Error", expanded=False):
                fig_err = go.Figure()
                for model_name, res in results.items():
                    errors = actual_gap - res['predictions']
                    color = model_colors.get(model_name, '#f59e0b')
                    fig_err.add_trace(go.Bar(
                        x=[h.strftime('%H:%M') for h in res['forecast'].index],
                        y=errors,
                        name=model_name,
                        marker_color=color,
                        opacity=0.7,
                        hovertemplate=f'<b>{model_name}</b><br>%{{x}}: %{{y:.3f}} kW error<extra></extra>',
                    ))
                fig_err.update_layout(
                    **get_layout(
                        title='Hourly Prediction Error (Actual − Predicted)',
                        height=300,
                        barmode='group',
                        xaxis_title='Hour', yaxis_title='Error (kW)',
                    )
                )
                st.plotly_chart(fig_err, use_container_width=True)


# ─────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div style="text-align: center; padding: 1rem 0; color: #5a6178; font-size: 0.75rem;">
    <strong>⚡ SOTA Energy Forecast System</strong> — Advanced Recurrent-Attention Hybrid Model<br>
    Individual Household Electric Power Consumption (IHEPC) Dataset · Clamart, France · 2006–2010<br>
    Built with PyTorch, Streamlit & Plotly
</div>
""", unsafe_allow_html=True)
