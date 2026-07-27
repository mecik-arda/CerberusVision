#!/usr/bin/env python3
"""
CerberusVision — Yeni Turkce BL Sentetik Veri Jeneratoru
===========================================================

Phase 5.1 icin 25 yeni benzersiz Turkce Konşimento Talimati ornegi uretir.
Farkli sirketler, limanlar, konteyner tipleri ve yuk cesitleri.

Kullanim:
    .venv/bin/python scripts/generate_turkish_bl_data.py \
        --count 25 \
        --output veriler/turkce_bl_yeni_25.jsonl \
        --seed 3407
"""

import argparse
import json
import random
from pathlib import Path

TURKISH_SHIPPERS = [
    ("EGE SERAMIK SAN. VE TIC. A.S.", "MANISA", "TR", "9988776655"),
    ("KARADENIZ BAKIR ISLETMELERI A.S.", "SAMSUN", "TR", "7766554433"),
    ("ORTA ANADOLU TEKSTIL IHRACAT LTD. STI.", "KAYSERI", "TR", "5544332211"),
    ("MARMARA OTOMOTIV YAN SANAYI A.S.", "BURSA", "TR", "3322110099"),
    ("AKDENIZ MEYVE SEBZE IHRACATCILAR BIRLIGI", "ANTALYA", "TR", "1100998877"),
    ("TRAKYA YAGLI TOHUM TARIM KOOPERATIFI", "TEKIRDAG", "TR", "9988007766"),
    ("DOGU ANADOLU HALI VE KILIM LTD.", "VAN", "TR", "6655443322"),
    ("GAP TARIMSAL URUNLER A.S.", "SANLIURFA", "TR", "4433221100"),
    ("ISTANBUL DERI VE KONFEKSIYON DIS TIC.", "ISTANBUL", "TR", "2211009988"),
    ("CUKUROVA PAMUK YAGI SANAYI A.S.", "ADANA", "TR", "9900887766"),
    ("BATI AKDENIZ MERMER MADENCILIK LTD.", "BURDUR", "TR", "7788990011"),
    ("IC ANADOLU MAKINA SANAYI A.S.", "ANKARA", "TR", "5566778899"),
]

TURKISH_CONSIGNEES = [
    ("EURO FOODS DISTRIBUTION GMBH", "HAMBURG", "DE"),
    ("MED GOODS TRADING SRL", "GENOA", "IT"),
    ("ASIA PACIFIC WHOLESALE PTE", "SINGAPORE", "SG"),
    ("AMERICAN RETAIL IMPORTS INC", "NEW YORK", "US"),
    ("GULF TRADING COMPANY LLC", "JEBEL ALI", "AE"),
    ("NORTH SEA SUPPLY CHAIN AS", "OSLO", "NO"),
    ("BRITISH WHOLESALE DISTRIBUTORS", "FELIXSTOWE", "GB"),
    ("RUSSIAN IMPORT SOLUTIONS", "NOVOROSSIYSK", "RU"),
    ("CHINA INTERNATIONAL TRADE CORP", "SHANGHAI", "CN"),
    ("AUSTRALIAN RETAIL GROUP PTY", "SYDNEY", "AU"),
    ("FRENCH DISTRIBUTION SARL", "LE HAVRE", "FR"),
    ("JAPAN TRADING COMPANY KK", "TOKYO", "JP"),
]

TURKISH_PORTS = [
    ("AMBARLI / ISTANBUL", "TR"),
    ("MERSIN", "TR"),
    ("ALIAGA / IZMIR", "TR"),
    ("GEMLIK / BURSA", "TR"),
    ("ISKENDERUN", "TR"),
    ("SAMSUN", "TR"),
    ("TRABZON", "TR"),
    ("TEKIRDAG", "TR"),
    ("ANTALYA", "TR"),
    ("IZMIR ALSANCAK", "TR"),
    ("DERINCE / KOCAELI", "TR"),
    ("HEREKE / KOCAELI", "TR"),
]

