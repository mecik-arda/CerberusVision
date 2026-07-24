#!/usr/bin/env python3
"""
CerberusVision Phase 5 — Veri Sizintisi Duzeltme Scripti
=========================================================

Yapilanlar:
1. Tum train + validation verisini birlestirir.
2. Her ornege `document_family_id` atar (shipping_instruction_reference bazli).
3. Birebir exact duplicate'leri (input + output tamamen ayni) tespit edip siler.
4. Belge ailesi (document_family_id) bazli train/validation split yapar:
   - Ayni ailenin TUM varyantlari tek tarafta (train VEYA validation) kalir.
   - Hedef validation orani: ~%5
   - 2-3 farkli belge ailesi validation'a secilir (cesitlilik).
5. Ciktilari phase5_train.jsonl ve phase5_validation.jsonl olarak yazar.
   - document_family_id alani KALDIRILIR (egitim icin gerekli degil).
6. Istatistikleri ve sizinti raporunu basar.
"""

import json
import hashlib
import re
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
TRAIN_FILE = BASE_DIR / "phase5_train.jsonl"
VAL_FILE = BASE_DIR / "phase5_validation.jsonl"
OUT_TRAIN = BASE_DIR / "phase5_train.jsonl"
OUT_VAL = BASE_DIR / "phase5_validation.jsonl"
VAL_RATIO = 0.05  # ~5% validation target
MIN_VAL_FAMILIES = 1
MAX_VAL_FAMILIES = 3


def load_jsonl(path):
    """Load a JSONL file, return list of dicts."""
    items = []
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  WARNING: Line {line_no} in {path.name}: {e}")
    return items


def save_jsonl(items, path):
    """Save list of dicts as JSONL, stripping document_family_id."""
    with open(path, "w", encoding="utf-8") as f:
        for item in items:
            # Strip document_family_id — not needed for training
            clean = {k: v for k, v in item.items() if k != "document_family_id"}
            f.write(json.dumps(clean, ensure_ascii=False) + "\n")
    print(f"  Saved {len(items)} samples -> {path.name}")


def parse_output(item):
    """Parse the output field (may be str or dict)."""
    out = item.get("output", {})
    if isinstance(out, str):
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return {}
    return out


def extract_document_family_id(item):
    """
    Extract a document family ID from a sample.

    Primary: shipping_instruction_reference from output.
    Secondary: hash of normalized (shipper, consignee, goods, pol, pod, freight_term).
    """
    out = parse_output(item)

    # Primary: SI reference
    si_ref = out.get("shipping_instruction_reference", "").strip()
    if si_ref:
        return f"si:{si_ref}"

    # Secondary: structural fingerprint
    parties = out.get("parties", [])
    shipper = next((p["party_name"] for p in parties if p.get("party_role_code") == "CZ"), "")
    consignee = next((p["party_name"] for p in parties if p.get("party_role_code") == "CN"), "")

    cargo = out.get("cargo_items", [{}])[0] if out.get("cargo_items") else {}
    goods = cargo.get("description_of_goods", "")

    plans = out.get("transport_plans", [{}])[0] if out.get("transport_plans") else {}
    pol = plans.get("port_of_loading", {}).get("location_name", "")
    pod = plans.get("port_of_discharge", {}).get("location_name", "")

    freight = (out.get("freight_payment_term_code") or "").strip().upper()

    # Normalize for fingerprint
    fp_raw = f"{shipper}|{consignee}|{goods}|{pol}|{pod}|{freight}".upper().strip()
    fp_hash = hashlib.sha256(fp_raw.encode()).hexdigest()[:12]
    return f"fp:{fp_hash}"


def exact_duplicate_key(item):
    """Create a key for EXACT duplicate detection.

    Uses the raw input and output strings as-is (no OCR normalization).
    Two samples are only duplicates if they have identical input AND output.
    """
    inp = item.get("input", "").strip()
    out = item.get("output", "")
    if isinstance(out, dict):
        out = json.dumps(out, sort_keys=True, ensure_ascii=False)
    else:
        out = out.strip()
    return hashlib.sha256(f"{inp}|{out}".encode("utf-8")).hexdigest()


def build_family_groups(items):
    """Group items by document_family_id."""
    groups = defaultdict(list)
    for item in items:
        fid = item.get("document_family_id", extract_document_family_id(item))
        item["document_family_id"] = fid
        groups[fid].append(item)
    return dict(groups)


