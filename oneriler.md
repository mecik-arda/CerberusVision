# Phase 5.1 Strateji ve Öneriler

## Phase 5 Sonuçları (25.07.2026)

Phase 5 temiz veri eğitimi Colab A100'de tamamlandı. Sonuçlar:

| Metrik | Temel Qwen | Phase 4 | **Phase 5** | vs Temel |
|---|---:|---:|---:|---|
| Doğruluk | %69.01 | %76.86 | **%72.31** | +3.3 ✅ |
| Kesinlik | %49.85 | %53.45 | **%52.01** | +2.2 ✅ |
| Geri Çağırma | %90.76 | %91.18 | **%89.74** | -1.0 |
| F1 | %64.35 | %67.39 | **%65.85** | +1.5 ✅ |
| XSD Geçiş | 13/13 | 12/13 | **13/13** | = |
| Çıkarım Hatası | 0 | 1 | **0** | = |

Eğitim: 198 adım, 3 epoch, LoRA rank=16 alpha=32, en iyi checkpoint adım 40 (eval_loss=0.169).

---

## Phase 5'ten Çıkarılan Dersler

### 1. En büyük kazanım: kararlılık

Phase 5'in en önemli başarısı **sıfır çıkarım hatası ve %100 XSD geçişi**.
Phase 4 ve Legacy, `TR_Konsimento_Talimati` vakasında uzun/kapanmamış JSON üreterek
çöküyordu. Phase 5 bu belgede de geçerli XML üretiyor. Doğruluk düşük (%23) ama
**çökme yok**. Bu üretim kullanımı için kritik bir eşik.


### 2. Overfitting: erken peak, sonra ezber

Eval loss adım 40'ta 0.169 ile zirve yaptı, sonra sürekli yükselerek 0.203'e çıktı.
Train loss ise 0.049'a kadar düşmeye devam etti. Bu klasik overfitting:

```
Adım 20:  eval_loss=0.217
Adım 40:  eval_loss=0.169  ← EN İYİ (early stopping 3 değerlendirme sonra tetiklenmeliydi)
Adım 60:  eval_loss=0.189  ← patience=2 olsa burada dururdu
Adım 80:  eval_loss=0.194
Adım 100: eval_loss=0.199
Adım 120: eval_loss=0.201
...
Adım 198: eval_loss=0.203  ← 3 epoch sonu
```

**Phase 5.1 için**: `early_stopping_patience=2` (3 değerlendirme yerine 2),
`eval_steps=10` (daha sık kontrol) veya `eval_steps=15` + `patience=2`.

### 3. Ekipman kategorisi hâlâ en zayıf halka

Ekipman doğruluğu %41.4'te sabit kaldı — ne temel model ne Phase 4 ne Phase 5
bu kategoride ilerleme sağlayamadı. Sorun **çoklu konteyner indeks kayması**:
konteyner numaraları, ISO kodları, ağırlıklar ve mühürler konteynerler arasında
karışıyor. Model ekipman özelliklerini doğru konteynerle eşleştiremiyor.

**Phase 5.1 için**: Eğitim verisine özellikle çoklu konteyner (3-5 ekipman)
örnekleri eklenmeli. `equipment_reference` ↔ `cargo_gross_weight` ↔ `seal_number`
bağlantısını pekiştirecek varyantlar çoğaltılmalı.

### 4. Rec 21 Çift Kademeli Kural Motoru Başarısı

Kural motoruna eklenen **çift kademeli Rec 21 ambalaj normalizasyonu** ve fixture düzeltmeleri sonrasında gerçek Phase 5 doğruluğu ortaya çıktı:

**Üç Aşamalı Karşılaştırma:**
- **Base (Orijinal):** %72.3 Genel Doğruluk / %80.9 Yük Kalemleri (6 ambalaj kodu hatası)
- **ISO (Yalnızca Fixture Fix):** %70.9 Genel Doğruluk / %73.5 Yük Kalemleri (21 sahte hata)
- **Fix (Fixture + Backend Rec21 Kuralı):** **%72.9 Genel Doğruluk / %82.3 Yük Kalemleri** (Sadece 3 gerçek hata)

