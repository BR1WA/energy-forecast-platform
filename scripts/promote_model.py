import os
import sys
import argparse
from sqlalchemy.orm import Session

backend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend")
sys.path.append(backend_dir)

from app.database import SessionLocal
from app.models.models import ModelRegistry

def promote_model(model_name: str):
    db: Session = SessionLocal()
    try:
        # Check if the model exists in the database
        target_model = db.query(ModelRegistry).filter(ModelRegistry.name == model_name).first()
        
        if not target_model:
            print(f"[ERROR] Model '{model_name}' not found in the registry.")
            print("Available models:")
            for m in db.query(ModelRegistry).all():
                print(f" - {m.name}")
            sys.exit(1)
            
        # Verify offline
        print(f"Validating {model_name} before promotion...")
        exp_path = target_model.experiment_path
        required_files = ["model.pt", "pipeline.pkl", "config.yaml", "metrics.json"]
        if not all(os.path.exists(os.path.join(exp_path, f)) for f in required_files):
            print(f"[ERROR] Missing required artifacts in {exp_path}")
            sys.exit(1)
            
        # Deactivate all active models
        active_models = db.query(ModelRegistry).filter(ModelRegistry.active == True).all()
        for m in active_models:
            m.active = False
            
        # Activate target
        target_model.active = True
        
        db.commit()
        print(f"\n[SUCCESS] Promoted '{model_name}' to Active.")
        print("The backend will automatically start using it for /api/v1/forecast/run.")
        
    except Exception as e:
        print(f"[ERROR] Failed to promote model: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="Name of the experiment to promote (e.g. 24h_patchtst)")
    args = parser.parse_args()
    
    promote_model(args.name)
