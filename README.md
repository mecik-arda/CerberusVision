# CerberusVision

Konşimento talimatı (Shipping Instruction) PDF belgelerini OCR ile okuyan, lokal LLM ile yapısal JSON verisine dönüştüren ve DCSA standartlarına dayalı XML çıktısı üreten uçtan uca otomasyon sistemidir.

## Mimari Genel Bakış

```
PDF → Spatial OCR (PaddleOCR) → Lokal LLM (Qwen-2.5-14B / OpenVINO GenAI) → JSON → XML (DCSA Subset) → XSD Doğrulama → Arayüz
```

### Temel Bileşenler

| Bileşen | Teknoloji | Açıklama |
|---------|-----------|----------|
| Frontend | Vanilla JS + HTML + Tailwind CSS (CDN) | Split-screen arayüz, drag-drop, SSE canlı durum |
| Backend | FastAPI | Asenkron API, statik dosya sunumu, SSE streaming |
| OCR | PaddleOCR | Bounding box tabanlı uzamsal metin çıkarımı |
| LLM | Qwen-2.5-14B-Instruct (INT4/OpenVINO) | Guided Decoding ile JSON üretimi |
| XML | lxml + XSD | DCSA v2 subset şema doğrulaması |
| Benchmark | DeepSeek API (OpenAI SDK) | Lokal model vs referans kıyaslama |

## Kurulum

### 1. Python Sanal Ortam

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

### 2. Bağımlılıklar

```bash
pip install -r requirements.txt
```

### 3. Qwen Modeli İndirme

Sistem, Qwen-2.5-14B-Instruct modelinin OpenVINO INT4 formatını kullanır. Modeli indirmek için:

```bash
# Hugging Face'den OpenVINO formatında indirin
# https://huggingface.co/Qwen/Qwen2.5-14B-Instruct

# OpenVINO'ya dönüştürün veya hazır INT4 sürümünü kullanın
# Varsayılan konum: ./models/Qwen-2.5-14B-Instruct-INT4

# Alternatif olarak ortam değişkeni ile yol belirtebilirsiniz:
set QWEN_MODEL_PATH=C:\path\to\your\model
```

### 4. DeepSeek API Key (Benchmark için - opsiyonel)

```bash
# Windows
set DEEPSEEK_API_KEY=your_api_key_here

# Linux/macOS
export DEEPSEEK_API_KEY=your_api_key_here
```

## Çalıştırma

### Web Uygulaması

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Tarayıcıda açın: `http://localhost:8000`

### Benchmark (api_compare.py)

```bash
# OCR metni ile kıyaslama
python scripts/api_compare.py --ocr-text logs/session_id/ocr_layout_text.txt

# PDF ile kıyaslama (OCR önce çalışır)
python scripts/api_compare.py --pdf uploads/sample.pdf --output benchmark_report.json
```

### Testler

```bash
pytest tests/ -v
```

## Sistem Mimarisi Detayları

### Faz 1: Web Arayüzü

- **Split Screen:** Sol tarafta PDF önizleme (`<iframe>`), sağ tarafta XML çıktısı ve interaktif form
- **SSE (Server-Sent Events):** Canlı işlem durumu akışı ("OCR İşleniyor...", "LLM Analizi...", "XML Doğrulanıyor")
- **Draft Mekanizması:** Eksik zorunlu alanlar kırmızı renkte (`bg-red-50`, `border-red-300`) "(Required)" etiketiyle gösterilir
- **Tasarım:** Light mode, glassmorphism paneller, teal aksan renkleri

### Faz 2: Spatial OCR (Layout Preservation)

PaddleOCR'ın bounding box koordinatları kullanılarak uzamsal düzen korunur:

1. **Y-Eksenine Göre Gruplama:** Yakın Y koordinatlarındaki metin blokları aynı satır olarak gruplanır (`y_threshold = 15.0`)
2. **X-Eksenine Göre Sıralama:** Aynı satırdaki metinler X koordinatına göre sıralanır
3. **Orantılı Boşluk:** Metin blokları arasındaki fiziksel mesafeye orantılı olarak boşluk karakteri eklenir (`space_factor = 0.15`)

Bu algoritma, konteyner numaraları ile ağırlık/hacim gibi yan yana sütun verilerinin bağlamının korunmasını sağlar.

### Faz 3: LLM Entegrasyonu (Guided Decoding)

