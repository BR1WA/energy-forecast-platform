import nbformat
import sys
import re

with open('notebooks/advanced_patchtst_kaggle.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Split into cells based on the header comments
# The regex looks for blocks starting with # ==========================================
parts = re.split(r'(# ={42}\n# \d+\. .*\n# ={42})', content)

nb = nbformat.v4.new_notebook()

# Add instructions as a markdown cell
markdown_cell = """# Advanced Kaggle Training Script for Medium-Term Forecasting
Based on official PatchTST (Nie et al., ICLR 2023)

Instructions:
1. Upload your dataset.
2. Run these cells to train State-of-the-Art models for 1-Week and 1-Month horizons.
3. Download the generated `.pth` files.
"""
nb.cells.append(nbformat.v4.new_markdown_cell(markdown_cell))

# The first part is the imports (before the first header)
if parts[0].strip():
    nb.cells.append(nbformat.v4.new_code_cell(parts[0].strip()))

# The rest are pairs of (header, content)
for i in range(1, len(parts), 2):
    header = parts[i]
    body = parts[i+1] if i+1 < len(parts) else ""
    combined = header + "\n" + body.strip()
    if combined.strip():
        nb.cells.append(nbformat.v4.new_code_cell(combined.strip()))

with open('notebooks/advanced_patchtst_kaggle.ipynb', 'w', encoding='utf-8') as f:
    nbformat.write(nb, f)

print("Notebook created successfully!")
