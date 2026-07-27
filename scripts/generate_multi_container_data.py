#!/usr/bin/env python3
"""
CerberusVision — Coklu Konteyner Sentetik Veri Jeneratoru
============================================================

Ekipman skoru %41.4'u yukseltmek icin 5-14 konteynerli zorlu ornekler uretir.
Her ornekte ekipman ↔ yuk eslemesi modelin ogrenmesi gereken ana zorluktur.

Kullanim:
    .venv/bin/python scripts/generate_multi_container_data.py \
        --count 60 \
        --min-containers 5 \
        --max-containers 20 \
        --output veriler/multi_container_sentetik.jsonl \
        --seed 3407
"""

import argparse
import json
import random
from pathlib import Path

# --- Veri Bankalari ---

SHIPPERS = [
    ("GLOBAL FREIGHT SOLUTIONS LTD", "GB"),
    ("PACIFIC RIM TRADING CO", "US"),
    ("EUROASIA LOGISTICS GMBH", "DE"),
    ("SINOCARGO INTERNATIONAL", "CN"),
    ("MED CARGO SHIPPING SRL", "IT"),
    ("ATLANTIC TRADE WINDS INC", "US"),
    ("NORTH SEA FREIGHT AS", "NO"),
    ("INDIAN OCEAN EXPORTS PVT", "IN"),
    ("BRAZIL COMMODITIES SA", "BR"),
    ("AFRICA MINERALS EXPORT LTD", "ZA"),
    ("JAPAN PRECISION TRADING CO", "JP"),
    ("AUSTRALASIA LOGISTICS PTY", "AU"),
    ("CARIBBEAN FREIGHT SERVICES", "PA"),
    ("BALTIC SHIPPING GROUP OU", "EE"),
    ("SOUTH EAST ASIA TRADERS", "SG"),
]

CONSIGNEES = [
    ("MAJOR RETAIL DISTRIBUTION", "US"),
    ("INDUSTRIAL SUPPLIES GMBH", "DE"),
    ("ASIA WHOLESALE NETWORK", "CN"),
    ("EUROPEAN CONSORTIUM SA", "FR"),
    ("MIDDLE EAST TRADING LLC", "AE"),
    ("AFRICAN IMPORT SOLUTIONS", "KE"),
    ("LATIN AMERICA DISTRIBUTORS", "MX"),
    ("CANADIAN WHOLESALE CORP", "CA"),
    ("AUSTRALIAN RETAIL GROUP", "AU"),
    ("NORTHERN EUROPE SUPPLY AS", "SE"),
    ("JAPAN DISTRIBUTION KK", "JP"),
    ("SOUTH ASIA IMPORTS", "IN"),
    ("RUSSIAN FAR EAST TRADING", "RU"),
    ("KOREAN LOGISTICS HUB", "KR"),
    ("MEDITERRANEAN WAREHOUSE LTD", "MT"),
]

PORTS = [
    ("ROTTERDAM", "NL"), ("HAMBURG", "DE"), ("ANTWERP", "BE"),
    ("SINGAPORE", "SG"), ("SHANGHAI", "CN"), ("BUSAN", "KR"),
    ("HONG KONG", "HK"), ("JEBEL ALI", "AE"), ("LOS ANGELES", "US"),
    ("NEW YORK", "US"), ("SANTOS", "BR"), ("VALENCIA", "ES"),
    ("FELIXSTOWE", "GB"), ("GENOA", "IT"), ("PIRAEUS", "GR"),
    ("TANJUNG PELEPAS", "MY"), ("COLOMBO", "LK"), ("MUNDRA", "IN"),
    ("MOMBASA", "KE"), ("DURBAN", "ZA"), ("SYDNEY", "AU"),
    ("VANCOUVER", "CA"), ("MANZANILLO", "MX"), ("CARTAGENA", "CO"),
]

EQUIPMENT_TYPES = {
    "20GP": {"iso": "22G1", "max_weight": 28000, "typical_weight": (8000, 24000)},
    "40GP": {"iso": "42G1", "max_weight": 30000, "typical_weight": (12000, 28000)},
    "40HC": {"iso": "45G1", "max_weight": 30000, "typical_weight": (15000, 28000)},
    "20RF": {"iso": "22R1", "max_weight": 27000, "typical_weight": (5000, 20000)},
    "40RF": {"iso": "42R1", "max_weight": 29000, "typical_weight": (12000, 27000)},
}