**Rec 21 Düzeltmesi Ne Yaptı?**
21 sahte hatayı 3 gerçek hataya indirdi. Kalan 3 hata, modelin `nested_packaging` vakasında yanlış paket türü (PL/CR yerine CT/DR) seçmesinden kaynaklanan gerçek model hatalarıdır.

**Belge Bazlı Kazançlar:**
- `Dangerous_Goods`: %72.7 → %75.8 (+3.1)
- `Multi_Container`: %68.2 → %69.7 (+1.5)
- Diğer belgelerdeki ISO run kaynaklı sahte kayıplar (-4/-6 puan) telafi edilerek base seviyesine döndü.
- `TR_Konsimento`: %23.1'de kalarak (geçici PDF varyansı hariç) modelin bu konudaki zayıflığını net biçimde doğruladı.

**Son Durum:**
`%72.9` doğruluk, `%52.2` kesinlik, `%89.8` geri çağırma, `%66.0` F1 ve `13/13` XSD geçiş oranı ile Phase 5 şu ana kadarki en yüksek ve stabil kategori skoru olan **Yük Kalemleri (%82.3)** seviyesine ulaştı. 
**Ekipman doğruluğu ise %41.4'te takılı kaldı.** Bu nedenle Phase 5.1'in ana hedefi kesinlikle Ekipman ve Çoklu Konteyner eşleştirmeleri olmalıdır.


### 5. Türkçe BL vakası (%23) en büyük fırsat

`TR_Konsimento_Talimati` 13 alandan sadece 3'ünü doğru çıkardı (document_status_code,
iki liman). Tarafların hiçbiri çıkarılamadı (party_role_code, party_name, party_id,
address — hepsi missing). Bu vaka eğitim verisinde hiç Türkçe BL olmamasından
kaynaklanıyor.

**Phase 5.1 için**: Türkçe konşimento örnekleri en yüksek öncelikli ekleme.


## Phase 5.1 Stratejisi

### Hedef

Phase 5.1'in amacı: **Türkçe BL, reefer ve yeni belge aileleriyle modelin
genelleme yeteneğini artırmak**, Phase 5'in kararlılığını koruyarak
doğruluğu Phase 4 seviyesinin üzerine taşımak.

### Eklenecek Veriler (öncelik sırasıyla)

#### 1. Türkçe Konşimento Ailesi (EN YÜKSEK ÖNCELİK)

- **Neden**: Benchmark'ta `TR_Konsimento_Talimati` %23 doğrulukta. Train'de hiç Türkçe BL yok.
- **Etki**: Yüksek — mevcut en zayıf vakayı doğrudan iyileştirir.
- **Efor**: Yüksek — sıfırdan etiketli Türkçe BL verisi gerek.
- **Hedef**: En az 15-20 Türkçe BL örneği. Farklı formatlar (Ticaret Bakanlığı,
  özel hatlar, forwarder formatları).
- **Etiketleme**: OCR → manuel JSON etiketleme → Phase 5 formatında kaydetme.

#### 2. Reefer/Soğutmalı Konteyner Verisi

- **Neden**: `reefer_benchmark` %72.92 doğrulukta. Sıcaklık, nem, havalandırma
  alanları sadece kural motoruyla yakalanıyor.
- **Etki**: Orta — mevcut performans fena değil ama iyileştirilebilir.
- **Efor**: Orta — mevcut reefer verileri augmentasyonla çoğaltılabilir.
- **Hedef**: 10-15 yeni reefer örneği. `-18°C`, `+2°C`, `SET TEMP`, `VENTILATION`
  gibi alanları içeren.

#### 3. Gerçek BL PDF'lerinden Yeni Aileler

- **Neden**: Model şu anda sadece 11 belge ailesini biliyor. Yeni formatlar
  genellemeyi artırır.
- **Etki**: Orta-Yüksek.
- **Efor**: Çok yüksek — manuel etiketleme gerek.
- **Hedef**: 3-5 yeni belge ailesi, her birinden 5-10 örnek.

### Continual Fine-Tuning Yaklaşımı

Phase 5.1 **sıfırdan eğitim değil**, Phase 5 adapter'ından **continual fine-tuning**
olarak yapılmalı. Bu, Phase 5'in kararlılığını (sıfır çökme) korurken yeni verileri
öğretir.

