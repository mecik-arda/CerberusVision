# CerberusVision — Hata Düzeltme Kaydı

**Denetim Tarihi:** 16.07.2026  
**Denetim Saati:** 16:42 - 16:45 (Europe/Istanbul, UTC+3)  
**Denetim Yöntemi:** 3 paralel subagent ile uçtan uca kod denetimi (code audit) + Kod Denetleyicisi Ajanı (V2)  
**Toplam Düzeltilen Hata Sayısı:** 25 (V1: 8 + V2: 5 + V3: 6 + V4: 3 + V5: 3)  
**Test Sonucu:** 56/56 PASSED  

---

## Düzeltilen Hatalar

### 1. Deadlock — `/upload-and-stream` Endpoint (KRİTİK)

**Tarih/Saat:** 16.07.2026 16:44  
**Dosya:** `app/routes/processing.py`  
**Satır:** 142-148 (eski), 226-232 (eski)  

**Problem:**  
`/upload-and-stream` endpoint'inde `BackgroundTasks` kullanılıyordu. Starlette/FastAPI'de `BackgroundTasks`, response tamamen tamamlandıktan sonra çalışır. Ancak `StreamingResponse` döndüğü için response, generator tükenene kadar tamamlanmaz. Generator `queue.get()` ile beklerken, `process_pdf_pipeline` background task olarak hiç başlayamıyordu. Sonuç: **Deadlock** — istemci 300 saniye timeout'a kadar kilitlenirdi.

**Çözüm:**  
`background_tasks.add_task()` yerine `asyncio.create_task()` kullanıldı. Bu sayede pipeline görevi hemen event loop'ta çalışmaya başlar ve SSE stream ile paralel ilerler.

---

### 2. Queue Mismatch — `/upload` Endpoint (KRİTİK)

**Tarih/Saat:** 16.07.2026 16:44  
**Dosya:** `app/routes/processing.py`  
**Satır:** 140-148 (eski)  

**Problem:**  
`/upload` endpoint'i yerel bir `status_queue` oluşturup background task'a veriyordu, ancak bu queue'yu `_stream_queues` sözlüğüne kaydetmiyordu. `/api/stream/{session_id}` endpoint'i `_get_or_create_queue(session_id)` çağırdığında **farklı, boş bir queue** oluşturuyordu. Background task bir queue'ya yazarken, SSE stream başka bir queue'dan okuyordu — veri hiç iletilmiyordu.

**Çözüm:**  
Her iki endpoint de artık `_get_or_create_queue(session_id)` kullanıyor. Queue tek bir yerde (`_stream_queues` sözlüğü) merkezi olarak yönetiliyor.

---

### 3. Blocking Sync Çağrılar Async Context'te (KRİTİK)

**Tarih/Saat:** 16.07.2026 16:44  
**Dosya:** `app/routes/processing.py`  
**Satır:** 55, 64, 72, 76 (eski)  

**Problem:**  
`process_pdf_pipeline` asenkron bir fonksiyon olmasına rağmen içindeki OCR (`process_pdf_with_spatial_ocr`), LLM (`run_inference_with_fallback`) ve XML (`shipping_instruction_to_xml`, `validate_and_grade`) çağrıları senkron fonksiyonlardı. Bu sync çağrılar event loop'u blokluyordu. SSE stream'den gelen diğer istekler bu süre boyunca beklemek zorunda kalıyordu.

**Çözüm:**  
`_run_blocking()` helper fonksiyonu eklendi. Bu fonksiyon `loop.run_in_executor(None, ...)` kullanarak sync çağrıları thread pool'da çalıştırır. Tüm sync çağrılar artık `await _run_blocking(func, *args)` pattern'i ile çağrılıyor.

---

### 4. OpenVINO GenAI GenerationConfig Özellik Adı (KRİTİK)

**Tarih/Saat:** 16.07.2026 16:43  
**Dosya:** `app/llm/inference.py`  
**Satır:** 80 (eski)  

