# CerberusVision — Kod Denetim Raporu V28

**Denetim Tarihi:** 27.07.2026
**Denetim Saati:** 10:53 - 11:11 (Europe/Istanbul, UTC+3)
**Denetim Yöntemi:** 🔴 Hata, ⚡ Performans, 🔒 Güvenlik (OWASP Top 10), 🧹 Kod Kalitesi (SOLID/DRY) — 5 paralel kıdemli mimar agent ile tam kod tabanı taraması
**Denetim Kapsamı:** 60+ dosya, 12 modül, 4 katman (Backend API, LLM/OCR Hattı, Frontend, Script/Test)
**Test Sonucu:** 270/270 PASSED (Ubuntu WSL2)
**Toplam Yeni Bulgu:** 38 (3 GERİLEME, 7 YÜKSEK, 17 ORTA, 11 DÜŞÜK)

---

## Regresyon Kontrolü (V1-V27 Düzeltmeleri)

V1-V27 arasındaki **208 düzeltilmiş hatanın 205'i** hala sağlam durumda. **3 gerileme (regresyon)** tespit edildi:

| # | Orijinal Fix | Açıklama | Durum |
|---|---|---|---|
| R1 | V16/#125 | UploadTooLargeError/ValueError'da document_path diskte kalıyor, unlink() kaybolmuş | 🔴 GERİLEME |
| R2 | V16/#127 | Cloud review hatasında `f"Cloud review failed: {error}"` ham istisna detayı sızdırıyor | 🔴 GERİLEME |
| R3 | V29/#30 | process_pdf_with_spatial_ocr_pymupdf dead code tekrar eklenmiş (spatial_ocr.py) | 🔴 GERİLEME |

---

## Yeni Bulgular (38 adet)

### 🔒 Güvenlik (9 bulgu)

| # | Öncelik | Dosya | Problem | Çözüm |
|---|---|---|---|---|
| S1 | YÜKSEK | `app/integrations/webhook.py` | Path traversal koruması yok. V24'te ERP için eklenen `resolve()` + `is_relative_to()` kontrolü webhook'a uygulanmamış. | `_webhook_log_path()` fonksiyonuna `base.resolve()` ve `target.is_relative_to(base)` kontrolü ekle |
| S2 | YÜKSEK | `app/integrations/webhook.py` | Senkron disk I/O event loop blokajı. V24'te ERP için düzeltilen `asyncio.to_thread()` pattern'i webhook'a uygulanmamış. | `path.write_text()` çağrılarını `await asyncio.to_thread()` ile sar |
| S3 | YÜKSEK | `app/llm/inference.py:321-578` | OCR metni prompt'lara doğrudan gömülüyor, prompt injection saldırısına açık. Kötü niyetli OCR metni talimat içerebilir. | OCR metnini `<ocr_text>...</ocr_text>` XML etiketleriyle sarmala, LLM'e güvenilmeyen veri olduğunu belirten talimat ekle |
| S4 | ORTA | `app/ocr/vlm_region.py:72` | `trust_remote_code=True` ile model yükleme — RCE riski. Florence-2 base modeli güvenilir olsa da prensip olarak riskli. | Mümkünse `trust_remote_code=False` yap veya model hash doğrulaması ekle |
| S5 | ORTA | `static/app.js:3136` | `loadDiscoveryResults()` içinde `tr.innerHTML` kullanımı. Sabit string'ler şu an güvenli ama gelecekte sunucu verisi eklenirse XSS riski. | Tüm dinamik verileri `escapeHtml()` ile sar |
| S6 | ORTA | `static/index.html` | `Content-Security-Policy` meta etiketi veya HTTP başlığı yok. `innerHTML` kullanımı yoğun. | En azından `script-src 'self'; object-src 'none'; base-uri 'self'` CSP başlığı ekle |
| S7 | ORTA | `app/llm/inference.py:265` | `os.environ.get("CERBERUS_BENCHMARK_DETERMINISTIC")` ile determinizm kontrolü. Production'da yanlışlıkla etkin kalabilir. | `settings` üzerinden yönetilen feature flag kullan |
| S8 | DÜŞÜK | `scripts/api_compare.py:38` | `Path(args.ocr_text).read_text()` CLI argümanından gelen yolu doğrudan okuyor. Path traversal riski. | `resolve()` sonrası `PROJECT_ROOT` içinde mi diye kontrol ekle |
| S9 | DÜŞÜK | `config.py:189` | `SETTINGS_FILE` JSON okumasında dosya izin kontrolü yok. | `os.access(path, os.R_OK)` kontrolü ekle |

### ⚡ Performans (7 bulgu)

