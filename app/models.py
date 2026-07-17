from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class DocumentStatusCode(str, Enum):
    DRAFT = "DRF"
    FINAL = "FNL"


class FreightPaymentTermCode(str, Enum):
    PREPAID = "PPD"
    COLLECT = "COL"


class TransportDocumentType(str, Enum):
    BILL_OF_LADING = "B/L"
    SEA_WAYBILL = "SWB"


class PartyRoleCode(str, Enum):
    SHIPPER = "SHI"
    CONSIGNEE = "CON"
    NOTIFY = "NTF"


class TransportMode(str, Enum):
    SEA = "SEA"
    ROAD = "ROD"
    AIR = "AIR"
    RAIL = "RAI"


class PackageKindCode(str, Enum):
    PALLET = "PALLET"
    CARTON = "CARTON"
    CRATE = "CRATE"
    BALE = "BALE"
    DRUM = "DRUM"
    BOX = "BOX"


class WeightUnit(str, Enum):
    KILOGRAM = "KGM"
    TON = "TON"


class VolumeUnit(str, Enum):
    CUBIC_METERS = "CBM"


class TemperatureUnit(str, Enum):
    CELSIUS = "CEL"


class Address(BaseModel):
    street: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country_code: Optional[str] = None


class ContactDetails(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None


class Party(BaseModel):
    party_role_code: PartyRoleCode
    party_id: Optional[str] = None
    party_name: Optional[str] = None
    address: Optional[Address] = None
    contact_details: Optional[ContactDetails] = None
    same_as_consignee: Optional[bool] = None


class Location(BaseModel):
    un_location_code: Optional[str] = None
    location_name: Optional[str] = None


class TransportPlan(BaseModel):
    leg_sequence_number: int
    transport_mode: Optional[TransportMode] = None
    port_of_loading: Optional[Location] = None
    port_of_discharge: Optional[Location] = None
    place_of_receipt: Optional[Location] = None
    place_of_delivery: Optional[Location] = None
    carrier_voyage_number: Optional[str] = None
    vessel_imo_number: Optional[str] = None


class Weight(BaseModel):
    weight: Optional[float] = None
    unit: WeightUnit = WeightUnit.KILOGRAM


class VerifiedGrossMass(BaseModel):
    weight: Optional[float] = None
    unit: WeightUnit = WeightUnit.KILOGRAM
    verification_method: Optional[str] = None


class Seal(BaseModel):
    seal_number: Optional[str] = None
    seal_source_code: Optional[str] = None
    seal_type_code: Optional[str] = None


class TareWeight(BaseModel):
    weight: Optional[float] = None
    unit: WeightUnit = WeightUnit.KILOGRAM


class Equipment(BaseModel):
    equipment_reference: Optional[str] = None
    iso_equipment_code: Optional[str] = None
    is_shipper_owned: Optional[bool] = None
    cargo_gross_weight: Optional[Weight] = None
    verified_gross_mass: Optional[VerifiedGrossMass] = None
    seals: Optional[List[Seal]] = None
    tare_weight: Optional[TareWeight] = None


class EquipmentReferenceDetail(BaseModel):
    equipment_reference: Optional[str] = None
    number_of_packages: Optional[int] = None


class EquipmentReferences(BaseModel):
    equipment_reference_detail: List[EquipmentReferenceDetail] = Field(default_factory=list)


class FlashPoint(BaseModel):
    temperature: Optional[float] = None
    unit: TemperatureUnit = TemperatureUnit.CELSIUS


class EmergencyContact(BaseModel):
    name: Optional[str] = None
    phone_number: Optional[str] = None


class DangerousGoods(BaseModel):
    un_number: Optional[str] = None
    imdg_class: Optional[str] = None
    packing_group: Optional[str] = None
    technical_name: Optional[str] = None
    flash_point: Optional[FlashPoint] = None
    emergency_contact: Optional[EmergencyContact] = None


class CargoWeight(BaseModel):
    weight_value: Optional[float] = None
    unit: WeightUnit = WeightUnit.KILOGRAM


class CargoVolume(BaseModel):
    volume_value: Optional[float] = None
    unit: VolumeUnit = VolumeUnit.CUBIC_METERS


class CargoItem(BaseModel):
    package_quantity: Optional[int] = None
    package_kind_code: Optional[PackageKindCode] = None
    description_of_goods: Optional[str] = None
    shipping_marks: Optional[str] = None
    commodity_code: Optional[str] = None
    weight: Optional[CargoWeight] = None
    volume: Optional[CargoVolume] = None
    equipment_references: Optional[EquipmentReferences] = None
    dangerous_goods_list: Optional[List[DangerousGoods]] = None


class DocumentReference(BaseModel):
    type_code: Optional[str] = None
    reference_number: Optional[str] = None


class CustomsInformation(BaseModel):
    fta_declaration: Optional[str] = None
    export_customs_clearance_location: Optional[Location] = None


class ShippingInstruction(BaseModel):
    shipping_instruction_reference: Optional[str] = None
    document_status_code: Optional[DocumentStatusCode] = None
    shipping_instruction_date_time: Optional[str] = None
    carrier_booking_reference: Optional[str] = None
    transport_document_type: Optional[TransportDocumentType] = None
    freight_payment_term_code: Optional[FreightPaymentTermCode] = None
    issue_date: Optional[str] = None
    place_of_issue: Optional[Location] = None
    export_declaration_number: Optional[str] = None
    service_contract_reference: Optional[str] = None
    parties: List[Party] = Field(default_factory=list)
    transport_plans: List[TransportPlan] = Field(default_factory=list)
    equipment_list: List[Equipment] = Field(default_factory=list)
    cargo_items: List[CargoItem] = Field(default_factory=list)
    document_references: List[DocumentReference] = Field(default_factory=list)
    customs_information: Optional[CustomsInformation] = None
    remarks: Optional[str] = None


class ProcessingStatus(str, Enum):
    PENDING = "PENDING"
    OCR_PROCESSING = "OCR_PROCESSING"
    LLM_ANALYZING = "LLM_ANALYZING"
    XML_VALIDATING = "XML_VALIDATING"
    COMPLETED = "COMPLETED"
    DRAFT = "DRAFT"
    ERROR = "ERROR"


class FieldValidation(BaseModel):
    field_path: str
    field_label: str
    value: Optional[str] = None
    is_required: bool = False
    is_missing: bool = False


class ProcessingResult(BaseModel):
    status: ProcessingStatus
    xml_content: Optional[str] = None
    raw_ocr_text: Optional[str] = None
    raw_llm_json: Optional[str] = None
    validation_errors: List[str] = Field(default_factory=list)
    missing_fields: List[FieldValidation] = Field(default_factory=list)
    message: Optional[str] = None