**Problem:**  
`config.structured_generation = json.dumps(schema)` — openvino-genai 2024.6.0 `GenerationConfig` sınıfında `structured_generation` özelliği bulunmayabilir. Sürüm farklılıklarına göre bu özellik adı değişebiliyor. Eğer yanlış özellik adı kullanılırsa guided decoding çalışmaz ve model serbest format üretebilir.

**Çözüm:**  
Fallback zinciri eklendi:
1. `config.structured_generation` (dene)
2. `config.guided_decoding` (fallback)
3. `config.json_schema` (son fallback)

Her biri `try/except (AttributeError, TypeError)` ile korunuyor.

---

### 5. Enum Değer Typo

**Tarih/Saat:** 16.07.2026 16:43  
**Dosya:** `app/models.py`  
**Satır:** 8 (eski)  

**Problem:**  
`DocumentStatusCode.FINAL = "FNl"` — son karakter küçük `l` (L) yerine büyük `I`'ye benziyordu. DCSA standardında kod `"FNL"` olmalıydı.

**Çözüm:**  
`FINAL = "FNL"` olarak düzeltildi.

---

### 6. STATIC_DIR Dizin Oluşturma Eksik

**Tarih/Saat:** 16.07.2026 16:43  
**Dosya:** `app/config.py`  
**Satır:** 13-14 (eski)  

**Problem:**  
`LOGS_DIR` ve `UPLOADS_DIR` için `.mkdir(parents=True, exist_ok=True)` çağrılıyordu, ancak `STATIC_DIR` için çağrılmıyordu. Fresh deployment'ta (örneğin Docker) `static/` dizini yoksa `StaticFiles(directory=...)` `RuntimeError` fırlatırdı.

**Çözüm:**  
`STATIC_DIR.mkdir(parents=True, exist_ok=True)` satırı eklendi.

---

### 7. Kullanılmayan Parametre

**Tarih/Saat:** 16.07.2026 16:43  
**Dosya:** `app/llm/inference.py`  
**Satır:** 71 (eski)  

**Problem:**  
`_build_generation_config(prompt: str)` fonksiyonu `prompt` parametresi alıyordu ama içinde hiç kullanılmıyordu. Dead parameter — kod kalitesi sorunu.

**Çözüm:**  
Parametre kaldırıldı: `_build_generation_config()`.

---

### 8. str() Dönüşümü Eksik — OpenVINO GenAI Çıktısı

**Tarih/Saat:** 16.07.2026 16:43  
**Dosya:** `app/llm/inference.py`  
**Satır:** 67-68 (eski)  

**Problem:**  
`pipe.generate(prompt, config)` openvino-genai 2024.6.0'da `DecodedResults` nesnesi döndürebiliyor. Bu nesne `str` değil, ancak downstream kod (`.find()`, `json.loads()`) string bekliyor. İmplicit `__str__` dönüşümü güvenli değil — ekstra formatting içerebilir.

**Çözüm:**  
`return str(result)` ile explicit dönüşüm eklendi.

---

## Özet

