import json
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
SETTINGS_FILE = BASE_DIR / ".cerberus-settings.json"

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
    max_new_tokens: int = _env_int("QWEN_MAX_NEW_TOKENS", 2048)
    refinement_enabled: bool = os.environ.get("QWEN_REFINEMENT_ENABLED", "1") == "1"
    refinement_risk_threshold: int = _env_int("QWEN_REFINEMENT_RISK_THRESHOLD", 30)

    def __post_init__(self):
        self.max_new_tokens = min(8192, max(512, self.max_new_tokens))
        self.refinement_risk_threshold = min(
            100, max(0, self.refinement_risk_threshold)
        )


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
class ServerConfig:
    api_key: Optional[str] = os.environ.get("CERBERUS_API_KEY")
    upload_rate_limit: int = _env_int("UPLOAD_RATE_LIMIT", 5)
    upload_rate_window_seconds: int = _env_int("UPLOAD_RATE_WINDOW_SECONDS", 60)
    max_active_pipelines: int = _env_int("MAX_ACTIVE_PIPELINES", 2)
    stream_queue_max_size: int = _env_int("STREAM_QUEUE_MAX_SIZE", 20)
    stream_queue_ttl_seconds: int = _env_int("STREAM_QUEUE_TTL_SECONDS", 300)
    log_retention_days: int = _env_int("LOG_RETENTION_DAYS", 30)

    def __post_init__(self):
        self.upload_rate_limit = min(1000, max(1, self.upload_rate_limit))
        self.upload_rate_window_seconds = min(
            3600, max(1, self.upload_rate_window_seconds)
        )
        self.max_active_pipelines = min(32, max(1, self.max_active_pipelines))
        self.stream_queue_max_size = min(10000, max(10, self.stream_queue_max_size))
        self.stream_queue_ttl_seconds = min(
            86400, max(30, self.stream_queue_ttl_seconds)
        )
        self.log_retention_days = min(3650, max(1, self.log_retention_days))


@dataclass
class InterfacePreferences:
    theme: str = "system"
    interface_language: str = "tr"
    document_language: str = "auto"
    output_language: str = "en"
    translation_enabled: bool = True

    def __post_init__(self):
        if self.theme not in {"system", "light", "dark"}:
            self.theme = "system"
        if self.interface_language not in {"tr", "en"}:
            self.interface_language = "tr"
        if self.document_language not in {"auto", "tr", "en"}:
            self.document_language = "auto"
        if self.output_language not in {"tr", "en"}:
            self.output_language = "en"


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
    server: ServerConfig = field(default_factory=ServerConfig)
    interface: InterfacePreferences = field(default_factory=InterfacePreferences)
    ocr_lang: str = field(default_factory=lambda: os.environ.get("OCR_LANG", "en"))
    line_grouping_y_threshold: float = 15.0
    horizontal_space_factor: float = 0.15
    sse_timeout_seconds: int = max(30, _env_int("SSE_TIMEOUT_SECONDS", 1800))


settings = Settings()


def load_persistent_settings() -> None:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return
    model_path = payload.get("local_model_path")
    if (
        isinstance(model_path, str)
        and Path(model_path).is_dir()
        and (Path(model_path) / "openvino_model.xml").is_file()
    ):
        settings.model.model_path = model_path
    review_mode = payload.get("deepseek_review_mode")
    if review_mode in {"off", "manual", "risk", "always"}:
        settings.deepseek.review_mode = review_mode
    risk_threshold = payload.get("deepseek_risk_threshold")
    if isinstance(risk_threshold, int):
        settings.deepseek.risk_threshold = min(100, max(0, risk_threshold))
    interface_payload = payload.get("interface")
    if isinstance(interface_payload, dict):
        settings.interface = InterfacePreferences(
            theme=interface_payload.get("theme", settings.interface.theme),
            interface_language=interface_payload.get(
                "interface_language", settings.interface.interface_language
            ),
            document_language=interface_payload.get(
                "document_language", settings.interface.document_language
            ),
            output_language=interface_payload.get(
                "output_language", settings.interface.output_language
            ),
            translation_enabled=bool(
                interface_payload.get(
                    "translation_enabled", settings.interface.translation_enabled
                )
            ),
        )


def save_persistent_settings() -> None:
    payload = {
        "local_model_path": settings.model.model_path,
        "deepseek_review_mode": settings.deepseek.review_mode,
        "deepseek_risk_threshold": settings.deepseek.risk_threshold,
        "interface": {
            "theme": settings.interface.theme,
            "interface_language": settings.interface.interface_language,
            "document_language": settings.interface.document_language,
            "output_language": settings.interface.output_language,
            "translation_enabled": settings.interface.translation_enabled,
        },
    }
    temporary_path = SETTINGS_FILE.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(SETTINGS_FILE)


load_persistent_settings()
