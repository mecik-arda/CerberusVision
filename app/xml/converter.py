from __future__ import annotations
from typing import Optional
from enum import Enum
from lxml import etree
from app.models import (
    ShippingInstruction,
    Party,
    TransportPlan,
    Equipment,
    CargoItem,
    DocumentReference,
    CustomsInformation,
    Location,
    Address,
    ContactDetails,
    Weight,
    VerifiedGrossMass,
    Seal,
    TareWeight,
    CargoWeight,
    CargoVolume,
    EquipmentReferences,
    DangerousGoods,
    FlashPoint,
    EmergencyContact,
)


DCSA_NS = "http://dcsa.org/schemas/si/v2"
NSMAP = {None: DCSA_NS, "xsi": "http://www.w3.org/2001/XMLSchema-instance"}


def _ns(tag: str) -> str:
    return f"{{{DCSA_NS}}}{tag}"


def _add_text_element(parent: etree._Element, tag: str, value) -> Optional[etree._Element]:
    if value is None:
        return None
    elem = etree.SubElement(parent, _ns(tag))
    if isinstance(value, bool):
        elem.text = str(value).lower()
    elif isinstance(value, Enum):
        elem.text = str(value.value)
    else:
        elem.text = str(value)
    return elem


def _add_location(parent: etree._Element, tag: str, location: Optional[Location]) -> Optional[etree._Element]:
    if location is None:
        return None
    elem = etree.SubElement(parent, _ns(tag))
    _add_text_element(elem, "UNLocationCode", location.un_location_code)
    _add_text_element(elem, "LocationName", location.location_name)
    return elem


def _add_address(parent: etree._Element, address: Optional[Address]) -> Optional[etree._Element]:
    if address is None:
        return None
    elem = etree.SubElement(parent, _ns("Address"))
    _add_text_element(elem, "Street", address.street)
    _add_text_element(elem, "City", address.city)
    _add_text_element(elem, "PostalCode", address.postal_code)
    _add_text_element(elem, "CountryCode", address.country_code)
    return elem


def _add_contact_details(parent: etree._Element, contact: Optional[ContactDetails]) -> Optional[etree._Element]:
    if contact is None:
        return None
    elem = etree.SubElement(parent, _ns("ContactDetails"))
    _add_text_element(elem, "Name", contact.name)
    _add_text_element(elem, "Email", contact.email)
    _add_text_element(elem, "PhoneNumber", contact.phone_number)
    return elem


def _add_party(parent: etree._Element, party: Party) -> etree._Element:
    elem = etree.SubElement(parent, _ns("Party"))
    _add_text_element(elem, "PartyRoleCode", party.party_role_code)
    _add_text_element(elem, "PartyID", party.party_id)
    _add_text_element(elem, "PartyName", party.party_name)
    _add_address(elem, party.address)
    _add_contact_details(elem, party.contact_details)
    _add_text_element(elem, "SameAsConsignee", party.same_as_consignee)
    return elem


def _add_weight(parent: etree._Element, tag: str, weight: Optional[Weight]) -> Optional[etree._Element]:
    if weight is None:
        return None
    elem = etree.SubElement(parent, _ns(tag))
    _add_text_element(elem, "Weight", weight.weight)
    _add_text_element(elem, "Unit", weight.unit)
    return elem


def _add_verified_gross_mass(parent: etree._Element, vgm: Optional[VerifiedGrossMass]) -> Optional[etree._Element]:
    if vgm is None:
        return None
    elem = etree.SubElement(parent, _ns("VerifiedGrossMass"))
    _add_text_element(elem, "Weight", vgm.weight)
    _add_text_element(elem, "Unit", vgm.unit)
    _add_text_element(elem, "VerificationMethod", vgm.verification_method)
    return elem


def _add_seal(parent: etree._Element, seal: Seal) -> etree._Element:
    elem = etree.SubElement(parent, _ns("Seal"))
    _add_text_element(elem, "SealNumber", seal.seal_number)
    _add_text_element(elem, "SealSourceCode", seal.seal_source_code)
    _add_text_element(elem, "SealTypeCode", seal.seal_type_code)
    return elem


