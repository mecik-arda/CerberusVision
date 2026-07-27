#!/usr/bin/env python3
"""
CerberusVision — Fazdan Bagimsiz Egitim Verisi Hazirlama
==========================================================

Tum fazlar (5.1, 5.2, 5.3, ...) icin global aile bazli train/validation split olusturur.
From-scratch VEYA continual fine-tuning modunda kullanilabilir.

Phase 5.1 stratejisi (oneriler.md):
- Phase 5 adapter'dan continual fine-tuning
- %35 Turkce BL, %20 Reefer, %15 Yeni Aileler, %30 Phase 5 replay

Phase 5.2/5.3 stratejisi:
- Sifirdan QLoRA (from-scratch)
- Tum veriyle replay (--replay-ratio 1.0)
- Global aile bazli split — sifir sizinti

Kullanim:
    # Phase 5.3 from-scratch
    .venv/bin/python scripts/prepare_phase5_1_data.py \
        --phase5-train CerberusVision_Phase5_Colab/phase5_train.jsonl \
        --new-turkish-bl veriler/phase5_2_turkce_bl.jsonl \
        --new-reefer veriler/phase5_3_multi_container.jsonl \
        --replay-ratio 1.0 \
        --validation-ratio 0.15 \
        --output-dir veriler/phase5_3_splits \
        --phase 5.3 \
        --seed 3407
"""

import argparse
import hashlib
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# --- Family ID extraction ---

def get_document_family_id(out_obj: dict) -> str:
    """
    Extract document family ID from output JSON.

    Uses shipping_instruction_reference as primary family identifier.
    Falls back to structural fingerprint hash.
    """
    si_ref = out_obj.get("shipping_instruction_reference", "").strip()
    if si_ref:
        return si_ref

    parties = out_obj.get("parties", [])
    shipper = next((p["party_name"] for p in parties if p.get("party_role_code") == "CZ"), "")
    consignee = next((p["party_name"] for p in parties if p.get("party_role_code") == "CN"), "")
    cargo = out_obj.get("cargo_items", [{}])[0] if out_obj.get("cargo_items") else {}
    goods = cargo.get("description_of_goods", "")
    plans = out_obj.get("transport_plans", [{}])[0] if out_obj.get("transport_plans") else {}
    pol = plans.get("port_of_loading", {}).get("location_name", "")
    pod = plans.get("port_of_discharge", {}).get("location_name", "")
    fp = f"{shipper}|{consignee}|{goods}|{pol}|{pod}".upper()
    return f"fp:{hashlib.sha256(fp.encode()).hexdigest()[:12]}"


def load_jsonl(path: Path) -> list[dict]:
    """Load a JSONL file, returning list of parsed records."""
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
            if "input" in record and "output" in record:
                records.append(record)
        except json.JSONDecodeError as e:
            print(f"  WARNING: Skipping malformed line in {path.name}: {e}")
    return records


def load_jsonl_dir(dir_path: Path) -> list[dict]:
    """Load all JSONL files from a directory."""
    records = []
    if dir_path.is_dir():
        for jsonl_file in sorted(dir_path.glob("*.jsonl")):
            loaded = load_jsonl(jsonl_file)
            print(f"  Loaded {len(loaded)} from {jsonl_file.name}")
            records.extend(loaded)
    return records


def parse_output(item: dict) -> dict:
    """Parse output field — handles both string and dict forms."""
    out = item.get("output", {})
    if isinstance(out, str):
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return {}
    return out


def assign_family_ids(records: list[dict]) -> list[dict]:
    """Assign document_family_id to each record based on shipping_instruction_reference."""
    for item in records:
        out_obj = parse_output(item)
        item["document_family_id"] = get_document_family_id(out_obj)
    return records


def group_by_family(records: list[dict]) -> dict[str, list[dict]]:
    """Group records by document_family_id."""
    families = defaultdict(list)
    for item in records:
        families[item["document_family_id"]].append(item)
    return dict(families)


def normalize_output(item: dict) -> dict:
    """Ensure output is a compact JSON string (no extra whitespace)."""
    out_obj = parse_output(item)
    return {
        "input": item["input"].strip(),
        "output": json.dumps(out_obj, ensure_ascii=False),
    }


