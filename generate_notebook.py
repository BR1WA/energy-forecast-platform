import nbformat as nbf
import os

nb = nbf.v4.new_notebook()

markdown_intro = """# Proper Short-Term Load Forecasting (STLF) using Regression
**Context:** The original DEPM paper treated electricity consumption forecasting as a binary classification problem (High vs. Low), which is practically useless for real-world energy management. Furthermore, it suffered from severe data leakage by using random splits on time-series data.

**Objective:** This notebook implements a **methodologically sound regression approach**.
1. **Target:** Predict actual continuous `Global_active_power` (kW).
2. **Splitting:** Strict **chronological split** (Train: 2006-2009, Test: 2010).
3. **Metrics:** MAE, RMSE, MAPE.
4. **Model:** XGBoost Regressor and a baseline Linear Regression (these can be easily expanded to LSTM)."""

code_imports = """import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import mean_absolute_error, mean_squared_error, mean_absolute_percentage_error
from sklearn.model_selection import TimeSeriesSplit
from xgboost import XGBRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

plt.style.use('seaborn-v0_8-darkgrid')"""

code_load = """print('Loading data...')
df = pd.read_csv('../data/household_power_consumption.txt', sep=';', 
                 na_values=['?'], dtype={'Date': str, 'Time': str})

print('Converting datetime...')
df['Datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='%d/%m/%Y %H:%M:%S')
df = df.drop(columns=['Date', 'Time']).set_index('Datetime')

# Convert columns to numeric
for col in df.columns:
    df[col] = pd.to_numeric(df[col], errors='coerce')

# Forward fill missing values (more appropriate for time series than global median)
df = df.ffill().bfill()

print('Resampling to hourly frequency...')
df_h = df.resample('h').mean()
print(f'Shape after resampling: {df_h.shape}')"""

markdown_features = """## 1. Feature Engineering
We create temporal and lagged features to capture autocorrelation and seasonality.
*Crucially, no future information is leaked into past rows.*"""

code_features = """# Target variable
target_col = 'Global_active_power'

# Temporal Features
df_h['Hour'] = df_h.index.hour
df_h['DayOfWeek'] = df_h.index.dayofweek
df_h['Month'] = df_h.index.month
df_h['IsWeekend'] = (df_h['DayOfWeek'] >= 5).astype(int)

# Lagged Features (Previous 1, 2, 3, 24 hours)
for lag in [1, 2, 3, 24]:
    df_h[f'Lag_{lag}h'] = df_h[target_col].shift(lag)

# Rolling Mean Feature
df_h['Rolling_Mean_24h'] = df_h[target_col].shift(1).rolling(window=24).mean()

# Drop rows with NaN due to lagging
df_h = df_h.dropna()

features = [c for c in df_h.columns if c != target_col]
print(f'Features used: {features}')"""

markdown_split = """## 2. Chronological Train-Test Split
*Never use `train_test_split(random_state=42)` on time-series data!* We will train on data up to the end of 2009, and test on 2010."""

code_split = """train_mask = df_h.index.year < 2010
test_mask = df_h.index.year >= 2010

X_train = df_h.loc[train_mask, features]
y_train = df_h.loc[train_mask, target_col]

X_test = df_h.loc[test_mask, features]
y_test = df_h.loc[test_mask, target_col]

print(f'Training Set: {X_train.shape[0]} hours (up to 2009)')
print(f'Test Set: {X_test.shape[0]} hours (2010 onwards)')

# Scaling
scaler = StandardScaler()
X_train_sc = scaler.fit_transform(X_train)
X_test_sc = scaler.transform(X_test) # Transform only to prevent leakage!"""

markdown_train = """## 3. Model Training & Evaluation"""

code_train = """def evaluate_model(name, y_true, y_pred):
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mape = mean_absolute_percentage_error(y_true, y_pred)
    
    print(f'--- {name} Results ---')
    print(f'MAE:  {mae:.4f} kW')
    print(f'RMSE: {rmse:.4f} kW')
    print(f'MAPE: {mape:.2%}')
    print('-'*20)
    return mae, rmse, mape

# 1. Baseline: Linear Regression
lr = LinearRegression()
lr.fit(X_train_sc, y_train)
preds_lr = lr.predict(X_test_sc)
evaluate_model('Linear Regression', y_test, preds_lr)

# 2. XGBoost Regressor
xgb = XGBRegressor(n_estimators=100, learning_rate=0.1, max_depth=5, random_state=42, n_jobs=-1)
xgb.fit(X_train_sc, y_train)
preds_xgb = xgb.predict(X_test_sc)
evaluate_model('XGBoost Regressor', y_test, preds_xgb)"""

markdown_plot = """## 4. Visualizing Predictions
Let's zoom in on a typical week in the test set to see how closely the model tracks actual consumption."""

code_plot = """# Plot one week (168 hours) from the test set
plot_start = 1000
plot_end = plot_start + 168

plt.figure(figsize=(15, 6))
plt.plot(y_test.values[plot_start:plot_end], label='Actual Consumption (kW)', color='black', linewidth=2)
plt.plot(preds_xgb[plot_start:plot_end], label='XGBoost Prediction', color='red', linestyle='--')
plt.plot(preds_lr[plot_start:plot_end], label='Linear Regression Prediction', color='blue', linestyle=':', alpha=0.7)

plt.title('Short-Term Load Forecasting: 1 Week Comparison')
plt.xlabel('Hours')
plt.ylabel('Global Active Power (kW)')
plt.legend()
plt.tight_layout()
plt.show()"""

nb.cells = [
    nbf.v4.new_markdown_cell(markdown_intro),
    nbf.v4.new_code_cell(code_imports),
    nbf.v4.new_code_cell(code_load),
    nbf.v4.new_markdown_cell(markdown_features),
    nbf.v4.new_code_cell(code_features),
    nbf.v4.new_markdown_cell(markdown_split),
    nbf.v4.new_code_cell(code_split),
    nbf.v4.new_markdown_cell(markdown_train),
    nbf.v4.new_code_cell(code_train),
    nbf.v4.new_markdown_cell(markdown_plot),
    nbf.v4.new_code_cell(code_plot)
]

os.makedirs('notebooks', exist_ok=True)
with open('notebooks/proper_regression_forecasting.ipynb', 'w', encoding='utf-8') as f:
    nbf.write(nb, f)
print('Notebook created successfully.')
