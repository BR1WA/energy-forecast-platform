import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
import glob
import json

def compute_metrics(actual, predicted):
    """
    Computes rigorous forecasting metrics.
    actual, predicted should be numpy arrays of shape (Batch, Horizon, Channels)
    """
    mae = np.mean(np.abs(predicted - actual))
    mse = np.mean((predicted - actual) ** 2)
    rmse = np.sqrt(mse)
    
    # Avoid division by zero in MAPE
    epsilon = 1e-8
    mape = np.mean(np.abs((actual - predicted) / (actual + epsilon))) * 100
    
    # sMAPE
    smape = np.mean(2.0 * np.abs(predicted - actual) / (np.abs(actual) + np.abs(predicted) + epsilon)) * 100
    
    # R squared
    ss_res = np.sum((actual - predicted) ** 2)
    ss_tot = np.sum((actual - np.mean(actual)) ** 2)
    r2 = 1 - (ss_res / (ss_tot + epsilon))
    
    return {
        "MAE": float(mae),
        "RMSE": float(rmse),
        "MAPE": float(mape),
        "sMAPE": float(smape),
        "R2": float(r2)
    }

def generate_comparison_table(experiments_dir="training/experiments"):
    """
    Scans the experiments directory, aggregates results, and generates Markdown tables.
    """
    results = []
    for file in glob.glob(f"{experiments_dir}/*.json"):
        with open(file, 'r') as f:
            data = json.load(f)
            
        metrics = data.get("metrics", {}).get("final", {})
        config = data.get("config", {})
        
        # We assume the best/final metrics are recorded
        results.append({
            "Model": config.get("model", {}).get("name", "Unknown"),
            "Horizon": config.get("model", {}).get("forecast_horizon", "Unknown"),
            "Lookback": config.get("model", {}).get("lookback", "Unknown"),
            "MAE": metrics.get("MAE", 0),
            "RMSE": metrics.get("RMSE", 0),
            "MAPE": metrics.get("MAPE", 0),
            "sMAPE": metrics.get("sMAPE", 0),
            "R2": metrics.get("R2", 0)
        })
        
    df = pd.DataFrame(results)
    if df.empty:
        print("No experiment results found.")
        return
        
    # Sort by Horizon, then by R2 descending
    df = df.sort_values(by=["Horizon", "R2"], ascending=[True, False])
    
    markdown = df.to_markdown(index=False, floatfmt=".4f")
    
    with open(os.path.join(experiments_dir, "comparison_table.md"), "w") as f:
        f.write("# Model Comparison Benchmark\n\n")
        f.write(markdown)
        f.write("\n")
        
    df.to_csv(os.path.join(experiments_dir, "metrics.csv"), index=False)
    print("Generated evaluation tables successfully.")

if __name__ == "__main__":
    generate_comparison_table()
