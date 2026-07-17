from __future__ import annotations

import hashlib
import html
import ipaddress
import json
import re
import socket
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Protocol
from urllib.parse import quote_plus, unquote, urljoin, urlparse

import httpx

from app.config import settings
from app.llm.document_relevance import (
    DocumentRelevanceReview,
    build_document_relevance_payload,
    run_document_relevance_review,
)


DEFAULT_SEARCH_QUERIES = (
    'filetype:pdf "shipping instruction" "port of loading" "port of discharge"',
    'filetype:pdf "bill of lading" sample "container no" freight',
    'filetype:pdf "cargo gross weight" "notify party" "HS code"',
    'inurl:sample filetype:pdf "bill of lading"',
    'filetype:png "bill of lading" sample',
    'filetype:jpg "shipping instruction" sample',
)

KEYWORD_GROUPS = {
    "document": ("shipping instruction", "bill of lading", "sea waybill"),
    "parties": ("shipper", "consignee", "notify party", "carrier"),
    "ports": ("port of loading", "port of discharge", "place of delivery"),
    "cargo": ("cargo", "gross weight", "container", "packages"),
    "trade": ("freight", "hs code", "booking", "vessel"),
}

ALLOWED_TYPES = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
}


@dataclass(frozen=True)
class SearchCandidate:
    provider: str
    query: str
    title: str
    url: str
    snippet: str = ""
    declared_mime_type: str = ""


@dataclass(frozen=True)
class DownloadedContent:
    content: bytes
    final_url: str
    file_type: str
    mime_type: str
    sha256: str


@dataclass(frozen=True)
class DocumentFeatures:
    page_count: int
    width: float
    height: float
    text: str
    ocr_used: bool


@dataclass(frozen=True)
class LocalQualityAssessment:
    score: float
    relevant: bool
    english: bool
    english_likelihood: float
    keyword_hits: List[str]
    matched_groups: List[str]
    text_chars: int
    concerns: List[str]


class SearchProvider(Protocol):
    name: str

    def search(self, query: str, count: int) -> List[SearchCandidate]: ...


def _clean_snippet(value: str) -> str:
    cleaned = html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    return re.sub(r"\s+", " ", cleaned).strip()


class BraveSearchProvider:
    name = "brave"

    def __init__(self, api_key: str, client: Optional[httpx.Client] = None):
        if not api_key:
            raise ValueError("BRAVE_SEARCH_API_KEY is required for Brave search.")
        self.api_key = api_key
        self.client = client or httpx.Client(timeout=30)

    def search(self, query: str, count: int) -> List[SearchCandidate]:
        response = self.client.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": self.api_key,
            },
            params={
                "q": query,
                "count": min(20, max(1, count)),
                "country": "us",
                "search_lang": "en",
                "ui_lang": "en-US",
                "safesearch": "strict",
                "spellcheck": "1",
            },
        )
        response.raise_for_status()
        results = response.json().get("web", {}).get("results", [])
        return [
            SearchCandidate(
                provider=self.name,
                query=query,
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=_clean_snippet(item.get("description", "")),
            )
            for item in results
            if item.get("url")
        ]


class GoogleSearchProvider:
    name = "google"

    def __init__(
        self,
        api_key: str,
        engine_id: str,
        client: Optional[httpx.Client] = None,
    ):
        if not api_key or not engine_id:
            raise ValueError(
                "GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID are required."
            )
        self.api_key = api_key
        self.engine_id = engine_id
        self.client = client or httpx.Client(timeout=30)

    def search(self, query: str, count: int) -> List[SearchCandidate]:
        response = self.client.get(
            "https://customsearch.googleapis.com/customsearch/v1",
            params={
                "key": self.api_key,
                "cx": self.engine_id,
                "q": query,
                "num": min(10, max(1, count)),
                "safe": "active",
                "lr": "lang_en",
                "filter": "1",
            },
        )
        response.raise_for_status()
        return [
            SearchCandidate(
                provider=self.name,
                query=query,
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
                declared_mime_type=item.get("mime", ""),
            )
            for item in response.json().get("items", [])
            if item.get("link")
        ]