def main():
    parser = argparse.ArgumentParser(
        description="CerberusVision Phase 5.1 — Continual Fine-Tuning Veri Hazirlama"
    )
    parser.add_argument(
        "--phase5-train",
        type=Path,
        required=True,
        help="Path to Phase 5 training JSONL (for replay data)"
    )
    parser.add_argument(
        "--new-turkish-bl",
        type=Path,
        nargs="*",
        default=[],
        help="Path(s) to new Turkish BL JSONL file(s)"
    )
    parser.add_argument(
        "--new-reefer",
        type=Path,
        nargs="*",
        default=[],
        help="Path(s) to new reefer JSONL file(s)"
    )
    parser.add_argument(
        "--new-families",
        type=Path,
        nargs="*",
        default=[],
        help="Path(s) to new document families JSONL file(s) or directories"
    )
    parser.add_argument(
        "--replay-ratio",
        type=float,
        default=0.30,
        help="Fraction of Phase 5 data to include as replay (default: 0.30)"
    )
    parser.add_argument(
        "--validation-ratio",
        type=float,
        default=0.15,
        help="Fraction of total data to reserve for validation (default: 0.15)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "veriler" / "phase5_1_splits",
        help="Output directory for train/validation JSONL files"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=3407,
        help="Random seed for reproducibility (default: 3407)"
    )
    parser.add_argument(
        "--phase",
        type=str,
        default="5.1",
        help="Phase label for manifest metadata (default: 5.1)"
    )
    args = parser.parse_args()

    random.seed(args.seed)

    # ============================================================
    # Step 1: Load all data sources
    # ============================================================
    print("=" * 70)
    print("Phase 5.1 Veri Hazirlama — Continual Fine-Tuning")
    print("=" * 70)

    print("\n[1] Loading data sources...")

    # New Turkish BL data (load first — needed for replay calculation)
    print("\n  Turkish BL:")
    turkish_bl_all = []
    for path in args.new_turkish_bl:
        if path.is_dir():
            loaded = load_jsonl_dir(path)
        else:
            loaded = load_jsonl(path)
        print(f"    {path.name}: {len(loaded)} records")
        turkish_bl_all.extend(loaded)
    turkish_bl_all = assign_family_ids(turkish_bl_all)
    turkish_bl_families = group_by_family(turkish_bl_all)
    print(f"    Total: {len(turkish_bl_all)} records in {len(turkish_bl_families)} families")

    # New reefer data
    print("\n  Reefer:")
    reefer_all = []
    for path in args.new_reefer:
        if path.is_dir():
            loaded = load_jsonl_dir(path)
        else:
            loaded = load_jsonl(path)
        print(f"    {path.name}: {len(loaded)} records")
        reefer_all.extend(loaded)
    reefer_all = assign_family_ids(reefer_all)
    reefer_families = group_by_family(reefer_all)
    print(f"    Total: {len(reefer_all)} records in {len(reefer_families)} families")

    # New document families
    print("\n  New families:")
    new_families_all = []
    for path in args.new_families:
        if path.is_dir():
            loaded = load_jsonl_dir(path)
        else:
            loaded = load_jsonl(path)
        print(f"    {path.name}: {len(loaded)} records")
        new_families_all.extend(loaded)
    new_families_all = assign_family_ids(new_families_all)
    new_families_fams = group_by_family(new_families_all)
    print(f"    Total: {len(new_families_all)} records in {len(new_families_fams)} families")

    # Phase 5 replay data — sample proportionally to achieve target ratio
    print("\n  Phase 5 replay:")
    phase5_all = load_jsonl(args.phase5_train)
    phase5_all = assign_family_ids(phase5_all)
    phase5_families = group_by_family(phase5_all)
    print(f"    Total available: {len(phase5_all)} records in {len(phase5_families)} families")

    new_data_total = len(turkish_bl_all) + len(reefer_all) + len(new_families_all)
    # replay_ratio = replay / (replay + new_data)  =>  replay = new_data * replay_ratio / (1 - replay_ratio)
    if args.replay_ratio >= 1.0:
        replay_needed = len(phase5_all)
    else:
        replay_needed = max(
            len(phase5_families),  # At least 1 record per family for diversity
            int(new_data_total * args.replay_ratio / max(0.01, 1.0 - args.replay_ratio))
        )
    replay_needed = min(replay_needed, len(phase5_all))

    # Stratified sample: pick records evenly across families, then shuffle
    phase5_by_family = list(phase5_families.items())
    random.shuffle(phase5_by_family)
    phase5_replay = []
    records_per_family = max(1, replay_needed // len(phase5_by_family))
    remaining = replay_needed
    for fid, items in phase5_by_family:
        take = min(len(items), records_per_family, remaining)
        sampled = random.sample(items, take)
        for item in sampled:
            item["document_family_id"] = fid
        phase5_replay.extend(sampled)
        remaining -= take
        if remaining <= 0:
            break
    # If we still need more, top up from remaining families
    if remaining > 0:
        all_phase5_shuffled = list(phase5_all)
        random.shuffle(all_phase5_shuffled)
        already_in = {id(item) for item in phase5_replay}
        for item in all_phase5_shuffled:
            if id(item) not in already_in:
                phase5_replay.append(item)
                already_in.add(id(item))
                remaining -= 1
                if remaining <= 0:
                    break

    replay_family_count = len(set(item["document_family_id"] for item in phase5_replay))
    replay_actual_pct = len(phase5_replay) / max(1, len(phase5_replay) + new_data_total) * 100
    print(f"    Replay sample: {len(phase5_replay)} records ({replay_family_count} families)")
    print(f"    Actual replay ratio: {replay_actual_pct:.1f}% (target: {args.replay_ratio*100:.0f}%)")

    # ============================================================
    # Step 2: Tag records with source, merge into global pool
    # ============================================================
    print("\n[2] Merging all data into global pool...")

    def tag_records(records: list[dict], source: str) -> list[dict]:
        for item in records:
            item["_source"] = source
        return records

    all_records = []
    all_records.extend(tag_records(phase5_replay, "phase5"))
    all_records.extend(tag_records(turkish_bl_all, "turkish_bl"))
    all_records.extend(tag_records(reefer_all, "reefer"))
    all_records.extend(tag_records(new_families_all, "new_families"))

    # Group globally by family_id
    global_families = group_by_family(all_records)
    print(f"  Global pool: {len(all_records)} records in {len(global_families)} families")

    # ============================================================
    # Step 3: Global family-based train/validation split
    # ============================================================
    print(f"\n[3] Global family-based train/validation split (val_ratio={args.validation_ratio})...")

    family_items = sorted(global_families.items(), key=lambda x: len(x[1]), reverse=True)
    total_records = len(all_records)
    target_val_records = max(1, int(total_records * args.validation_ratio))

    # Greedy: pick families until target validation size is reached
    val_fids = set()
    val_records = []
    current_val = 0
    remaining = [(fid, items) for fid, items in family_items]

    while current_val < target_val_records and remaining:
        best_idx = 0
        best_diff = float("inf")
        for i, (_, items) in enumerate(remaining):
            new_val = current_val + len(items)
            diff = abs(new_val - target_val_records)
            if diff < best_diff:
                best_diff = diff
                best_idx = i
        fid, items = remaining.pop(best_idx)
        val_fids.add(fid)
        val_records.extend(items)
        current_val += len(items)

    train_records = []
    for fid, items in family_items:
        if fid not in val_fids:
            train_records.extend(items)

    val_pct = len(val_records) / max(1, len(train_records) + len(val_records)) * 100
    print(f"  Train: {len(train_records)} records, Validation: {len(val_records)} records "
          f"({len(val_fids)} families, {val_pct:.1f}%)")

    # Per-category breakdown AFTER global split
    def count_by_source(records):
        counts = defaultdict(int)
        for r in records:
            counts[r.get("_source", "unknown")] += 1
        return dict(counts)

    train_sources = count_by_source(train_records)
    val_sources = count_by_source(val_records)
    print(f"  Train by source: {train_sources}")
    print(f"  Val by source:   {val_sources}")

    # Calculate actual mix percentages
    total_train = len(train_records)
    if total_train > 0:
        print("\n  Actual train mix:")
        for src, count in sorted(train_sources.items()):
            pct = count / total_train * 100
            print(f"    {src:15s}: {pct:.1f}% ({count} records)")

    # ============================================================
    # Step 4: Normalize output format
    # ============================================================
    print("\n[4] Normalizing output format...")
    train_all = [normalize_output(item) for item in train_records]
    val_all = [normalize_output(item) for item in val_records]

    # ============================================================
    # Step 5: Deduplicate within train
    # ============================================================
    print("\n[5] Removing exact duplicates within train...")
    seen = set()
    train_deduped = []
    dupes = 0
    for item in train_all:
        key = (item['input'].strip(), item['output'].strip())
        if key in seen:
            dupes += 1
        else:
            seen.add(key)
            train_deduped.append(item)
    print(f"  Duplicates removed: {dupes}")

    # Also check train/val overlap
    train_keys = {(item['input'].strip(), item['output'].strip()) for item in train_deduped}
    val_keys = {(item['input'].strip(), item['output'].strip()) for item in val_all}
    train_val_overlap = train_keys & val_keys
    if train_val_overlap:
        print(f"  WARNING: {len(train_val_overlap)} records appear in BOTH train and val!")
        val_all = [item for item in val_all
                   if (item['input'].strip(), item['output'].strip()) not in train_val_overlap]

    train_all = train_deduped

    # ============================================================
    # Step 6: Shuffle
    # ============================================================
    print(f"\n[6] Shuffling (seed={args.seed})...")
    random.shuffle(train_all)
    random.shuffle(val_all)

    # ============================================================
    # Step 7: Save
    # ============================================================
    print(f"\n[7] Saving to {args.output_dir}...")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    train_path = args.output_dir / "train.jsonl"
    val_path = args.output_dir / "validation.jsonl"
    manifest_path = args.output_dir / "manifest.json"

    train_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in train_all) + "\n",
        encoding="utf-8"
    )
    val_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in val_all) + "\n",
        encoding="utf-8"
    )

    # Manifest
    actual_ratios = {}
    if total_train > 0:
        actual_ratios = {src: round(count / total_train, 4)
                         for src, count in train_sources.items()}

    manifest = {
        "schema_version": 1,
        "phase": args.phase,
        "description": f"Phase {args.phase} training data (from-scratch)",
        "seed": args.seed,
        "validation_ratio": args.validation_ratio,
        "replay_ratio": args.replay_ratio,
        "train_count": len(train_all),
        "validation_count": len(val_all),
        "total_count": len(train_all) + len(val_all),
        "actual_ratios": actual_ratios,
        "split_method": "global_family_based",
        "sources": {
            "phase5": {
                "total": len(phase5_replay),
                "families": replay_family_count,
                "train": train_sources.get("phase5", 0),
                "validation": val_sources.get("phase5", 0),
            },
            "turkish_bl": {
                "total": len(turkish_bl_all),
                "families": len(turkish_bl_families),
                "train": train_sources.get("turkish_bl", 0),
                "validation": val_sources.get("turkish_bl", 0),
            },
            "reefer": {
                "total": len(reefer_all),
                "families": len(reefer_families),
                "train": train_sources.get("reefer", 0),
                "validation": val_sources.get("reefer", 0),
            },
            "new_families": {
                "total": len(new_families_all),
                "families": len(new_families_fams),
                "train": train_sources.get("new_families", 0),
                "validation": val_sources.get("new_families", 0),
            },
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # ============================================================
    # Step 8: Verification
    # ============================================================
    print("\n[8] Verifying zero leakage...")

    # Family overlap check (key defense against data leakage)
    train_fids = set()
    for item in train_all:
        out_obj = parse_output(item)
        train_fids.add(get_document_family_id(out_obj))

    val_fids = set()
    for item in val_all:
        out_obj = parse_output(item)
        val_fids.add(get_document_family_id(out_obj))

    overlap = train_fids & val_fids
    if overlap:
        print(f"  *** LEAKAGE DETECTED: {len(overlap)} families in both train and val! ***")
        for fid in sorted(overlap):
            print(f"      {fid}")
    else:
        print("  OK: Zero family overlap between train and validation")

    # Exact input overlap
    train_inputs = {item["input"].strip() for item in train_all}
    val_inputs = {item["input"].strip() for item in val_all}
    print(f"  Exact input overlap: {len(train_inputs & val_inputs)}")

    # ============================================================
    # Final Report
    # ============================================================
    actual_val_ratio = len(val_all) / max(1, len(train_all) + len(val_all)) * 100

    print("\n" + "=" * 70)
    print("FINAL REPORT")
    print("=" * 70)
    print(f"  Pool:              {len(global_families)} families, {total_records} records")
    print(f"  Phase 5 replay:    {len(phase5_replay)} records ({replay_family_count} families)")
    print(f"  Turkish BL new:    {len(turkish_bl_all)} records ({len(turkish_bl_families)} families)")
    print(f"  Reefer new:        {len(reefer_all)} records ({len(reefer_families)} families)")
    print(f"  New families:      {len(new_families_all)} records ({len(new_families_fams)} families)")
    print("  ---")
    print(f"  Train:             {len(train_all)} samples")
    print(f"  Validation:        {len(val_all)} samples")
    print(f"  Validation ratio:  {actual_val_ratio:.1f}%")
    print(f"  Val families:      {len(val_fids)}")
    print(f"  Family leakage:    {'*** YES ***' if overlap else 'OK NONE'}")
    print(f"  Train/Val overlap: {len(train_val_overlap)}")
    print("\n  Output files:")
    print(f"    {train_path}")
    print(f"    {val_path}")
    print(f"    {manifest_path}")
    print("\nPhase 5.1 Veri Paketi Hazir!")


if __name__ == "__main__":
    main()
