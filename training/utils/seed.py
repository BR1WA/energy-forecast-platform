import os
import random
import numpy as np
import torch

def set_seed(seed: int = 42):
    """
    Fixes all random seeds to ensure full reproducibility of experiments.
    """
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        
    # Ensure deterministic behavior in PyTorch
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    
    # Also set Python hash seed
    os.environ['PYTHONHASHSEED'] = str(seed)
