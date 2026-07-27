import io
import json
import os
import time as time_module
import zipfile

import pytest
from fastapi import UploadFile

from app import config as config_module
from app.config import settings
from app.models import (
    CloudAuditResponse,
    ProcessingResult,
    ProcessingStatus,
    SaveInstructionRequest,
)
from app.ocr.line_grouper import TextBox
from app.routes import processing
from app.utils import audit_logger
from tests.test_validator import create_complete_si


class ConnectedRequest:
    async def is_disconnected(self):
        return False


@pytest.fixture(autouse=True)
def isolate_qwen_post_processing(monkeypatch):
    monkeypatch.setattr(settings.model, "refinement_enabled", False)
    monkeypatch.setattr(settings, "inference_mode", "single_stage")
    monkeypatch.setattr(
        processing,
        "translate_instruction_content",
        lambda instruction, output_language: (instruction, ""),
    )


def test_copy_upload_enforces_streaming_size_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(processing, "_MAX_UPLOAD_SIZE", 10)
    destination = tmp_path / "too-large.pdf"
    upload = UploadFile(filename="sample.pdf", file=io.BytesIO(b"%PDF-" + b"x" * 10))

    with pytest.raises(processing.UploadTooLargeError):
        processing._copy_upload_to_path(upload, destination)

    assert not destination.exists()


def test_copy_upload_rejects_non_pdf_content(tmp_path):
    destination = tmp_path / "invalid.pdf"
    upload = UploadFile(filename="sample.pdf", file=io.BytesIO(b"not-a-pdf"))

    with pytest.raises(ValueError, match="not a valid PDF"):
        processing._copy_upload_to_path(upload, destination)

    assert not destination.exists()


@pytest.mark.asyncio
async def test_pipeline_runs_short_cloud_review_and_keeps_local_as_source(tmp_path, monkeypatch):
    local = create_complete_si()
    local.equipment_list[0].equipment_reference = "INVALID"
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF-test")
    queue = processing.asyncio.Queue()

    monkeypatch.setattr(settings, "logs_dir", tmp_path / "logs")
    monkeypatch.setattr(settings.deepseek, "api_key", "test-key")
    monkeypatch.setattr(settings.deepseek, "risk_threshold", 30)
    monkeypatch.setattr(
        processing,
        "process_pdf_with_spatial_ocr",
        lambda path, language: (
            "OCR text",
            [[TextBox(text="SI-1", x_min=0, y_min=0, x_max=10, y_max=10)]],
        ),
    )
    monkeypatch.setattr(
        processing,
        "run_inference_with_fallback",
        lambda text, document_language, output_language: (
            local,
            "```json\n{broken-wrapper}\n```",
        ),
    )
    monkeypatch.setattr(settings.deepseek, "review_mode", "risk")
    monkeypatch.setattr(processing, "run_deepseek_review", lambda instruction, assessment, text: (
        CloudAuditResponse(
            score=82,
            summary="Container reference should be reviewed.",
            suspicious_fields=["equipment_list[0].equipment_reference"],
        ),
        '{"score":82}',
        {"task": "audit_only_no_corrections"},
    ))

    await processing.process_pdf_pipeline(pdf_path, "consensus-test", "source.pdf", queue)

    events = []
    while True:
        item = queue.get_nowait()
        if item is None:
            break
        events.append(json.loads(item))

    assert ProcessingStatus.CLOUD_REVIEW.value in [event["status"] for event in events]
    final_event = events[-1]
    assert final_event["status"] == ProcessingStatus.COMPLETED.value
    assert final_event["data"]["audit_confidence_score"] == 82
    assert final_event["data"]["cloud_review_used"] is True
    assert final_event["data"]["audit_summary"] == "Container reference should be reviewed."
    assert "equipment_list[0].equipment_reference" in final_event["data"]["suspicious_fields"]
    assert json.loads(final_event["data"]["raw_llm_json"])["carrier_booking_reference"] == "CBR-12345"
    assert not pdf_path.exists()
    assert (tmp_path / "logs" / "consensus-test" / "ocr_boxes.json").exists()

    processing._processing_store.pop("consensus-test", None)
    processing._session_models.pop("consensus-test", None)


@pytest.mark.asyncio
async def test_pipeline_skips_cloud_review_when_local_risk_is_low(tmp_path, monkeypatch):
    local = create_complete_si()
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF-test")
    queue = processing.asyncio.Queue()

    monkeypatch.setattr(settings, "logs_dir", tmp_path / "logs")
    monkeypatch.setattr(settings.deepseek, "api_key", "test-key")
    monkeypatch.setattr(settings.deepseek, "review_mode", "risk")
    monkeypatch.setattr(
        processing,
        "process_pdf_with_spatial_ocr",
        lambda path, language: ("OCR " * 40, []),
    )
    monkeypatch.setattr(
        processing,
        "run_inference_with_fallback",
        lambda text, document_language, output_language: (local, local.model_dump_json()),
    )
    monkeypatch.setattr(
        processing,
        "run_deepseek_review",
        lambda *args: (_ for _ in ()).throw(AssertionError("DeepSeek should not be called")),
    )

    await processing.process_pdf_pipeline(pdf_path, "low-risk-test", "source.pdf", queue)
    events = []
    while True:
        item = queue.get_nowait()
        if item is None:
            break
        events.append(json.loads(item))

    assert ProcessingStatus.CLOUD_REVIEW.value not in [event["status"] for event in events]
    final_data = events[-1]["data"]
    assert final_data["cloud_review_used"] is False
    assert final_data["local_risk_score"] == 0
    assert final_data["audit_confidence_score"] == 100
    assert "DeepSeek cagrilmadi" in final_data["audit_summary"]
    assert final_data["document_language"] == "en"
    assert final_data["output_language"] == "en"

    processing._processing_store.pop("low-risk-test", None)
    processing._session_models.pop("low-risk-test", None)


def test_processing_language_validation_accepts_only_supported_values():
    assert processing._validate_processing_languages(" TR ", "en") == ("tr", "en")
    with pytest.raises(ValueError, match="Document language"):
        processing._validate_processing_languages("de", "en")
    with pytest.raises(ValueError, match="Output language"):
        processing._validate_processing_languages("tr", "de")