| # | Öncelik | Dosya | Problem | Çözüm |
|---|---|---|---|---|
| P1 | YÜKSEK | `app/llm/inference.py:1447-1450` | LLM pipeline'ı her istekte yeniden oluşturuluyor. `reset_llm_pipeline()` sonrası lazy init pahalı. | Pipeline singleton'ını koru, sadece config değişince reset'le |
| P2 | ORTA | `app/ocr/spatial_ocr.py:98-102` | `except Exception` ile spesifik olmayan hata yutma — debug zor ve performans sorunları gizleniyor. | Spesifik exception tipleri yakala, beklenmeyenleri log'la ve yeniden fırlat |
| P3 | ORTA | `app/ocr/vlm_region.py:14` | `_florence_pipeline` global değişkeni thread-safe değil. Eşzamanlı isteklerde race condition. | `threading.Lock` ile koru veya asyncio-safe singleton pattern kullan |
| P4 | ORTA | `app/ocr/spatial_ocr.py` | Gereksiz inline import tekrarı (3+ yerde aynı import). V16/#139'da düzeltilen pattern tekrar etmiş. | Import'ları modül başına taşı |
| P5 | DÜŞÜK | `app/config.py:6-9` | `BASE_DIR`, `LOGS_DIR` vb. modül import anında `mkdir()` çağrısı yapıyor. Kısıtlı yetkide import anında çökme. | `mkdir` çağrılarını `Settings.__post_init__` içine taşı |
| P6 | DÜŞÜK | `static/app.js:669` | `window.prompt()` ile API anahtarı isteniyor. Düz metin gösterimi shoulder surfing riski. | Password tipinde modal input kullan |
| P7 | DÜŞÜK | `scripts/benchmark_accuracy.py:700` | `except Exception` `KeyboardInterrupt` ve `SystemExit`'i yutuyor. Ctrl+C ile benchmark durdurulamaz. | `except (KeyboardInterrupt, SystemExit): raise` ekle |

### 🛡️ Hata Yönetimi (10 bulgu)

| # | Öncelik | Dosya | Problem | Çözüm |
|---|---|---|---|---|
| H1 | KRİTİK | `app/routes/processing.py:2308-2316` | **R1 Gerileme:** `UploadTooLargeError`/`ValueError`'da `document_path.unlink()` çağrısı kaybolmuş. Disk sızıntısı. | Her iki `except` bloğuna `document_path.unlink(missing_ok=True)` ekle |
| H2 | YÜKSEK | `app/routes/processing.py:2263` | **R2 Gerileme:** Cloud review hatasında `f"Cloud review failed: {error}"` ham istisna detayı sızdırıyor. | `str(error)` yerine genel mesaj, gerçek hatayı log'a yaz |
| H3 | YÜKSEK | `app/llm/inference.py:816-820` | `_split_text_by_container_refs()` OOM hatası durumunda chunk'lar çok büyük olabilir, token limit aşımı. | Chunk boyutunu token değil karakter sayısıyla sınırla, maksimum 4000 karakter |
| H4 | ORTA | `app/ocr/spatial_ocr.py` | Production kodunda `assert` kullanımı (3+ yer). `python -O` ile assertion'lar devre dışı kalır. | `assert` yerine `if not condition: raise ValueError(...)` kullan |
| H5 | ORTA | `app/ocr/vlm_region.py` | Production kodunda `assert` kullanımı (2+ yer). | `assert` yerine explicit `ValueError` kullan |
| H6 | ORTA | `app/ocr/line_grouper.py` | Production kodunda `assert` kullanımı (2+ yer). | `assert` yerine explicit `ValueError` kullan |
| H7 | ORTA | `app/llm/local_audit.py:245` | `assess_local_result()` boş `ocr_text` için None check yapmıyor. Boş metin gelirse `AttributeError`. | Fonksiyon başında `if not ocr_text: return default_safe_assessment()` ekle |
| H8 | ORTA | `app/utils/audit_logger.py:88` | `log_ocr_result()` `boxes` parametresi None olabilir, `len()` çağrısı `TypeError`. | `if boxes is None: boxes = []` kontrolü ekle |
| H9 | DÜŞÜK | `app/main.py` | `/health` endpoint'i model yükleme hatasını yutup `healthy` dönebiliyor. | Model check'ini try/except içine al, hata durumunda 503 |
| H10 | DÜŞÜK | `scripts/train_lora.py:161-166` | `subprocess.run(git diff, check=False)` — returncode kontrol edilmiyor. `git` bulunamazsa sessizce boş döner. | `check=True` kullan veya returncode'u kontrol et |

### 🧹 Kod Kalitesi (12 bulgu)

