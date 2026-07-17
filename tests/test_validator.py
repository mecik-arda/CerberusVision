import pytest
from app.models import (
    ShippingInstruction,
    Party,
    PartyRoleCode,
    Address,
    TransportPlan,
    TransportMode,
    Location,
    Equipment,
    Weight,
    WeightUnit,
    CargoItem,
    PackageKindCode,
    CargoWeight,
    ProcessingStatus,
)
from app.xml.converter import shipping_instruction_to_xml
from app.xml.validator import (
    validate_xml_against_xsd,
    check_mandatory_fields,
    validate_and_grade,
)


def create_complete_si() -> ShippingInstruction:
    return ShippingInstruction(
        shipping_instruction_reference="SI-2026-001",
        document_status_code="DRF",
        shipping_instruction_date_time="2026-01-15T10:00:00",
        carrier_booking_reference="CBR-12345",
        issue_date="2026-01-15",
        place_of_issue=Location(location_name="ALIAGA"),
        parties=[
            Party(
                party_role_code=PartyRoleCode.SHIPPER,
                party_name="FORENTIS GLOBAL",
                address=Address(street="MAH NO:3", city="ANTALYA", country_code="TR"),
            ),
            Party(
                party_role_code=PartyRoleCode.CONSIGNEE,
                party_name="SHAHEEN PLASTIC",
                address=Address(street="OFF # 15", city="KARACHI", country_code="PK"),
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
            ),
        ],
        cargo_items=[
            CargoItem(
                package_quantity=32,
                package_kind_code=PackageKindCode.PALLET,
                description_of_goods="MDF-LAMINATE FLOOR",
                weight=CargoWeight(weight_value=26080.00, unit=WeightUnit.KILOGRAM),
            ),
        ],
    )


def create_incomplete_si() -> ShippingInstruction:
    return ShippingInstruction(
        shipping_instruction_reference=None,
        parties=[
            Party(party_role_code=PartyRoleCode.SHIPPER),
        ],
        transport_plans=[],
        equipment_list=[],
        cargo_items=[],
    )


class TestValidateXmlAgainstXsd:
    def test_valid_xml_passes(self):
        si = create_complete_si()
        xml_str = shipping_instruction_to_xml(si)
        is_valid, errors = validate_xml_against_xsd(xml_str)
        assert is_valid is True
        assert len(errors) == 0

    def test_empty_si_still_validates(self):
        si = ShippingInstruction()
        xml_str = shipping_instruction_to_xml(si)
        is_valid, errors = validate_xml_against_xsd(xml_str)
        assert is_valid is True

    def test_invalid_xml_returns_errors(self):
        bad_xml = "<ShippingInstruction><bad></bad></ShippingInstruction>"
        is_valid, errors = validate_xml_against_xsd(bad_xml)
        assert is_valid is False
        assert len(errors) > 0


class TestCheckMandatoryFields:
    def test_complete_si_no_missing(self):
        si = create_complete_si()
        missing = check_mandatory_fields(si)
        assert len(missing) == 0

    def test_incomplete_si_finds_missing(self):
        si = create_incomplete_si()
        missing = check_mandatory_fields(si)
        assert len(missing) > 0
        field_labels = [m.field_label for m in missing]
        assert "Shipping Instruction Reference" in field_labels
        assert "Consignee Name" in field_labels
        assert "Port of Loading" in field_labels
        assert "Equipment Reference" in field_labels

    def test_missing_field_has_correct_attributes(self):
        si = create_incomplete_si()
        missing = check_mandatory_fields(si)
        for field in missing:
            assert field.is_required is True
            assert field.is_missing is True
            assert field.value is None


class TestValidateAndGrade:
    def test_complete_si_returns_completed(self):
        si = create_complete_si()
        xml_str = shipping_instruction_to_xml(si)
        status, errors, missing = validate_and_grade(si, xml_str)
        assert status == ProcessingStatus.COMPLETED
        assert len(missing) == 0

    def test_incomplete_si_returns_draft(self):
        si = create_incomplete_si()
        xml_str = shipping_instruction_to_xml(si)
        status, errors, missing = validate_and_grade(si, xml_str)
        assert status == ProcessingStatus.DRAFT
        assert len(missing) > 0

    def test_graceful_degradation_no_exception(self):
        si = ShippingInstruction()
        xml_str = shipping_instruction_to_xml(si)
        status, errors, missing = validate_and_grade(si, xml_str)
        assert status == ProcessingStatus.DRAFT
        assert isinstance(missing, list)
        assert isinstance(errors, list)

    def test_draft_status_when_partially_complete(self):
        si = create_complete_si()
        si.shipping_instruction_reference = None
        si.parties[1].address.street = None
        xml_str = shipping_instruction_to_xml(si)
        status, errors, missing = validate_and_grade(si, xml_str)
        assert status == ProcessingStatus.DRAFT
        missing_labels = [m.field_label for m in missing]
        assert "Shipping Instruction Reference" in missing_labels
        assert "Consignee Address" in missing_labels