def resolve_search_provider(
    provider_name: Optional[str] = None,
    client: Optional[httpx.Client] = None,
) -> SearchProvider:
    selected = (provider_name or settings.document_search.provider).lower()
    if selected == "google":
        return GoogleSearchProvider(
            settings.document_search.google_api_key or "",
            settings.document_search.google_engine_id or "",
            client,
        )
    if selected == "brave":
        return BraveSearchProvider(
            settings.document_search.brave_api_key or "", client
        )
    if settings.document_search.google_api_key and settings.document_search.google_engine_id:
        return GoogleSearchProvider(
            settings.document_search.google_api_key,
            settings.document_search.google_engine_id,
            client,
        )
    if settings.document_search.brave_api_key:
        return BraveSearchProvider(settings.document_search.brave_api_key, client)
    raise ValueError(
        "No search provider is configured. Set BRAVE_SEARCH_API_KEY or both "
        "GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID."
    )


def build_manual_google_urls(queries: Iterable[str]) -> List[str]:
    return [f"https://www.google.com/search?q={quote_plus(query)}" for query in queries]


def _assert_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only public HTTP(S) document URLs are allowed.")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are not allowed.")
    default_port = 443 if parsed.scheme == "https" else 80
    addresses = socket.getaddrinfo(
        parsed.hostname, parsed.port or default_port, type=socket.SOCK_STREAM
    )
    if not addresses:
        raise ValueError("The document host could not be resolved.")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError("Private or non-global document addresses are not allowed.")


def detect_file_type(content: bytes) -> tuple[str, str]:
    if content.startswith(b"%PDF-"):
        return "pdf", ALLOWED_TYPES["pdf"]
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", ALLOWED_TYPES["png"]
    if content.startswith(b"\xff\xd8\xff"):
        return "jpg", ALLOWED_TYPES["jpg"]
    raise ValueError("Downloaded content is not a valid PDF, PNG, or JPEG file.")


def download_candidate(
    candidate: SearchCandidate,
    client: httpx.Client,
    max_bytes: int,
) -> DownloadedContent:
    current_url = candidate.url
    headers = {
        "Accept": "application/pdf,image/png,image/jpeg;q=0.9,*/*;q=0.1",
        "User-Agent": "CerberusVisionDocumentFinder/1.0",
    }
    content = b""
    for _ in range(6):
        _assert_public_url(current_url)
        with client.stream("GET", current_url, headers=headers, follow_redirects=False) as response:
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    raise ValueError("Redirect response did not include a location.")
                current_url = urljoin(current_url, location)
                continue
            response.raise_for_status()
            declared_length = response.headers.get("content-length")
            if declared_length and int(declared_length) > max_bytes:
                raise ValueError("Document exceeds the configured download size limit.")
            chunks = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("Document exceeds the configured download size limit.")
                chunks.append(chunk)
            content = b"".join(chunks)
            break
    else:
        raise ValueError("Document URL exceeded the redirect limit.")
    if not content:
        raise ValueError("Downloaded document is empty.")
    file_type, mime_type = detect_file_type(content)
    return DownloadedContent(
        content=content,
        final_url=current_url,
        file_type=file_type,
        mime_type=mime_type,
        sha256=hashlib.sha256(content).hexdigest(),
    )


def _ocr_text(image_bytes: bytes) -> str:
    from app.ocr.spatial_ocr import run_ocr_on_image

    lines = []
    for item in run_ocr_on_image(image_bytes):
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            text_data = item[1]
            if isinstance(text_data, (list, tuple)) and text_data:
                lines.append(str(text_data[0]))
    return "\n".join(lines)


def extract_document_features(
    content: bytes,
    file_type: str,
    use_ocr: bool = True,
) -> DocumentFeatures:
    import fitz

    document = fitz.open(stream=content, filetype=file_type)
    try:
        page_count = document.page_count
        first_page = document[0]
        width = float(first_page.rect.width)
        height = float(first_page.rect.height)
        text = "\n".join(page.get_text("text") for page in document).strip()
        ocr_used = False
        if use_ocr and len(text) < 200:
            ocr_pages = []
            for page_number in range(
                min(page_count, settings.document_search.max_ocr_pages)
            ):
                page = document[page_number]
                pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                ocr_pages.append(_ocr_text(pixmap.tobytes("png")))
            ocr_text = "\n".join(ocr_pages).strip()
            if ocr_text:
                text = ocr_text
                ocr_used = True
        return DocumentFeatures(
            page_count=page_count,
            width=width,
            height=height,
            text=text,
            ocr_used=ocr_used,
        )
    finally:
        document.close()