def _add_tare_weight(parent: etree._Element, tare: Optional[TareWeight]) -> Optional[etree._Element]:
    if tare is None:
        return None
    elem = etree.SubElement(parent, _ns("TareWeight"))
    _add_text_element(elem, "Weight", tare.weight)
    _add_text_element(elem, "Unit", tare.unit)
    return elem


def _add_equipment(parent: etree._Element, equipment: Equipment) -> etree._Element:
    elem = etree.SubElement(parent, _ns("Equipment"))
    _add_text_element(elem, "EquipmentReference", equipment.equipment_reference)
    _add_text_element(elem, "ISOEquipmentCode", equipment.iso_equipment_code)
    _add_text_element(elem, "IsShipperOwned", equipment.is_shipper_owned)
    _add_weight(elem, "CargoGrossWeight", equipment.cargo_gross_weight)
    _add_verified_gross_mass(elem, equipment.verified_gross_mass)
    if equipment.seals:
        seals_elem = etree.SubElement(elem, _ns("Seals"))
        for seal in equipment.seals:
            _add_seal(seals_elem, seal)
    _add_tare_weight(elem, equipment.tare_weight)
    return elem


def _add_transport_plan(parent: etree._Element, plan: TransportPlan) -> etree._Element:
    elem = etree.SubElement(parent, _ns("TransportPlan"))
    _add_text_element(elem, "LegSequenceNumber", plan.leg_sequence_number)
    _add_text_element(elem, "TransportMode", plan.transport_mode)
    _add_location(elem, "PortOfLoading", plan.port_of_loading)
    _add_location(elem, "PortOfDischarge", plan.port_of_discharge)
    _add_location(elem, "PlaceOfReceipt", plan.place_of_receipt)
    _add_location(elem, "PlaceOfDelivery", plan.place_of_delivery)
    _add_text_element(elem, "CarrierVoyageNumber", plan.carrier_voyage_number)
    _add_text_element(elem, "VesselIMONumber", plan.vessel_imo_number)
    return elem


def _add_equipment_references(parent: etree._Element, refs: Optional[EquipmentReferences]) -> Optional[etree._Element]:
    if refs is None or not refs.equipment_reference_detail:
        return None
    elem = etree.SubElement(parent, _ns("EquipmentReferences"))
    for detail in refs.equipment_reference_detail:
        detail_elem = etree.SubElement(elem, _ns("EquipmentReferenceDetail"))
        _add_text_element(detail_elem, "EquipmentReference", detail.equipment_reference)
        _add_text_element(detail_elem, "NumberOfPackages", detail.number_of_packages)
    return elem


def _add_flash_point(parent: etree._Element, fp: Optional[FlashPoint]) -> Optional[etree._Element]:
    if fp is None:
        return None
    elem = etree.SubElement(parent, _ns("FlashPoint"))
    _add_text_element(elem, "Temperature", fp.temperature)
    _add_text_element(elem, "Unit", fp.unit)
    return elem


def _add_emergency_contact(parent: etree._Element, ec: Optional[EmergencyContact]) -> Optional[etree._Element]:
    if ec is None:
        return None
    elem = etree.SubElement(parent, _ns("EmergencyContact"))
    _add_text_element(elem, "Name", ec.name)
    _add_text_element(elem, "PhoneNumber", ec.phone_number)
    return elem


def _add_dangerous_goods(parent: etree._Element, dg: DangerousGoods) -> etree._Element:
    elem = etree.SubElement(parent, _ns("DangerousGoods"))
    _add_text_element(elem, "UNNumber", dg.un_number)
    _add_text_element(elem, "IMDGClass", dg.imdg_class)
    _add_text_element(elem, "PackingGroup", dg.packing_group)
    _add_text_element(elem, "TechnicalName", dg.technical_name)
    _add_flash_point(elem, dg.flash_point)
    _add_emergency_contact(elem, dg.emergency_contact)
    return elem


