import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"
UPLOADS_DIR = BASE_DIR / "uploads"
STATIC_DIR = BASE_DIR / "static"
XSD_DIR = BASE_DIR / "app" / "xml" / "schemas"
DATA_DIR = BASE_DIR / "veriler"

LOGS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


@dataclass
class ModelConfig:
    model_path: str = os.environ.get(
        "QWEN_MODEL_PATH",
        str(BASE_DIR / "models" / "Qwen-2.5-7B-Instruct-INT4"),
    )
    device: str = os.environ.get("OPENVINO_DEVICE", "GPU")
    cache_dir: str = os.environ.get(
        "OPENVINO_CACHE_DIR", str(BASE_DIR / ".openvino_cache")
    )
    kv_cache_precision: str = os.environ.get("OPENVINO_KV_CACHE_PRECISION", "u8")
    max_new_tokens: int = 2048


@dataclass
class DeepSeekConfig:
    api_key: Optional[str] = os.environ.get("DEEPSEEK_API_KEY")
    base_url: str = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model_name: str = "deepseek-chat"
    review_mode: str = os.environ.get("DEEPSEEK_REVIEW_MODE", "risk").lower()
    risk_threshold: int = _env_int("DEEPSEEK_RISK_THRESHOLD", 30)
    max_ocr_excerpt_chars: int = _env_int("DEEPSEEK_MAX_OCR_EXCERPT_CHARS", 2500)

    def __post_init__(self):
        if self.review_mode not in {"off", "manual", "risk", "always"}:
            self.review_mode = "risk"
        self.risk_threshold = min(100, max(0, self.risk_threshold))
        self.max_ocr_excerpt_chars = min(
            10000, max(200, self.max_ocr_excerpt_chars)
        )


@dataclass
class DocumentSearchConfig:
    provider: str = os.environ.get("DOCUMENT_SEARCH_PROVIDER", "auto").lower()
    brave_api_key: Optional[str] = os.environ.get("BRAVE_SEARCH_API_KEY")
    google_api_key: Optional[str] = os.environ.get("GOOGLE_SEARCH_API_KEY")
    google_engine_id: Optional[str] = os.environ.get("GOOGLE_SEARCH_ENGINE_ID")
    output_dir: str = os.environ.get(
        "DOCUMENT_SEARCH_OUTPUT_DIR", str(DATA_DIR / "discovered")
    )
    max_file_mb: int = _env_int("DOCUMENT_SEARCH_MAX_FILE_MB", 20)
    max_results: int = _env_int("DOCUMENT_SEARCH_MAX_RESULTS", 20)
    min_local_score: float = _env_float("DOCUMENT_SEARCH_MIN_LOCAL_SCORE", 60.0)
    max_review_chars: int = _env_int("DOCUMENT_SEARCH_MAX_REVIEW_CHARS", 3500)
    max_ocr_pages: int = _env_int("DOCUMENT_SEARCH_MAX_OCR_PAGES", 2)

    def __post_init__(self):
        if self.provider not in {"auto", "brave", "google"}:
            self.provider = "auto"
        self.max_file_mb = min(100, max(1, self.max_file_mb))
        self.max_results = min(100, max(1, self.max_results))
        self.min_local_score = min(100.0, max(0.0, self.min_local_score))
        self.max_review_chars = min(10000, max(500, self.max_review_chars))
        self.max_ocr_pages = min(10, max(1, self.max_ocr_pages))


@dataclass
class Settings:
    base_dir: Path = BASE_DIR
    logs_dir: Path = LOGS_DIR
    uploads_dir: Path = UPLOADS_DIR
    static_dir: Path = STATIC_DIR
    xsd_dir: Path = XSD_DIR
    model: ModelConfig = field(default_factory=ModelConfig)
    deepseek: DeepSeekConfig = field(default_factory=DeepSeekConfig)
    document_search: DocumentSearchConfig = field(default_factory=DocumentSearchConfig)
    ocr_lang: str = "en"
    line_grouping_y_threshold: float = 15.0
    horizontal_space_factor: float = 0.15
    sse_timeout_seconds: int = max(30, _env_int("SSE_TIMEOUT_SECONDS", 1800))


settings = Settings()
