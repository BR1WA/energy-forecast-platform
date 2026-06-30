import numpy as np
import torch
from sklearn.metrics import r2_score

def compute_metrics(y_true, y_pred, inference_time_total=None, num_samples=None, num_batches=None):
    """
    Computes a comprehensive suite of forecasting metrics.
    Works with both numpy arrays and torch tensors.
    """
    if isinstance(y_true, torch.Tensor):
        y_true = y_true.detach().cpu().numpy()
    if isinstance(y_pred, torch.Tensor):
        y_pred = y_pred.detach().cpu().numpy()
        
    y_true_flat = y_true.flatten()
    y_pred_flat = y_pred.flatten()
    
    # MAE
    mae = np.mean(np.abs(y_true_flat - y_pred_flat))
    
    # RMSE
    rmse = np.sqrt(np.mean(np.square(y_true_flat - y_pred_flat)))
    
    # MAPE (Mean Absolute Percentage Error)
    # Adding a small epsilon to avoid division by zero
    epsilon = np.finfo(np.float64).eps
    mape = np.mean(np.abs((y_true_flat - y_pred_flat) / (np.maximum(np.abs(y_true_flat), epsilon)))) * 100
    
    # sMAPE (Symmetric Mean Absolute Percentage Error)
    smape = np.mean(2.0 * np.abs(y_true_flat - y_pred_flat) / (np.abs(y_true_flat) + np.abs(y_pred_flat) + epsilon)) * 100
    
    # R2
    r2 = r2_score(y_true_flat, y_pred_flat)
    
    metrics = {
        "mae": float(mae),
        "rmse": float(rmse),
        "mape": float(mape),
        "smape": float(smape),
        "r2": float(r2)
    }
    
    if inference_time_total is not None and num_samples is not None:
        metrics["inference_time_per_sample_ms"] = (inference_time_total / num_samples) * 1000
    if inference_time_total is not None and num_batches is not None:
        metrics["inference_time_per_batch_ms"] = (inference_time_total / num_batches) * 1000
        
    return metrics
