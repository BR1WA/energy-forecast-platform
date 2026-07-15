import os
import urllib.request
import zipfile

def download_ecl(data_dir: str = "data"):
    os.makedirs(data_dir, exist_ok=True)
    csv_path = os.path.join(data_dir, "electricity.csv")
    
    if os.path.exists(csv_path):
        print(f"ECL dataset already exists at {csv_path}")
        return

    # Using a common public mirror for the electricity.csv dataset
    # (Usually hosted on UCI or GitHub for time series benchmarks)
    url = "https://archive.ics.uci.edu/ml/machine-learning-databases/00321/LD2011_2014.txt.zip"
    zip_path = os.path.join(data_dir, "electricity.zip")
    
    print(f"Downloading ECL dataset from {url}...")
    urllib.request.urlretrieve(url, zip_path)
    
    print(f"Extracting...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(data_dir)
        
    # UCI gives it as LD2011_2014.txt, ECL benchmark reformats it to electricity.csv
    # Note: To exactly match the benchmark format used by Informer/PatchTST,
    # it is often better to use the pre-processed version. If you have the standard 
    # electricity.csv from the Autoformer/PatchTST Google Drive, place it in `data/electricity.csv`.
    print(f"\n[IMPORTANT] The raw UCI dataset was downloaded. For exact benchmark reproducibility,")
    print(f"please ensure you use the pre-processed 'electricity.csv' provided by the PatchTST/Informer authors.")
    print(f"Place it at: {csv_path}")
    
    # Cleanup
    if os.path.exists(zip_path):
        os.remove(zip_path)

if __name__ == "__main__":
    download_ecl()
