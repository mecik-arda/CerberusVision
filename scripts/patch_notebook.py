import json
from pathlib import Path

notebook_path = Path("CerberusVision_Phase5_1_Colab/CerberusVision_Phase5_1_Qwen_QLoRA.ipynb")
with open(notebook_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell["cell_type"] == "code":
        source = cell["source"]
        
        # 1. Add import
        for i, line in enumerate(source):
            if line.startswith("from trl import SFTTrainer, SFTConfig"):
                source.insert(i+1, "from transformers import EarlyStoppingCallback\n")
                break
                
        # 2. Remove args from SFTConfig
        source = [line for line in source if "early_stopping_patience=2" not in line and "early_stopping_threshold=0.001" not in line]
        
        # 3. Add callbacks to SFTTrainer
        for i, line in enumerate(source):
            if "args=training_args," in line:
                source.insert(i+1, "    callbacks=[EarlyStoppingCallback(early_stopping_patience=2, early_stopping_threshold=0.001)],\n")
                break
                
        cell["source"] = source

with open(notebook_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1)

print("Patched notebook successfully.")
