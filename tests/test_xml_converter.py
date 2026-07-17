import pytest
from lxml import etree
from app.models import (
    ShippingInstruction,
    Party,
    PartyRoleCode,
    Address,
    ContactDetails,
    TransportPlan,
    TransportMode,
    Location,
    Equipment,
    Weight,
    WeightUnit,
    Seal,
    CargoItem,
    PackageKindCode,
    CargoWeight,
    CargoVolume,
    EquipmentReferences,
    EquipmentReferenceDetail,
)
from app.xml.converter import shipping_instruction_to_xml, DCSA_NS


def create_sample_shipping_instruction() -> ShippingInstruction:
    return ShippingInstruction(
        shipping_instruction_reference="SI-2026-001",
        carrier_booking_reference="CBR-12345",
        transport_document_type="B/L",
        freight_payment_term_code="PPD",
        issue_date="2026-01-15",
        place_of_issue=Location(un_location_code="TRALI", location_name="ALIAGA"),
        parties=[
            Party(
                party_role_code=PartyRoleCode.SHIPPER,
                party_name="FORENTIS GLOBAL",
                address=Address(
                    street="YESILYURT MAH. NO:3",
                    city="ANTALYA",
                    country_code="TR",
                ),
                contact_details=ContactDetails(
                    phone_number="05365400708",
                ),
            ),
            Party(
                party_role_code=PartyRoleCode.CONSIGNEE,
                party_name="SHAHEEN PLASTIC",
                address=Address(
                    street="OFF # 15, FRERE ROAD",
                    city="KARACHI",
                    country_code="PK",
                ),
            ),
        ],
        transport_plans=[
            TransportPlan(
                leg_sequence_number=1,
                transport_mode=TransportMode.SEA,
                port_of_loading=Location(location_name="TCEGE ALIAGA"),
                port_of_discharge=Location(location_name="KARACHI"),
            ),
        ],
        equipment_list=[
            Equipment(
                equipment_reference="MSKU1875698",
                cargo_gross_weight=Weight(weight=26080.00, unit=WeightUnit.KILOGRAM),
                seals=[Seal(seal_number="SEAL123")],
            ),
        ],
        cargo_items=[
            CargoItem(
                package_quantity=32,
                package_kind_code=PackageKindCode.PALLET,
                description_of_goods="MDF-LAMINATE FLOOR",
                commodity_code="4418.9910",
                weight=CargoWeight(weight_value=26080.00, unit=WeightUnit.KILOGRAM),
                volume=CargoVolume(volume_value=28.16),
                equipment_references=EquipmentReferences(
                    equipment_reference_detail=[
                        EquipmentReferenceDetail(
                            equipment_reference="MSKU1875698",
                            number_of_packages=32,
                        )
                    ]
                ),
            ),
        ],
    )


class TestShippingInstructionToXml:
    def test_generates_valid_xml(self):
        si = create_sample_shipping_instruction()
        xml_str = shipping_instruction_to_xml(si)
        assert xml_str.startswith("<?xml")
        assert "ShippingInstruction" in xml_str

    def test_xml_has_namespace(self):
        si = create_sample_shipping_instruction()
        xml_str = shipping_instruction_to_xml(si)
        doc = etree.fromstring(xml_str.encode("UTF-8"))
        assert doc.tag == f"{{{DCSA_NS}}}ShippingInstruction"

    def test_xml_contains_parties(self):
        si = create_sample_shipping_instruction()
        xml_str = shipping_instruction_to_xml(si)
        doc = etree.fromstring(xml_str.encode("UTF-8"))
        parties = doc.findall(f".//{{{DCSA_NS}}}Party")
        assert len(parties) == 2

    def test_xml_contains_party_name(self):
        si = create_sample_shipping_instruction()
        xml_str = shipping_instruction_to_xml(si)
        assert "FORENTIS GLOBAL" in xml_str
        assert "SHAHEEN PLASTIC" in xml_str

    def test_xml_contains_equipment(self):
        si = create_sample_shipping_instruction()
        xml_str = shipping_instruction_to_xml(si)
        assert "MSKU1875698" in xml_str
        assert "26080" in xml_str

    def test_xml_contains_cargo_items(self):
        si = create_sample_shipping_instruction()
        xml_str = shipping_instruction_to_xml(si)
        assert "MDF-LAMINATE FLOOR" in xml_str
        assert "PALLET" in xml_str
        assert "4418.9910" in xml_str

    def test_xml_contains_transport_plans(self):
        si = create_sample_shipping_instruction()
        xml_str = shipping_instruction_to_xml(si)
        assert "TCEGE ALIAGA" in xml_str
        assert "KARACHI" in xml_str
        assert "SEA" in xml_str

    def test_xml_with_empty_instruction(self):
        si = ShippingInstruction()
        xml_str = shipping_instruction_to_xml(si)
        doc = etree.fromstring(xml_str.encode("UTF-8"))
        assert doc.tag == f"{{{DCSA_NS}}}ShippingInstruction"

    def test_xml_seals_present(self):
        si = create_sample_shipping_instruction()
        xml_str = shipping_instruction_to_xml(si)
        assert "SEAL123" in xml_str

    def test_xml_volume_present(self):
        si = create_sample_shipping_instruction()
        xml_str = shipping_instruction_to_xml(si)
        assert "28.16" in xml_str

    def test_xml_parseable_by_lxml(self):
        si = create_sample_shipping_instruction()
        xml_str = shipping_instruction_to_xml(si)
        parser = etree.XMLParser(remove_blank_text=False)
        doc = etree.fromstring(xml_str.encode("UTF-8"), parser)
        assert doc is not None