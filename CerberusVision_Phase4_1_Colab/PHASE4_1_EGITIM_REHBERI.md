# CerberusVision Phase 4.1 Devam Eğitimi

Bu paket Phase 4 temiz QLoRA adapter'ını düşük öğrenme oranıyla kontrollü
biçimde geliştirmek için hazırlanmıştır. Temel modelden yeni adapter başlatmaz
ve mevcut Phase 4 adapter dosyalarının üzerine yazmaz.

## Neden Devam Eğitimi

Phase 4 donmuş OCR benchmark sonucu:

- Precision: yüzde 53,45
- Recall: yüzde 91,18
- F1: yüzde 67,39
- XSD: 12/13
- Inference error: 1

Phase 4 özellikle düşük kaliteli OCR, çok dilli belge ve çok konteynerli
belgelerde temel modelden daha iyi sonuç verdi. En belirgin zayıflıklar taşıma
alanlarında gereksiz değer üretimi, Türkçe vakada tekrarlı/kapanmayan JSON ve
bazı equipment/cargo satır hizalama hatalarıdır.

## Eğitim Karışımı

- 269 temiz Phase 4 train kaydı replay olarak korunur.
- 135 hedefli zor train kaydı deterministik olarak tekrar edilir.
- Toplam 404 eğitim kaydı vardır.
- Replay oranı yüzde 66,58'dir.
- Hard replay oranı yüzde 33,42'dir.
- 34 validation kaydı değişmeden korunur.
- 16 zor validation kaydı yalnız ayrı loss görünümü için kullanılır.
- 13 benchmark fixture'ı train verisinden fiziksel olarak ayrıdır.

Hard replay seçimi mevcut doğrulanmış etiketleri değiştirmez. Yalnız taşıma
alanları boş olan, Türkçe, çok ekipmanlı, çok kargolu, uzun, seyrek opsiyonel
alanlı veya OCR alfanümerik gürültüsü içeren temiz train örneklerini daha sık
gösterir.

## Google Drive Dizini

Google Drive altında aşağıdaki dizini oluşturun:

`MyDrive/CerberusVision_Phase4_1_Colab`

Bu repodaki `CerberusVision_Phase4_1_Colab` içeriğini aynı dizine yükleyin.
Ardından projedeki
`models/Qwen-2.5-7B-Instruct-Phase4-LoRA` dizinini Drive içindeki
`CerberusVision_Phase4_1_Colab/phase4_adapter` adıyla kopyalayın.

Notebook başlamadan önce parent adapter için şu hash'leri doğrular:

- `adapter_model.safetensors`:
  `ef99c4313a98dc1060e7aa97aa8b92962b13b24a65a6a8d7840c32095c0e5faf`
- `adapter_config.json`:
  `78cd1b0760239244d9036be3ca56224ec4515d141009c71f7fe71f68a5cadbcb`

## Colab Çalıştırma

1. Colab Pro çalışma zamanında A100 GPU seçin.
2. `CerberusVision_Phase4_1_Devam.ipynb` dosyasını açın.
3. Hücreleri sırayla çalıştırın.
4. İlk koşuda `RESUME_FROM_MATCHING_CHECKPOINT = False` bırakın.
5. Yalnız aynı koşu kesildiyse değeri `True` yapın.
6. Son hücrenin ürettiği delivery ZIP'i bilgisayara indirin.

## Eğitim Parametreleri

- Base model: `Qwen/Qwen2.5-7B-Instruct`
- Base revision:
  `a09a35458c702b33eeacc393d103063234e8bc28`
- Parent: Phase 4 temiz adapter
- Quantization: NF4 4-bit, double quantization
- Compute dtype: bfloat16
- Learning rate: `2e-5`
- Maximum epoch: 2
- Effective batch size: 16
- Warmup steps: 3
- Scheduler: cosine
- Evaluation interval: 5 optimizer adımı
- Early stopping patience: 2
- Early stopping threshold: `0.0002`
- Maximum sequence length: 2048
- Completion-only loss: etkin
- Packing: kapalı

## Kabul Kapısı

Phase 4.1 yalnız aşağıdaki koşulların tamamında üretim adayı olabilir:

- Precision en az yüzde 58
- Recall en az yüzde 90
- F1 en az yüzde 69
- XSD 13/13
- Inference error 0
- İki deterministik tekrar arasında mismatch 0

Validation loss düşse bile bu ölçütlerden biri sağlanmazsa Phase 4.1 varsayılan
yapılmaz. Phase 4 adapter korunur ve hata sınıfları yeniden analiz edilir.

## Paket Doğrulama

Projede aşağıdaki komutu çalıştırın:

```bash
python scripts/validate_phase4_1_colab_package.py
```

Doğrulayıcı veri hash'lerini, train/validation izolasyonunu, replay oranını,
parent adapter sözleşmesini, notebook sözdizimini ve kod hücrelerinde yorum
satırı bulunmadığını denetler.
