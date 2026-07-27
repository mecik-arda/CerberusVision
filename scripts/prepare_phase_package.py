#!/usr/bin/env python3
"""
CerberusVision — Colab Egitim Paketi Hazirlama (Fazdan Bagimsiz)
==================================================================

Verilen faz numarasina gore tum dosyalari bir dizinde toplar:
  1. Egitim verisi (train.jsonl + validation.jsonl + manifest.json)
  2. Egitim notebook'u (hazirsa)
  3. README

Kullanim:
    .venv/bin/python scripts/prepare_phase_package.py 5.2
"""

import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main():
    if len(sys.argv) < 2:
        print("Kullanim: .venv/bin/python scripts/prepare_phase_package.py <phase>")
        print("Ornek:   .venv/bin/python scripts/prepare_phase_package.py 5.2")
        sys.exit(1)

    phase = sys.argv[1]  # "5.1", "5.2", vb.
    phase_underscore = phase.replace(".", "_")  # "5_2"
    phase_nodot = phase.replace(".", "")        # "52"

    package_dir = PROJECT_ROOT / f"CerberusVision_Phase{phase_underscore}_Colab"
    splits_dir = PROJECT_ROOT / "veriler" / f"phase{phase_underscore}_splits"
    notebook_name = f"CerberusVision_Phase{phase_underscore}_Qwen_QLoRA.ipynb"
    drive_dir = f"MyDrive/CerberusVision_Phase{phase_underscore}_Colab"

    # Clean data directory only (keep notebook if it exists)
    package_dir.mkdir(parents=True, exist_ok=True)
    data_dir = package_dir / "data"
    if data_dir.exists():
        shutil.rmtree(data_dir)

    # 1. Copy training data
    print(f"[1] Kopyalaniyor: Phase {phase} egitim verisi...")
    data_dir.mkdir()
    for fname in ["train.jsonl", "validation.jsonl", "manifest.json"]:
        src = splits_dir / fname
        if src.exists():
            shutil.copy2(src, data_dir / fname)
            size = src.stat().st_size
            print(f"    {fname} ({size:,} bytes)")
        else:
            print(f"    {fname} — BULUNAMADI: {src}")

    # 2. Notebook
    notebook_path = package_dir / notebook_name
    if notebook_path.exists():
        print(f"\n[2] Notebook mevcut: {notebook_path.name}")
    else:
        print(f"\n[2] Notebook BULUNAMADI: {notebook_path}")
        print(f"    Lutfen {notebook_name} dosyasini {package_dir} icine kopyalayin.")

    # 3. Create README
    print(f"\n[3] README olusturuluyor...")
    readme = f"""# CerberusVision Phase {phase} — From-Scratch QLoRA Fine-Tuning

Phase {phase}: Tum veriyle sifirdan QLoRA egitimi.

## Icerik

- `data/train.jsonl` — Egitim verisi
- `data/validation.jsonl` — Dogrulama verisi (global aile bazli, sifir sizinti)
- `{notebook_name}` — Colab egitim defteri

## Google Drive'a Yukleme

Colab'da calistirmadan once:

1. `{drive_dir}/` klasoru olusturun
2. `data/` klasorunu buraya yukleyin
3. `{notebook_name}` dosyasini bu klasore yukleyin

## Phase {phase} Stratejisi

- **From-scratch**: Sifir modelden basla (onceki faz adapter'i yuklenmez)
- **Global aile split**: Ayni aile train VE validation'da olamaz
- **Erken durdurma**: patience=2, eval_steps=10
- **Seed**: 3407

## Tahmini Kaynak Kullanimi

- GPU: A100 (40 GB)
- VRAM: ~12-15 GB (QLoRA 4-bit)
"""
    (package_dir / "README.md").write_text(readme, encoding="utf-8")

    # 4. Show summary
    print("\n" + "=" * 70)
    print(f"Phase {phase} Colab Paketi Hazir!")
    print(f"  Dizin:      {package_dir}")
    print(f"  Drive yolu: {drive_dir}")
    total_files = sum(1 for _ in package_dir.rglob("*") if _.is_file())
    print(f"  Dosya sayisi: {total_files}")
    print(f"\n  Google Drive'a yuklenecek klasor yapisi:")
    for item in sorted(package_dir.rglob("*")):
        if item.is_file():
            rel = item.relative_to(package_dir)
            print(f"    {rel}")


if __name__ == "__main__":
    main()
