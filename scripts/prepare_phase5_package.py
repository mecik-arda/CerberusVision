#!/usr/bin/env python3
"""
CerberusVision Phase 5 — Veri Paketi Hazirlama (Data Leakage Fix)
==================================================================

Duzeltmeler:
1. document_family_id (shipping_instruction_reference) bazli gruplama.
   Eskiden output string'i birebir karsilastiriyordu, bu nedenle booking/konteyner
   numarasi degisen ayni sablon farkli grup sayiliyordu.
2. Aile bazli train/validation split: Her aile SADECE tek tarafta kalir.
3. Validation'a 2-3 farkli aile secilir (~%5 oran).
4. Her aile icinde augment_record ile OCR/konteyner/booking varyantlari uretilir.
5. Train icindeki birebir exact duplicate'ler temizlenir.
"""

import json
import random
import re
import math
from collections import defaultdict
from itertools import combinations
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# --- Configuration ---
VAL_RATIO = 0.05       # Target ~5% validation
MIN_VAL_FAMILIES = 2    # At least 2 families in validation for diversity
MAX_VAL_FAMILIES = 3    # At most 3 families
AUGMENT_COUNT = 4       # How many augmented variants per base record
RANDOM_SEED = 42


# --- Synthetic data generation ---

def generate_synthetic_container() -> str:
    letters = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=4))
    numbers = "".join(random.choices("0123456789", k=7))
    return f"{letters}{numbers}"


def generate_synthetic_booking() -> str:
    return "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=9))


def augment_record(record: dict) -> dict:
    """Create a variant of a record with different container/booking numbers."""
    augmented = dict(record)
    input_text = str(augmented["input"])
    output_json = json.loads(str(augmented["output"]))

    for equipment in output_json.get("equipment_list") or []:
        old_container = equipment.get("equipment_reference")
        if old_container and re.search(r"\b" + re.escape(old_container) + r"\b", input_text):
            new_container = generate_synthetic_container()
            input_text = re.sub(r"\b" + re.escape(old_container) + r"\b", new_container, input_text)
            equipment["equipment_reference"] = new_container

    old_booking = output_json.get("transport_document_number")
    if not old_booking:
        old_booking = output_json.get("carrier_booking_reference")

    if old_booking and re.search(r"\b" + re.escape(old_booking) + r"\b", input_text):
        new_booking = generate_synthetic_booking()
        input_text = re.sub(r"\b" + re.escape(old_booking) + r"\b", new_booking, input_text)
        if "transport_document_number" in output_json:
            output_json["transport_document_number"] = new_booking
        elif "carrier_booking_reference" in output_json:
            output_json["carrier_booking_reference"] = new_booking

    augmented["input"] = input_text
    augmented["output"] = json.dumps(output_json, ensure_ascii=False)

    return augmented


# --- Family ID extraction ---

def get_document_family_id(item: dict) -> str:
    """
    Extract document family ID from a record.

    Uses shipping_instruction_reference as the primary family identifier.
    Falls back to a structural fingerprint hash.
    """
    out = item.get("output", {})
    if isinstance(out, str):
        try:
            out = json.loads(out)
        except json.JSONDecodeError:
            out = {}

    si_ref = out.get("shipping_instruction_reference", "").strip()
    if si_ref:
        return si_ref

    # Fallback: structural fingerprint
    import hashlib
    parties = out.get("parties", [])
    shipper = next((p["party_name"] for p in parties if p.get("party_role_code") == "CZ"), "")
    consignee = next((p["party_name"] for p in parties if p.get("party_role_code") == "CN"), "")
    cargo = out.get("cargo_items", [{}])[0] if out.get("cargo_items") else {}
    goods = cargo.get("description_of_goods", "")
    plans = out.get("transport_plans", [{}])[0] if out.get("transport_plans") else {}
    pol = plans.get("port_of_loading", {}).get("location_name", "")
    pod = plans.get("port_of_discharge", {}).get("location_name", "")
    fp = f"{shipper}|{consignee}|{goods}|{pol}|{pod}".upper()
    return f"fp:{hashlib.sha256(fp.encode()).hexdigest()[:12]}"


# --- Main pipeline ---

