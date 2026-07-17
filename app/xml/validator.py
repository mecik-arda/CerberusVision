from __future__ import annotations
from typing import List, Tuple, Optional
from lxml import etree
from app.config import settings
from app.models import (
    ShippingInstruction,
    FieldValidation,
    PartyRoleCode,
    ProcessingStatus,
)


MANDATORY_FIELDS = [
    ("shipping_instruction_reference", "Shipping Instruction Reference"),
    ("document_status_code", "Document Status Code"),
    ("shipping_instruction_date_time", "Shipping Instruction DateTime"),
    ("carrier_booking_reference", "Carrier Booking Reference"),
    ("issue_date", "Issue Date"),
    ("place_of_issue.location_name", "Place of Issue"),
]

COLLECTION_MANDATORY_FIELDS = {
    "transport_plans": [
        ("port_of_loading.location_name", "Port of Loading"),
        ("port_of_discharge.location_name", "Port of Discharge"),
    ],
    "equipment_list": [
        ("equipment_reference", "Equipment Reference"),
        ("cargo_gross_weight.weight", "Cargo Gross Weight"),
    ],
    "cargo_items": [
        ("package_quantity", "Package Quantity"),
        ("description_of_goods", "Description of Goods"),
        ("weight.weight_value", "Cargo Weight"),
    ],
}

PARTY_MANDATORY_FIELDS = {
    PartyRoleCode.SHIPPER: (
        "Shipper",
        [("party_name", "Name"), ("address.street", "Address"),
         ("address.city", "City"), ("address.country_code", "Country")],
    ),
    PartyRoleCode.CONSIGNEE: (
        "Consignee",
        [("party_name", "Name"), ("address.street", "Address"),
         ("address.city", "City"), ("address.country_code", "Country")],
    ),
}


def load_xsd_schema() -> etree.XMLSchema:
    xsd_path = settings.xsd_dir / "shipping_instruction.xsd"
    with open(xsd_path, "rb") as f:
        schema_doc = etree.parse(f)
    return etree.XMLSchema(schema_doc)


def validate_xml_against_xsd(xml_content: str) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    try:
        xml_bytes = xml_content.encode("UTF-8")
        doc = etree.fromstring(xml_bytes)
        schema = load_xsd_schema()
        is_valid = schema.validate(doc)
        if not is_valid:
            for error in schema.error_log:
                errors.append(f"Line {error.line}: {error.message}")
        return is_valid, errors
    except etree.XMLSyntaxError as e:
        errors.append(f"XML Syntax Error: {str(e)}")
        return False, errors
    except Exception as e:
        errors.append(f"Validation Error: {str(e)}")
        return False, errors


def _get_nested_value(obj, path: str):
    parts = path.replace("]", "").split(".")
    current = obj
    for part in parts:
        if current is None:
            return None
        if "[" in part:
            attr_name, index_part = part.split("[")
            index = int(index_part)
            if not hasattr(current, attr_name):
                return None
            seq = getattr(current, attr_name)
            if seq is None or index >= len(seq):
                return None
            current = seq[index]
        else:
            if hasattr(current, part):
                current = getattr(current, part)
            else:
                return None
    return current


def check_mandatory_fields(si: ShippingInstruction) -> List[FieldValidation]:
    missing: List[FieldValidation] = []
    for path, label in MANDATORY_FIELDS:
        value = _get_nested_value(si, path)
        if value is None or (isinstance(value, str) and value.strip() == ""):
            missing.append(
                FieldValidation(
                    field_path=path,
                    field_label=label,
                    value=None,
                    is_required=True,
                    is_missing=True,
                )
            )
    for collection_name, fields in COLLECTION_MANDATORY_FIELDS.items():
        items = getattr(si, collection_name)
        targets = list(enumerate(items)) if items else [(0, None)]
        for index, item in targets:
            for relative_path, field_label in fields:
                value = _get_nested_value(item, relative_path) if item is not None else None
                if value is None or (isinstance(value, str) and value.strip() == ""):
                    missing.append(
                        FieldValidation(
                            field_path=f"{collection_name}[{index}].{relative_path}",
                            field_label=field_label,
                            value=None,
                            is_required=True,
                            is_missing=True,
                        )
                    )
    for role, (role_label, fields) in PARTY_MANDATORY_FIELDS.items():
        party_index = next(
            (index for index, party in enumerate(si.parties) if party.party_role_code == role),
            None,
        )
        for relative_path, field_label in fields:
            path = (
                f"parties[{party_index}].{relative_path}"
                if party_index is not None
                else f"parties[role={role.value}].{relative_path}"
            )
            value = _get_nested_value(si.parties[party_index], relative_path) if party_index is not None else None
            if value is None or (isinstance(value, str) and value.strip() == ""):
                missing.append(
                    FieldValidation(
                        field_path=path,
                        field_label=f"{role_label} {field_label}",
                        value=None,
                        is_required=True,
                        is_missing=True,
                    )
                )
    return missing


def validate_and_grade(
    si: ShippingInstruction,
    xml_content: str,
) -> Tuple[ProcessingStatus, List[str], List[FieldValidation]]:
    is_valid, xml_errors = validate_xml_against_xsd(xml_content)
    missing_fields = check_mandatory_fields(si)

    if is_valid and not missing_fields:
        return ProcessingStatus.COMPLETED, xml_errors, missing_fields

    return ProcessingStatus.DRAFT, xml_errors, missing_fields
