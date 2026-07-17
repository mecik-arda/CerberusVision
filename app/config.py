import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"
UPLOADS_DIR = BASE_DIR / "uploads"
STATIC_DIR = BASE_DIR / "static"
XSD_DIR = BASE_DIR / "app" / "xml" / "schemas"

LOGS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ModelConfig:
    model_path: str = os.environ.get(
        "QWEN_MODEL_PATH",
        str(BASE_DIR / "models" / "Qwen-2.5-14B-Instruct-INT4"),
    )
    device: str = os.environ.get("OPENVINO_DEVICE", "GPU")
    max_new_tokens: int = 2048


@dataclass
class DeepSeekConfig:
    api_key: Optional[str] = os.environ.get("DEEPSEEK_API_KEY")
    base_url: str = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model_name: str = "deepseek-chat"


@dataclass
class Settings:
    base_dir: Path = BASE_DIR
    logs_dir: Path = LOGS_DIR
    uploads_dir: Path = UPLOADS_DIR
    static_dir: Path = STATIC_DIR
    xsd_dir: Path = XSD_DIR
    model: ModelConfig = field(default_factory=ModelConfig)
    deepseek: DeepSeekConfig = field(default_factory=DeepSeekConfig)
    ocr_lang: str = "en"
    line_grouping_y_threshold: float = 15.0
    horizontal_space_factor: float = 0.15


settings = Settings()