import yaml
import argparse
import os

def load_config(config_path):
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config

def get_args_and_config():
    parser = argparse.ArgumentParser(description="Time Series Forecasting Training Pipeline")
    parser.add_argument('--config', type=str, required=True, help="Path to the YAML configuration file")
    args = parser.parse_args()
    
    config = load_config(args.config)
    return args, config
