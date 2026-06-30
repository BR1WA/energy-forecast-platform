import os
import glob
import json
import pandas as pd

def generate_leaderboard(experiments_dir="training/experiments"):
    """
    Scans all experiment results and generates a leaderboard markdown file.
    """
    results = []
    
    # Load all json results
    for file in glob.glob(f"{experiments_dir}/*.json"):
        with open(file, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                continue
                
        metrics = data.get("metrics", {}).get("final", {})
        if not metrics:
            continue
            
        config = data.get("config", {})
        
        results.append({
            "Model": config.get("model", {}).get("name", "Unknown"),
            "Horizon": config.get("model", {}).get("forecast_horizon", "Unknown"),
            "MAE": metrics.get("MAE", 0.0),
            "RMSE": metrics.get("RMSE", 0.0),
            "MAPE": metrics.get("MAPE", 0.0),
            "sMAPE": metrics.get("sMAPE", 0.0),
            "R2": metrics.get("R2", 0.0)
        })
        
    df = pd.DataFrame(results)
    if df.empty:
        print("No valid experiments found to benchmark.")
        return
        
    horizons = df["Horizon"].unique()
    horizons.sort()
    
    with open(os.path.join(experiments_dir, "leaderboard.md"), "w") as f:
        f.write("# Forecasting Leaderboard\n\n")
        
        for h in horizons:
            f.write(f"## {h} HOURS HORIZON\n\n")
            
            # Filter and sort by R2 descending
            subset = df[df["Horizon"] == h].sort_values(by="R2", ascending=False)
            
            # Reset index to show ranking 1, 2, 3...
            subset = subset.reset_index(drop=True)
            subset.index = subset.index + 1
            
            markdown_table = subset.to_markdown(floatfmt=".4f")
            f.write(markdown_table)
            f.write("\n\n")
            
    # Also save the raw leaderboard to CSV
    df.sort_values(by=["Horizon", "R2"], ascending=[True, False]).to_csv(
        os.path.join(experiments_dir, "leaderboard.csv"), index=False
    )
    
    print(f"Generated benchmark leaderboard in {experiments_dir}/leaderboard.md")

if __name__ == "__main__":
    generate_leaderboard()
