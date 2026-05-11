"""DEPM Prediction Dashboard — FastAPI Backend."""
import json, os, numpy as np, pandas as pd, torch, joblib
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from models import CascadedResNet, make_model

# ── Paths ──
BASE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE, '..', 'models')
STATIC_DIR = os.path.join(BASE, 'static')

app = FastAPI(title="DEPM Dashboard", version="1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ── Load artifacts on startup ──
device = torch.device('cpu')  # CPU for inference

config = json.load(open(os.path.join(MODEL_DIR, 'config.json')))
FEATURES = config['features']
THRESHOLD = config['threshold']

scaler = joblib.load(os.path.join(MODEL_DIR, 'scaler.pkl'))
pca = joblib.load(os.path.join(MODEL_DIR, 'pca.pkl'))

# Load ResNet
N_PCA = pca.n_components_
resnet = CascadedResNet(N_PCA).to(device)
resnet.load_state_dict(torch.load(os.path.join(MODEL_DIR, 'resnet.pt'), map_location=device))
resnet.eval()

# Combined feature dim
N_COMBINED = N_PCA + 32  # PCA + ResNet output

# Load all models
ARCH_NAMES = ['DNN', 'LSTM', 'BiLSTM', 'GRU', 'BiGRU']
loaded_models = {}

for name in ARCH_NAMES:
    # Standalone
    key = f'{name}'
    m = make_model(name, N_COMBINED)
    path = os.path.join(MODEL_DIR, f'standalone_{name.lower()}.pt')
    if os.path.exists(path):
        m.load_state_dict(torch.load(path, map_location=device))
        m.eval()
        loaded_models[key] = {'type': 'standalone', 'dl': m}

    # DEPM
    key_d = f'DEPM-{name}'
    m_d = make_model(name, N_COMBINED)
    path_dl = os.path.join(MODEL_DIR, f'depm_{name.lower()}_dl.pt')
    path_xgb = os.path.join(MODEL_DIR, f'depm_{name.lower()}_xgb.pkl')
    if os.path.exists(path_dl) and os.path.exists(path_xgb):
        m_d.load_state_dict(torch.load(path_dl, map_location=device))
        m_d.eval()
        xgb = joblib.load(path_xgb)
        loaded_models[key_d] = {'type': 'depm', 'dl': m_d, 'xgb': xgb}

# Load results
results_path = os.path.join(MODEL_DIR, 'results.csv')
results_df = pd.read_csv(results_path, index_col=0) if os.path.exists(results_path) else None

print(f"Loaded {len(loaded_models)} models: {list(loaded_models.keys())}")
print(f"Features ({len(FEATURES)}): {FEATURES}")
print(f"PCA components: {N_PCA}, Combined dim: {N_COMBINED}")

# ── Typical hourly profiles (based on dataset statistics) ──
HOURLY_PROFILES = {}
for h in range(24):
    is_weekend = 0
    # Typical consumption patterns by hour
    if 0 <= h <= 5:    # Night
        grp, vol, s1, s2, s3 = 0.05, 240, 0, 0, 2
    elif 6 <= h <= 8:  # Morning
        grp, vol, s1, s2, s3 = 0.12, 239, 2, 1, 5
    elif 9 <= h <= 11: # Late morning
        grp, vol, s1, s2, s3 = 0.08, 240, 1, 1, 3
    elif 12 <= h <= 13:# Lunch
        grp, vol, s1, s2, s3 = 0.15, 238, 5, 2, 4
    elif 14 <= h <= 17:# Afternoon
        grp, vol, s1, s2, s3 = 0.07, 240, 1, 1, 2
    elif 18 <= h <= 20:# Evening peak
        grp, vol, s1, s2, s3 = 0.20, 237, 6, 4, 8
    else:              # Late evening
        grp, vol, s1, s2, s3 = 0.10, 239, 2, 2, 5

    sub_total = s1 + s2 + s3
    HOURLY_PROFILES[h] = {
        'Global_reactive_power': grp, 'Voltage': vol,
        'Sub_metering_1': s1, 'Sub_metering_2': s2, 'Sub_metering_3': s3,
        'Hour': h, 'DayOfWeek': 2, 'Month': 6, 'Season': 2, 'IsWeekend': is_weekend,
        'SubTotal': sub_total,
        'SubRatio_1': s1 / (sub_total + 1e-6),
        'SubRatio_2': s2 / (sub_total + 1e-6),
        'SubRatio_3': s3 / (sub_total + 1e-6),
        'IsHoliday': 0,
    }


def preprocess_and_predict(features_dict: dict, model_name: str):
    """Run full pipeline: scale → PCA → ResNet → model → prediction."""
    # Build feature vector
    vec = np.array([[features_dict.get(f, 0) for f in FEATURES]], dtype=np.float32)

    # Scale + PCA
    vec_sc = scaler.transform(vec)
    vec_pca = pca.transform(vec_sc)

    # ResNet features
    with torch.no_grad():
        t = torch.FloatTensor(vec_pca).to(device)
        z = resnet(t).cpu().numpy()

    # Combine
    combined = np.hstack([vec_pca, z])

    info = loaded_models[model_name]
    if info['type'] == 'standalone':
        with torch.no_grad():
            prob = info['dl'](torch.FloatTensor(combined).to(device)).cpu().item()
        pred = int(prob > 0.5)
        return pred, prob
    else:  # DEPM
        with torch.no_grad():
            dl_feat = info['dl'].features(torch.FloatTensor(combined).to(device)).cpu().numpy()
        hybrid = np.hstack([combined, dl_feat])
        prob = info['xgb'].predict_proba(hybrid)[:, 1][0]
        pred = int(prob > 0.5)
        return pred, float(prob)


# ── Schemas ──
class PredictRequest(BaseModel):
    model_name: str
    Global_reactive_power: float = 0.1
    Voltage: float = 240.0
    Sub_metering_1: float = 1.0
    Sub_metering_2: float = 1.0
    Sub_metering_3: float = 5.0
    Hour: int = 12
    DayOfWeek: int = 2
    Month: int = 6
    Season: int = 2
    IsWeekend: int = 0
    IsHoliday: int = 0


class HourPredictRequest(BaseModel):
    model_name: str
    hour: int = 12
    day_of_week: Optional[int] = 2
    month: Optional[int] = 6
    is_weekend: Optional[int] = 0
    is_holiday: Optional[int] = 0


# ── Routes ──
@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, 'index.html'))