**Veri karışım oranı**:

| Veri Kaynağı | Oran | Açıklama |
|---|---|---|
| Yeni Türkçe BL | %35 | En yüksek öncelikli yeni veri |
| Yeni Reefer | %20 | Soğutmalı konteyner verileri |
| Yeni belge aileleri | %15 | Hiç görülmemiş formatlar |
| Phase 5 replay | %30 | Eski belge türlerinde gerilemeyi önler |

Replay verisi olmadan sadece yeni veri verilirse model eski belge türlerinde
(unstructured email, dangerous goods, multi-container) gerileyebilir (catastrophic forgetting).

### Eğitim Konfigürasyonu

```python
# Phase 5.1 continual fine-tuning
training_config = {
    "base_model": "Qwen/Qwen2.5-7B-Instruct",
    "resume_from_checkpoint": "models/Qwen-2.5-7B-Instruct-Phase5-LoRA",  # Phase 5 adapter'dan devam
    "qlora": True,                 # NF4 4-bit
    "lora_r": 16,
    "lora_alpha": 32,
    "lora_dropout": 0.05,
    "target_modules": ["gate_proj", "k_proj", "q_proj", "v_proj", "down_proj", "up_proj", "o_proj"],

    # Overfitting kontrolü (Phase 5 deneyiminden)
    "max_epochs": 5,               # Daha az epoch
    "eval_steps": 10,              # Daha sık değerlendirme
    "save_steps": 10,
    "early_stopping_patience": 2,  # 2 değerlendirme iyileşmezse dur (3 yerine 2)
    "early_stopping_threshold": 0.001,  # Minimum iyileşme eşiği

    # Batch
    "per_device_train_batch_size": 2,
    "gradient_accumulation_steps": 8,  # Etkin batch 16
    "learning_rate": 1e-5,         # Continual için daha düşük LR (Phase 5'teki 5e-5 yerine)
    "lr_scheduler_type": "cosine",
    "warmup_steps": 5,
    "max_seq_length": 2048,
    "packing": False,
}
```

**Önemli değişiklikler**:
- **Daha düşük LR (1e-5)**: Continual fine-tuning'de catastrophic forgetting'i önler
- **Daha sık eval (10 adım)**: Overfitting'i erken yakalar
- **Daha agresif early stopping (patience=2)**: Phase 5'teki geç kalma sorununu çözer
- **Phase 5 adapter'dan başla**: Sıfırdan değil, mevcut kararlılığı koru

### Eğitim Verisi Hazırlama