TURKISH_CARGO = [
    ("SERAMIK KARO", "PL", 18, 28, 15000, 25000),
    ("BAKIR TEL", "DR", 30, 60, 12000, 22000),
    ("PAMUKLU HAVLU VE BORNZ", "CT", 50, 150, 8000, 18000),
    ("OTOMOTIV YEDEK PARCA", "PL", 10, 20, 10000, 20000),
    ("NARENCİYE (LIMON/PORTAL)", "PL", 20, 26, 18000, 26000),
    ("AYCICEK YAGI (RAFIN)", "DR", 60, 100, 15000, 24000),
    ("EL DOKUMASI HALI", "BX", 10, 30, 5000, 12000),
    ("ANTEP FISTIGI ISLENMIS", "CT", 40, 80, 10000, 18000),
    ("DERI MONT VE CIKET", "CT", 20, 50, 6000, 14000),
    ("PAMUK YAGI HAM", "DR", 40, 80, 16000, 26000),
    ("MERMER LEVHA", "CR", 8, 16, 18000, 28000),
    ("TARIM MAKINALARI YEDEK", "PL", 10, 20, 12000, 22000),
    ("FINDIK ICI (ISLENMIS)", "CT", 30, 60, 10000, 17000),
    ("ZEYTINYAGI SIZMA", "DR", 50, 90, 14000, 23000),
    ("TEKSTIL KONFEKSIYON", "BX", 30, 80, 8000, 16000),
    ("BEYAZ ESYA PARCALARI", "PL", 12, 22, 13000, 21000),
    ("MOBILYA AKSAMI", "CT", 40, 90, 10000, 18000),
    ("KURU INCIR", "CT", 30, 60, 9000, 16000),
    ("DEMIR CELIK BORU", "CR", 10, 20, 16000, 26000),
    ("SERAMIK SIHHI TESISAT", "PL", 8, 16, 14000, 24000),
]

TURKISH_REEFER_CARGO = [
    ("DONDURULMUS LIMON SUYU", "-18.0"),
    ("DONDURULMUS BALIK FILE", "-25.0"),
    ("SOGUK HAVA DEPOLU PEYNIR", "+2.0"),
    ("DONDURULMUS BOREK VE PASTA", "-18.0"),
    ("TAZE SERA DOMATES", "+4.0"),
    ("DONDURULMUS TAVUK PARCA", "-18.0"),
]

EQUIPMENT_TYPES = {
    "20GP": {"iso": "22G1", "max_w": 28000},
    "40GP": {"iso": "42G1", "max_w": 30000},
    "40HC": {"iso": "45G1", "max_w": 30000},
    "20RF": {"iso": "22R1", "max_w": 27000},
    "40RF": {"iso": "42R1", "max_w": 29000},
}


def generate_container_ref():
    letters = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=4))
    numbers = "".join(random.choices("0123456789", k=7))
    return letters + numbers


def generate_seal():
    return f"TR-{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}-{random.randint(100000,999999)}"


def generate_booking():
    return f"BKG-TR-{random.randint(100000,999999)}"


def generate_turkish_input(
    si_ref, booking, date, shipper, consignee, notify, pol, pod, containers, freight_term
):
    lines = []
    lines.append("KONSIMENTO TALIMATI")
    lines.append(f"REFERANS: {si_ref}")
    lines.append(f"TARIH: {date}")
    lines.append(f"REZERVASYON: {booking}")
    lines.append(f"GONDERICI: {shipper[0]}")
    lines.append(f"  {shipper[1]}, TURKIYE")
    lines.append(f"  VKN: {shipper[3]}")
    lines.append(f"ALICI: {consignee[0]}")
    lines.append(f"  {consignee[1]}, {consignee[2]}")
    if notify:
        lines.append(f"BILDIRIM: {notify[0]}")
        lines.append(f"  {notify[1]}, {notify[2]}")
    lines.append(f"YUKLEME LIMANI: {pol[0]}")
    lines.append(f"BOSALTMA LIMANI: {consignee[1]}")
    lines.append(f"NAVLUN: {'ODENDI' if freight_term == 'PPD' else 'ODEMELI'}")
    lines.append("TASIMA TURU: BILL OF LADING")
    lines.append("")
    lines.append("KONTEYNER BILGILERI:")

    for c in containers:
        lines.append(f"  {c['ref']} {c['type']}")
        if c.get('seal'):
            lines.append(f"  MUHUR: {c['seal']}")
        lines.append(f"  BRUT: {c['gross']:,.2f} KG")
        lines.append(f"  NET: {c['net']:,.2f} KG")
        if c.get('temp'):
            lines.append(f"  SICAKLIK: {c['temp']} DERECE CELSIUS")
            lines.append(f"  HAVALANDIRMA: {'KAPALI' if random.random() < 0.5 else f'{random.randint(10,30)} CBM/H'}")
            lines.append(f"  NEM: %{random.randint(75,95)}")
        lines.append(f"  {c['pkg_qty']} {c['pkg_name']} {c['cargo_name']}")
        lines.append(f"  HACIM: {c['volume']:.2f} CBM")
        lines.append("")

    return "\n".join(lines)


