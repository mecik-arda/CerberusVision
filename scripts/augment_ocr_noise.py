#!/usr/bin/env python3
"""
CerberusVision — OCR Gürültü Augmentasyon Motoru
==================================================

Egitim verisindeki input metinlerine gercekci OCR gurultusu ekler.
Output (DCSA JSON) her zaman temiz kalir — model OCR hatalarini duzeltmeyi ogrenir.

Karakter degisim haritasi (OCR'da sik gorulen hatalar):
    O ↔ 0, I ↔ 1 ↔ l, S ↔ 5, B ↔ 8, G ↔ 6, Z ↔ 2
    Turkce: Ş↔S, Ğ↔G, Ç↔C, İ↔I, Ü↔U, Ö↔O

Seviyeler:
    light   — %5-10 karakter bozulumu, 1-2 satir kaymasi
    medium  — %10-20 karakter bozulumu, bosluk/dilimlenme
    heavy   — %20-35 karakter bozulumu, satir kopmalari, noktalama kaybi

Kullanim:
    .venv/bin/python scripts/augment_ocr_noise.py \
        --input veriler/turkce_bl_sentetik.jsonl \
        --output veriler/turkce_bl_augmented.jsonl \
        --level medium \
        --multiplier 5 \
        --seed 3407
"""

import argparse
import json
import random
import re
from pathlib import Path

# --- Karakter Degisim Haritasi ---

# Standart OCR gurultusu
OCR_SUBSTITUTIONS = {
    'O': '0', '0': 'O',
    'I': '1', '1': 'I',
    'l': '1', 'L': '1',
    'S': '5', '5': 'S',
    'B': '8', '8': 'B',
    'G': '6', '6': 'G',
    'Z': '2', '2': 'Z',
    'A': '4', '4': 'A',
    'E': '3', '3': 'E',
    'T': '7', '7': 'T',
}

# Turkce karakter gurultusu
TURKISH_OCR = {
    'Ğ': 'G', 'ğ': 'g',
    'Ü': 'U', 'ü': 'u',
    'Ş': 'S', 'ş': 's',
    'İ': 'I', 'ı': 'i',
    'Ç': 'C', 'ç': 'c',
    'Ö': 'O', 'ö': 'o',
}

# Birlestirilmis harita
ALL_SUBSTITUTIONS = {**OCR_SUBSTITUTIONS, **TURKISH_OCR}


def inject_character_noise(text: str, level: str) -> str:
    """Karakter seviyesinde OCR gurultusu enjekte et."""
    if level == "light":
        prob = 0.05
    elif level == "medium":
        prob = 0.12
    elif level == "heavy":
        prob = 0.25
    else:
        return text

    chars = list(text)
    for i, c in enumerate(chars):
        if c in ALL_SUBSTITUTIONS and random.random() < prob:
            chars[i] = ALL_SUBSTITUTIONS[c]
    return ''.join(chars)


def inject_whitespace_noise(text: str, level: str) -> str:
    """Bosluk/satir gurultusu."""
    if level == "light":
        ws_prob = 0.02
        nl_prob = 0.01
    elif level == "medium":
        ws_prob = 0.05
        nl_prob = 0.03
    elif level == "heavy":
        ws_prob = 0.10
        nl_prob = 0.06
    else:
        return text

    lines = text.split('\n')
    result = []

    for line in lines:
        # Bosluk bozulumu
        if random.random() < ws_prob:
            # Cift bosluk
            line = re.sub(r' ', '  ', line, count=random.randint(1, 3))
        if random.random() < ws_prob:
            # Bosluk kaybi
            line = re.sub(r': ', ':', line, count=random.randint(1, 2))
        if random.random() < ws_prob:
            # Gereksiz bosluk ekle
            pos = random.randint(0, max(0, len(line) - 1))
            line = line[:pos] + ' ' + line[pos:]

        # Satir kaymasi/birlesmesi
        if random.random() < nl_prob:
            result.append(line)
            if random.random() < 0.5:
                result.append('')  # Ekstra bos satir
        elif random.random() < nl_prob and len(result) > 0:
            # Satir birlesmesi
            result[-1] = result[-1] + '  ' + line
        else:
            result.append(line)

    return '\n'.join(result)


def inject_punctuation_noise(text: str, level: str) -> str:
    """Noktalama isaretlerinde bozulma."""
    if level == "light":
        prob = 0.02
    elif level == "medium":
        prob = 0.05
    elif level == "heavy":
        prob = 0.12
    else:
        return text

    # Noktalama isaretlerini kaldir/degistir
    result = []
    for c in text:
        if c in ',.;:' and random.random() < prob:
            # Kaybolan noktalama
            continue
        elif c == '-' and random.random() < prob or c == '/' and random.random() < prob:
            result.append(' ')
            continue
        else:
            result.append(c)
    return ''.join(result)


def inject_container_noise(text: str, level: str) -> str:
    """Konteyner numaralarinda OCR gurultusu (sadece medium+ seviyede)."""
    if level == "light":
        return text
    elif level == "medium" and random.random() < 0.3 or level == "heavy" and random.random() < 0.6:
        pass
    else:
        return text

    # 4 harf + 7 rakam formatindaki konteyner numaralarini bul ve boz
    container_pattern = re.compile(r'\b([A-Z]{4}\d{7})\b')

    def noise_container(match):
        ref = match.group(1)
        if random.random() < 0.5:
            # Bir rakami boz
            pos = random.randint(4, 10)
            c = ref[pos]
            if c in OCR_SUBSTITUTIONS:
                ref = ref[:pos] + OCR_SUBSTITUTIONS[c] + ref[pos+1:]
        return ref

    return container_pattern.sub(noise_container, text)