def assess_local_quality(features: DocumentFeatures) -> LocalQualityAssessment:
    normalized_text = re.sub(r"\s+", " ", features.text).casefold()
    keyword_hits = sorted(
        {
            keyword
            for keywords in KEYWORD_GROUPS.values()
            for keyword in keywords
            if keyword in normalized_text
        }
    )
    matched_groups = sorted(
        group
        for group, keywords in KEYWORD_GROUPS.items()
        if any(keyword in normalized_text for keyword in keywords)
    )
    letters = [character for character in features.text if character.isalpha()]
    latin_letters = [character for character in letters if ord(character) < 768]
    latin_ratio = len(latin_letters) / len(letters) if letters else 0.0
    keyword_ratio = min(1.0, len(keyword_hits) / 8.0)
    english_likelihood = round(min(1.0, latin_ratio * 0.6 + keyword_ratio * 0.4), 4)
    text_score = min(20.0, len(features.text) / 25.0)
    group_score = len(matched_groups) / len(KEYWORD_GROUPS) * 40.0
    geometry_score = 10.0 if features.page_count > 0 and features.width > 0 and features.height > 0 else 0.0
    language_score = english_likelihood * 10.0
    score = round(min(100.0, 20.0 + text_score + group_score + geometry_score + language_score), 2)
    relevant = "document" in matched_groups and len(matched_groups) >= 3
    english = english_likelihood >= 0.72
    concerns = []
    if len(features.text) < 200:
        concerns.append("Insufficient readable text")
    if "document" not in matched_groups:
        concerns.append("Document type keywords are missing")
    if len(matched_groups) < 3:
        concerns.append("Shipping field coverage is too narrow")
    if not english:
        concerns.append("English-language confidence is low")
    return LocalQualityAssessment(
        score=score,
        relevant=relevant,
        english=english,
        english_likelihood=english_likelihood,
        keyword_hits=keyword_hits,
        matched_groups=matched_groups,
        text_chars=len(features.text),
        concerns=concerns,
    )


def _safe_filename(candidate: SearchCandidate, downloaded: DownloadedContent) -> str:
    source_name = unquote(Path(urlparse(downloaded.final_url).path).name)
    stem = Path(source_name).stem or candidate.title or "shipping_document"
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    safe_stem = safe_stem[:70] or "shipping_document"
    return f"{safe_stem}_{downloaded.sha256[:12]}.{downloaded.file_type}"


def _read_known_hashes(manifest_path: Path) -> set[str]:
    if not manifest_path.exists():
        return set()
    hashes = set()
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("sha256") and record.get("status") in {
            "accepted",
            "pending_review",
        }:
            hashes.add(record["sha256"])
    return hashes


