import json
import random
import re
import math
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.prepare_phase4_1_continuation import select_hard_examples

def generate_synthetic_container() -> str:
    letters = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=4))
    numbers = "".join(random.choices("0123456789", k=7))
    return f"{letters}{numbers}"

def generate_synthetic_booking() -> str:
    return "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=9))

def augment_record(record: dict) -> dict:
    augmented = dict(record)
    input_text = str(augmented["input"])
    output_json = json.loads(str(augmented["output"]))
    
    # 1. Augment Container Numbers
    for equipment in output_json.get("equipment_list") or []:
        old_container = equipment.get("container_number")
        if old_container and re.search(r"\b" + re.escape(old_container) + r"\b", input_text):
            new_container = generate_synthetic_container()
            input_text = re.sub(r"\b" + re.escape(old_container) + r"\b", new_container, input_text)
            equipment["container_number"] = new_container

    # 2. Augment Booking/BL numbers
    old_booking = output_json.get("transport_document_number")
    if old_booking and re.search(r"\b" + re.escape(old_booking) + r"\b", input_text):
        new_booking = generate_synthetic_booking()
        input_text = re.sub(r"\b" + re.escape(old_booking) + r"\b", new_booking, input_text)
        output_json["transport_document_number"] = new_booking

    augmented["input"] = input_text
    augmented["output"] = json.dumps(output_json, ensure_ascii=False)
    
    # Sanity Check Sync
    for equipment in output_json.get("equipment_list") or []:
        cont = equipment.get("container_number")
        if cont and cont not in augmented["input"]:
            return record # Fallback to original if sync failed
            
    bn = output_json.get("transport_document_number")
    if bn and bn not in augmented["input"]:
        return record

    return augmented

def main():
    source_train_path = PROJECT_ROOT / "CerberusVision_Colab_Egitim_Seti" / "train.jsonl"
    source_val_path = PROJECT_ROOT / "CerberusVision_Colab_Egitim_Seti" / "validation.jsonl"
    output_dir = PROJECT_ROOT / "CerberusVision_Phase5_Colab"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load base
    source_train = [json.loads(line) for line in source_train_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    validation = [json.loads(line) for line in source_val_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    
    # Get hard examples (50% of the dataset)
    hard_count = math.ceil(len(source_train) / 2)
    hard_examples = select_hard_examples(source_train, hard_count)
    
    # Oversample x3 with Data Augmentation
    augmented_hard_cases = []
    for _ in range(3):
        for record in hard_examples:
            augmented_hard_cases.append(augment_record(record))
            
    # Combine and Shuffle
    combined_train = [dict(record) for record in source_train] + augmented_hard_cases
    random.seed(42)
    random.shuffle(combined_train)
    
    # Save
    combined_train_path = output_dir / "phase5_train.jsonl"
    combined_val_path = output_dir / "phase5_validation.jsonl"
    
    serialized_train = [json.dumps(r, ensure_ascii=False) for r in combined_train]
    serialized_val = [json.dumps(r, ensure_ascii=False) for r in validation]
    
    combined_train_path.write_text("\n".join(serialized_train) + "\n", encoding="utf-8")
    combined_val_path.write_text("\n".join(serialized_val) + "\n", encoding="utf-8")
    
    print(f"Phase 5 data ready! Base size: {len(source_train)}, Hard cases: {len(hard_examples)}, Augmented cases: {len(augmented_hard_cases)}")
    print(f"Total training size: {len(combined_train)}")

if __name__ == "__main__":
    main()
