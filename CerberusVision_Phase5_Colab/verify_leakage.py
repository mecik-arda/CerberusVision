#!/usr/bin/env python3
"""
CerberusVision Phase 5 — Veri Sizintisi Dogrulama Araci
=========================================================

Kontroller:
1. Bozuk JSON satiri var mi?
2. Train icinde birebir exact duplicate var mi?
3. Train-validation arasi birebir input cakismasi var mi?
4. Train-validation arasi birebir output cakismasi var mi?
5. Aile bazli (document_family_id) cakisma var mi? ← ANA KONTROL
6. Yapisal parmak izi (shipper+consignee+goods+POL+POD) cakismasi var mi?
7. Benzerlik skoru yuksek train-val ciftleri var mi? (sequence matcher)
8. Istatistik raporu

Eger bir aile hem train'de hem validation'da varsa → DATA LEAKAGE.
"""

import json
import hashlib
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
TRAIN_FILE = BASE_DIR / "phase5_train.jsonl"
VAL_FILE = BASE_DIR / "phase5_validation.jsonl"
SIMILARITY_THRESHOLD = 0.90  # Flag pairs with >90% similarity as suspicious


def load_jsonl(path):
    """Load JSONL, track broken lines."""
    items = []
    broken = 0
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                broken += 1
                print(f"  BROKEN JSON at {path.name}:{line_no}")
    return items, broken


def parse_output(item):
    """Parse output field."""
    out = item.get("output", {})
    if isinstance(out, str):
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return {}
    return out


def get_document_family_id(item):
    """Extract document_family_id from a sample."""
    out = parse_output(item)
    si_ref = out.get("shipping_instruction_reference", "").strip()
    if si_ref:
        return si_ref
    # Fallback hash
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


def structural_fingerprint(item):
    """Create a structural fingerprint (shipper+consignee+goods+POL+POD)."""
    out = parse_output(item)
    parties = out.get("parties", [])
    shipper = next((p["party_name"] for p in parties if p.get("party_role_code") == "CZ"), "")
    consignee = next((p["party_name"] for p in parties if p.get("party_role_code") == "CN"), "")
    cargo = out.get("cargo_items", [{}])[0] if out.get("cargo_items") else {}
    goods = cargo.get("description_of_goods", "")
    plans = out.get("transport_plans", [{}])[0] if out.get("transport_plans") else {}
    pol = plans.get("port_of_loading", {}).get("location_name", "")
    pod = plans.get("port_of_discharge", {}).get("location_name", "")
    freight = (out.get("freight_payment_term_code") or "").strip().upper()
    return f"{shipper}|{consignee}|{goods}|{pol}|{pod}|{freight}".upper()