def _append_manifest(manifest_path: Path, record: Dict[str, Any]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


class DiscoveryEngine:
    def __init__(
        self,
        provider: SearchProvider,
        output_dir: Path,
        download_client: Optional[httpx.Client] = None,
        min_local_score: Optional[float] = None,
        max_file_bytes: Optional[int] = None,
    ):
        self.provider = provider
        self.output_dir = output_dir
        self.download_client = download_client or httpx.Client(timeout=45)
        self.min_local_score = (
            settings.document_search.min_local_score
            if min_local_score is None
            else min_local_score
        )
        self.max_file_bytes = max_file_bytes or (
            settings.document_search.max_file_mb * 1024 * 1024
        )

    def collect_candidates(
        self,
        queries: Iterable[str],
        max_results: int,
    ) -> List[SearchCandidate]:
        query_list = [query for query in queries if query.strip()]
        if not query_list:
            return []
        candidates = []
        seen_urls = set()
        per_query = max(1, (max_results + len(query_list) - 1) // len(query_list))
        for query in query_list:
            if len(candidates) >= max_results:
                break
            count = min(per_query, max_results - len(candidates))
            for candidate in self.provider.search(query, count):
                normalized_url = candidate.url.split("#", 1)[0]
                if normalized_url in seen_urls:
                    continue
                seen_urls.add(normalized_url)
                candidates.append(candidate)
                if len(candidates) >= max_results:
                    break
        return candidates

    def run(
        self,
        queries: Iterable[str],
        max_results: int,
        local_only: bool = False,
        use_ocr: bool = True,
    ) -> Dict[str, Any]:
        if not local_only and not settings.deepseek.api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY is required for accepted documents. Use "
                "--local-only to place locally screened files in pending_review."
            )
        accepted_dir = self.output_dir / "accepted"
        pending_dir = self.output_dir / "pending_review"
        manifest_path = self.output_dir / "manifest.jsonl"
        accepted_dir.mkdir(parents=True, exist_ok=True)
        pending_dir.mkdir(parents=True, exist_ok=True)
        known_hashes = _read_known_hashes(manifest_path)
        summary = {
            "provider": self.provider.name,
            "searched": 0,
            "downloaded": 0,
            "accepted": 0,
            "pending_review": 0,
            "rejected": 0,
            "duplicates": 0,
            "errors": 0,
            "records": [],
        }
        for candidate in self.collect_candidates(queries, max_results):
            summary["searched"] += 1
            record: Dict[str, Any] = {
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "provider": candidate.provider,
                "query": candidate.query,
                "source_title": candidate.title,
                "source_url": candidate.url,
                "source_snippet": candidate.snippet,
                "deepseek_used": False,
            }
            try:
                downloaded = download_candidate(
                    candidate, self.download_client, self.max_file_bytes
                )
                summary["downloaded"] += 1
                record.update(
                    {
                        "final_url": downloaded.final_url,
                        "sha256": downloaded.sha256,
                        "mime_type": downloaded.mime_type,
                        "size_bytes": len(downloaded.content),
                    }
                )
                if downloaded.sha256 in known_hashes:
                    record["status"] = "duplicate"
                    summary["duplicates"] += 1
                    _append_manifest(manifest_path, record)
                    summary["records"].append(record)
                    continue
                features = extract_document_features(
                    downloaded.content, downloaded.file_type, use_ocr
                )
                local_quality = assess_local_quality(features)
                record["features"] = {
                    "page_count": features.page_count,
                    "width": features.width,
                    "height": features.height,
                    "ocr_used": features.ocr_used,
                }
                record["local_quality"] = asdict(local_quality)
                deepseek_review: Optional[DocumentRelevanceReview] = None
                if local_quality.score >= self.min_local_score and local_quality.relevant and local_quality.english and not local_only:
                    payload = build_document_relevance_payload(
                        candidate.title,
                        candidate.snippet,
                        downloaded.final_url,
                        features.text,
                    )
                    deepseek_review, _ = run_document_relevance_review(payload)
                    record["deepseek_used"] = True
                    record["deepseek_relevance"] = deepseek_review.model_dump(mode="json")
                local_passed = (
                    local_quality.score >= self.min_local_score
                    and local_quality.relevant
                    and local_quality.english
                )
                deepseek_passed = bool(
                    deepseek_review
                    and deepseek_review.relevant
                    and deepseek_review.english
                    and deepseek_review.document_type != "other"
                )
                filename = _safe_filename(candidate, downloaded)
                if local_only and local_passed:
                    destination = pending_dir / filename
                    destination.write_bytes(downloaded.content)
                    record["status"] = "pending_review"
                    record["stored_path"] = str(destination)
                    summary["pending_review"] += 1
                    known_hashes.add(downloaded.sha256)
                elif local_passed and deepseek_passed:
                    destination = accepted_dir / filename
                    destination.write_bytes(downloaded.content)
                    record["status"] = "accepted"
                    record["stored_path"] = str(destination)
                    summary["accepted"] += 1
                    known_hashes.add(downloaded.sha256)
                else:
                    record["status"] = "rejected"
                    summary["rejected"] += 1
                _append_manifest(manifest_path, record)
                summary["records"].append(record)
            except Exception as error:
                record["status"] = "error"
                record["error"] = str(error)
                summary["errors"] += 1
                _append_manifest(manifest_path, record)
                summary["records"].append(record)
        return summary