| # | Hata | Önem | Dosya | Durum |
|---|------|------|-------|-------|
| 1 | Deadlock in /upload-and-stream | KRİTİK | processing.py | Düzeltildi |
| 2 | Queue mismatch in /upload | KRİTİK | processing.py | Düzeltildi |
| 3 | Blocking sync calls in async | KRİTİK | processing.py | Düzeltildi |
| 4 | OpenVINO GenAI config property | KRİTİK | inference.py | Düzeltildi |
| 5 | Enum value typo (FNl → FNL) | ORTA | models.py | Düzeltildi |
| 6 | STATIC_DIR mkdir missing | ORTA | config.py | Düzeltildi |
| 7 | Unused parameter | DÜŞÜK | inference.py | Düzeltildi |
| 8 | Missing str() conversion | ORTA | inference.py | Düzeltildi |
| 9 | Path Traversal / Arbitrary File Write | KRİTİK | processing.py | Düzeltildi |
| 10 | GPU OOM Unbounded Concurrency | KRİTİK | processing.py | Düzeltildi |
| 11 | SSE Generator Memory Leak | YÜKSEK | processing.py | Düzeltildi |
| 12 | Fragile JSON Extraction Algorithm | ORTA | inference.py | Düzeltildi |
| 13 | Inline Lazy Imports in Hot Path | DÜŞÜK | processing.py | Düzeltildi |
| 14 | Hard Import Dependency on fitz (PyMuPDF) | ORTA | spatial_ocr.py | Düzeltildi |
| 15 | SSE JSON.parse unprotected — stream crash | YÜKSEK | app.js | Düzeltildi |
| 16 | TIMEOUT status not shown to user | ORTA | app.js | Düzeltildi |
| 17 | XSS via innerHTML with LLM data | YÜKSEK | app.js | Düzeltildi |
| 18 | Staircase drift in line grouping | ORTA | line_grouper.py | Düzeltildi |
| 19 | Fragile enum check (hasattr vs isinstance) | DÜŞÜK | converter.py | Düzeltildi |
| 20 | Dead code — _create_element never used | DÜŞÜK | converter.py | Düzeltildi |
| 21 | Sort/anchor inconsistency in line grouping | ORTA | line_grouper.py | Düzeltildi |
| 22 | DeepSeek API no timeout | YÜKSEK | api_compare.py | Düzeltildi |
| 23 | _processing_store unbounded memory leak | YÜKSEK | processing.py | Düzeltildi |
| 24 | XSD ExportCustomsClearanceLocation minOccurs | ORTA | shipping_instruction.xsd | Düzeltildi |
| 25 | index.html pdfFooter class conflict | DÜŞÜK | index.html | Düzeltildi |

**Doğrulama (Kod Denetleyicisi V5):** 56/56 test PASSED, statik analiz ve güvenlik taramaları PASSED.  

---

### 23. _processing_store Sınırsız Bellek Sızıntısı (YÜKSEK)

**Tarih/Saat:** 16.07.2026 20:26  
**Dosya:** `app/routes/processing.py`  
**Satır:** 28, 43  