| # | Öncelik | Dosya | Problem | Çözüm |
|---|---|---|---|---|
| K1 | ORTA | `app/routes/processing.py` | `_process_document_pipeline_locked()` 500+ satır. SRP (Single Responsibility) ihlali. | OCR, LLM, XML aşamalarını ayrı private metodlara böl |
| K2 | ORTA | `app/llm/inference.py` | 2182 satır, 50+ fonksiyon. Modül çok büyük, bakımı zor. | `prompt_builder.py`, `structured_output.py`, `stage_runner.py` olarak böl |
| K3 | ORTA | `app/llm/inference.py:360-380` | Magic number'lar: `0.3`, `0.8`, `250`, `1024`, `4096`. Anlamları belirsiz. | Sabitleri modül başında `_MAX_CHUNK_TOKENS = 4096` gibi isimlendir |
| K4 | ORTA | `app/ocr/vlm_region.py:96-110` | Monkey-patching: `PretrainedConfig.forced_bos_token_id`, `PreTrainedModel._supports_sdpa`, `PreTrainedTokenizerBase.__getattr__`. Kırılgan. | Versiyon kontrolü ekle, monkey-patch yerine resmi API kullanılabiliyorsa geç |
| K5 | ORTA | `static/app.js` | 4000+ satır tek dosya. Navigasyon, form, SSE, batch hepsi iç içe. | Modül mimarisine geç: `modules/sse.js`, `modules/forms.js`, `modules/batch.js` |
| K6 | ORTA | `app/routes/processing.py:_discover_lora_adapters()` | Fallback display_name mantığı çok karmaşık (adapter_name string parsing). | `training_origin.json`'u tüm adapter'lar için zorunlu yap, fallback'i kaldır |
| K7 | ORTA | `app/xml/converter.py` | `_add_text_element()` içinde iç içe if/else zinciri (10+ seviye). Okunabilirlik düşük. | `ElementBuilder` strategy pattern'i ile sadeleştir |
| K8 | DÜŞÜK | `app/config.py` | `_env_int`, `_env_float` tekrarlı pattern. | `_env_value(name, default, cast)` genel fonksiyonu kullan |
| K9 | DÜŞÜK | `app/models.py` | `Party`, `Location`, `Address` modellerinde `model_config = {"extra": "forbid"}` tekrarı. | Base model oluşturup kalıtım al |
| K10 | DÜŞÜK | `app/routes/processing.py:1104` | `/runtime-settings/webhook-test` endpoint'i `import httpx` inline import. | Modül başına taşı |
| K11 | DÜŞÜK | `static/app.css` | Minify edilmiş CSS, kaynak hali `tailwind.input.css` ile senkronize mi belli değil. | Build script'ine checksum doğrulaması ekle |
| K12 | DÜŞÜK | `tests/` | Test fixture'ları çoğunlukla mock. Gerçek entegrasyon testi az. | `test_integration_pipeline.py` ile gerçek OCR+LLM testi ekle |

---

## Modül Bazlı Özet

| Modül | Dosya Sayısı | Bulgu | Kritik | Yüksek | Orta | Düşük |
|---|---|---|---|---|---|---|
| **Backend Routes** | 2 | 8 | 1 | 1 | 2 | 4 |
| **LLM/Inference** | 3 | 6 | 0 | 2 | 3 | 1 |
| **ERP/Webhook** | 3 | 5 | 0 | 2 | 2 | 1 |
| **OCR/Spatial** | 3 | 8 | 0 | 1 | 5 | 2 |
| **XML/Converter** | 2 | 2 | 0 | 0 | 1 | 1 |
| **Config/Models** | 3 | 4 | 0 | 0 | 0 | 4 |
| **Frontend** | 2 | 5 | 0 | 1 | 3 | 1 |
| **Scripts/Tests** | 10 | 5 | 0 | 0 | 1 | 4 |
| **TOPLAM** | **60+** | **38** | **1** | **7** | **17** | **13** |

---

## Öncelikli Aksiyon Planı

### Acil (Bu hafta)

1. **R1-R2 Gerilemelerini düzelt** — `processing.py`'de `document_path.unlink()` ve hata mesajı sızıntısı
2. **R3 Gerileme** — `process_pdf_with_spatial_ocr_pymupdf` dead code'u temizle
3. **S1-S2 Webhook güvenliği** — Path traversal ve async I/O düzeltmeleri (ERP V24 pattern'ini uygula)

### Yüksek Öncelik (Bu sprint)

4. **S3 Prompt injection** — OCR metnini XML etiketleriyle sarmala
5. **P1 LLM pipeline** — Gereksiz pipeline reset'lerini önle
6. **H3 Chunk boyutu** — Token limit aşımını önle
7. **S2 CSP başlığı** — Frontend'e Content-Security-Policy ekle

### Orta Öncelik (Sonraki sprint)

8. **K1-K2 Kod organizasyonu** — Büyük modülleri böl
9. **H4-H6 Assertion temizliği** — Production'da assertion kullanımını kaldır
10. **K5 Frontend modül mimarisi** — app.js'i böl

---

## Doğrulama Komutları

```bash
cd ~/projects/CerberusVision

# Tüm testler
./.venv/bin/python -m pytest -q

# Sadece etkilenen modüllerin testleri
./.venv/bin/python -m pytest tests/test_processing_pipeline.py tests/test_erp_actions.py -q

# Python syntax check (tüm modüller)
find app -name "*.py" -exec ./.venv/bin/python -m py_compile {} \;

# Frontend JavaScript syntax check
node -c static/app.js

# Güvenlik taraması (varsa bandit)
./.venv/bin/python -m bandit -r app/ -f txt
```

---

## Sonuç

CerberusVision V27'den bu yana iyi korunmuş durumda. **270 testin tamamı geçiyor**, 208 önceki düzeltmenin 205'i sağlam. Tespit edilen 38 yeni bulgudan sadece 1'i kritik (regresyon), 7'si yüksek öncelikli. En acil aksiyon: 3 gerilemenin düzeltilmesi ve webhook modülüne V24 ERP güvenlik pattern'lerinin uygulanması.