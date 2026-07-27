# CerberusVision Phase 5.1 — From-Scratch QLoRA Fine-Tuning

Phase 5.1: Tum veriyle sifirdan QLoRA egitimi.

## Icerik

- `data/train.jsonl` — Egitim verisi
- `data/validation.jsonl` — Dogrulama verisi (global aile bazli, sifir sizinti)
- `CerberusVision_Phase5_1_Qwen_QLoRA.ipynb` — Colab egitim defteri

## Google Drive'a Yukleme

Colab'da calistirmadan once:

1. `MyDrive/CerberusVision_Phase5_1_Colab/` klasoru olusturun
2. `data/` klasorunu buraya yukleyin
3. `CerberusVision_Phase5_1_Qwen_QLoRA.ipynb` dosyasini bu klasore yukleyin

## Phase 5.1 Stratejisi

- **From-scratch**: Sifir modelden basla (onceki faz adapter'i yuklenmez)
- **Global aile split**: Ayni aile train VE validation'da olamaz
- **Erken durdurma**: patience=2, eval_steps=10
- **Seed**: 3407

## Tahmini Kaynak Kullanimi

- GPU: A100 (40 GB)
- VRAM: ~12-15 GB (QLoRA 4-bit)