def build_dcsa_output(si_ref, booking, date, shipper, consignee, notify, pol, containers, freight_term):
    parties = [
        {"party_role_code": "CZ", "party_name": shipper[0], "party_id": shipper[3],
         "address": {"city": shipper[1], "country_code": "TR"}},
        {"party_role_code": "CN", "party_name": consignee[0],
         "address": {"city": consignee[1], "country_code": consignee[2]}},
    ]
    if notify:
        parties.append({"party_role_code": "N1", "party_name": notify[0],
                        "address": {"city": notify[1], "country_code": notify[2]}})

    equipment_list = []
    cargo_items = []
    remarks = []

    for c in containers:
        etype = c['type']
        equipment_list.append({
            "equipment_reference": c['ref'],
            "iso_equipment_code": EQUIPMENT_TYPES[etype]["iso"],
            "cargo_gross_weight": {"weight": c['gross'], "unit": "KGM"},
            **({"seals": [{"seal_number": c['seal']}]} if c.get('seal') else {}),
        })
        cargo_items.append({
            "package_quantity": c['pkg_qty'],
            "package_kind_code": c['pkg_code'],
            "description_of_goods": c['cargo_name'],
            "weight": {"weight_value": c['net'], "unit": "KGM"},
            "volume": {"volume_value": c['volume'], "unit": "CBM"},
        })
        if c.get('temp'):
            remarks.append(f"{c['ref']}: {c['temp']}C")

    out = {
        "document_status_code": "DRF",
        "transport_document_type": "B/L",
        "shipping_instruction_reference": si_ref,
        "carrier_booking_reference": booking,
        "issue_date": date,
        "freight_payment_term_code": freight_term,
        "parties": parties,
        "transport_plans": [{
            "port_of_loading": {"location_name": pol[0].split(" / ")[0]},
            "port_of_discharge": {"location_name": consignee[1]},
        }],
        "equipment_list": equipment_list,
        "cargo_items": cargo_items,
    }
    if remarks:
        out["remarks"] = "SICAKLIK: " + " | ".join(remarks)

    return json.dumps(out, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="Turkce BL Sentetik Veri Jeneratoru")
    parser.add_argument("--count", type=int, default=25)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=3407)
    args = parser.parse_args()

    random.seed(args.seed)

    print(f"Generating {args.count} Turkish BL examples...")
    examples = []

    for i in range(args.count):
        shipper = random.choice(TURKISH_SHIPPERS)
        consignee = random.choice(TURKISH_CONSIGNEES)
        notify = random.choice(TURKISH_SHIPPERS) if random.random() < 0.35 else None

        pol = random.choice(TURKISH_PORTS)
        si_ref = f"SI-TR-51-{i+1001:04d}"  # Offset to avoid collision

        booking = generate_booking()
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        date = f"2026-{month:02d}-{day:02d}"
        freight_term = random.choice(["PPD", "COL"])

        # 1-3 containers
        num_containers = random.choices([1, 2, 3], weights=[35, 40, 25])[0]
        has_reefer = random.random() < 0.2 and num_containers >= 1

        containers = []
        used_refs = set()
        for j in range(num_containers):
            is_reefer = has_reefer and j == 0
            ctype = random.choice(["20RF", "40RF"]) if is_reefer else random.choice(["20GP", "40GP", "40HC"])
            ref = generate_container_ref()
            while ref in used_refs:
                ref = generate_container_ref()
            used_refs.add(ref)
            seal = generate_seal() if random.random() < 0.7 else None

            if is_reefer:
                cargo_name, temp = random.choice(TURKISH_REEFER_CARGO)
                pkg_code, pkg_name = "PL", "PALET"
            else:
                cargo_name, pkg_code, pkg_min, pkg_max, w_min, w_max = random.choice(TURKISH_CARGO)
                pkg_name = {"PL": "PALET", "CT": "KOLI", "DR": "VARIL", "CR": "SANDIK", "BX": "KUTU"}[pkg_code]

            pkg_qty = random.randint(pkg_min if not is_reefer else 10, pkg_max if not is_reefer else 28)
            max_w = EQUIPMENT_TYPES[ctype]["max_w"]
            w_min_actual = w_min if not is_reefer else 12000
            w_max_actual = min(w_max if not is_reefer else 26000, max_w)
            gross = round(random.uniform(w_min_actual, w_max_actual), -2)
            net = round(gross * random.uniform(0.88, 0.96), -2)
            volume = round(gross / random.uniform(650, 950), 2)

            containers.append({
                "ref": ref, "type": ctype, "seal": seal,
                "gross": gross, "net": net,
                "pkg_qty": pkg_qty, "pkg_name": pkg_name, "pkg_code": pkg_code,
                "cargo_name": cargo_name, "volume": volume,
                "temp": temp if is_reefer else None,
            })

        inp = generate_turkish_input(si_ref, booking, date, shipper, consignee, notify, pol, consignee, containers, freight_term)
        out = build_dcsa_output(si_ref, booking, date, shipper, consignee, notify, pol, containers, freight_term)
        examples.append({"input": inp, "output": out})

    random.seed(args.seed)
    random.shuffle(examples)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(ex, ensure_ascii=False) + "\n" for ex in examples)

    total = sum(len(json.loads(ex["output"]).get("equipment_list", [])) for ex in examples)
    print(f"Generated: {len(examples)} examples, {total} containers")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
