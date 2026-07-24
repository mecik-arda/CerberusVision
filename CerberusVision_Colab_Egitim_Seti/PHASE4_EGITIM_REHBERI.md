# CerberusVision Phase 4 Colab Eğitim Rehberi

Bu paket Qwen2.5-7B-Instruct modelini temiz Phase 3 verisiyle Google Colab
Pro A100 üzerinde yeniden eğitmek için hazırlanmıştır.

## Eğitim kararı

Eski LoRA adaptörünün üstüne eğitim yapılmayacaktır. Eski adaptör, daha önce
benchmark belgeleriyle çakışan veri akışından üretildiği için yalnız baseline
karşılaştırmasında kullanılacaktır. Phase 4 adaptörü sabitlenmiş aynı temel
model revision'ından yeni QLoRA ağırlıklarıyla başlayacaktır.

## Paketteki dosyalar

- `CerberusVision_Qwen_LoRA.ipynb`: Uçtan uca A100 eğitim notebook'u.
- `train.jsonl`: 137 temiz kaynak ve 132 yalnız-train augmentation kaydı.
- `validation.jsonl`: 34 bağımsız validation kaydı.
- `manifest.json`: Phase 3 split ve sızıntı denetim kayıtları.
- `phase4_contract.json`: Model, veri hash'leri ve hiperparametre sözleşmesi.

`si_training.jsonl` eski ve sızıntı riski taşıyan birleşik veri dosyasıdır.
Phase 4 paketinden kaldırılmıştır ve kullanılmamalıdır.

## Google Drive yerleşimi

Klasörün tamamını Google Drive ana dizinine şu adla yükleyin:

`MyDrive/CerberusVision_Colab_Egitim_Seti`

Colab çalışma zamanında A100 GPU seçin ve notebook hücrelerini sırayla
çalıştırın. Notebook veri ve sözleşme hash'lerini doğrulamadan model yüklemez.

## Checkpoint politikası

İlk Phase 4 koşusunda `RESUME_FROM_MATCHING_CHECKPOINT` değeri `False`
kalmalıdır. Colab oturumu eğitim sırasında kesilirse aynı veri, aynı model
revision'ı ve aynı eğitim sözleşmesiyle ikinci koşuda bu değer `True`
yapılabilir.

Eski `CerberusVision/checkpoints` klasöründeki checkpoint'ler kullanılmaz.
Phase 4 kendine ait sözleşme hash'li dizin oluşturur. Sözleşme uyuşmazsa
resume işlemi reddedilir.

## Eğitim ölçütleri

Model en fazla 10 epoch eğitilir. Validation loss her 10 optimizer adımında
ölçülür. Üç değerlendirme boyunca en az `0.0005` iyileşme olmazsa eğitim erken
durur. Kaydedilen nihai adaptör son epoch değil, en düşük validation loss
değerine sahip checkpoint'tir.

Notebook eğitim öncesi baseline validation loss, eğitim sonrası best
validation loss, token uzunluk dağılımı, GPU bilgisi, paket sürümleri, eğitim
geçmişi ve örnek validation üretimlerini Drive'a kaydeder.

## Holdout politikası

Bağımsız gerçek dünya holdout belgeleri bu pakete konulmamalıdır. Holdout
eğitim veya erken durdurma sırasında kullanılırsa bilimsel geçerliliğini
kaybeder. Adaptör Colab'dan projeye alındıktan sonra holdout yalnız bir kez
nihai karşılaştırma için çalıştırılmalıdır.

## Colab sonrası

Başarılı koşu sonunda Drive altında oluşan `adapter_best` klasörünü ve
`training_report.json` dosyasını projeye indirin. Eski adaptörü silmeyin;
baseline adıyla saklayın. Yeni adaptör farklı bir dizinde değerlendirilip
donmuş OCR benchmark, bağımsız holdout ve canlı PDF kararlılık testleri
geçildikten sonra üretim modeli olarak seçilmelidir.