def test_persistent_hybrid_layout_restores_effective_engine_flags(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "inference": {
                    "mode": "multi_stage",
                    "layout_engine": "hybrid",
                    "nmt_enabled": False,
                    "nmt_fallback_to_llm": False,
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(config_module, "SETTINGS_FILE", settings_path)
    monkeypatch.setattr(settings, "layout_engine", "y_ratio")
    monkeypatch.setattr(settings, "region_segmentation_enabled", True)
    monkeypatch.setattr(settings, "florence_enabled", False)
    monkeypatch.setattr(settings, "nmt_enabled", True)
    monkeypatch.setattr(settings, "nmt_fallback_to_llm", True)

    config_module.load_persistent_settings()

    assert settings.layout_engine == "hybrid"
    assert settings.region_segmentation_enabled is True
    assert settings.florence_enabled is True
    assert settings.nmt_enabled is False
    assert settings.nmt_fallback_to_llm is False


def test_processing_runtime_snapshot_does_not_drift_with_global_settings(
    monkeypatch,
):
    monkeypatch.setattr(settings, "inference_mode", "multi_stage")
    monkeypatch.setattr(settings, "layout_engine", "hybrid")
    monkeypatch.setattr(settings, "region_upper_ratio", 0.31)
    monkeypatch.setattr(settings, "region_middle_ratio", 0.71)

    snapshot = processing._capture_processing_runtime_snapshot()
    settings.apply_layout_engine("off")
    settings.region_upper_ratio = 0.4
    settings.region_middle_ratio = 0.8

    assert snapshot.inference_mode == "multi_stage"
    assert snapshot.layout_engine == "hybrid"
    assert snapshot.region_upper_ratio == 0.31
    assert snapshot.region_middle_ratio == 0.71


def test_effective_layout_labels_distinguish_florence_fallback():
    assert processing._effective_layout_label("hybrid") == "Florence-2 VLM"
    assert "bazı sayfalarda Y-Oranı Fallback" in processing._effective_layout_label(
        "hybrid_partial_fallback"
    )
    assert processing._effective_layout_label(
        "y_ratio_fallback"
    ) == "Florence-2 başarısız → Y-Oranı Fallback"


@pytest.mark.asyncio
async def test_runtime_settings_update_never_returns_api_key(monkeypatch):
    monkeypatch.setattr(settings.deepseek, "api_key", None)
    monkeypatch.setattr(settings.deepseek, "review_mode", "risk")
    monkeypatch.setattr(settings.deepseek, "risk_threshold", 30)
    monkeypatch.setattr(processing, "discover_local_models", lambda *args: [])
    monkeypatch.setattr(processing, "save_persistent_settings", lambda: None)

    response = await processing.update_runtime_settings(
        processing.RuntimeSettingsUpdate(
            deepseek_api_key="secret-key",
            deepseek_review_mode="manual",
            deepseek_risk_threshold=45,
        )
    )
    data = json.loads(response.body)

    assert response.status_code == 200
    assert data["deepseek"]["configured"] is True
    assert data["deepseek"]["review_mode"] == "manual"
    assert data["deepseek"]["risk_threshold"] == 45
    assert "api_key" not in data["deepseek"]


@pytest.mark.asyncio
async def test_runtime_settings_hybrid_selection_updates_all_engine_state(
    monkeypatch,
):
    monkeypatch.setattr(settings, "layout_engine", "y_ratio")
    monkeypatch.setattr(settings, "region_segmentation_enabled", True)
    monkeypatch.setattr(settings, "florence_enabled", False)
    monkeypatch.setattr(processing, "save_persistent_settings", lambda: None)
    monkeypatch.setattr(
        processing,
        "_runtime_settings_payload",
        lambda: {
            "inference": {
                "layout_engine": settings.layout_engine,
                "region_segmentation_enabled": (
                    settings.region_segmentation_enabled
                ),
                "florence_enabled": settings.florence_enabled,
            }
        },
    )

    response = await processing.update_runtime_settings(
        processing.RuntimeSettingsUpdate(layout_engine="hybrid")
    )
    data = json.loads(response.body)

    assert response.status_code == 200
    assert settings.layout_engine == "hybrid"
    assert settings.region_segmentation_enabled is True
    assert settings.florence_enabled is True
    assert data["inference"]["florence_enabled"] is True


@pytest.mark.asyncio
async def test_invalid_adapter_does_not_partially_change_layout_engine(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(settings, "layout_engine", "y_ratio")
    monkeypatch.setattr(settings, "region_segmentation_enabled", True)
    monkeypatch.setattr(settings, "florence_enabled", False)
    monkeypatch.setattr(processing, "_discover_lora_adapters", lambda: [])
    monkeypatch.setattr(processing, "save_persistent_settings", lambda: None)

    response = await processing.update_runtime_settings(
        processing.RuntimeSettingsUpdate(
            layout_engine="hybrid",
            lora_enabled=True,
            lora_adapter_path=str(tmp_path / "missing_adapter"),
        )
    )

    assert response.status_code == 422
    assert settings.layout_engine == "y_ratio"
    assert settings.region_segmentation_enabled is True
    assert settings.florence_enabled is False


@pytest.mark.asyncio
async def test_inference_settings_cannot_change_during_active_processing(
    monkeypatch,
):
    session_id = "runtime-settings-active"
    monkeypatch.setattr(settings, "layout_engine", "y_ratio")
    monkeypatch.setattr(processing, "save_persistent_settings", lambda: None)
    processing._active_pipeline_sessions.add(session_id)
    try:
        response = await processing.update_runtime_settings(
            processing.RuntimeSettingsUpdate(layout_engine="hybrid")
        )
    finally:
        processing._active_pipeline_sessions.discard(session_id)

    assert response.status_code == 409
    assert settings.layout_engine == "y_ratio"


@pytest.mark.asyncio
async def test_runtime_settings_selects_one_openvino_model(tmp_path, monkeypatch):
    model_path = tmp_path / "Qwen-7B"
    model_path.mkdir()
    (model_path / "openvino_model.xml").write_text("<xml/>", encoding="utf-8")
    resets = []
    monkeypatch.setattr(processing, "save_persistent_settings", lambda: None)
    monkeypatch.setattr(processing, "reset_llm_pipeline", lambda: resets.append(True))
    monkeypatch.setattr(
        processing,
        "discover_local_models",
        lambda *args: [{
            "name": "Qwen-7B",
            "path": str(model_path.resolve()),
            "source": "Test",
            "format": "OpenVINO",
            "active": False,
            "selectable": True,
        }],
    )

    response = await processing.update_runtime_settings(
        processing.RuntimeSettingsUpdate(local_model_path=str(model_path))
    )

    assert response.status_code == 200
    assert settings.model.model_path == str(model_path.resolve())
    assert resets == [True]


@pytest.mark.asyncio
async def test_runtime_settings_reset_qwen_pipeline_for_lora_change(
    tmp_path,
    monkeypatch,
):
    adapter_path = tmp_path / "qwen_adapter"
    resets = []
    monkeypatch.setattr(settings, "lora_enabled", False)
    monkeypatch.setattr(settings, "lora_adapter_path", "")
    monkeypatch.setattr(processing, "save_persistent_settings", lambda: None)
    monkeypatch.setattr(processing, "reset_llm_pipeline", lambda: resets.append(True))
    monkeypatch.setattr(processing, "_runtime_settings_payload", lambda: {})
    monkeypatch.setattr(
        processing,
        "_discover_lora_adapters",
        lambda: [{"path": str(adapter_path.resolve())}],
    )

    response = await processing.update_runtime_settings(
        processing.RuntimeSettingsUpdate(
            lora_enabled=True,
            lora_adapter_path=str(adapter_path),
        )
    )

    assert response.status_code == 200
    assert settings.lora_enabled is True
    assert settings.lora_adapter_path == str(adapter_path)
    assert resets == [True]


@pytest.mark.asyncio
async def test_runtime_settings_reject_uninstalled_lora_adapter(
    tmp_path,
    monkeypatch,
):
    external_adapter = tmp_path / "external_adapter"
    monkeypatch.setattr(settings, "lora_enabled", False)
    monkeypatch.setattr(settings, "lora_adapter_path", "")
    monkeypatch.setattr(processing, "_discover_lora_adapters", lambda: [])
    monkeypatch.setattr(processing, "save_persistent_settings", lambda: None)

    response = await processing.update_runtime_settings(
        processing.RuntimeSettingsUpdate(
            lora_enabled=True,
            lora_adapter_path=str(external_adapter),
        )
    )

    assert response.status_code == 422
    assert settings.lora_enabled is False
    assert settings.lora_adapter_path == ""


@pytest.mark.asyncio
async def test_draft_and_approval_regenerate_xml(tmp_path, monkeypatch):
    session_id = "save-test"
    instruction = create_complete_si()
    processing._session_models[session_id] = instruction
    monkeypatch.setattr(settings, "logs_dir", tmp_path / "logs")

    edited = instruction.model_copy(deep=True)
    edited.carrier_booking_reference = "EDITED-BOOKING"
    request = SaveInstructionRequest(shipping_instruction=edited)

    draft_response = await processing._save_instruction(session_id, request, approve=False)
    draft_data = json.loads(draft_response.body)
    assert draft_response.status_code == 200
    assert draft_data["status"] == ProcessingStatus.DRAFT.value
    assert "EDITED-BOOKING" in draft_data["xml_content"]
    assert draft_data["structured_data"]["document_status_code"] == "DRF"
    assert (tmp_path / "logs" / session_id / "draft_shipping_instruction.xml").exists()

    approval_response = await processing._save_instruction(session_id, request, approve=True)
    approval_data = json.loads(approval_response.body)
    assert approval_response.status_code == 200
    assert approval_data["status"] == ProcessingStatus.COMPLETED.value
    assert approval_data["structured_data"]["document_status_code"] == "FNL"
    assert (tmp_path / "logs" / session_id / "approved_shipping_instruction.xml").exists()

    processing._processing_store.pop(session_id, None)
    processing._session_models.pop(session_id, None)


@pytest.mark.asyncio
async def test_manual_cloud_review_returns_short_comment_without_changing_data(tmp_path, monkeypatch):
    session_id = "manual-review-test"
    instruction = create_complete_si()
    processing._session_models[session_id] = instruction
    processing._processing_store[session_id] = ProcessingResult(
        status=ProcessingStatus.COMPLETED,
        raw_ocr_text="OCR " * 40,
        structured_data=instruction.model_dump(mode="json"),
    )
    monkeypatch.setattr(settings, "logs_dir", tmp_path / "logs")
    monkeypatch.setattr(settings.deepseek, "api_key", "test-key")
    monkeypatch.setattr(settings.deepseek, "review_mode", "manual")
    calls = {"count": 0}

    def fake_review(*args):
        calls["count"] += 1
        return (
            CloudAuditResponse(score=94, summary="Local extraction appears consistent.", suspicious_fields=[]),
            '{"score":94}',
            {"task": "audit_only_no_corrections"},
        )

    monkeypatch.setattr(processing, "run_deepseek_review", fake_review)

    response = await processing.run_manual_cloud_review(
        session_id,
        ConnectedRequest(),
    )
    data = json.loads(response.body)

    assert response.status_code == 200
    assert data["cloud_review_used"] is True
    assert data["audit_confidence_score"] == 94
    assert data["structured_data"]["carrier_booking_reference"] == "CBR-12345"
    assert (tmp_path / "logs" / session_id / "manual_cloud_review_report.json").exists()
    cached_response = await processing.run_manual_cloud_review(
        session_id,
        ConnectedRequest(),
    )
    assert cached_response.status_code == 200
    assert calls["count"] == 1

    processing._processing_store.pop(session_id, None)
    processing._session_models.pop(session_id, None)


@pytest.mark.asyncio
async def test_save_waits_for_same_session_cloud_review(tmp_path, monkeypatch):
    session_id = "session-lock-test"
    instruction = create_complete_si()
    processing._session_models[session_id] = instruction
    processing._processing_store[session_id] = ProcessingResult(
        status=ProcessingStatus.COMPLETED,
        raw_ocr_text="OCR " * 40,
        structured_data=instruction.model_dump(mode="json"),
    )
    monkeypatch.setattr(settings, "logs_dir", tmp_path / "logs")
    monkeypatch.setattr(settings.deepseek, "api_key", "test-key")
    monkeypatch.setattr(settings.deepseek, "review_mode", "manual")
    review_started = processing.asyncio.Event()
    release_review = processing.asyncio.Event()

    async def fake_execute(*args):
        review_started.set()
        await release_review.wait()
        return {
            "audit_confidence_score": 90,
            "audit_summary": "Reviewed.",
            "cloud_review_used": True,
            "cloud_review_available": True,
            "local_risk_score": 0,
            "local_warnings": [],
            "suspicious_fields": [],
        }, None

    monkeypatch.setattr(processing, "_execute_cloud_review", fake_execute)
    review_task = processing.asyncio.create_task(
        processing.run_manual_cloud_review(
            session_id,
            ConnectedRequest(),
        )
    )
    await review_started.wait()
    edited = instruction.model_copy(deep=True)
    edited.carrier_booking_reference = "LOCKED-SAVE"
    save_task = processing.asyncio.create_task(
        processing._save_instruction(
            session_id,
            SaveInstructionRequest(shipping_instruction=edited),
            approve=False,
        )
    )
    await processing.asyncio.sleep(0)
    assert save_task.done() is False
    release_review.set()
    assert (await review_task).status_code == 200
    save_response = await save_task
    assert save_response.status_code == 200
    assert json.loads(save_response.body)["structured_data"]["carrier_booking_reference"] == "LOCKED-SAVE"
    processing._processing_store.pop(session_id, None)
    processing._session_models.pop(session_id, None)
    processing._session_locks.pop(session_id, None)

class TestVolumeCbmEngine:
    """Hacim/CBM motoru testleri."""

    def test_extracts_single_volume_from_labeled_ocr(self):
        from app.llm.inference import _normalize_cargo_volume
        from app.models import ShippingInstruction

        si = ShippingInstruction()
        ocr = "VOLUME: 28.16 CBM"
        _normalize_cargo_volume(si, ocr)

        assert len(si.cargo_items) == 1
        assert si.cargo_items[0].volume is not None
        assert si.cargo_items[0].volume.volume_value == 28.16
        assert si.cargo_items[0].volume.unit == "CBM"

    def test_extracts_volume_value_before_unit(self):
        from app.llm.inference import _normalize_cargo_volume
        from app.models import ShippingInstruction

        si = ShippingInstruction()
        ocr = "28.16 CBM"
        _normalize_cargo_volume(si, ocr)

        assert len(si.cargo_items) == 1
        assert si.cargo_items[0].volume.volume_value == 28.16

    def test_extracts_volume_with_m3_unit(self):
        from app.llm.inference import _normalize_cargo_volume
        from app.models import ShippingInstruction

        si = ShippingInstruction()
        ocr = "12.5 M3"
        _normalize_cargo_volume(si, ocr)

        assert len(si.cargo_items) == 1
        assert si.cargo_items[0].volume.volume_value == 12.5

    def test_handles_european_number_format(self):
        from app.llm.inference import _normalize_cargo_volume
        from app.models import ShippingInstruction

        si = ShippingInstruction()
        ocr = "28,16 CBM"
        _normalize_cargo_volume(si, ocr)

        assert si.cargo_items[0].volume.volume_value == 28.16

    def test_distributes_multiple_volumes_sequentially(self):
        from app.llm.inference import _normalize_cargo_volume
        from app.models import ShippingInstruction, CargoItem

        si = ShippingInstruction(cargo_items=[CargoItem(), CargoItem()])
        ocr = "ITEM1: 28.16 CBM  ITEM2: 12.5 CBM"
        _normalize_cargo_volume(si, ocr)

        assert si.cargo_items[0].volume.volume_value == 28.16
        assert si.cargo_items[1].volume.volume_value == 12.5

    def test_does_not_overwrite_existing_volume(self):
        from app.llm.inference import _normalize_cargo_volume
        from app.models import ShippingInstruction, CargoItem, CargoVolume

        existing_vol = CargoVolume(volume_value=99.99)
        si = ShippingInstruction(cargo_items=[CargoItem(volume=existing_vol)])
        ocr = "VOLUME: 28.16 CBM"
        _normalize_cargo_volume(si, ocr)

        assert si.cargo_items[0].volume.volume_value == 99.99

    def test_skips_filled_slots_and_fills_next(self):
        from app.llm.inference import _normalize_cargo_volume
        from app.models import ShippingInstruction, CargoItem, CargoVolume

        existing_vol = CargoVolume(volume_value=99.99)
        si = ShippingInstruction(cargo_items=[
            CargoItem(volume=existing_vol),
            CargoItem(),
        ])
        ocr = "28.16 CBM"
        _normalize_cargo_volume(si, ocr)

        assert si.cargo_items[0].volume.volume_value == 99.99
        assert si.cargo_items[1].volume.volume_value == 28.16

    def test_empty_ocr_does_nothing(self):
        from app.llm.inference import _normalize_cargo_volume
        from app.models import ShippingInstruction

        si = ShippingInstruction()
        _normalize_cargo_volume(si, ocr_text="")

        assert len(si.cargo_items) == 0


class TestEquipmentTypeEngine:
    """Konteyner tipi (ISO Equipment Code) motoru testleri."""

    def test_maps_40hc_to_45g1(self):
        from app.llm.inference import _normalize_equipment_types
        from app.models import ShippingInstruction, Equipment

        si = ShippingInstruction(equipment_list=[
            Equipment(equipment_reference="MSKU1875698"),
        ])
        ocr = "CONTAINER: MSKU1875698  TYPE: 40HC"
        _normalize_equipment_types(si, ocr)

        assert si.equipment_list[0].iso_equipment_code == "45G1"

    def test_maps_20gp_to_22g1(self):
        from app.llm.inference import _normalize_equipment_types
        from app.models import ShippingInstruction, Equipment

        si = ShippingInstruction(equipment_list=[
            Equipment(equipment_reference="MSCU1234567"),
        ])
        ocr = "MSCU1234567  20GP"
        _normalize_equipment_types(si, ocr)

        assert si.equipment_list[0].iso_equipment_code == "22G1"

    def test_does_not_overwrite_existing_iso_code(self):
        from app.llm.inference import _normalize_equipment_types
        from app.models import ShippingInstruction, Equipment

        si = ShippingInstruction(equipment_list=[
            Equipment(
                equipment_reference="MSKU1875698",
                iso_equipment_code="42G1",
            ),
        ])
        ocr = "CONTAINER: MSKU1875698  40HC"
        _normalize_equipment_types(si, ocr)

        assert si.equipment_list[0].iso_equipment_code == "42G1"

    def test_handles_multiple_equipment_types(self):
        from app.llm.inference import _normalize_equipment_types
        from app.models import ShippingInstruction, Equipment

        si = ShippingInstruction(equipment_list=[
            Equipment(equipment_reference="MSKU1875698"),
            Equipment(equipment_reference="MSCU1234567"),
        ])
        ocr = "MSKU1875698 40HC  MSCU1234567 20GP"
        _normalize_equipment_types(si, ocr)

        assert si.equipment_list[0].iso_equipment_code == "45G1"
        assert si.equipment_list[1].iso_equipment_code == "22G1"

    def test_empty_ocr_does_nothing(self):
        from app.llm.inference import _normalize_equipment_types
        from app.models import ShippingInstruction, Equipment

        si = ShippingInstruction(equipment_list=[
            Equipment(equipment_reference="MSKU1875698"),
        ])
        _normalize_equipment_types(si, ocr_text="")

        assert si.equipment_list[0].iso_equipment_code is None

    def test_handles_reefer_type(self):
        from app.llm.inference import _normalize_equipment_types
        from app.models import ShippingInstruction, Equipment

        si = ShippingInstruction(equipment_list=[
            Equipment(equipment_reference="MSCU5555555"),
        ])
        ocr = "MSCU5555555 40 REEFER"
        _normalize_equipment_types(si, ocr)

        assert si.equipment_list[0].iso_equipment_code == "42R1"


class TestAddressParserEngine:
    """Adres ve ulke kodu parcAlayici testleri."""

    def test_extracts_country_from_street_end_with_slash(self):
        from app.llm.inference import _normalize_party_addresses
        from app.models import (
            ShippingInstruction, Party, Address, PartyRoleCode,
        )

        si = ShippingInstruction(parties=[
            Party(
                party_role_code=PartyRoleCode.SHIPPER,
                party_name="TEST EXPORT",
                address=Address(
                    street="YESILYURT MAH. 4306 SOK. NO:3 KEPEZ/ANTALYA/TURKEY",
                ),
            ),
        ])
        _normalize_party_addresses(si)

        addr = si.parties[0].address
        assert addr.country_code == "TR"
        assert addr.city == "ANTALYA"
        assert "TURKEY" not in (addr.street or "")

    def test_country_already_set_is_not_modified(self):
        from app.llm.inference import _normalize_party_addresses
        from app.models import (
            ShippingInstruction, Party, Address, PartyRoleCode,
        )

        si = ShippingInstruction(parties=[
            Party(
                party_role_code=PartyRoleCode.SHIPPER,
                party_name="TEST EXPORT",
                address=Address(
                    street="YESILYURT MAH. KEPEZ/ANTALYA/TURKEY",
                    country_code="TR",
                ),
            ),
        ])
        _normalize_party_addresses(si)

        addr = si.parties[0].address
        assert addr.country_code == "TR"
        # country_code zaten gecerli oldugu icin ulke cikarma yapilmamali
        # Sehir cikarma ise city None oldugu icin calisir (beklenen davranis)
        assert addr.city == "ANTALYA"
        assert "TURKEY" in (addr.street or "")

    def test_detects_city_and_sets_city_field(self):
        from app.llm.inference import _normalize_party_addresses
        from app.models import (
            ShippingInstruction, Party, Address, PartyRoleCode,
        )

        si = ShippingInstruction(parties=[
            Party(
                party_role_code=PartyRoleCode.CONSIGNEE,
                party_name="TEST IMPORT",
                address=Address(
                    street="OFF # 15, KARACHI",
                ),
            ),
        ])
        _normalize_party_addresses(si)

        addr = si.parties[0].address
        assert addr.city == "KARACHI"
        assert "KARACHI" not in (addr.street or "")

    def test_extracts_germany_country_code(self):
        from app.llm.inference import _normalize_party_addresses
        from app.models import (
            ShippingInstruction, Party, Address, PartyRoleCode,
        )

        si = ShippingInstruction(parties=[
            Party(
                party_role_code=PartyRoleCode.SHIPPER,
                party_name="GERMAN EXPORT GMBH",
                address=Address(street="HAMBURG/GERMANY"),
            ),
        ])
        _normalize_party_addresses(si)

        assert si.parties[0].address.country_code == "DE"
        assert si.parties[0].address.city == "HAMBURG"

    def test_handles_turkish_chars_in_country_name(self):
        from app.llm.inference import _normalize_party_addresses
        from app.models import (
            ShippingInstruction, Party, Address, PartyRoleCode,
        )

        si = ShippingInstruction(parties=[
            Party(
                party_role_code=PartyRoleCode.SHIPPER,
                party_name="TEST",
                address=Address(street="IZMIR/TÜRKİYE"),
            ),
        ])
        _normalize_party_addresses(si)

        assert si.parties[0].address.country_code == "TR"

    def test_no_address_does_not_crash(self):
        from app.llm.inference import _normalize_party_addresses
        from app.models import (
            ShippingInstruction, Party, PartyRoleCode,
        )

        si = ShippingInstruction(parties=[
            Party(
                party_role_code=PartyRoleCode.SHIPPER,
                party_name="TEST",
                address=None,
            ),
        ])
        _normalize_party_addresses(si)

        assert si.parties[0].address is None



class TestBatchUpload:
    """Batch upload endpoint testleri."""

    def setup_method(self):
        import app.routes.processing as proc

        proc._batch_rate_limiter.clear()

    def test_batch_rejects_more_than_max_files(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        # 51 empty files (MAX_BATCH_FILES = 50)
        files = [("files", (f"test_{i}.pdf", b"%PDF-test", "application/pdf")) for i in range(51)]
        response = client.post("/api/batch/upload", files=files, data={
            "document_language": "en", "output_language": "en",
        })
        assert response.status_code == 422

    def test_batch_accepts_valid_pdf_files(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        files = [("files", (f"doc_{i}.pdf", b"%PDF-test", "application/pdf")) for i in range(3)]
        response = client.post("/api/batch/upload", files=files, data={
            "document_language": "en", "output_language": "en",
        })
        assert response.status_code == 200
        data = response.json()
        assert "batch_id" in data
        assert data["total_count"] == 3
        assert data["rejected_count"] == 0
        assert data["queued_count"] == 3
        assert data["stream_url"].startswith("/api/batch/")

    def test_batch_assigns_unique_ids_and_paths_to_duplicate_filenames(self, monkeypatch):
        import app.routes.processing as proc
        from fastapi.testclient import TestClient
        from app.main import app

        async def keep_batch_pending(batch_id):
            return None

        monkeypatch.setattr(proc, "_process_batch", keep_batch_pending)
        client = TestClient(app)
        files = [
            ("files", ("duplicate.pdf", b"%PDF-first", "application/pdf")),
            ("files", ("duplicate.pdf", b"%PDF-second", "application/pdf")),
        ]
        response = client.post("/api/batch/upload", files=files, data={
            "document_language": "en", "output_language": "en",
        })
        assert response.status_code == 200
        batch_id = response.json()["batch_id"]
        try:
            items = proc._batch_store[batch_id]["items"]
            assert [item["item_id"] for item in items] == ["item-1", "item-2"]
            assert items[0]["filename"] != items[1]["filename"]
            assert items[0]["session_id"] != items[1]["session_id"]
        finally:
            proc._batch_store.pop(batch_id, None)
            proc._batch_tasks.pop(batch_id, None)

    def test_batch_rejects_invalid_extension(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        files = [
            ("files", ("doc_1.pdf", b"%PDF-test", "application/pdf")),
            ("files", ("bad.exe", b"malware", "application/octet-stream")),
        ]
        response = client.post("/api/batch/upload", files=files, data={
            "document_language": "en", "output_language": "en",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["rejected_count"] == 1
        assert data["queued_count"] == 1
        assert data["rejected_items"][0]["original_filename"] == "bad.exe"
        assert data["rejected_items"][0]["status"] == "REJECTED"

    def test_batch_requires_at_least_one_file(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.post("/api/batch/upload", files=[], data={
            "document_language": "en", "output_language": "en",
        })
        assert response.status_code == 422

    def test_batch_status_returns_404_for_unknown_batch(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.get("/api/batch/nonexistent/status")
        assert response.status_code == 404

    def test_batch_download_returns_409_when_zip_not_ready(self, monkeypatch):
        import app.routes.processing as proc
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        batch_id = "batch_test_123"
        proc._batch_store[batch_id] = {
            "batch_id": batch_id,
            "created_at": "2026-01-01T00:00:00",
            "total_count": 1,
            "error_count": 0,
            "items": [],
            "zip_ready": False,
            "_temp_dir": "/tmp/test",
        }
        try:
            response = client.get(f"/api/batch/{batch_id}/download")
            assert response.status_code == 409
        finally:
            proc._batch_store.pop(batch_id, None)

    def test_batch_status_returns_progress_for_active_batch(self, monkeypatch):
        import app.routes.processing as proc
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        batch_id = "batch_test_status"
        proc._batch_store[batch_id] = {
            "batch_id": batch_id,
            "created_at": "2026-01-01T00:00:00",
            "total_count": 5,
            "error_count": 0,
            "items": [
                {"filename": "f1.pdf", "original_filename": "f1.pdf", "status": "COMPLETED", "session_id": "s1", "error_message": None, "risk_score": 5.0, "confidence_score": 95.0},
                {"filename": "f2.pdf", "original_filename": "f2.pdf", "status": "PROCESSING", "session_id": "s2", "error_message": None, "risk_score": None, "confidence_score": None},
                {"filename": "f3.pdf", "original_filename": "f3.pdf", "status": "QUEUED", "session_id": "s3", "error_message": None, "risk_score": None, "confidence_score": None},
                {"filename": "f4.pdf", "original_filename": "f4.pdf", "status": "QUEUED", "session_id": "s4", "error_message": None, "risk_score": None, "confidence_score": None},
                {"filename": "f5.pdf", "original_filename": "f5.pdf", "status": "ERROR", "session_id": "s5", "error_message": "OCR failed", "risk_score": None, "confidence_score": None},
            ],
            "zip_ready": False,
            "_temp_dir": "/tmp/test",
        }
        try:
            response = client.get(f"/api/batch/{batch_id}/status")
            assert response.status_code == 200
            data = response.json()
            assert data["completed_count"] == 2
            assert data["error_count"] == 1
            assert data["current_file"] == "f2.pdf"
            assert data["current_status"] == "PROCESSING"
            assert data["percent"] == 40.0
        finally:
            proc._batch_store.pop(batch_id, None)

    def test_batch_cancel_marks_items_as_error(self, monkeypatch):
        import app.routes.processing as proc
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        batch_id = "batch_test_cancel"
        proc._batch_store[batch_id] = {
            "batch_id": batch_id,
            "created_at": "2026-01-01T00:00:00",
            "total_count": 3,
            "error_count": 0,
            "items": [
                {"filename": "f1.pdf", "original_filename": "f1.pdf", "status": "QUEUED", "session_id": "s1", "error_message": None, "risk_score": None, "confidence_score": None},
                {"filename": "f2.pdf", "original_filename": "f2.pdf", "status": "PROCESSING", "session_id": "s2", "error_message": None, "risk_score": None, "confidence_score": None},
                {"filename": "f3.pdf", "original_filename": "f3.pdf", "status": "COMPLETED", "session_id": "s3", "error_message": None, "risk_score": 5.0, "confidence_score": 95.0},
            ],
            "zip_ready": False,
            "_temp_dir": "/tmp/test",
        }
        try:
            response = client.delete(f"/api/batch/{batch_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "cancelled"
            # QUEUED and PROCESSING should now be ERROR
            items = proc._batch_store[batch_id]["items"]
            assert items[0]["status"] == "ERROR"
            assert items[1]["status"] == "ERROR"
            # COMPLETED should remain
            assert items[2]["status"] == "COMPLETED"
            assert proc._batch_store[batch_id]["zip_ready"] is False
            assert proc._batch_store[batch_id]["zip_error"]
        finally:
            proc._batch_store.pop(batch_id, None)

    def test_batch_cancel_awaits_the_cancelled_task(self):
        import asyncio
        import app.routes.processing as proc
        from fastapi.testclient import TestClient
        from app.main import app

        class CancellableTask:
            def __init__(self):
                self.cancelled = False
                self.awaited = False

            def done(self):
                return False

            def cancel(self):
                self.cancelled = True

            def __await__(self):
                self.awaited = True
                if False:
                    yield None
                raise asyncio.CancelledError

        client = TestClient(app)
        batch_id = "batch_test_await_cancel"
        task = CancellableTask()
        proc._batch_store[batch_id] = {
            "batch_id": batch_id,
            "created_at": "2026-01-01T00:00:00",
            "total_count": 1,
            "error_count": 0,
            "items": [
                {"item_id": "item-1", "filename": "f1.pdf", "original_filename": "f1.pdf", "status": "QUEUED", "session_id": "s1", "error_message": None, "risk_score": None, "confidence_score": None},
            ],
            "zip_ready": False,
            "_temp_dir": "/tmp/test",
        }
        proc._batch_tasks[batch_id] = task
        try:
            response = client.delete(f"/api/batch/{batch_id}")
            assert response.status_code == 200
            assert task.cancelled is True
            assert task.awaited is True
        finally:
            proc._batch_store.pop(batch_id, None)
            proc._batch_tasks.pop(batch_id, None)


def test_browser_security_headers_are_present():
    from fastapi.testclient import TestClient
    from app.main import app

    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"
    policy = response.headers["content-security-policy"]
    assert "script-src 'self'" in policy
    assert "object-src 'none'" in policy
    assert "frame-ancestors 'none'" in policy


@pytest.mark.asyncio
async def test_batch_zip_failure_is_not_reported_as_ready(monkeypatch, tmp_path):
    import app.routes.processing as proc

    batch_id = "batch_test_zip_failure"
    batch_temp_dir = tmp_path / batch_id
    batch_temp_dir.mkdir()
    proc._batch_store[batch_id] = {
        "batch_id": batch_id,
        "created_at": "2026-07-26T13:00:00+00:00",
        "total_count": 0,
        "error_count": 0,
        "items": [],
        "zip_ready": False,
        "document_language": "en",
        "output_language": "en",
        "translation_enabled": False,
        "runtime_snapshot": object(),
        "_temp_dir": str(batch_temp_dir),
    }

    async def fail_zip(_batch_id):
        raise OSError("disk full")

    monkeypatch.setattr(proc, "_build_batch_zip", fail_zip)

    try:
        await proc._process_batch(batch_id)
        batch = proc._batch_store[batch_id]
        assert batch["zip_ready"] is False
        assert batch["zip_error"] == "ZIP paketi olusturulamadi."
        assert "zip_path" not in batch
    finally:
        proc._batch_store.pop(batch_id, None)
        proc._batch_queues.pop(batch_id, None)


def test_batch_archive_name_removes_path_segments_and_unsafe_characters():
    assert processing._safe_archive_stem("../../outside.pdf") == "outside"
    assert processing._safe_archive_stem("..\\..\\nested\\invoice 01?.pdf") == "invoice_01"
    assert processing._safe_archive_stem("...") == "document"


@pytest.mark.asyncio
async def test_terminal_batch_stream_replays_completion_without_waiting():
    batch_id = "batch_terminal_replay"
    processing._batch_store[batch_id] = {
        "batch_id": batch_id,
        "total_count": 1,
        "items": [
            {
                "status": processing.BatchItemStatus.REJECTED.value,
            }
        ],
        "terminal": True,
        "zip_ready": True,
        "zip_error": None,
    }
    try:
        events = [
            event
            async for event in processing._batch_event_generator(batch_id)
        ]
        assert len(events) == 1
        payload = json.loads(events[0].removeprefix("data: ").strip())
        assert payload["status"] == "COMPLETE"
        assert payload["completed_count"] == 1
        assert payload["total_count"] == 1
        assert payload["zip_ready"] is True
    finally:
        processing._batch_store.pop(batch_id, None)
        processing._batch_queues.pop(batch_id, None)


def test_expired_batch_archives_are_removed_and_active_archives_are_kept(
    tmp_path,
    monkeypatch,
):
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    expired_archive = uploads_dir / "batch_expired.zip"
    active_archive = uploads_dir / "batch_active.zip"
    expired_archive.write_bytes(b"expired")
    active_archive.write_bytes(b"active")
    expired_timestamp = time_module.time() - processing._BATCH_ARTIFACT_TTL_SECONDS - 1
    os.utime(expired_archive, (expired_timestamp, expired_timestamp))
    monkeypatch.setattr(settings, "uploads_dir", uploads_dir)

    removed_count = processing._cleanup_expired_batch_archives()

    assert removed_count == 1
    assert not expired_archive.exists()
    assert active_archive.exists()


@pytest.mark.asyncio
async def test_rejected_items_are_included_in_batch_failure_reports(
    tmp_path,
    monkeypatch,
):
    uploads_dir = tmp_path / "uploads"
    logs_dir = tmp_path / "logs"
    uploads_dir.mkdir()
    logs_dir.mkdir()
    monkeypatch.setattr(settings, "uploads_dir", uploads_dir)
    monkeypatch.setattr(settings, "logs_dir", logs_dir)
    batch_id = "batch_rejected_report"
    processing._batch_store[batch_id] = {
        "batch_id": batch_id,
        "created_at": "2026-07-26T00:00:00+00:00",
        "total_count": 1,
        "items": [
            {
                "item_id": "item-1",
                "original_filename": "../../bad.pdf",
                "status": processing.BatchItemStatus.REJECTED.value,
                "session_id": "rejected-session",
                "error_message": "Unsupported file",
                "risk_score": None,
                "confidence_score": None,
            }
        ],
        "document_language": "en",
        "output_language": "en",
    }
    try:
        archive_path = await processing._build_batch_zip(batch_id)
        with zipfile.ZipFile(archive_path) as archive:
            summary = json.loads(archive.read("BATCH_SUMMARY.json"))
            error_report = json.loads(
                archive.read("HATALI_DOSYALAR_RAPORU.json")
            )
        assert summary["errors"] == 1
        assert summary["processing_errors"] == 0
        assert summary["rejected"] == 1
        assert error_report["error_count"] == 1
        assert error_report["errors"][0]["status"] == "REJECTED"
    finally:
        processing._batch_store.pop(batch_id, None)


@pytest.mark.asyncio
async def test_disconnected_instruction_request_does_not_commit_mutation(
    tmp_path,
    monkeypatch,
):
    class DisconnectedRequest:
        async def is_disconnected(self):
            return True

    session_id = "disconnected-save"
    instruction = create_complete_si()
    processing._session_models[session_id] = instruction
    monkeypatch.setattr(settings, "logs_dir", tmp_path / "logs")
    edited = instruction.model_copy(deep=True)
    edited.carrier_booking_reference = "MUST-NOT-COMMIT"
    request = SaveInstructionRequest(shipping_instruction=edited)

    try:
        response = await processing._save_instruction(
            session_id,
            request,
            approve=False,
            http_request=DisconnectedRequest(),
        )
        assert response.status_code == 499
        assert (
            processing._session_models[session_id].carrier_booking_reference
            != "MUST-NOT-COMMIT"
        )
        assert session_id not in processing._processing_store
    finally:
        processing._processing_store.pop(session_id, None)
        processing._session_models.pop(session_id, None)
        processing._session_locks.pop(session_id, None)


@pytest.mark.asyncio
async def test_cloud_review_is_cancelled_when_client_disconnects(
    tmp_path,
    monkeypatch,
):
    class MutableRequest:
        disconnected = False

        async def is_disconnected(self):
            return self.disconnected

    session_id = "cloud-disconnect-test"
    instruction = create_complete_si()
    processing._session_models[session_id] = instruction
    processing._processing_store[session_id] = ProcessingResult(
        status=ProcessingStatus.COMPLETED,
        raw_ocr_text="OCR " * 40,
        structured_data=instruction.model_dump(mode="json"),
    )
    monkeypatch.setattr(settings, "logs_dir", tmp_path / "logs")
    monkeypatch.setattr(settings.deepseek, "api_key", "test-key")
    monkeypatch.setattr(settings.deepseek, "review_mode", "manual")
    review_started = processing.asyncio.Event()
    review_cancelled = processing.asyncio.Event()

    async def wait_for_cancellation(*args):
        review_started.set()
        try:
            await processing.asyncio.Event().wait()
        finally:
            review_cancelled.set()

    monkeypatch.setattr(processing, "_execute_cloud_review", wait_for_cancellation)
    request = MutableRequest()
    review_task = processing.asyncio.create_task(
        processing.run_manual_cloud_review(session_id, request)
    )

    try:
        await review_started.wait()
        request.disconnected = True
        response = await processing.asyncio.wait_for(review_task, timeout=1)
        assert response.status_code == 499
        assert review_cancelled.is_set()
        assert processing._processing_store[session_id].cloud_review_used is False
    finally:
        if not review_task.done():
            review_task.cancel()
        processing._processing_store.pop(session_id, None)
        processing._session_models.pop(session_id, None)
        processing._session_locks.pop(session_id, None)


@pytest.mark.asyncio
async def test_batch_capacity_removes_only_terminal_batches(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(processing, "_MAX_BATCH_STORE", 2)
    active_id = "batch_active_capacity"
    terminal_id = "batch_terminal_capacity"
    active_temp_dir = tmp_path / active_id
    terminal_temp_dir = tmp_path / terminal_id
    active_temp_dir.mkdir()
    terminal_temp_dir.mkdir()
    processing._batch_store[active_id] = {
        "batch_id": active_id,
        "terminal": False,
        "_temp_dir": str(active_temp_dir),
        "zip_path": None,
    }
    processing._batch_store[terminal_id] = {
        "batch_id": terminal_id,
        "terminal": True,
        "_temp_dir": str(terminal_temp_dir),
        "zip_path": None,
    }

    try:
        assert await processing._ensure_batch_capacity() is True
        assert active_id in processing._batch_store
        assert terminal_id not in processing._batch_store
        assert active_temp_dir.exists()
        assert not terminal_temp_dir.exists()
    finally:
        processing._batch_store.pop(active_id, None)
        processing._batch_store.pop(terminal_id, None)


@pytest.mark.asyncio
async def test_batch_capacity_rejects_eviction_when_all_batches_are_active(
    monkeypatch,
):
    monkeypatch.setattr(processing, "_MAX_BATCH_STORE", 1)
    active_id = "batch_only_active"
    processing._batch_store[active_id] = {
        "batch_id": active_id,
        "terminal": False,
        "zip_path": None,
    }
    try:
        assert await processing._ensure_batch_capacity() is False
        assert active_id in processing._batch_store
    finally:
        processing._batch_store.pop(active_id, None)


@pytest.mark.asyncio
async def test_batch_archive_cleanup_is_interval_limited_and_offloaded(
    monkeypatch,
):
    cleanup_calls = []
    monkeypatch.setattr(
        processing,
        "_batch_cleanup_last_run",
        processing.monotonic() - processing._BATCH_CLEANUP_INTERVAL_SECONDS,
    )
    monkeypatch.setattr(
        processing,
        "_cleanup_expired_batch_archives",
        lambda: cleanup_calls.append(True) or 3,
    )

    assert await processing._maybe_cleanup_expired_batch_archives() == 3
    assert await processing._maybe_cleanup_expired_batch_archives() == 0
    assert cleanup_calls == [True]


def test_session_identifier_matches_api_and_retention_patterns():
    session_id = audit_logger.create_session_id()
    assert processing._is_valid_session_id(session_id)
    assert audit_logger.SESSION_ID_PATTERN.fullmatch(session_id)


def test_tokenized_session_directories_are_removed_by_retention(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(settings, "logs_dir", tmp_path)
    monkeypatch.setattr(settings.server, "log_retention_days", 1)
    session_dir = tmp_path / audit_logger.create_session_id()
    session_dir.mkdir()
    expired_timestamp = time_module.time() - 172800
    os.utime(session_dir, (expired_timestamp, expired_timestamp))

    removed = audit_logger.cleanup_expired_sessions(now=time_module.time())

    assert removed == 1
    assert not session_dir.exists()