def main():
    print("=" * 70)
    print("CerberusVision Phase 5 — Veri Sizintisi Dogrulama")
    print("=" * 70)

    # --- Load ---
    print("\n[1] Loading data...")
    train, train_broken = load_jsonl(TRAIN_FILE)
    val, val_broken = load_jsonl(VAL_FILE)
    total_broken = train_broken + val_broken
    print(f"  Train: {len(train)} samples ({train_broken} broken)")
    print(f"  Validation: {len(val)} samples ({val_broken} broken)")

    # --- Check 1: Broken JSON ---
    print(f"\n  [Check 1] Broken JSON lines: {total_broken} {'OK' if total_broken == 0 else '*** FIX NEEDED'}")

    # --- Check 2: Exact duplicates in train ---
    print("\n[2] Checking exact duplicates in train...")
    seen_train = {}
    train_dupes = 0
    for item in train:
        key = f"{item['input'].strip()}|||{item['output'].strip()}"
        if key in seen_train:
            train_dupes += 1
        else:
            seen_train[key] = item
    print(f"  Train exact duplicates: {train_dupes} {'OK' if train_dupes == 0 else '*** REMOVE THESE'}")

    # --- Check 3: Exact input overlap ---
    print("\n[3] Checking exact input overlap (train vs validation)...")
    train_inputs = {item["input"].strip() for item in train}
    val_inputs = {item["input"].strip() for item in val}
    input_overlap = train_inputs & val_inputs
    print(f"  Exact input overlap: {len(input_overlap)} {'OK' if len(input_overlap) == 0 else '*** LEAKAGE'}")

    # --- Check 4: Exact output overlap ---
    print("\n[4] Checking exact output overlap (train vs validation)...")
    train_outputs = set()
    for item in train:
        out = item["output"]
        if isinstance(out, dict):
            out = json.dumps(out, sort_keys=True)
        train_outputs.add(out.strip())
    val_outputs = set()
    for item in val:
        out = item["output"]
        if isinstance(out, dict):
            out = json.dumps(out, sort_keys=True)
        val_outputs.add(out.strip())
    output_overlap = train_outputs & val_outputs
    print(f"  Exact output overlap: {len(output_overlap)} {'OK' if len(output_overlap) == 0 else '*** LEAKAGE'}")

    # --- Check 5: Family-based overlap (DOCUMENT_FAMILY_ID) ---
    print("\n[5] Checking document family overlap (PRIMARY CHECK)...")
    train_families = defaultdict(list)
    val_families = defaultdict(list)

    for item in train:
        fid = get_document_family_id(item)
        train_families[fid].append(item)
    for item in val:
        fid = get_document_family_id(item)
        val_families[fid].append(item)

    train_fids = set(train_families.keys())
    val_fids = set(val_families.keys())
    family_overlap = train_fids & val_fids

    if family_overlap:
        print(f"  *** DATA LEAKAGE: {len(family_overlap)} families in BOTH train and validation!")
        for fid in sorted(family_overlap):
            print(f"      {fid}: train={len(train_families[fid])}, val={len(val_families[fid])}")
    else:
        print(f"  OK Zero family overlap: all {len(train_fids)} train families and {len(val_fids)} validation families are disjoint")

    # --- Check 6: Structural fingerprint overlap ---
    print("\n[6] Checking structural fingerprint overlap...")
    train_sfp = {structural_fingerprint(item) for item in train}
    val_sfp = {structural_fingerprint(item) for item in val}
    sfp_overlap = train_sfp & val_sfp
    if sfp_overlap:
        print(f"  NOTE: {len(sfp_overlap)} structural fingerprints appear in both sets")
        print(f"        (different SI refs may share parties/goods — this is OK if families differ)")
        for sfp in sorted(sfp_overlap):
            train_fids_with_sfp = {get_document_family_id(item) for item in train
                                   if structural_fingerprint(item) == sfp}
            val_fids_with_sfp = {get_document_family_id(item) for item in val
                                 if structural_fingerprint(item) == sfp}
            if train_fids_with_sfp != val_fids_with_sfp:
                print(f"        OK: Different families share same structure")
                print(f"        Train families: {train_fids_with_sfp}")
                print(f"        Val families: {val_fids_with_sfp}")
    else:
        print(f"  OK No structural fingerprint overlap")

    # --- Check 7: Near-duplicate similarity check (full scan) ---
    print("\n[7] Checking near-duplicate similarity (full scan)...")
    # Check ALL validation items against ALL train items
    val_sample = val

    suspicious_pairs = []
    for i, val_item in enumerate(val_sample):
        val_input = val_item["input"]
        # Find best match in train
        best_score = 0
        best_train_idx = -1
        for j, train_item in enumerate(train):
            score = SequenceMatcher(None, val_input, train_item["input"]).ratio()
            if score > best_score:
                best_score = score
                best_train_idx = j

        if best_score > SIMILARITY_THRESHOLD:
            suspicious_pairs.append((i, best_train_idx, best_score, val_item, train[best_train_idx]))

    if suspicious_pairs:
        print(f"  WARNING: {len(suspicious_pairs)} validation samples have >{SIMILARITY_THRESHOLD*100:.0f}% similar train counterparts")
        for vi, ti, score, val_item, train_item in suspicious_pairs[:5]:
            val_fid = get_document_family_id(val_item)
            train_fid = get_document_family_id(train_item)
            print(f"    Val[{vi}] <-> Train[{ti}]: similarity={score:.3f}")
            print(f"      Val family:  {val_fid}")
            print(f"      Train family: {train_fid}")
            if val_fid == train_fid:
                print(f"      *** SAME FAMILY — DATA LEAKAGE!")
    else:
        print(f"  OK No suspicious near-duplicates found (threshold: {SIMILARITY_THRESHOLD*100:.0f}%)")

    # --- Statistics ---
    print("\n" + "=" * 70)
    print("STATISTICS")
    print("=" * 70)
    print(f"  Train samples:             {len(train)}")
    print(f"  Validation samples:        {len(val)}")
    print(f"  Validation ratio:          {len(val)/(len(train)+len(val))*100:.1f}%")
    print(f"  Unique train families:     {len(train_fids)}")
    print(f"  Unique validation families: {len(val_fids)}")
    print(f"  Unique validation outputs: {len(val_outputs)}")
    print(f"  Train exact duplicates:    {train_dupes}")

    print(f"\n  Train families:")
    for fid in sorted(train_fids):
        print(f"    {fid:35s} -> {len(train_families[fid]):4d} samples")

    print(f"\n  Validation families:")
    for fid in sorted(val_fids):
        items = val_families[fid]
        sample_out = parse_output(items[0])
        parties = sample_out.get("parties", [])
        shipper = next((p["party_name"] for p in parties if p.get("party_role_code") == "CZ"), "N/A")
        cargo = sample_out.get("cargo_items", [{}])[0] if sample_out.get("cargo_items") else {}
        goods = cargo.get("description_of_goods", "N/A")
        print(f"    {fid:35s} -> {len(items):4d} samples")
        print(f"      Shipper: {shipper[:50]}")
        print(f"      Goods: {goods[:50]}")

    # --- Final Verdict ---
    print("\n" + "=" * 70)
    print("FINAL VERDICT")
    print("=" * 70)

    checks = [
        ("Broken JSON", total_broken == 0),
        ("Train exact duplicates", train_dupes == 0),
        ("Exact input overlap", len(input_overlap) == 0),
        ("Exact output overlap", len(output_overlap) == 0),
        ("FAMILY-BASED LEAKAGE", len(family_overlap) == 0),
        ("Near-duplicate leakage", len(suspicious_pairs) == 0),
    ]

    all_pass = True
    for name, passed in checks:
        status = "OK PASS" if passed else "*** FAIL"
        print(f"  [{status}] {name}")
        if not passed:
            all_pass = False

    if all_pass:
        print("\n  VERDICT: DATA IS CLEAN — Ready for training.")
        print("  Validation measures generalization to NEW document templates.")
    else:
        print("\n  VERDICT: DATA HAS ISSUES — Fix before training.")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