**ÖNEMLİ NOT:**
- Phase 5.1 eğitimi **Google Colab üzerinde A100 GPU** kullanılarak gerçekleştirilecektir.
- Eğitim dosyaları (split'ler) oluşturulurken, bilgisayarın **İndirilenler** klasöründeki `CerberusVision_Phase5_Colab-20260725T122003Z-1-001.zip` dosyası baz alınmalıdır (bu arşivdeki veriler temizlenmiş ve sızıntıdan arındırılmış baz veriyi içerir).

```bash
# Phase 5.1 veri hazırlama (yeni script)
.venv/bin/python scripts/prepare_phase5_1_data.py \
  --phase5-train CerberusVision_Phase5_Colab/phase5_train.jsonl \
  --new-turkish-bl veriler/turkce_bl/*.jsonl \
  --new-reefer veriler/reefer/*.jsonl \
  --new-families veriler/yeni_aileler/*.jsonl \
  --replay-ratio 0.30 \
  --validation-ratio 0.15 \
  --output-dir veriler/phase5_1_splits \
  --seed 3407
```

### Benchmark Fixture Düzeltmeleri

Phase 5.1'den önce veya eş zamanlı olarak şu fixture düzeltmeleri yapılmalı:

1. **Rec 21 paket kodları**: `"DRUM"` → `"DR"`, `"CARTON"` → `"CT"`, `"BOX"` → `"BX"`
   - Dosyalar: `dangerous_goods_benchmark.json`, `multi_container_benchmark.json`,
     `nested_packaging_benchmark.json`
2. **Port ismi temizleme**: `"NHAVA SHEVA"` → `"Nhava Sheva"` (case normalization)
   - Dosya: `narrative_unstructured_benchmark.json`

Bu düzeltmeler Phase 5 doğruluğunu ~1-1.5 puan, Phase 5.1'de daha fazla artıracak.

### Beklenen Sonuçlar

| Metrik | Phase 5 | Phase 5.1 Hedef | Açıklama |
|---|---:|---:|---|
| Doğruluk | %72.31 | **%78-82** | Türkçe BL + yeni aileler + fixture düzeltmeleri |
| XSD Geçiş | 13/13 | **13/13** | Kararlılık korunmalı |
| Çıkarım Hatası | 0 | **0** | Kritik — sıfır tolerans |
| TR_Konsimento | %23 | **%60+** | En büyük sıçrama burada bekleniyor |
| Reefer | %72.92 | **%80+** | Reefer verisi eklenince |
| Ekipman | %41.4 | **%55+** | Çoklu konteyner örnekleriyle |

### Gerileme Kontrolü

Phase 5.1 eğitimi sonrası şu kontroller yapılmalı:

```bash
# Phase 5 vs Phase 5.1 aynı donmuş benchmark'ta karşılaştır
.venv/bin/python scripts/benchmark_accuracy.py tests/fixtures/qwen_benchmark \
  --output benchmark_results_phase5_1.json \
  --html benchmark_report_phase5_1.html
```

Herhangi bir kategoride Phase 5'in altına düşülürse, replay oranı artırılıp
tekrar eğitim yapılmalı.

---

## OCR Augmentasyon Deneyi (Phase 5.0-OCR)

Phase 5.1'e paralel veya sonra yapılabilecek düşük maliyetli bir deney:

Phase 5'in aynı verisiyle, sadece OCR gürültüsü eklenmiş bir varyant eğit.
Bu, Phase 5.1'in temiz eğitimini etkilemez, ayrı bir adapter olarak kalır.

**Augmentasyon stratejisi**:
- Her temiz örnekten: 1 temiz + 1 hafif OCR bozuk + bazı örneklerde 1 orta bozuk
- Toplam veri ~2-2.5x (1043 → ~2500)
- Karakter değişimleri: O↔0, I↔1↔l, S↔5, B↔8, Z↔2, G↔6
- Boşluk/satır bozulmaları, noktalama kaybı
- **Input bozulur, output temiz kalır** (model OCR hatalarını düzeltmeyi öğrenir)

```bash
.venv/bin/python scripts/prepare_training_data.py \
  --source-data CerberusVision_Phase5_Colab/phase5_train.jsonl \
  --output-dir veriler/phase5_ocr_splits \
  --augment 2 \
  --ocr-noise \
  --validation-ratio 0.15 \
  --seed 3407
```

Aynı benchmark'ta Phase 5 Base ile karşılaştır. OCR gürültülü validation setinde
(`validation_ocr_noisy.jsonl`) özellikle `Scanned_Low_Quality` ve `Overstamped`
vakalarında iyileşme beklenir.

---

## Özet: Öncelikli Yapılacaklar

| # | Görev | Faz | Öncelik |
|---|---|---|---|
| 1 | Benchmark fixture'larını Rec 21 kodlarıyla güncelle | Hemen | 🔴 Kritik |
| 2 | Türkçe BL verisi topla ve etiketle | 5.1 hazırlık | 🔴 Kritik |
| 3 | Reefer örnekleri hazırla | 5.1 hazırlık | 🟡 Yüksek |
| 4 | `prepare_phase5_1_data.py` script'ini yaz | 5.1 hazırlık | 🟡 Yüksek |
| 5 | Phase 5.1 continual fine-tuning (Colab A100) | 5.1 eğitim | 🟡 Yüksek |
| 6 | Phase 5.1 benchmark ve Phase 5 ile karşılaştır | 5.1 doğrulama | 🟡 Yüksek |
| 7 | OCR augmentasyon deneyi | 5.0-OCR | 🟢 Orta |
| 8 | Yeni gerçek BL aileleri ekle | 5.1 genişletme | 🟢 Orta |
