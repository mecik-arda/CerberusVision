import sys
import logging

logging.basicConfig(level=logging.INFO)

try:
    from app.config import settings
    # Set mock settings
    settings.lora_enabled = True
    settings.lora_adapter_path = "/home/ardam/projects/CerberusVision/models/florence-lora-adapter"

    from app.ocr.vlm_region import get_florence_pipeline
    model, processor = get_florence_pipeline()
    print("TEST BASARILI! Model ve LoRA yuklendi.")
except Exception as e:
    import traceback
    print(f"TEST BASARISIZ! Hata: {e}")
    traceback.print_exc()
    sys.exit(1)
