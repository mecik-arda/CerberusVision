# CerberusVision Phase 5.1 — From-Scratch QLoRA Fine-Tuning

Phase 5.1: Tum veriyle sifirdan QLoRA egitimi (Phase 5'in yerine gececek).

## Icerik

- `data/train.jsonl` — Egitim verisi (Phase 5 + Turkce BL + Reefer)
- `data/validation.jsonl` — Dogrulama verisi (global aile bazli, sifir sizinti)
- `CerberusVision_Phase5_1_Qwen_QLoRA.ipynb` — Colab egitim defteri

## Google Drive'a Yukleme

Colab'da calistirmadan once:

1. `MyDrive/CerberusVision_Phase5_1_Colab/` klasoru olusturun
2. `data/` klasorunu buraya yukleyin

## Phase 5.1 Stratejisi

- **From-scratch**: Sifir modelden basla (Phase 5 adapter yuklenmez)
- **Tum veri**: %100 Phase 5 + %100 yeni Turkce BL + %100 Reefer
- **Global aile split**: Ayni aile train VE validation'da olamaz
- **Erken durdurma**: patience=2, eval_steps=10
- **Seed**: 3407

## Tahmini Kaynak Kullanimi

- GPU: A100 (40 GB)
- Sure: ~45-60 dakika (1070 train + 160 val, 3-5 epoch)
- VRAM: ~12-15 GB (QLoRA 4-bit)
