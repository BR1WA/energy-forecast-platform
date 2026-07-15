import os
import sys
import yaml
import torch
import inspect
import torch

# Add backend directory to sys.path so we can import from app
backend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend")
sys.path.append(backend_dir)

from app.ml.model_registry import get_model_class

def validate_experiment(exp_name: str, exp_path: str) -> bool:
    print(f"\nValidating experiment: {exp_name}")
    
    required_files = ["model.pt", "pipeline.pkl", "config.yaml", "metrics.json"]
    missing = [f for f in required_files if not os.path.exists(os.path.join(exp_path, f))]
    
    if missing:
        print(f"  [FAIL] Missing required files: {missing}")
        return False
        
    print("  [OK] All required files present.")
    
    # Check config format
    config_path = os.path.join(exp_path, "config.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
        
    arch_name = config.get("architecture", {}).get("name") or config.get("model", {}).get("name")
    if not arch_name:
        print("  [FAIL] Missing architecture name in config.")
        return False
        
    print(f"  [OK] Architecture specified: {arch_name}")
    
    # Load Model Class
    try:
        ModelClass = get_model_class(arch_name)
    except ValueError as e:
        print(f"  [FAIL] Could not load model class: {e}")
        return False
        
    print(f"  [OK] Loaded class from registry: {ModelClass.__name__}")
    
    # Instantiate Model
    try:
        model_kwargs = config.get("architecture", config.get("model", {}))
        if isinstance(model_kwargs, dict) and "name" in model_kwargs:
            model_kwargs = model_kwargs.copy()
            del model_kwargs["name"]
            
        if arch_name in ("Hybrid_v2", "HybridV2", "iTransformer"):
            # Legacy models expect full dict
            model = ModelClass(config.get("model", {}))
        else:
            # Filter kwargs to match signature
            sig = inspect.signature(ModelClass.__init__)
            valid_keys = set(sig.parameters.keys())
            filtered_kwargs = {k: v for k, v in model_kwargs.items() if k in valid_keys}
            model = ModelClass(**filtered_kwargs)
    except Exception as e:
        print(f"  [FAIL] Failed to instantiate model {ModelClass.__name__}: {e}")
        return False
        
    print("  [OK] Model instantiated successfully.")
    
    # Load Weights
    weights_path = os.path.join(exp_path, "model.pt")
    try:
        # We load to CPU to avoid CUDA dependency in validation script
        state_dict = torch.load(weights_path, map_location="cpu", weights_only=True)
        # Some legacy models saved the full model instead of state_dict or nested it under 'model_state_dict'
        if isinstance(state_dict, dict) and "model_state_dict" in state_dict:
            state_dict = state_dict["model_state_dict"]
        elif hasattr(state_dict, "state_dict"): # Saved full model
            state_dict = state_dict.state_dict()
            
        # load_state_dict returns (missing_keys, unexpected_keys)
        result = model.load_state_dict(state_dict, strict=False)
        
        if result.missing_keys:
            print(f"  [WARNING] Missing keys in state_dict: {len(result.missing_keys)} keys missing")
            print(f"    Sample missing: {result.missing_keys[:3]}")
        if result.unexpected_keys:
            print(f"  [WARNING] Unexpected keys in state_dict: {len(result.unexpected_keys)} keys unexpected")
            print(f"    Sample unexpected: {result.unexpected_keys[:3]}")
            
        if result.missing_keys or result.unexpected_keys:
            print("  [FAIL] State dict keys do not perfectly match model architecture.")
            return False
            
    except Exception as e:
        print(f"  [FAIL] Failed to load state dict: {e}")
        return False
        
    print("  [OK] Weights loaded perfectly cleanly (no missing/unexpected keys).")
    return True

if __name__ == "__main__":
    experiments_dir = os.path.join(backend_dir, "experiments")
    if not os.path.exists(experiments_dir):
        print(f"Experiments directory not found: {experiments_dir}")
        sys.exit(1)
        
    all_passed = True
    for exp_name in sorted(os.listdir(experiments_dir)):
        exp_path = os.path.join(experiments_dir, exp_name)
        if os.path.isdir(exp_path):
            if not validate_experiment(exp_name, exp_path):
                all_passed = False
                
    if all_passed:
        print("\n=> ALL EXPERIMENTS PASSED VALIDATION.")
        sys.exit(0)
    else:
        print("\n=> SOME EXPERIMENTS FAILED VALIDATION.")
        sys.exit(1)
