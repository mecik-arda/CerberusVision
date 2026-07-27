#!/usr/bin/env python3
"""
CerberusVision — Token Uzunluk Guvenlik Kontrolu
=================================================

Egitim verisindeki en uzun ornegin token sayisini kontrol eder.
max_length asimi varsa truncation riski olusturur — erken uyari sistemi.

Calisma sekli:
  1. Tokenizer'i yukle (Qwen2.5)
  2. Tum train + validation orneklerini SFT formatinda tokenize et
  3. En uzun, en kisa, ortalama, medyan token sayilarini raporla
  4. max_length'i asan ornek varsa ALARM ver

Kullanim:
    .venv/bin/python scripts/check_token_lengths.py \
        --data-dir veriler/phase5_3_splits \
        --max-length 4096

    .venv/bin/python scripts/check_token_lengths.py \
        --train veriler/phase5_3_splits/train.jsonl \
        --val veriler/phase5_3_splits/validation.jsonl \
        --max-length 4096
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def load_jsonl(path: Path) -> list[dict]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return records


def format_sft(record: dict) -> str:
    """Apply SFT chat template (same as Colab notebook)."""
    # Chat format with system + user + assistant
    messages = [
        {"role": "system", "content": "Extract shipping instruction data from OCR text as JSON."},
        {"role": "user", "content": str(record["input"])},
        {"role": "assistant", "content": str(record["output"])},
    ]
    return messages


def main():
    parser = argparse.ArgumentParser(description="Token uzunluk guvenlik kontrolu")
    parser.add_argument("--data-dir", type=Path, help="Path to splits directory")
    parser.add_argument("--train", type=Path, help="Path to train.jsonl")
    parser.add_argument("--val", type=Path, help="Path to validation.jsonl")
    parser.add_argument("--max-length", type=int, default=4096, help="Max token limit (default: 4096)")
    parser.add_argument("--model-id", type=str, default="Qwen/Qwen2.5-7B-Instruct",
                        help="Tokenizer model ID (default: Qwen/Qwen2.5-7B-Instruct)")
    parser.add_argument("--top-n", type=int, default=10, help="Show top N longest examples")
    args = parser.parse_args()

    # Resolve paths
    if args.data_dir:
        train_path = args.data_dir / "train.jsonl"
        val_path = args.data_dir / "validation.jsonl"
    else:
        train_path = args.train
        val_path = args.val

    if not train_path or not train_path.exists():
        print(f"HATA: Train dosyasi bulunamadi: {train_path}")
        sys.exit(1)

    # Load tokenizer
    print(f"Tokenizer yukleniyor: {args.model_id}...")
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.model_id)
    print(f"  Tokenizer hazir. Vocab size: {tokenizer.vocab_size}")

    # Load data
    print(f"\nVeriler yukleniyor...")
    train_records = load_jsonl(train_path)
    print(f"  Train: {len(train_records)} records from {train_path.name}")

    val_records = []
    if val_path and val_path.exists():
        val_records = load_jsonl(val_path)
        print(f"  Validation: {len(val_records)} records from {val_path.name}")

    all_records = train_records + val_records

    # Tokenize
    print(f"\nTokenize ediliyor ({len(all_records)} ornek)...")
    token_counts = []
    for i, record in enumerate(all_records):
        messages = format_sft(record)
        try:
            text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=False,
            )
        except Exception:
            # Fallback: manual format
            text = ""
            for msg in messages:
                text += f"<|im_start|>{msg['role']}\n{msg['content']}<|im_end|>\n"

        tokens = tokenizer.encode(text, add_special_tokens=False)
        token_counts.append({
            "index": i,
            "source": "train" if i < len(train_records) else "val",
            "token_count": len(tokens),
            "input_chars": len(record.get("input", "")),
            "output_chars": len(record.get("output", "")),
        })

    # Sort by token count descending
    token_counts.sort(key=lambda x: x["token_count"], reverse=True)

    # Statistics
    counts = [t["token_count"] for t in token_counts]
    max_count = max(counts)
    min_count = min(counts)
    avg_count = sum(counts) / len(counts)
    median_count = sorted(counts)[len(counts) // 2]

    # Count exceeding
    over_limit = [t for t in token_counts if t["token_count"] > args.max_length]
    near_limit = [t for t in token_counts if args.max_length * 0.85 <= t["token_count"] <= args.max_length]

    # Report
    print("\n" + "=" * 70)
    print("TOKEN UZUNLUK RAPORU")
    print("=" * 70)
    print(f"  Model max_length:  {args.max_length}")
    print(f"  Toplam ornek:      {len(token_counts)}")
    print(f"  En uzun:           {max_count} tokens")
    print(f"  En kisa:           {min_count} tokens")
    print(f"  Ortalama:          {avg_count:.0f} tokens")
    print(f"  Medyan:            {median_count} tokens")
    print(f"  Limit asan:        {len(over_limit)} ornek (>{args.max_length})")
    print(f"  Limit yakin:       {len(near_limit)} ornek (%85-100)")

    # Safety buffer
    safety_margin = args.max_length - max_count
    if safety_margin >= 0:
        print(f"\n  ✅ Guvenli: En uzun ornek limitten {safety_margin} token kisa.")
        print(f"     Buffer: {safety_margin}/{args.max_length} = {safety_margin/args.max_length*100:.1f}%")
    else:
        print(f"\n  🔴 TEHLIKE: En uzun ornek limitten {-safety_margin} token UZUN!")
        print(f"     Bu ornekler truncation'a ugrayacak!")

    # Distribution histogram
    print(f"\n  Token Dagilimi:")
    buckets = [(0, 512), (512, 1024), (1024, 1536), (1536, 2048),
               (2048, 2560), (2560, 3072), (3072, 3584), (3584, 4096), (4096, 99999)]
    for lo, hi in buckets:
        in_range = sum(1 for c in counts if lo <= c < hi)
        if in_range > 0:
            label = f"{lo}-{hi}" if hi < 99999 else f"{lo}+"
            bar = "█" * (in_range * 60 // max(counts))
            pct = in_range / len(counts) * 100
            print(f"    {label:>10s}: {in_range:5d} ({pct:5.1f}%) {bar}")

    # Top N longest
    print(f"\n  En Uzun {args.top_n} Ornek:")
    print(f"  {'#':>4s} {'Kaynak':>6s} {'Token':>7s} {'Input Chars':>12s} {'Output Chars':>13s}")
    print(f"  {'-'*4} {'-'*6} {'-'*7} {'-'*12} {'-'*13}")
    for i, t in enumerate(token_counts[:args.top_n]):
        marker = " ⚠️" if t["token_count"] > args.max_length else ""
        print(f"  {i+1:4d} {t['source']:>6s} {t['token_count']:7d} {t['input_chars']:12d} {t['output_chars']:13d}{marker}")

    # Eval subset report
    train_only = [t for t in token_counts if t["source"] == "train"]
    val_only = [t for t in token_counts if t["source"] == "val"]
    if train_only:
        tmax = max(t["token_count"] for t in train_only)
        print(f"\n  Train en uzun: {tmax} tokens")
    if val_only:
        vmax = max(t["token_count"] for t in val_only)
        print(f"  Val en uzun:   {vmax} tokens")

    # Final verdict
    print("\n" + "=" * 70)
    if len(over_limit) > 0:
        print(f"🔴 GUvensiz: {len(over_limit)} ornek max_length'i ({args.max_length}) ASIYOR.")
        print("   Cozum: max_length'i artir VEYA veriyi kisalt.")
        sys.exit(1)
    else:
        print(f"✅ Guvenli: Tum ornekler {args.max_length} token siniri icinde.")
        print(f"   Guvenlik marji: {safety_margin} token ({safety_margin/args.max_length*100:.1f}%)")
        sys.exit(0)


if __name__ == "__main__":
    main()
