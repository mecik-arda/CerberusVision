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
                party_role_code=PartyRoleCode.SHIPPER_DCSA,
                party_name="FORENTIS GLOBAL",
                address=Address(street="MAH NO:3", city="ANTALYA", country_code="TR"),
            ),
            Party(
                party_role_code=PartyRoleCode.CONSIGNEE_DCSA,
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
        assert "Document Status Code" in field_labels
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

    def test_optional_xsd_control_fields_do_not_block_approval(self):
        si = create_complete_si()
        si.shipping_instruction_reference = None
        si.shipping_instruction_date_time = None
        si.carrier_booking_reference = None
        si.issue_date = None
        si.place_of_issue = None

        missing_paths = {field.field_path for field in check_mandatory_fields(si)}

        assert "shipping_instruction_reference" not in missing_paths
        assert "shipping_instruction_date_time" not in missing_paths
        assert "carrier_booking_reference" not in missing_paths
        assert "issue_date" not in missing_paths
        assert "place_of_issue.location_name" not in missing_paths

    def test_party_order_is_resolved_by_role(self):
        si = create_complete_si()
        si.parties.reverse()
        missing = check_mandatory_fields(si)
        assert missing == []

    def test_missing_shipper_is_not_masked_by_consignee(self):
        si = create_complete_si()
        si.parties = [si.parties[1]]
        missing_labels = [field.field_label for field in check_mandatory_fields(si)]
        assert "Shipper Name" in missing_labels
        assert "Shipper Address" in missing_labels

    def test_every_collection_item_is_validated(self):
        si = create_complete_si()
        si.transport_plans.append(
            TransportPlan(leg_sequence_number=2, transport_mode=TransportMode.SEA)
        )
        si.equipment_list.append(Equipment())
        si.cargo_items.append(CargoItem())
        missing_paths = {field.field_path for field in check_mandatory_fields(si)}
        assert "transport_plans[1].port_of_loading.location_name" in missing_paths
        assert "equipment_list[1].equipment_reference" in missing_paths
        assert "cargo_items[1].description_of_goods" in missing_paths

    def test_empty_collections_keep_first_item_paths_for_the_ui(self):
        missing_paths = {field.field_path for field in check_mandatory_fields(create_incomplete_si())}
        assert "transport_plans[0].port_of_loading.location_name" in missing_paths
        assert "equipment_list[0].equipment_reference" in missing_paths
        assert "cargo_items[0].description_of_goods" in missing_paths

    def test_schema_location_matches_bundled_xsd(self):
        xml_str = shipping_instruction_to_xml(create_complete_si())
        assert "shipping_instruction.xsd" in xml_str
        assert "dcsa_shipping_instruction_v2.xsd" not in xml_str

    def test_shipper_owned_is_validated_as_boolean(self):
        si = create_complete_si()
        si.equipment_list[0].is_shipper_owned = True
        xml_str = shipping_instruction_to_xml(si)
        valid, errors = validate_xml_against_xsd(xml_str)
        assert valid is True
        invalid_xml = xml_str.replace(">true</IsShipperOwned>", ">invalid</IsShipperOwned>")
        valid, errors = validate_xml_against_xsd(invalid_xml)
        assert valid is False
        assert errors


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
        assert "Shipping Instruction Reference" not in missing_labels
        assert "Consignee Address" in missing_labels