PACKAGE_TYPES = [
    ("PL", "PALLET", 500, 1200),
    ("CT", "CARTON", 5, 50),
    ("DR", "DRUM", 100, 300),
    ("CR", "CRATE", 200, 800),
    ("BX", "BOX", 10, 100),
    ("BG", "BAG", 20, 60),
]

CARGO_TYPES = [
    "STEEL PIPES", "CERAMIC TILES", "TEXTILE FABRICS", "MDF PANELS",
    "AUTO PARTS", "ELECTRONIC COMPONENTS", "PLASTIC GRANULES",
    "PAPER ROLLS", "COPPER WIRE", "ALUMINUM PROFILES",
    "FURNITURE PARTS", "CONSTRUCTION MATERIALS", "FOOD PROCESSING EQUIPMENT",
    "RUBBER SHEETS", "GLASS PANELS", "WOODEN FLOORING",
    "INDUSTRIAL VALVES", "PACKAGING MATERIALS", "RAW COTTON",
    "CEMENT BAGS", "AGRICULTURAL MACHINERY", "PRINTED BOOKS",
    "PET FOOD", "CANNED GOODS", "KITCHEN APPLIANCES",
    "PVC PIPES", "SOLAR PANELS", "BICYCLE PARTS",
    "LEATHER GOODS", "SPORTS EQUIPMENT",
]

REEFER_CARGO_TYPES = [
    "FROZEN CHICKEN", "FROZEN BEEF", "FROZEN FISH FILLETS",
    "FRESH APPLES", "FRESH GRAPES", "FRESH BERRIES",
    "CHILLED DAIRY PRODUCTS", "FROZEN VEGETABLES", "ICE CREAM",
    "PHARMACEUTICAL RAW MATERIALS", "FROZEN SEAFOOD",
    "FRESH FLOWERS", "CHOCOLATE CONFECTIONERY",
]

REEFER_TEMP_SETTINGS = [
    "-25.0 CELSIUS", "-18.0 CELSIUS", "-10.0 CELSIUS",
    "0.0 CELSIUS", "+2.0 CELSIUS", "+4.0 CELSIUS", "+8.0 CELSIUS",
]

REEFER_VENT_SETTINGS = ["CLOSED", "10 CBM/H", "15 CBM/H", "20 CBM/H", "25 CBM/H", "30 CBM/H"]

# Ondalik format cesitlendirmesi: %50 EU (1.234,56), %50 US (1,234.56 veya 1234.56)
def format_number(value: float, is_weight: bool = False) -> str:
    """Format a number with randomized EU/US decimal separators to prevent 1000x errors."""
    # Standard US format first (comma thousands, dot decimal)
    base_str = f"{value:,.2f}" if (is_weight and value >= 1000) else f"{value:.2f}"

    if random.random() < 0.5:
        # EU: swap comma↔dot using placeholder trick (1,234.56 → 1.234,56)
        return base_str.replace(",", "X").replace(".", ",").replace("X", ".")

    return base_str


def generate_container_prefix() -> str:
    return "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=4))


def generate_container_number() -> str:
    return "".join(random.choices("0123456789", k=7))


def generate_container_ref() -> str:
    return generate_container_prefix() + generate_container_number()


def generate_seal() -> str:
    prefix = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=2))
    suffix = "".join(random.choices("0123456789", k=6))
    return f"{prefix}-SL-{suffix}"


def generate_booking_ref() -> str:
    return "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=9))


def generate_vessel_name() -> str:
    prefixes = ["MSC", "MAERSK", "CMA CGM", "COSCO", "HAPAG", "ONE", "EVER", "HMM"]
    names = ["STAR", "OCEAN", "GLOBE", "PEARL", "SUN", "WAVE", "CREST", "HORIZON",
             "VOYAGER", "NAVIGATOR", "PIONEER", "EXPLORER", "VICTORY", "LIBERTY"]
    return f"{random.choice(prefixes)} {random.choice(names)}"


def generate_voyage() -> str:
    letters = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=2))
    numbers = "".join(random.choices("0123456789", k=4))
    return f"{letters}-{numbers}"


