import torch
import torch.nn as nn
import torch.optim as optim
from torch.cuda.amp import autocast, GradScaler
from utils.config import get_args_and_config
from utils.tracker import ExperimentTracker

# Dummy import for models (to be replaced with actual dynamic loading)
from models.baseline import NaivePersistence
from models.autoformer import Autoformer

def train():
    args, config = get_args_and_config()
    tracker = ExperimentTracker(config)
    
    # 1. Setup Model
    if config['model']['name'] == 'Autoformer':
        model = Autoformer(config['model'])
    else:
        model = NaivePersistence(config['model']['forecast_horizon'], config['model']['num_targets'])
        
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device)
    
    # 2. Setup Loss & Optimizer
    if config['training']['loss'] == 'huber':
        criterion = nn.HuberLoss()
    else:
        criterion = nn.MSELoss()
        
    optimizer = optim.AdamW(model.parameters(), 
                            lr=config['training']['learning_rate'], 
                            weight_decay=float(config['training']['weight_decay']))
                            
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=3, factor=0.5)
    scaler = GradScaler(enabled=config['training'].get('mixed_precision', False))
    
    # Training Loop Skeleton
    epochs = config['training']['epochs']
    patience = config['training']['early_stopping_patience']
    best_val_loss = float('inf')
    patience_counter = 0
    
    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        
        # for batch in dataloader:
        #     optimizer.zero_grad()
        #     with autocast(enabled=config['training'].get('mixed_precision', False)):
        #         output = model(batch_x, batch_temporal)
        #         loss = criterion(output, batch_y)
        #     scaler.scale(loss).backward()
        #     nn.utils.clip_grad_norm_(model.parameters(), config['training']['gradient_clipping'])
        #     scaler.step(optimizer)
        #     scaler.update()
            
        # Simulate validation
        val_loss = 0.1 # simulated
        scheduler.step(val_loss)
        
        tracker.log_metrics({"train_loss": train_loss, "val_loss": val_loss, "lr": optimizer.param_groups[0]['lr']}, epoch)
        
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            tracker.save_checkpoint(model, optimizer, epoch, val_loss)
            patience_counter = 0
        else:
            patience_counter += 1
            
        if patience_counter >= patience:
            print("Early stopping triggered.")
            break
            
    tracker.end_experiment()

if __name__ == "__main__":
    train()