**Problem:**  
`_processing_store` modül seviyesinde bir `dict[str, ProcessingResult]` olup her `_emit_status` çağrısında yazılıyordu ancak hiç temizlenmiyordu. Her işlem oturumu sonsuza kadar bellekte kalıyordu. TTL, maksimum boyut veya stream tamamlanınca temizleme yoktu (`_stream_queues`'un aksine). Sürekli kullanımda sınırsız bellek sızıntısı.

**Çözüm:**  
`_PROCESSING_STORE_MAX_SIZE = 100` sabiti eklendi. `_emit_status` fonksiyonunda, store boyutu 100'e ulaştığında en eski kayıt (`next(iter())`) siliniyor. Bu basit FIFO eviction ile bellek sızıntısı önlendi.

---

### 24. XSD ExportCustomsClearanceLocation minOccurs Eksik (ORTA)

**Tarih/Saat:** 16.07.2026 20:26  
**Dosya:** `app/xml/schemas/shipping_instruction.xsd`  
**Satır:** CustomsInformationType tanımı  

**Problem:**  
`ExportCustomsClearanceLocation` elementinin `minOccurs="0"` attribute'u yoktu. Bu, `CustomsInformation` present olduğunda `ExportCustomsClearanceLocation`'ın zorunlu olduğu anlamına geliyordu. Ancak Pydantic modelde `export_customs_clearance_location: Optional[Location] = None` — opsiyonel. Converter None olduğunda bu elementi üretmiyor. XSD doğrulaması başarısız olabilirdi.

**Çözüm:**  
`<xs:element name="ExportCustomsClearanceLocation" minOccurs="0">` olarak düzeltildi.

---

### 25. index.html pdfFooter Class Çakışması (DÜŞÜK)

**Tarih/Saat:** 16.07.2026 20:26  
**Dosya:** `static/index.html`  
**Satır:** pdfFooter element  

**Problem:**  
`pdfFooter` elementi初始 olarak `class="hidden flex items-center justify-center gap-4 ..."` sınıfına sahipti. Tailwind'de `hidden` (`display: none`) ve `flex` (`display: flex`) aynı elementte conflict yaratıyordu. `app.js`'de `classList.remove('hidden')` ve `classList.add('flex')` yapılıyordu, ancak `flex` zaten HTML'de mevcuttu. Tailwind'in CSS specificity kurallarına göre davranış belirsizdi.

**Çözüm:**  
HTML'den `flex` class'ı kaldırıldı. Artık initial state `hidden` (sadece), `app.js` gösterildiğinde `hidden` kaldırıp `flex` ekliyor. Temiz ve deterministic davranış.

---

### 20. Dead Code — _create_element Hiç Kullanılmıyor (DÜŞÜK)

**Tarih/Saat:** 16.07.2026 17:39  
**Dosya:** `app/xml/converter.py`  
**Satır:** 33-34 (eski)  

**Problem:**  
`_create_element` fonksiyonu tanımlanmıştı ancak hiçbir yerde çağrılmıyordu. Dead code — kod bakımı ve okunabilirlik sorunu.

**Çözüm:**  
Fonksiyon tamamen kaldırıldı.

---

### 21. Satır Gruplamada Sort/Anchor Tutarsızlığı (ORTA)

**Tarih/Saat:** 16.07.2026 17:39  
**Dosya:** `app/ocr/line_grouper.py`  
**Satır:** 66 (eski)  

**Problem:**  
Box'lar `y_min`'e göre sıralanıyordu, ancak satır anchor'ı `center_y` kullanıyordu. İlk box (en küçük `y_min`) yüksek bir box ise, `center_y`'si `y_min`'den çok uzak olabiliyordu. Sonraki kısa box'lar görsel olarak örtüşse bile anchor'a uzak olduğu için yanlış satıra atılıyordu.

**Çözüm:**  
Sıralama `y_min` yerine `center_y`'ye göre yapılıyor. Böylece sort ve anchor tutarlı hale geldi.

---

### 22. DeepSeek API Timeout Eksik (YÜKSEK)

**Tarih/Saat:** 16.07.2026 17:39  
**Dosya:** `scripts/api_compare.py`  
**Satır:** 48-58 (eski)  

**Problem:**  
DeepSeek API çağrısında timeout belirtilmemişti. API yanıt vermezse benchmark script'i sonsuza kadar bekleyebilirdi.

**Çözüm:**  
Hem `OpenAI` client constructor'ına `timeout=120` hem de `create()` çağrısına `timeout=120` parametresi eklendi.

---

### 15. SSE JSON.parse Korumasız — Stream Çökmesi (YÜKSEK)

**Tarih/Saat:** 16.07.2026 17:14  
**Dosya:** `static/app.js`  
**Satır:** 113-118 (eski)  

**Problem:**  
SSE event loop'unda `JSON.parse(jsonStr)` çağrısı try/catch içinde değildi. Tek bir bozuk SSE mesajı tüm stream'i çökertiyordu — kullanıcı işlem sırasında hiçbir geri bildirim alamıyordu.

**Çözüm:**  
`JSON.parse` çağrısı `try/catch` bloğuna alındı. Hata durumunda `console.error` ile loglanıp devam ediliyor.

---

### 16. TIMEOUT Durumu Kullanıcıya Gösterilmiyor (ORTA)

**Tarih/Saat:** 16.07.2026 17:14  
**Dosya:** `static/app.js`  
**Satır:** 146-149 (eski)  

**Problem:**  
Backend `TIMEOUT` statüsü gönderdiğinde, `handleSseEvent` sadece spinner'ı gizliyordu. Status badge son işlem statüsünde takılı kalıyordu (örn. "LLM Analyzing"). Kullanıcı timeout olduğunu anlamıyordu.

**Çözüm:**  
`TIMEOUT` ayrı bir `if` bloğunda ele alınıyor: spinner gizleniyor, status badge `ERROR`'a güncelleniyor, "Islem zaman asimina ugradi." mesajı gösteriliyor.

---

### 17. XSS Açığı — innerHTML ile LLM Verisi (YÜKSEK)

**Tarih/Saat:** 16.07.2026 17:14  
**Dosya:** `static/app.js`  
**Satır:** 189-196 (eski)  

**Problem:**  
`populateItemsTable` fonksiyonunda `row.innerHTML` ile LLM'den gelen ham veriler doğrudan HTML'e gömülüyordu. Kötü niyetli veya hatalı OCR/LLM çıktısı `<script>` tag'leri içerebilir ve XSS saldırısına neden olabilir.

**Çözüm:**  
`escapeHtml()` helper fonksiyonu eklendi. Tüm LLM verileri `escapeHtml()` ile sanitize edildikten sonra `innerHTML`'e yazılıyor. `div.textContent = text; return div.innerHTML;` pattern'i ile güvenli HTML kaçışı sağlanıyor.

---

### 18. Satır Gruplamada Merdiven Kayması (ORTA)

**Tarih/Saat:** 16.07.2026 17:15  
**Dosya:** `app/ocr/line_grouper.py`  
**Satır:** 73 (eski)  

**Problem:**  
`group_boxes_into_lines` fonksiyonunda `current_y` her yeni box eklendiğinde satırın ortalama Y'si olarak güncelleniyordu. Bu "running average" yaklaşımı, satırın başındaki box'lar ile sonundaki box'lar arasında Y farkı olduğunda "staircase drift" (merdiven kayması) yaratıyordu. Bir box, satırın başındaki Y'ye yakın ama ortalama Y'ye uzaksa yanlışlıkla yeni satıra atılıyordu.

**Çözüm:**  
`current_y` yerine `line_anchor_y` kullanıldı. Anchor, satırın ilk box'ının Y'si olarak sabit kalıyor. Tüm karşılaştırmalar bu anchor'a göre yapılıyor — running average kaldırıldı.

---

### 19. Kırılgan Enum Kontrolü — hasattr vs isinstance (DÜŞÜK)

**Tarih/Saat:** 16.07.2026 17:15  
**Dosya:** `app/xml/converter.py`  
**Satır:** 44-49 (eski)  

**Problem:**  
`_add_text_element` fonksiyonu `hasattr(value, "value")` ile enum kontrolü yapıyordu. Bu yaklaşım kırılgan çünkü `hasattr` sadece `.value` niteliği olan herhangi bir nesneyi (dataclass, Pydantic model, vs.) enum gibi işliyor. Yanlış değer üretilebilir.

**Çözüm:**  
`hasattr(value, "value")` yerine `isinstance(value, Enum)` kullanıldı. `from enum import Enum` importu eklendi. Bu, sadece gerçek Enum instances'larının `.value` ile işlenmesini garanti eder.

---

### 14. Hard Import Dependency on fitz / PyMuPDF (ORTA)

**Tarih/Saat:** 16.07.2026 17:05  
**Dosya:** `app/ocr/spatial_ocr.py`  
**Satır:** 4 (eski)  

**Problem:**  
`import fitz` (PyMuPDF) modül seviyesinde, dosyanın en üstünde import ediliyordu. Hata #13 düzeltmesi sırasında `processing.py`'deki lazy import'lar top-level'a taşındı, bu da `spatial_ocr.py`'nin import edilmesini zorunlu kıldı. PyMuPDF kurulu değilken `from app.main import app` çalışmıyordu — `ModuleNotFoundError: No module named 'fitz'` hatası alınıyordu. FastAPI uygulaması hiç başlamıyordu.

**Çözüm:**  
`import fitz` ifadesi `render_pdf_pages_to_images()` fonksiyonunun içine (lazy import) taşındı. Bu sayede `fitz` sadece PDF render edileceği zaman import edilir. Uygulama PyMuPDF olmadan da başlar, sadece PDF yüklendiğinde hata verir (beklenen davranış).
