import json
from pathlib import Path
from typing import Literal


AdapterTarget = Literal["qwen", "florence", "unknown"]


def adapter_config_path(adapter_path: str | Path) -> Path:
    return Path(adapter_path).expanduser().resolve() / "adapter_config.json"


def adapter_model_path(adapter_path: str | Path) -> Path:
    return Path(adapter_path).expanduser().resolve() / "adapter_model.safetensors"


def read_adapter_base_model(adapter_path: str | Path) -> str:
    try:
        config = json.loads(
            adapter_config_path(adapter_path).read_text(encoding="utf-8")
        )
    except (OSError, TypeError, ValueError):
        return ""
    base_model = config.get("base_model_name_or_path")
    return base_model if isinstance(base_model, str) else ""


def classify_adapter(adapter_path: str | Path) -> AdapterTarget:
    normalized_base_model = read_adapter_base_model(adapter_path).casefold()
    if "qwen" in normalized_base_model:
        return "qwen"
    if "florence" in normalized_base_model:
        return "florence"
    return "unknown"


def enabled_adapter_path(
    enabled: bool,
    adapter_path: str,
    target: AdapterTarget,
) -> Path | None:
    if not enabled or not adapter_path or classify_adapter(adapter_path) != target:
        return None
    model_path = adapter_model_path(adapter_path)
    return model_path if model_path.is_file() else None