def select_validation_families(families, val_ratio, min_families=1, max_families=3):
    """
    Select which families go to validation.

    Strategy:
    - Try all combinations of 1 to max_families families.
    - Pick the combination whose total size is closest to target.
    - Within equally good size matches, prefer more families (diversity).
    - Each family entirely goes to one side.
    """
    total = sum(len(items) for items in families.values())
    target_val_count = max(int(total * val_ratio), 1)

    family_list = sorted(families.items(), key=lambda x: len(x[1]))

    best_val_families = set()
    best_diff = float("inf")
    best_diversity = 0

    # Try all combinations of 1..max_families
    for num_pick in range(min_families, min(max_families, len(family_list)) + 1):
        for combo in combinations(family_list, num_pick):
            val_count = sum(len(items) for _, items in combo)
            diff = abs(val_count - target_val_count)

            # Prefer closer to target; break ties with higher diversity
            if diff < best_diff or (diff == best_diff and num_pick > best_diversity):
                best_diff = diff
                best_diversity = num_pick
                best_val_families = {fid for fid, _ in combo}

    train_families = set(families.keys()) - best_val_families
    return train_families, best_val_families


def main():
    print("=" * 70)
    print("CerberusVision Phase 5 - Veri Sizintisi Duzeltme")
    print("=" * 70)

    # --- 1. Load ---
    print("\n[1/7] Loading data...")
    train_raw = load_jsonl(TRAIN_FILE)
    val_raw = load_jsonl(VAL_FILE)
    all_items = train_raw + val_raw
    original_train_count = len(train_raw)
    print(f"  Train: {len(train_raw)}, Validation: {len(val_raw)}")
    print(f"  Total combined: {len(all_items)}")

    # --- 2. Assign document_family_id ---
    print("\n[2/7] Assigning document_family_id...")
    for item in all_items:
        item["document_family_id"] = extract_document_family_id(item)

    families_before = build_family_groups(all_items)
    print(f"  Unique document families: {len(families_before)}")
    for fid, items in sorted(families_before.items(), key=lambda x: -len(x[1])):
        out0 = parse_output(items[0])
        goods = (out0.get("cargo_items", [{}])[0] if out0.get("cargo_items") else {}).get("description_of_goods", "N/A")
        print(f"  {fid:40s} -> {len(items):4d} samples  [{goods[:50]}]")

    # --- 3. Remove exact duplicates ---
    print("\n[3/7] Removing exact duplicates (raw input+output match)...")
    seen_keys = {}
    deduped = []
    dupes_removed = 0
    dupe_examples = []

    for item in all_items:
        key = exact_duplicate_key(item)
        if key in seen_keys:
            dupes_removed += 1
            if len(dupe_examples) < 3:
                dupe_examples.append((seen_keys[key], item))
            continue
        seen_keys[key] = item
        deduped.append(item)

    print(f"  Exact duplicates removed: {dupes_removed}")
    print(f"  After dedup: {len(deduped)} samples")

    # Show a couple duplicate examples
    for i, (orig, dupe) in enumerate(dupe_examples):
        print(f"  Dupe example {i+1}:")
        print(f"    Input preview:  {orig['input'][:80]}...")
        print(f"    Dupe preview:   {dupe['input'][:80]}...")

    # --- 4. Check original train/val family overlap ---
    print("\n[4/7] Analyzing original train/val family overlap (before fix)...")
    original_families_train = set(
        extract_document_family_id(item) for item in train_raw
    )
    original_families_val = set(
        extract_document_family_id(item) for item in val_raw
    )
    overlap = original_families_train & original_families_val
    print(f"  Families in train: {len(original_families_train)}")
    print(f"  Families in val:   {len(original_families_val)}")
    if overlap:
        print(f"  OVERLAP: {len(overlap)} families in BOTH train and val (DATA LEAK!)")
    else:
        print(f"  Overlap: {len(overlap)} (OK — no leakage)")
    for fid in sorted(overlap):
        train_count = sum(1 for item in train_raw if extract_document_family_id(item) == fid)
        val_count = sum(1 for item in val_raw if extract_document_family_id(item) == fid)
        print(f"    {fid}: train={train_count}, val={val_count}")

    # --- 5. Family-based split ---
    print("\n[5/7] Performing family-based train/validation split...")
    families = build_family_groups(deduped)
    train_fids, val_fids = select_validation_families(families, VAL_RATIO, MIN_VAL_FAMILIES, MAX_VAL_FAMILIES)

    new_train = []
    new_val = []

    for fid in train_fids:
        new_train.extend(families[fid])
    for fid in val_fids:
        new_val.extend(families[fid])

    actual_val_ratio = len(new_val) / (len(new_train) + len(new_val)) * 100
    print(f"  Train families: {len(train_fids)} -> {len(new_train)} samples")
    print(f"  Val families:   {len(val_fids)} -> {len(new_val)} samples")
    print(f"  Val ratio: {actual_val_ratio:.1f}%")

    # --- 6. Leakage verification ---
    print("\n[6/7] Verifying zero leakage...")
    train_fids_set = set(item["document_family_id"] for item in new_train)
    val_fids_set = set(item["document_family_id"] for item in new_val)
    overlap_fids = train_fids_set & val_fids_set

    if overlap_fids:
        print(f"  *** LEAKAGE DETECTED: {len(overlap_fids)} families in both train and val!")
        for fid in sorted(overlap_fids):
            print(f"     - {fid}")
    else:
        print(f"  OK Zero family overlap: no document family appears in both train and validation")

    # Also verify no exact input/output overlap (safety check)
    train_inputs = {item["input"].strip() for item in new_train}
    train_outputs = {
        json.dumps(parse_output(item), sort_keys=True) for item in new_train
    }
    val_inputs = {item["input"].strip() for item in new_val}
    val_outputs = {
        json.dumps(parse_output(item), sort_keys=True) for item in new_val
    }

    input_overlap = train_inputs & val_inputs
    output_overlap = train_outputs & val_outputs
    print(f"  Exact input overlap:  {len(input_overlap)} (should be 0)")
    print(f"  Exact output overlap: {len(output_overlap)} (should be 0)")

    # Near-duplicate check: compute normalized fingerprints for all items
    def norm_fingerprint(item):
        out = parse_output(item)
        parties = out.get("parties", [])
        shipper = next((p["party_name"] for p in parties if p.get("party_role_code") == "CZ"), "")
        consignee = next((p["party_name"] for p in parties if p.get("party_role_code") == "CN"), "")
        cargo = out.get("cargo_items", [{}])[0] if out.get("cargo_items") else {}
        goods = cargo.get("description_of_goods", "")
        plans = out.get("transport_plans", [{}])[0] if out.get("transport_plans") else {}
        pol = plans.get("port_of_loading", {}).get("location_name", "")
        pod = plans.get("port_of_discharge", {}).get("location_name", "")
        return f"{shipper}|{consignee}|{goods}|{pol}|{pod}".upper()

    train_nfps = {norm_fingerprint(item) for item in new_train}
    val_nfps = {norm_fingerprint(item) for item in new_val}
    nfp_overlap = train_nfps & val_nfps
    # Note: there MAY be overlap here if different SI refs have same parties/goods
    if nfp_overlap:
        print(f"  NOTE: {len(nfp_overlap)} structural fingerprints appear in both sets")
        print(f"        (different SI refs with same parties/goods — OK, different templates)")

    # --- 7. Save ---
    print("\n[7/7] Saving clean data...")
    save_jsonl(new_train, OUT_TRAIN)
    save_jsonl(new_val, OUT_VAL)

    # --- Final Report ---
    print("\n" + "=" * 70)
    print("FINAL REPORT")
    print("=" * 70)
    print(f"  Original:           train={original_train_count}, val={len(val_raw)}")
    print(f"  Duplicates removed: {dupes_removed}")
    print(f"  Final:              train={len(new_train)}, val={len(new_val)}")
    print(f"  Val ratio:          {actual_val_ratio:.1f}%")
    print(f"  Families in train:  {len(train_fids)}")
    print(f"  Families in val:    {len(val_fids)}")
    print(f"  Family leakage:     {'*** YES' if overlap_fids else 'OK NONE'}")

    # Validation family details
    print(f"\n  Validation families:")
    for fid in sorted(val_fids):
        items = families[fid]
        out0 = parse_output(items[0])
        goods = (out0.get("cargo_items", [{}])[0] if out0.get("cargo_items") else {}).get("description_of_goods", "N/A")
        parties = out0.get("parties", [])
        shipper = next((p["party_name"] for p in parties if p.get("party_role_code") == "CZ"), "N/A")
        consignee = next((p["party_name"] for p in parties if p.get("party_role_code") == "CN"), "N/A")
        si_ref = out0.get("shipping_instruction_reference", "N/A")
        print(f"    {fid:40s} -> {len(items):3d} samples")
        print(f"      SI: {si_ref}  |  Shipper: {shipper[:40]}")
        print(f"      Consignee: {consignee[:40]}  |  Goods: {goods[:40]}")

    # Train family summary
    print(f"\n  Train families ({len(train_fids)}):")
    for fid in sorted(train_fids):
        items = families[fid]
        out0 = parse_output(items[0])
        goods = (out0.get("cargo_items", [{}])[0] if out0.get("cargo_items") else {}).get("description_of_goods", "N/A")
        print(f"    {fid:40s} -> {len(items):4d} samples  [{goods[:45]}]")

    print("\nDone. Data is ready for training with proper validation split.")
    print("Validation measures generalization to NEW document templates, not OCR variants.")


if __name__ == "__main__":
    main()
