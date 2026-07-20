# CerberusVision — Model Kapasitesi ve Doğruluk Artırma Önerileri

Bu doküman, Qwen2.5-7B INT4 yerel modelinin doğruluk ve kapasite sınırlarını aşarak %95+ doğruluk oranına ulaşmasını sağlayacak mimari iyileştirme ve geliştirme adımlarını içerir.

---

## 1. 🧩 Modüler / 3 Aşamalı Çıkarım (Chunked Multi-Stage Extraction)

- **Mevcut Durum:** Modelden tek istemde (prompt) tüm Shipper, Consignee, Limanlar, Konteynerler, Mal Tanımları ve Gümrük alanları (30+ karmaşık alan) aynı anda istenmektedir. 7B modeli INT4 kuantizasyonla bu kadar çok alana aynı anda odaklanırken karmaşa yaşamakta ve veri atlamaktadır.
- **Çözüm & Uygulama Planı:**
  - **Aşama 1 (Taraflar & Belge Bilgileri):** Shipper, Consignee, Notify Party, SI No, Booking No, Düzenleme Tarihi.
  - **Aşama 2 (Lojistik & Taşıma):** Gemi Adı, IMO No, Sefer No, Yükleme Limanı (POL), Boşaltma Limanı (POD), Navlun Ödeme Şekli.
  - **Aşama 3 (Konteyner & Yük Tablosu):** Konteyner No, Mühür No, Paket Sayısı, Brüt/Net Ağırlık, Mal Açıklaması tablosu.
- **Uygulanabilirlik & Zorluk:** **%100 (Kolay & Hızlı)** — Ekstra model indirmeden, `app/llm/inference.py` içerisinde istem zinciri (prompt chaining) kurulacak. Donanım maliyeti sıfırdır.
- **Beklenen Etki:** Model üzerindeki dikkat (attention) yükü kalkar, doğruluk oranı anında %70'ten %90+ seviyesine çıkar.

---

## 2. 📐 Koordinat / Bölge Bazlı Metin Ayrıştırma (OCR Region Segmentation)

- **Mevcut Durum:** PaddleOCR tüm sayfadaki metinleri tek bir dikey dizilim olarak sıralamaktadır. Bu durum yan yana duran veya karmaşık tablolardaki etiket-değer ilişkisini bozmaktadır.
- **Çözüm & Uygulama Planı:**
  - Elimizdeki OCR Bounding Box (koordinat) verilerini kullanarak metni 3 ana görsel bölgeye ayırma:
    - **Üst Bölge (%0-35 Y-Oranı):** Taraflar ve Belge Numaraları.
    - **Orta Bölge (%35-65 Y-Oranı):** Liman, Gemi ve Sefer Bilgileri.
    - **Alt Bölge (%65-100 Y-Oranı):** Konteyner ve Yük Tabloları.
  - Her bölgenin ayrıştırılmış metnini ilgili modüler isteme (Pass 1-2-3) beslemek.
- **Uygulanabilirlik & Zorluk:** **%100 (Kolay)** — `app/ocr/line_grouper.py` ve `spatial_ocr.py` içinde koordinat filtreleme algoritması yazılacak.
- **Beklenen Etki:** İlgisiz metinlerin modeli yanıltması engellenir, 3 aşamalı çıkarım %100 nokta atışı veri alır.

---

## 3. 👁️ Görsel-Dil / VLM Modeli Entegrasyonu (Florence-2 / Qwen2-VL)

- **Mevcut Durum:** Dokümanlar saf metne dönüştürüldüğü için çizgiler, kutular ve mizanpaj hiyerarşisi kaybolmaktadır.
- **Çözüm & Uygulama Planı:**
  - Microsoft'un ultra hafif ve doküman mizanpajında uzman **Florence-2-base** (~230M parametre, ultra hızlı) veya **Qwen2-VL-7B** Görsel-Dil modelini boru hattına dahil etmek.
  - Florence-2 modeline PDF sayfa görüntüsü verilerek tablo ve metin kutucukları görsel olarak tespit edilecek.
- **Uygulanabilirlik & Zorluk:** **%100 (Orta Zorluk)** — `app/ocr/` altına PyTorch/OpenVINO Florence-2 entegrasyon dosyası eklenecektir.
- **Beklenen Etki:** Çizgili/çerçeveli tabloları ve karmaşık mizanpajları bir insan gibi "görerek" algılar, karmaşık konşimentolarda sıfır veri kaybı sağlar.

---

## 4. 🎯 Lojistik Odaklı LoRA / QLoRA İnce Ayarı (Fine-Tuning)

- **Mevcut Durum:** Qwen2.5-7B genel kültürlü bir modeldir; lojistik terminolojisi ve DCSA alan adlarına özel olarak eğitilmemiştir.
- **Çözüm & Uygulama Planı:**
  - Projedeki Keşif (`veriler/discovered`) veriseti ve sentetik SI örnekleri ile Qwen2.5-7B modeline QLoRA (Inference Fine-Tuning) uygulanması.
  - Eğitilen LoRA adapter ağırlıklarının OpenVINO formatına dökülerek projeye eklenmesi.
  - `scripts/` dizini altına `train_lora.py` otomasyon betiği eklenmesi.
- **Uygulanabilirlik & Zorluk:** **%100 (Orta Zorluk)** — Eğitim betiği ve OpenVINO dönüştürücü eklenecek, arayüzdeki LoRA mor rozeti mekanizması kullanılacak.
- **Beklenen Etki:** Model lojistik terimlerini, vergi formatlarını ve DCSA alan adlarını ezbere bilerek genel 14B/32B modellerden daha kararlı ve hızlı çıktı üretir.