def main():
    source_train_path = PROJECT_ROOT / "CerberusVision_Colab_Egitim_Seti" / "train.jsonl"
    source_val_path = PROJECT_ROOT / "CerberusVision_Colab_Egitim_Seti" / "validation.jsonl"
    output_dir = PROJECT_ROOT / "CerberusVision_Phase5_Colab"
    output_dir.mkdir(parents=True, exist_ok=True)

    random.seed(RANDOM_SEED)

    # ============================================================
    # Step 1: Load ALL source data (train + val merged)
    # ============================================================
    print("=" * 70)
    print("Phase 5 Veri Paketi - Aile Bazli Split (Data Leakage Fix)")
    print("=" * 70)

    raw_train = [json.loads(line) for line in
                 source_train_path.read_text(encoding="utf-8").splitlines()
                 if line.strip()]
    raw_val = [json.loads(line) for line in
               source_val_path.read_text(encoding="utf-8").splitlines()
               if line.strip()]
    all_raw = raw_train + raw_val
    print(f"\n[1] Source data: train={len(raw_train)}, val={len(raw_val)}, total={len(all_raw)}")

    # ============================================================
    # Step 2: Deduplicate exact (input, output) pairs
    # ============================================================
    print("\n[2] Removing exact duplicates from source data...")
    seen = {}
    dupes_removed = 0
    for item in all_raw:
        inp = item["input"].strip()
        out = item["output"]
        if isinstance(out, dict):
            out_str = json.dumps(out, sort_keys=True, ensure_ascii=False)
        else:
            out_str = str(out).strip()
        key = f"{inp}|||{out_str}"
        if key in seen:
            dupes_removed += 1
        else:
            seen[key] = item
    unique_records = list(seen.values())
    print(f"  Duplicates removed: {dupes_removed}")
    print(f"  Unique records: {len(unique_records)}")

    # ============================================================
    # Step 3: Assign document_family_id and group
    # ============================================================
    print("\n[3] Assigning document_family_id and grouping...")
    for item in unique_records:
        item["document_family_id"] = get_document_family_id(item)

    families = defaultdict(list)
    for item in unique_records:
        families[item["document_family_id"]].append(item)

    families = dict(families)
    print(f"  Unique families: {len(families)}")
    for fid, items in sorted(families.items(), key=lambda x: -len(x[1])):
        print(f"    {fid:35s} -> {len(items):3d} base records")

    # ============================================================
    # Step 4: Family-based train/validation split
    # ============================================================
    print("\n[4] Family-based train/validation split...")

    family_list = sorted(families.items(), key=lambda x: len(x[1]))
    total_base = sum(len(items) for items in families.values())

    # Try all combinations of 1..MAX_VAL_FAMILIES families
    # Pick the one whose size after augmentation is closest to VAL_RATIO
    best_val_fids = set()
    best_diff = float("inf")
    best_diversity = 0

    for num_pick in range(1, min(MAX_VAL_FAMILIES + 1, len(family_list) + 1)):
        for combo in combinations(family_list, num_pick):
            val_base = sum(len(items) for _, items in combo)
            train_base = total_base - val_base

            # After augmentation: base + base * AUGMENT_COUNT variants
            # (each base record generates AUGMENT_COUNT augmented versions)
            val_augmented = val_base + val_base * AUGMENT_COUNT
            train_augmented = train_base + train_base * AUGMENT_COUNT
            total_augmented = val_augmented + train_augmented

            if total_augmented == 0:
                continue
            actual_ratio = val_augmented / total_augmented
            diff = abs(actual_ratio - VAL_RATIO)

            if diff < best_diff or (diff == best_diff and num_pick > best_diversity):
                best_diff = diff
                best_diversity = num_pick
                best_val_fids = {fid for fid, _ in combo}

    train_fids = set(families.keys()) - best_val_fids

    # ============================================================
    # Step 5: Generate train set
    # ============================================================
    print("\n[5] Generating train set...")
    train_data = []
    for fid in sorted(train_fids):
        for base_record in families[fid]:
            # Add the base record
            clean_base = {
                "input": base_record["input"],
                "output": base_record["output"],
            }
            # Parse output once for use
            out_obj = json.loads(clean_base["output"]) if isinstance(clean_base["output"], str) else clean_base["output"]
            clean_base["output"] = json.dumps(out_obj, ensure_ascii=False)
            train_data.append(clean_base)

            # Add augmented variants
            for _ in range(AUGMENT_COUNT):
                augmented = augment_record(base_record)
                if augmented["input"] != base_record["input"]:
                    out_obj = json.loads(augmented["output"]) if isinstance(augmented["output"], str) else augmented["output"]
                    train_data.append({
                        "input": augmented["input"],
                        "output": json.dumps(out_obj, ensure_ascii=False),
                    })

    print(f"  Train families: {len(train_fids)} -> {len(train_data)} samples")

    # ============================================================
    # Step 6: Generate validation set
    # ============================================================
    print("\n[6] Generating validation set...")
    val_data = []
    for fid in sorted(best_val_fids):
        for base_record in families[fid]:
            # Add the base record
            clean_base = {
                "input": base_record["input"],
                "output": base_record["output"],
            }
            out_obj = json.loads(clean_base["output"]) if isinstance(clean_base["output"], str) else clean_base["output"]
            clean_base["output"] = json.dumps(out_obj, ensure_ascii=False)
            val_data.append(clean_base)

            # Add augmented variants
            for _ in range(AUGMENT_COUNT):
                augmented = augment_record(base_record)
                if augmented["input"] != base_record["input"]:
                    out_obj = json.loads(augmented["output"]) if isinstance(augmented["output"], str) else augmented["output"]
                    val_data.append({
                        "input": augmented["input"],
                        "output": json.dumps(out_obj, ensure_ascii=False),
                    })

    print(f"  Validation families: {len(best_val_fids)} -> {len(val_data)} samples")

    # ============================================================
    # Step 7: Remove exact duplicates within train
    # ============================================================
    print("\n[7] Removing exact duplicates from train...")
    seen_train = {}
    train_deduped = []
    train_dupes = 0
    for item in train_data:
        key = f"{item['input'].strip()}|||{item['output'].strip()}"
        if key in seen_train:
            train_dupes += 1
        else:
            seen_train[key] = item
            train_deduped.append(item)
    print(f"  Train duplicates removed: {train_dupes}")
    train_data = train_deduped

    # ============================================================
    # Step 8: Shuffle and save
    # ============================================================
    print("\n[8] Shuffling and saving...")
    random.shuffle(train_data)
    random.shuffle(val_data)

    combined_train_path = output_dir / "phase5_train.jsonl"
    combined_val_path = output_dir / "phase5_validation.jsonl"

    serialized_train = [json.dumps(r, ensure_ascii=False) for r in train_data]
    serialized_val = [json.dumps(r, ensure_ascii=False) for r in val_data]

    combined_train_path.write_text("\n".join(serialized_train) + "\n", encoding="utf-8")
    combined_val_path.write_text("\n".join(serialized_val) + "\n", encoding="utf-8")

    actual_val_ratio = len(val_data) / (len(train_data) + len(val_data)) * 100

    # ============================================================
    # Step 9: Verification
    # ============================================================
    print("\n[9] Verifying zero leakage...")

    # Check family overlap
    def get_fid(item):
        out = item.get("output", {})
        if isinstance(out, str):
            out = json.loads(out)
        return out.get("shipping_instruction_reference", "N/A")

    train_fids_final = {get_fid(item) for item in train_data}
    val_fids_final = {get_fid(item) for item in val_data}
    overlap = train_fids_final & val_fids_final

    if overlap:
        print(f"  *** LEAKAGE: {len(overlap)} families in both train and val!")
        for fid in sorted(overlap):
            print(f"      {fid}")
    else:
        print(f"  OK Zero family overlap: all families are exclusively in train or validation")

    # Check exact input overlap
    train_inputs = {item["input"].strip() for item in train_data}
    val_inputs = {item["input"].strip() for item in val_data}
    input_overlap = train_inputs & val_inputs
    print(f"  Exact input overlap: {len(input_overlap)}")

    # Check exact output overlap
    train_outputs = {item["output"].strip() for item in train_data}
    val_outputs = {item["output"].strip() for item in val_data}
    output_overlap = train_outputs & val_outputs
    print(f"  Exact output overlap: {len(output_overlap)}")

    # ============================================================
    # Final Report
    # ============================================================
    print("\n" + "=" * 70)
    print("FINAL REPORT")
    print("=" * 70)
    print(f"  Source data:        train={len(raw_train)}, val={len(raw_val)}")
    print(f"  Source duplicates:  {dupes_removed}")
    print(f"  Final train:        {len(train_data)} samples")
    print(f"  Final validation:   {len(val_data)} samples")
    print(f"  Validation ratio:   {actual_val_ratio:.1f}%")
    print(f"  Train families:     {len(train_fids)}")
    print(f"  Validation families: {len(best_val_fids)}")
    print(f"  Family leakage:     {'*** YES' if overlap else 'OK NONE'}")

    print(f"\n  Train families:")
    for fid in sorted(train_fids):
        base_count = len(families[fid])
        total_count = sum(1 for item in train_data if get_fid(item) == fid)
        print(f"    {fid:35s} -> {total_count:4d} samples ({base_count} base + variants)")

    print(f"\n  Validation families:")
    for fid in sorted(best_val_fids):
        base_count = len(families[fid])
        total_count = sum(1 for item in val_data if get_fid(item) == fid)
        # Show details
        sample = families[fid][0]
        out = json.loads(sample["output"]) if isinstance(sample["output"], str) else sample["output"]
        parties = out.get("parties", [])
        shipper = next((p["party_name"] for p in parties if p.get("party_role_code") == "CZ"), "N/A")
        cargo = out.get("cargo_items", [{}])[0] if out.get("cargo_items") else {}
        goods = cargo.get("description_of_goods", "N/A")
        print(f"    {fid:35s} -> {total_count:4d} samples ({base_count} base + variants)")
        print(f"      Shipper: {shipper[:50]}")
        print(f"      Goods: {goods[:50]}")

    print(f"\nPhase 5 Veri Paketi Hazir!")
    print(f"Validation, EGITIMDE GORULMEMIS YENI sablonlari olcer — gercek genelleme testi.")


if __name__ == "__main__":
    main()