def _add_cargo_item(parent: etree._Element, item: CargoItem) -> etree._Element:
    elem = etree.SubElement(parent, _ns("CargoItem"))
    _add_text_element(elem, "PackageQuantity", item.package_quantity)
    _add_text_element(elem, "PackageKindCode", item.package_kind_code)
    _add_text_element(elem, "DescriptionOfGoods", item.description_of_goods)
    _add_text_element(elem, "ShippingMarks", item.shipping_marks)
    _add_text_element(elem, "CommodityCode", item.commodity_code)
    if item.weight is not None:
        weight_elem = etree.SubElement(elem, _ns("Weight"))
        _add_text_element(weight_elem, "WeightValue", item.weight.weight_value)
        _add_text_element(weight_elem, "Unit", item.weight.unit)
    if item.volume is not None:
        vol_elem = etree.SubElement(elem, _ns("Volume"))
        _add_text_element(vol_elem, "VolumeValue", item.volume.volume_value)
        _add_text_element(vol_elem, "Unit", item.volume.unit)
    _add_equipment_references(elem, item.equipment_references)
    if item.dangerous_goods_list:
        dg_list_elem = etree.SubElement(elem, _ns("DangerousGoodsList"))
        for dg in item.dangerous_goods_list:
            _add_dangerous_goods(dg_list_elem, dg)
    return elem


def _add_document_reference(parent: etree._Element, ref: DocumentReference) -> etree._Element:
    elem = etree.SubElement(parent, _ns("DocumentReference"))
    _add_text_element(elem, "TypeCode", ref.type_code)
    _add_text_element(elem, "ReferenceNumber", ref.reference_number)
    return elem


def _add_customs_info(parent: etree._Element, customs: Optional[CustomsInformation]) -> Optional[etree._Element]:
    if customs is None:
        return None
    elem = etree.SubElement(parent, _ns("CustomsInformation"))
    _add_text_element(elem, "FTADeclaration", customs.fta_declaration)
    if customs.export_customs_clearance_location is not None:
        loc_elem = etree.SubElement(elem, _ns("ExportCustomsClearanceLocation"))
        _add_text_element(loc_elem, "UNLocationCode", customs.export_customs_clearance_location.un_location_code)
    return elem


def shipping_instruction_to_xml(si: ShippingInstruction) -> str:
    root = etree.Element(_ns("ShippingInstruction"), nsmap=NSMAP)
    root.set(
        "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation",
        f"{DCSA_NS} shipping_instruction.xsd",
    )
    _add_text_element(root, "ShippingInstructionReference", si.shipping_instruction_reference)
    _add_text_element(root, "DocumentStatusCode", si.document_status_code)
    _add_text_element(root, "ShippingInstructionDateTime", si.shipping_instruction_date_time)
    _add_text_element(root, "CarrierBookingReference", si.carrier_booking_reference)
    _add_text_element(root, "TransportDocumentType", si.transport_document_type)
    _add_text_element(root, "FreightPaymentTermCode", si.freight_payment_term_code)
    _add_text_element(root, "IssueDate", si.issue_date)
    _add_location(root, "PlaceOfIssue", si.place_of_issue)
    _add_text_element(root, "ExportDeclarationNumber", si.export_declaration_number)
    _add_text_element(root, "ServiceContractReference", si.service_contract_reference)

    if si.parties:
        parties_elem = etree.SubElement(root, _ns("Parties"))
        for party in si.parties:
            _add_party(parties_elem, party)

    if si.transport_plans:
        plans_elem = etree.SubElement(root, _ns("TransportPlans"))
        for plan in si.transport_plans:
            _add_transport_plan(plans_elem, plan)

    if si.equipment_list:
        equip_elem = etree.SubElement(root, _ns("EquipmentList"))
        for eq in si.equipment_list:
            _add_equipment(equip_elem, eq)

    if si.cargo_items:
        cargo_elem = etree.SubElement(root, _ns("CargoItems"))
        for item in si.cargo_items:
            _add_cargo_item(cargo_elem, item)

    if si.document_references:
        refs_elem = etree.SubElement(root, _ns("DocumentReferences"))
        for ref in si.document_references:
            _add_document_reference(refs_elem, ref)

    _add_customs_info(root, si.customs_information)
    _add_text_element(root, "Remarks", si.remarks)

    xml_bytes = etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    return xml_bytes.decode("UTF-8")