@app.get("/api/models")
def list_models():
    models = []
    for name, info in loaded_models.items():
        models.append({
            'name': name,
            'type': info['type'],
            'category': 'DEPM Hybrid' if info['type'] == 'depm' else 'Standalone DL',
        })
    return {'models': models, 'features': FEATURES, 'threshold': THRESHOLD}


@app.get("/api/stats")
def get_stats():
    if results_df is not None:
        return {
            'results': results_df.reset_index().to_dict(orient='records'),
            'columns': list(results_df.columns),
        }
    return {'results': [], 'columns': []}


@app.post("/api/predict")
def predict(req: PredictRequest):
    if req.model_name not in loaded_models:
        return {'error': f'Model {req.model_name} not found'}
    features = req.dict()
    model_name = features.pop('model_name')
    # Compute derived features
    sub_total = features['Sub_metering_1'] + features['Sub_metering_2'] + features['Sub_metering_3']
    features['SubTotal'] = sub_total
    features['SubRatio_1'] = features['Sub_metering_1'] / (sub_total + 1e-6)
    features['SubRatio_2'] = features['Sub_metering_2'] / (sub_total + 1e-6)
    features['SubRatio_3'] = features['Sub_metering_3'] / (sub_total + 1e-6)

    pred, prob = preprocess_and_predict(features, model_name)
    return {
        'prediction': 'High' if pred == 1 else 'Low',
        'probability': round(prob, 4),
        'confidence': round(max(prob, 1 - prob) * 100, 1),
        'model': model_name,
        'features_used': features,
    }


@app.post("/api/predict-hour")
def predict_hour(req: HourPredictRequest):
    if req.model_name not in loaded_models:
        return {'error': f'Model {req.model_name} not found'}
    features = dict(HOURLY_PROFILES.get(req.hour, HOURLY_PROFILES[12]))
    if req.day_of_week is not None:
        features['DayOfWeek'] = req.day_of_week
    if req.month is not None:
        features['Month'] = req.month
        features['Season'] = {12:0,1:0,2:0,3:1,4:1,5:1,6:2,7:2,8:2,9:3,10:3,11:3}.get(req.month, 2)
    if req.is_weekend is not None:
        features['IsWeekend'] = req.is_weekend
    if req.is_holiday is not None:
        features['IsHoliday'] = req.is_holiday

    pred, prob = preprocess_and_predict(features, req.model_name)
    return {
        'prediction': 'High' if pred == 1 else 'Low',
        'probability': round(prob, 4),
        'confidence': round(max(prob, 1 - prob) * 100, 1),
        'model': req.model_name,
        'hour': req.hour,
        'features_used': features,
    }


@app.get("/api/predict-all-hours")
def predict_all_hours(model_name: str):
    """Predict for all 24 hours — returns a daily consumption profile."""
    if model_name not in loaded_models:
        return {'error': f'Model {model_name} not found'}
    results = []
    for h in range(24):
        features = dict(HOURLY_PROFILES[h])
        pred, prob = preprocess_and_predict(features, model_name)
        results.append({'hour': h, 'prediction': 'High' if pred else 'Low',
                        'probability': round(prob, 4)})
    return {'model': model_name, 'profile': results}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