def generate_cargo_item(container_type: str) -> dict:
    """Generate a cargo item matching the container type."""
    is_reefer = "RF" in container_type

    if is_reefer:
        cargo = random.choice(REEFER_CARGO_TYPES)
        temp = random.choice(REEFER_TEMP_SETTINGS)
        vent = random.choice(REEFER_VENT_SETTINGS)
        remarks_hint = f"TEMP: {temp} VENT: {vent}"
        # Randomized reefer placement: 60% inline, 25% cargo, 15% block
        r = random.random()
        if r < 0.60:
            reefer_placement = "inline"   # CONTAINER: XXX 40RF (TEMP: -18C...)
        elif r < 0.85:
            reefer_placement = "cargo"    # CARGO: FROZEN FISH SET AT -18C / VENT: ...
        else:
            reefer_placement = "block"    # --- REEFER SETTINGS --- block
    else:
        cargo = random.choice(CARGO_TYPES)
        remarks_hint = None
        reefer_placement = None

    pkg_code, _pkg_name, pkg_min, pkg_max = random.choice(PACKAGE_TYPES)
    pkg_qty = max(1, random.randint(pkg_min // 20, pkg_max // 20)) * random.randint(1, 20)

    # Weight proportional to container type
    max_w = EQUIPMENT_TYPES[container_type]["max_weight"]
    typical = EQUIPMENT_TYPES[container_type]["typical_weight"]
    gross = round(random.uniform(typical[0], min(typical[1], max_w)), -2)  # round to 100s
    net = round(gross * random.uniform(0.88, 0.96), -2)
    volume = round(gross / random.uniform(600, 900), 2)

    return {
        "package_quantity": pkg_qty,
        "package_kind_code": pkg_code,
        "description_of_goods": cargo,
        "weight": {"weight_value": net, "unit": "KGM"},
        "volume": {"volume_value": volume, "unit": "CBM"},
        "_gross_weight": gross,
        "_remarks_hint": remarks_hint,
        "_reefer_placement": reefer_placement,
    }


def format_ocr_input(
    si_ref: str, booking: str, date: str,
    shipper: tuple, consignee: tuple, notify: tuple or None,
    pol: tuple, pod: tuple, vessel: str, voyage: str,
    containers: list[dict], freight: str
) -> str:
    """Format as realistic OCR-like Shipping Instruction text with diversified layouts."""
    lines = []
    lines.append(f"SHIPPING INSTRUCTION {si_ref}")
    lines.append(f"DATE: {date}")
    lines.append(f"BOOKING: {booking}")
    lines.append(f"SHIPPER: {shipper[0]}, {shipper[1]}")
    lines.append(f"CONSIGNEE: {consignee[0]}, {consignee[1]}")
    if notify:
        lines.append(f"NOTIFY: {notify[0]}, {notify[1]}")
    lines.append(f"PORT OF LOADING: {pol[0]}")
    lines.append(f"PORT OF DISCHARGE: {pod[0]}")
    lines.append(f"VESSEL: {vessel} / VOYAGE: {voyage}")
    lines.append("")
    lines.append("CONTAINER DETAILS:")
    lines.append("")

    use_weight_summary = random.random() < 0.25  # 25% chance of weight summary at end
    weight_summary_lines = []
    reefer_block_lines = []

    for i, c in enumerate(containers):
        seal = c.get('seal')
        seal_inline = seal and random.random() < 0.75  # 75% seal inline with container
        cargo = c['cargo']
        is_reefer = cargo.get('_reefer_placement') is not None
        placement = cargo.get('_reefer_placement')

        # Container line: optionally include seal and reefer info inline
        container_line = f"CONTAINER {i+1}: {c['ref']} {c['type']}"
        if seal_inline:
            container_line += f" / SEAL: {seal}"
        if is_reefer and placement == "inline":
            container_line += f" ({cargo['_remarks_hint']})"
        lines.append(container_line)

        # Seal on separate line if not inline
        if seal and not seal_inline:
            lines.append(f"SEAL: {seal}")

        # Cargo description
        if is_reefer and placement == "cargo":
            lines.append(f"CARGO: {cargo['description_of_goods']} SET AT {cargo['_remarks_hint'].replace('TEMP: ', '').replace('VENT: ', '/ VENT: ')}")
        else:
            lines.append(f"CARGO: {cargo['description_of_goods']}")

        # Reefer block mode: collect for later
        if is_reefer and placement == "block":
            reefer_block_lines.append(f"  {c['ref']}: {cargo['_remarks_hint']}")

        # Weight line — use format_number for diversity
        gross_str = format_number(cargo['_gross_weight'], is_weight=True)
        net_str = format_number(cargo['weight']['weight_value'], is_weight=True)
        vol_str = format_number(cargo['volume']['volume_value'], is_weight=False)

        if use_weight_summary:
            # Weight goes to summary table at end, only show cargo details here
            lines.append(f"{cargo['package_quantity']} {c.get('_pkg_name', 'PACKAGES')} {cargo['description_of_goods']}")
            lines.append(f"VOLUME: {vol_str} CBM")
            weight_summary_lines.append(f"  {c['ref']}: GROSS {gross_str} KG / NET {net_str} KG")
        else:
            # Standard inline weight
            lines.append(f"GROSS: {gross_str} KG  NET: {net_str} KG")
            lines.append(f"{cargo['package_quantity']} {c.get('_pkg_name', 'PACKAGES')} {cargo['description_of_goods']}")
            lines.append(f"VOLUME: {vol_str} CBM")

        lines.append("")

    # Reefer settings block (15% of reefers)
    if reefer_block_lines:
        lines.append("--- REEFER SETTINGS ---")
        lines.extend(reefer_block_lines)
        lines.append("")

    # Weight summary table (25% of examples)
    if use_weight_summary:
        lines.append("--- WEIGHT SUMMARY ---")
        lines.extend(weight_summary_lines)
        lines.append("")

    lines.append(f"FREIGHT {freight}")
    lines.append("BILL OF LADING")
    return "\n".join(lines)


def build_dcsa_output(
    si_ref: str, booking: str, date: str,
    shipper: tuple, consignee: tuple, notify: tuple or None,
    pol: tuple, pod: tuple, vessel: str, voyage: str,
    containers: list[dict], freight: str
) -> str:
    """Build DCSA-compliant JSON output for the shipping instruction."""
    parties = [
        {"party_role_code": "CZ", "party_name": shipper[0], "address": {"country_code": shipper[1]}},
        {"party_role_code": "CN", "party_name": consignee[0], "address": {"country_code": consignee[1]}},
    ]
    if notify:
        parties.append({"party_role_code": "N1", "party_name": notify[0], "address": {"country_code": notify[1]}})

    equipment_list = []
    cargo_items = []
    remarks_parts = []

    for c in containers:
        equip = {
            "equipment_reference": c['ref'],
            "iso_equipment_code": EQUIPMENT_TYPES[c['type']]["iso"],
            "cargo_gross_weight": {
                "weight": c['cargo']['_gross_weight'],
                "unit": "KGM"
            },
        }
        if c.get('seal'):
            equip["seals"] = [{"seal_number": c['seal']}]
        equipment_list.append(equip)

        cargo = c['cargo']
        cargo_item = {
            "package_quantity": cargo['package_quantity'],
            "package_kind_code": cargo['package_kind_code'],
            "description_of_goods": cargo['description_of_goods'],
            "weight": cargo['weight'],
            "volume": cargo['volume'],
        }
        cargo_items.append(cargo_item)

        if cargo.get('_remarks_hint'):
            remarks_parts.append(f"{c['ref']}: {cargo['_remarks_hint']}")

    output = {
        "document_status_code": "DRF",
        "transport_document_type": "B/L",
        "shipping_instruction_reference": si_ref,
        "carrier_booking_reference": booking,
        "issue_date": date,
        "freight_payment_term_code": freight,
        "parties": parties,
        "transport_plans": [{
            "port_of_loading": {"location_name": pol[0]},
            "port_of_discharge": {"location_name": pod[0]},
            "carrier_voyage_number": voyage,
        }],
        "equipment_list": equipment_list,
        "cargo_items": cargo_items,
    }

    if remarks_parts:
        output["remarks"] = " | ".join(remarks_parts)

    return json.dumps(output, ensure_ascii=False)


def generate_example(index: int, num_containers: int, has_reefer_mix: bool = False) -> dict:
    """Generate one multi-container shipping instruction example."""
    shipper = random.choice(SHIPPERS)
    consignee = random.choice(CONSIGNEES)
    while consignee == shipper:
        consignee = random.choice(CONSIGNEES)
    # 70% no notify (real-world missing data asymmetry)
    candidates = [s for s in SHIPPERS if s != shipper and s != consignee]
    notify = random.choice(candidates) if random.random() < 0.30 and candidates else None

    pol = random.choice(PORTS)
    pod = random.choice(PORTS)
    while pod == pol:
        pod = random.choice(PORTS)

    si_ref = f"SI-MULTI-51-{index:04d}"
    booking = generate_booking_ref()
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    date = f"2026-{month:02d}-{day:02d}"
    vessel = generate_vessel_name()
    voyage = generate_voyage()
    freight = random.choice(["PPD", "COL"])

    # Decide container mix
    if has_reefer_mix and num_containers >= 3:
        # 1-2 reefers mixed with dry containers
        num_reefers = min(random.randint(1, 2), num_containers // 3)
        dry_types = ["20GP", "40GP", "40HC"]
        reefer_types = ["20RF", "40RF"]
    else:
        num_reefers = 0
        dry_types = ["20GP", "40GP", "40HC"]
        reefer_types = []

    containers = []
    used_refs = set()

    for i in range(num_containers):
        is_reefer = i < num_reefers
        ctype = random.choice(reefer_types if is_reefer else dry_types)

        ref = generate_container_ref()
        while ref in used_refs:
            ref = generate_container_ref()
        used_refs.add(ref)

        seal = generate_seal() if random.random() < 0.75 else None  # 25% no seal (real-world)
        cargo = generate_cargo_item(ctype)

        containers.append({
            "ref": ref,
            "type": ctype,
            "seal": seal,
            "cargo": cargo,
            "_pkg_name": {p[0]: p[1] for p in PACKAGE_TYPES}.get(cargo['package_kind_code'], "PKG"),
        })

    input_text = format_ocr_input(
        si_ref, booking, date, shipper, consignee, notify,
        pol, pod, vessel, voyage, containers, "PREPAID" if freight == "PPD" else "COLLECT"
    )
    output_json = build_dcsa_output(
        si_ref, booking, date, shipper, consignee, notify,
        pol, pod, vessel, voyage, containers, freight
    )

    return {"input": input_text, "output": output_json}


def main():
    parser = argparse.ArgumentParser(description="Coklu Konteyner Sentetik Veri Jeneratoru")
    parser.add_argument("--count", type=int, default=60, help="Kac ornek (default: 60)")
    parser.add_argument("--min-containers", type=int, default=5, help="Min konteyner (default: 5)")
    parser.add_argument("--max-containers", type=int, default=14, help="Max konteyner (default: 14)")
    parser.add_argument("--output", type=Path, required=True, help="Output JSONL file")
    parser.add_argument("--seed", type=int, default=3407, help="Random seed")
    args = parser.parse_args()

    random.seed(args.seed)

    print(f"Generating {args.count} multi-container examples...")
    print(f"  Containers per example: {args.min_containers}-{args.max_containers}")
    print(f"  Seed: {args.seed}")

    examples = []
    total_containers = 0
    reefer_count = 0

    for i in range(args.count):
        # Container count distribution (Phase 5.3 — capped at 14 to prevent truncation):
        # 30% (2-4), 40% (5-8 benchmark range), 20% (9-11), 10% (12-14 stress test)
        r = random.random()
        if r < 0.30:
            num = random.randint(2, 4)
        elif r < 0.70:
            num = random.randint(5, 8)
        elif r < 0.90:
            num = random.randint(9, 11)
        else:
            num = random.randint(12, 14)

        has_reefer = random.random() < 0.25  # 25% include reefers
        example = generate_example(i + 1, num, has_reefer_mix=has_reefer)
        examples.append(example)

        total_containers += num
        if has_reefer:
            reefer_count += 1

    # Shuffle with fixed seed
    random.seed(args.seed)
    random.shuffle(examples)

    # Save
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for example in examples:
            f.write(json.dumps(example, ensure_ascii=False) + "\n")

    print(f"\nGenerated {len(examples)} examples")
    print(f"  Total containers: {total_containers}")
    print(f"  Avg containers/example: {total_containers/len(examples):.1f}")
    print(f"  Examples with reefers: {reefer_count}/{len(examples)}")
    print(f"  Output: {args.output}")


if __name__ == "__main__":
    main()