def inject_turkish_noise(text: str, level: str) -> str:
    """Turkce karakterleri ASCII'ye indirge (heavy seviyede agresif)."""
    if level == "light":
        prob = 0.05
    elif level == "medium":
        prob = 0.20
    elif level == "heavy":
        prob = 0.50
    else:
        return text

    chars = list(text)
    for i, c in enumerate(chars):
        if c in TURKISH_OCR and random.random() < prob:
            chars[i] = TURKISH_OCR[c]
    return ''.join(chars)


def augment_input(text: str, level: str = "medium", has_turkish: bool = False) -> str:
    """
    Ana augmentasyon fonksiyonu.
    Input metnine gercekci OCR gurultusu ekler, output temiz kalir.
    """
    augmented = text

    # 1. Karakter seviyesinde gurultu
    augmented = inject_character_noise(augmented, level)

    # 2. Turkce karakter bozumu (varsa)
    if has_turkish:
        augmented = inject_turkish_noise(augmented, level)

    # 3. Bosluk/satir gurultusu
    augmented = inject_whitespace_noise(augmented, level)

    # 4. Noktalama gurultusu
    augmented = inject_punctuation_noise(augmented, level)

    # 5. Konteyner numarasi gurultusu
    augmented = inject_container_noise(augmented, level)

    return augmented


# Turkce metin belirtecleri (ASCII formda yazilmis olsa bile)
TURKISH_MARKERS = [
    'GONDERICI', 'GÖNDERICI', 'GÖNDERİCİ', 'ALICI', 'KONSIMENTO',
    'KONŞIMENTO', 'TALIMATI', 'TALİMATI', 'YUKLEME', 'YÜKLEME',
    'BOSALTMA', 'BOŞALTMA', 'NAVLUN', 'MÜHÜR', 'MUHUR',
    'BRUT', 'BRÜT', 'HACIM', 'HACİM', 'KONTEYNER',
    'LİMANI', 'LIMANI', 'TARIH', 'TARİH', 'TASIMA', 'TAŞIMA',
    'ODENDI', 'ÖDENDİ', 'ODEMELI', 'ÖDEMELİ',
    'KOLI', 'KOLİ', 'PALET', 'VARIL', 'SANDIK',
    'DONDURULMUS', 'DONDURULMUŞ', 'SICAKLIK', 'SICAKLIK AYARI',
    'HAVALANDIRMA', 'NEM ORANI',
]


def has_turkish_chars(text: str) -> bool:
    """Metinde Turkce karakter veya Turkce kelime var mi?"""
    if bool(re.search(r'[ĞÜŞİÇÖğüşıçö]', text)):
        return True
    upper = text.upper()
    return any(marker in upper for marker in TURKISH_MARKERS)


def augment_record(record: dict, level: str) -> dict:
    """Tek bir kayda OCR gurultusu uygula."""
    inp = record.get("input", "")
    turkish = has_turkish_chars(inp)
    augmented_input = augment_input(inp, level, has_turkish=turkish)

    return {
        "input": augmented_input,
        "output": record["output"],  # Output her zaman temiz
    }


def main():
    parser = argparse.ArgumentParser(description="OCR Gurultu Augmentasyon Motoru")
    parser.add_argument("--input", type=Path, required=True, help="Input JSONL file")
    parser.add_argument("--output", type=Path, required=True, help="Output JSONL file")
    parser.add_argument(
        "--level", choices=["light", "medium", "heavy"], default="medium",
        help="Gurultu seviyesi (default: medium)"
    )
    parser.add_argument(
        "--multiplier", type=int, default=1,
        help="Her kayittan kac varyant uretilecek (default: 1)"
    )
    parser.add_argument(
        "--seed", type=int, default=3407,
        help="Random seed (default: 3407)"
    )
    parser.add_argument(
        "--include-original", action="store_true", default=True,
        help="Output'a orijinal kayitlari da ekle (default: True)"
    )
    parser.add_argument(
        "--no-original", action="store_true",
        help="Output'a sadece gurultulu varyantlari yaz"
    )
    args = parser.parse_args()

    random.seed(args.seed)

    # Load
    records = []
    for line in args.input.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(f"WARNING: Skipping malformed line: {e}")

    print(f"Input:  {len(records)} records from {args.input.name}")

    # Augment
    output_records = []
    if not args.no_original:
        output_records.extend(records)

    turkish_count = sum(1 for r in records if has_turkish_chars(r.get("input", "")))
    print(f"  Turkish records detected: {turkish_count}/{len(records)}")

    for mult in range(args.multiplier):
        # Her varyant turu icin farkli seed
        random.seed(args.seed + mult * 1000)
        for i, record in enumerate(records):
            augmented = augment_record(record, args.level)
            if augmented["input"] != record["input"]:  # Sadece degisti mi?
                output_records.append(augmented)

    # Shuffle with fixed seed
    random.seed(args.seed)
    random.shuffle(output_records)

    # Save
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for record in output_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    variant_count = len(output_records) - (0 if args.no_original else len(records))
    print(f"Output: {len(output_records)} records ({variant_count} augmented variants)")
    print(f"  Level: {args.level}, Multiplier: {args.multiplier}x")
    print(f"  Written to: {args.output}")


if __name__ == "__main__":
    main()