- **openvino-genai SDK:** Native Intel altyapısı, LangChain/LlamaIndex bağımlılığı yok
- **Guided Decoding (JSON Mode):** Model token üretirken sadece JSON şemasına uyan karakterler üretilir
- **Pydantic Schema:** `ShippingInstruction` modelinden otomatik JSON schema türetilir
- **Sıcaklık:** 0.1 (deterministik çıktı)

### Faz 4: XML Dönüşümü ve XSD Doğrulaması

- **DCSA v2 Subset:** Orijinal DCSA şemasının sadeleştirilmiş alt kümesi
- **lxml ile Namespace Desteği:** `http://dcsa.org/schemas/si/v2`
- **Graceful Degradation:** Zorunlu alan eksikse işlem durmaz; belge "DRAFT" statüsüne alınır
- **Mandatory Field Kontrolü:** 21 zorunlu alan otomatik kontrol edilir

### Faz 5: Audit Trail

Her işlem oturumu `logs/` klasörüne kaydedilir:

```
logs/
└── 20260115_140530_123456/
    ├── ocr_layout_text.txt       # OCR'ın ürettiği uzamsal metin
    ├── ocr_boxes.json            # Bounding box koordinatları
    ├── llm_raw_output.json       # LLM'in ham JSON çıktısı
    ├── shipping_instruction_output.xml  # DCSA XML çıktısı
    ├── validation_report.json    # XSD doğrulama raporu
    └── processing_summary.json   # İşlem özeti
```

### Faz 6: Benchmark

`scripts/api_compare.py` şu adımları izler:

1. OCR metnini alır (dosyadan veya PDF'ten)
2. Lokal Qwen modeli ile JSON çıkarımı yapar
3. DeepSeek API ile referans JSON çıkarımı yapar
4. İki sonucu alan bazında karşılaştırır (match/mismatch sayısı)
5. Sonuçları `logs/` altına JSON rapor olarak kaydeder

## Ortam Değişkenleri

| Değişken | Varsayılan | Açıklama |
|----------|-----------|----------|
| `QWEN_MODEL_PATH` | `./models/Qwen-2.5-14B-Instruct-INT4` | OpenVINO model dizini |
| `OPENVINO_DEVICE` | `GPU` | OpenVINO cihazı (GPU/CPU/NPU) |
| `DEEPSEEK_API_KEY` | - | DeepSeek API anahtarı (benchmark için) |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek API base URL |

## API Endpoints

| Method | Path | Açıklama |
|--------|------|----------|
| `POST` | `/api/upload` | PDF yükle, session ID döndür |
| `POST` | `/api/upload-and-stream` | PDF yükle ve SSE stream başlat |
| `GET` | `/api/stream/{session_id}` | SSE durum akışı |
| `GET` | `/api/status/{session_id}` | İşlem durumu sorgula |
| `GET` | `/health` | Sağlık kontrolü |

## Proje Yapısı

```
CerberusVision/
├── app/
│   ├── main.py                 # FastAPI uygulaması
│   ├── config.py               # Konfigürasyon
│   ├── models.py               # Pydantic modelleri (JSON schema)
│   ├── ocr/
│   │   ├── spatial_ocr.py      # PaddleOCR entegrasyonu
│   │   └── line_grouper.py     # Uzamsal düzen koruma algoritması
│   ├── llm/
│   │   └── inference.py        # OpenVINO GenAI guided decoding
│   ├── xml/
│   │   ├── converter.py        # JSON → DCSA XML
│   │   ├── validator.py        # XSD doğrulama + graceful degradation
│   │   └── schemas/
│   │       └── shipping_instruction.xsd
│   ├── routes/
│   │   └── processing.py       # Upload + SSE endpoints
│   └── utils/
│       └── audit_logger.py     # Audit trail logging
├── static/
│   ├── index.html              # Split-screen UI
│   └── app.js                  # Frontend logic
├── scripts/
│   └── api_compare.py          # DeepSeek benchmark
├── tests/
│   ├── test_line_grouper.py    # Spatial OCR tests
│   ├── test_xml_converter.py   # XML conversion tests
│   ├── test_validator.py       # XSD validation tests
│   └── test_guided_decoding.py # JSON schema tests
├── logs/                       # Audit trail (gitignore)
├── uploads/                    # Temp PDF storage (gitignore)
├── requirements.txt
├── README.md
├── LICENSE
└── .gitignore
```

## Donanım Gereksinimleri

- **CPU:** Intel Core Ultra (NPU önerilir)
- **GPU:** Intel Arc (OpenVINO GPU加速)
- **RAM:** 32 GB önerilir
- **Depolama:** Model için ~10 GB

## Lisans

MIT License - detaylar için `LICENSE` dosyasına bakın.