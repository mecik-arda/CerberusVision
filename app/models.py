from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr


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
    SHIPPER_DCSA = "CZ"
    CONSIGNEE_DCSA = "CN"
    NOTIFY_DCSA = "N1"
    FORWARDER = "FW"


class TransportMode(str, Enum):
    SEA = "SEA"
    ROAD = "ROD"
    AIR = "AIR"
    RAIL = "RAI"


class PackageKindCode(str, Enum):
    PALLET = "PALLET"
    PL = "PL"
    CARTON = "CARTON"
    CT = "CT"
    CRATE = "CRATE"
    CR = "CR"
    BALE = "BALE"
    BA = "BA"
    DRUM = "DRUM"
    DR = "DR"
    BOX = "BOX"
    BX = "BX"
    BG = "BG"
    BE = "BE"
    RO = "RO"
    CA = "CA"
    BO = "BO"
    BJ = "BJ"
    CY = "CY"
    PC = "PC"
    PK = "PK"
    NE = "NE"
    IBC = "IBC"


class WeightUnit(str, Enum):
    KILOGRAM = "KGM"
    TON = "TON"
    LBR = "LBR"


class VolumeUnit(str, Enum):
    CUBIC_METERS = "CBM"


class TemperatureUnit(str, Enum):
    CELSIUS = "CEL"


class Address(BaseModel):
    street: str | None = None
    city: str | None = None
    postal_code: str | None = None
    country_code: str | None = None


class ContactDetails(BaseModel):
    name: str | None = None
    email: str | None = None
    phone_number: str | None = None


class Party(BaseModel):
    party_role_code: PartyRoleCode
    party_id: str | None = None
    party_name: str | None = None
    address: Address | None = None
    contact_details: ContactDetails | None = None
    same_as_consignee: bool | None = None


class Location(BaseModel):
    un_location_code: str | None = None
    location_name: str | None = None


class TransportPlan(BaseModel):
    leg_sequence_number: int
    transport_mode: TransportMode | None = None
    port_of_loading: Location | None = None
    port_of_discharge: Location | None = None
    place_of_receipt: Location | None = None
    place_of_delivery: Location | None = None
    carrier_voyage_number: str | None = None
    vessel_imo_number: str | None = None


class Weight(BaseModel):
    weight: float | None = None
    unit: WeightUnit = WeightUnit.KILOGRAM


class VerifiedGrossMass(BaseModel):
    weight: float | None = None
    unit: WeightUnit = WeightUnit.KILOGRAM
    verification_method: str | None = None


class Seal(BaseModel):
    seal_number: str | None = None
    seal_source_code: str | None = None
    seal_type_code: str | None = None


class TareWeight(BaseModel):
    weight: float | None = None
    unit: WeightUnit = WeightUnit.KILOGRAM


class Equipment(BaseModel):
    equipment_reference: str | None = None
    iso_equipment_code: str | None = None
    is_shipper_owned: bool | None = None
    cargo_gross_weight: Weight | None = None
    verified_gross_mass: VerifiedGrossMass | None = None
    seals: list[Seal] | None = None
    tare_weight: TareWeight | None = None


class EquipmentReferenceDetail(BaseModel):
    equipment_reference: str | None = None
    number_of_packages: int | None = None


class EquipmentReferences(BaseModel):
    equipment_reference_detail: list[EquipmentReferenceDetail] = Field(default_factory=list)


class FlashPoint(BaseModel):
    temperature: float | None = None
    unit: TemperatureUnit = TemperatureUnit.CELSIUS


class EmergencyContact(BaseModel):
    name: str | None = None
    phone_number: str | None = None


class DangerousGoods(BaseModel):
    un_number: str | None = None
    imdg_class: str | None = None
    packing_group: str | None = None
    technical_name: str | None = None
    flash_point: FlashPoint | None = None
    emergency_contact: EmergencyContact | None = None


