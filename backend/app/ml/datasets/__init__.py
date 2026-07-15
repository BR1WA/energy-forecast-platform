from .provider import DatasetProvider
from .ihepc import IHEPCDataset
from .ecl import ECLDataset

def get_dataset(dataset_name: str, data_dir: str = "data") -> DatasetProvider:
    if dataset_name.lower() == "ihepc":
        return IHEPCDataset(data_dir=data_dir)
    elif dataset_name.lower() == "ecl":
        return ECLDataset(data_dir=data_dir)
    else:
        raise ValueError(f"Unknown dataset: {dataset_name}")