class CargoWeight(BaseModel):
    weight_value: float | None = None
    unit: WeightUnit = WeightUnit.KILOGRAM


class CargoVolume(BaseModel):
    volume_value: float | None = None
    unit: VolumeUnit = VolumeUnit.CUBIC_METERS


class CargoItem(BaseModel):
    package_quantity: int | None = None
    package_kind_code: PackageKindCode | None = None
    description_of_goods: str | None = None
    shipping_marks: str | None = None
    commodity_code: str | None = None
    weight: CargoWeight | None = None
    volume: CargoVolume | None = None
    equipment_references: EquipmentReferences | None = None
    dangerous_goods_list: list[DangerousGoods] | None = None


class DocumentReference(BaseModel):
    type_code: str | None = None
    reference_number: str | None = None


class CustomsInformation(BaseModel):
    fta_declaration: str | None = None
    export_customs_clearance_location: Location | None = None


class ShippingInstruction(BaseModel):
    shipping_instruction_reference: str | None = None
    document_status_code: DocumentStatusCode | None = None
    shipping_instruction_date_time: str | None = None
    carrier_booking_reference: str | None = None
    transport_document_type: TransportDocumentType | None = None
    freight_payment_term_code: FreightPaymentTermCode | None = None
    issue_date: str | None = None
    place_of_issue: Location | None = None
    export_declaration_number: str | None = None
    service_contract_reference: str | None = None
    parties: list[Party] = Field(default_factory=list)
    transport_plans: list[TransportPlan] = Field(default_factory=list)
    equipment_list: list[Equipment] = Field(default_factory=list)
    cargo_items: list[CargoItem] = Field(default_factory=list)
    document_references: list[DocumentReference] = Field(default_factory=list)
    customs_information: CustomsInformation | None = None
    remarks: str | None = None


class ProcessingStatus(str, Enum):
    PENDING = "PENDING"
    OCR_PROCESSING = "OCR_PROCESSING"
    LLM_ANALYZING = "LLM_ANALYZING"
    CLOUD_REVIEW = "CLOUD_REVIEW"
    XML_VALIDATING = "XML_VALIDATING"
    COMPLETED = "COMPLETED"
    DRAFT = "DRAFT"
    ERROR = "ERROR"


class FieldValidation(BaseModel):
    field_path: str
    field_label: str
    value: str | None = None
    is_required: bool = False
    is_missing: bool = False


class AuditFinding(BaseModel):
    field_path: str
    code: str
    message: str
    severity: str
    risk_points: int = Field(ge=0, le=100)


class LocalAuditAssessment(BaseModel):
    risk_score: float = Field(ge=0.0, le=100.0)
    confidence_score: float = Field(ge=0.0, le=100.0)
    requires_cloud_review: bool = False
    findings: list[AuditFinding] = Field(default_factory=list)


class CloudAuditResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float = Field(ge=0.0, le=100.0)
    summary: str = Field(min_length=1, max_length=400)
    suspicious_fields: list[str] = Field(default_factory=list, max_length=10)


class ProcessingResult(BaseModel):
    status: ProcessingStatus
    xml_content: str | None = None
    raw_ocr_text: str | None = None
    raw_llm_json: str | None = None
    structured_data: dict[str, Any] | None = None
    audit_confidence_score: float | None = None
    audit_summary: str | None = None
    cloud_review_used: bool = False
    cloud_review_available: bool = False
    local_risk_score: float | None = None
    local_refinement_used: bool = False
    local_warnings: list[AuditFinding] = Field(default_factory=list)
    suspicious_fields: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)
    missing_fields: list[FieldValidation] = Field(default_factory=list)
    document_language: Literal["auto", "tr", "en"] | None = None
    output_language: Literal["tr", "en"] | None = None
    translation_enabled: bool = True
    message: str | None = None


class SaveInstructionRequest(BaseModel):
    shipping_instruction: ShippingInstruction


class RuntimeSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deepseek_api_key: SecretStr | None = Field(default=None, max_length=512)
    clear_deepseek_api_key: bool = False
    deepseek_review_mode: Literal["off", "manual", "risk", "always"] | None = None
    deepseek_risk_threshold: int | None = Field(default=None, ge=0, le=100)
    local_model_path: str | None = Field(default=None, max_length=2048)
    theme: Literal["system", "light", "dark"] | None = None
    interface_language: Literal["tr", "en"] | None = None
    document_language: Literal["auto", "tr", "en"] | None = None
    output_language: Literal["tr", "en"] | None = None
    translation_enabled: bool | None = None
    nmt_enabled: bool | None = None
    inference_mode: Literal["multi_stage", "single_pass"] | None = None
    layout_engine: Literal["hybrid", "y_ratio", "off"] | None = None
    lora_enabled: bool | None = None
    lora_adapter_path: str | None = Field(default=None, max_length=2048)
    region_upper_ratio: float | None = Field(default=None, ge=0.10, le=0.45)
    region_middle_ratio: float | None = Field(default=None, ge=0.50, le=0.80)
    stage_timeout_seconds: int | None = Field(default=None, ge=60, le=1800)



class BatchItemStatus(str, Enum):
    VALIDATING = "VALIDATING"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    DRAFT = "DRAFT"
    ERROR = "ERROR"
    REJECTED = "REJECTED"


class BatchItemResult(BaseModel):
    item_id: str = ""
    filename: str
    original_filename: str
    status: BatchItemStatus
    session_id: str | None = None
    error_message: str | None = None
    risk_score: float | None = None
    confidence_score: float | None = None


class BatchStatusResponse(BaseModel):
    batch_id: str
    created_at: str
    total_count: int
    completed_count: int = 0
    error_count: int = 0
    percent: float = 0.0
    current_file: str | None = None
    current_status: str | None = None
    items: list[BatchItemResult] = Field(default_factory=list)
    zip_ready: bool = False
    zip_error: str | None = None
    zip_size_bytes: int | None = None
    terminal: bool = False


class BatchUploadResponse(BaseModel):
    batch_id: str
    total_count: int
    rejected_count: int
    rejected_items: list[BatchItemResult] = Field(default_factory=list)
    queued_count: int
    stream_url: str
    status_url: str


class BatchEvent(BaseModel):
    batch_id: str
    completed_count: int
    total_count: int
    percent: float
    current_file: str | None = None
    current_status: str | None = None
    error_count: int = 0
    item: BatchItemResult | None = None
    zip_ready: bool = False
    zip_error: str | None = None


# ---------------------------------------------------------------------------
# Phase 6.1 — ERP Function Calling (Tool Use) modelleri
# ---------------------------------------------------------------------------


class ErpShipmentPayload(BaseModel):
    """ShippingInstruction'dan ERP'ye dönüştürülen gönderi kaydı."""

    shipping_instruction_reference: str | None = None
    carrier_booking_reference: str | None = None
    transport_document_type: str | None = None
    freight_payment_term_code: str | None = None
    issue_date: str | None = None
    place_of_issue_name: str | None = None
    shipper_name: str | None = None
    shipper_address: str | None = None
    shipper_city: str | None = None
    shipper_country: str | None = None
    consignee_name: str | None = None
    consignee_address: str | None = None
    consignee_city: str | None = None
    consignee_country: str | None = None
    notify_party_name: str | None = None
    port_of_loading: str | None = None
    port_of_discharge: str | None = None
    vessel_imo_number: str | None = None
    carrier_voyage_number: str | None = None
    equipment_list: list[dict] = Field(default_factory=list)
    cargo_items: list[dict] = Field(default_factory=list)
    remarks: str | None = None


class ErpCreateShipmentResponse(BaseModel):
    """Mock ERP API yanıtı."""

    success: bool
    tracking_number: str
    message: str
    shipment_payload: ErpShipmentPayload | None = None
