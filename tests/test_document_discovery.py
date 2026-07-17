import json
from pathlib import Path

import fitz
import httpx
import pytest
from pydantic import ValidationError

from app.config import settings
from app.llm.document_relevance import (
    DOCUMENT_RELEVANCE_SYSTEM_PROMPT,
    DocumentRelevanceReview,
    build_document_relevance_payload,
)
from app.search import document_discovery
from app.search.document_discovery import (
    DEFAULT_SEARCH_QUERIES,
    BraveSearchProvider,
    DiscoveryEngine,
    GoogleSearchProvider,
    SearchCandidate,
    assess_local_quality,
    build_manual_google_urls,
    detect_file_type,
    extract_document_features,
)


def _make_pdf(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_textbox(page.rect + (36, 36, -36, -36), text, fontsize=9)
    content = document.tobytes()
    document.close()
    return content


def _shipping_text() -> str:
    block = (
        "BILL OF LADING SHIPPING INSTRUCTION SHIPPER CONSIGNEE NOTIFY PARTY "
        "CARRIER PORT OF LOADING PORT OF DISCHARGE PLACE OF DELIVERY CARGO "
        "GROSS WEIGHT CONTAINER PACKAGES FREIGHT HS CODE BOOKING VESSEL "
    )
    return block * 6


def test_default_queries_target_english_pdf_and_images():
    combined = " ".join(DEFAULT_SEARCH_QUERIES).casefold()
    assert "shipping instruction" in combined
    assert "bill of lading" in combined
    assert "filetype:pdf" in combined
    assert "filetype:png" in combined
    assert "filetype:jpg" in combined


def test_manual_google_urls_preserve_dork_queries():
    urls = build_manual_google_urls(['filetype:pdf "bill of lading"'])
    assert len(urls) == 1
    assert urls[0].startswith("https://www.google.com/search?q=")
    assert "filetype%3Apdf" in urls[0]


def test_brave_provider_returns_normalized_candidates():
    def handler(request):
        assert request.headers["x-subscription-token"] == "brave-key"
        return httpx.Response(200, json={
            "web": {
                "results": [{
                    "title": "B/L Sample",
                    "url": "https://example.com/sample.pdf",
                    "description": "<strong>Bill of Lading</strong> sample",
                }]
            }
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = BraveSearchProvider("brave-key", client)
    candidates = provider.search('filetype:pdf "bill of lading"', 5)
    assert candidates[0].provider == "brave"
    assert candidates[0].snippet == "Bill of Lading sample"


def test_google_provider_uses_english_and_safe_search():
    def handler(request):
        assert request.url.params["safe"] == "active"
        assert request.url.params["lr"] == "lang_en"
        return httpx.Response(200, json={
            "items": [{
                "title": "Shipping Instruction",
                "link": "https://example.com/si.pdf",
                "snippet": "English sample",
                "mime": "application/pdf",
            }]
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = GoogleSearchProvider("google-key", "engine-id", client)
    candidates = provider.search('filetype:pdf "shipping instruction"', 5)
    assert candidates[0].provider == "google"
    assert candidates[0].declared_mime_type == "application/pdf"


def test_file_type_detection_uses_content_magic():
    assert detect_file_type(b"%PDF-1.7\n")[0] == "pdf"
    assert detect_file_type(b"\x89PNG\r\n\x1a\nrest")[0] == "png"
    assert detect_file_type(b"\xff\xd8\xffrest")[0] == "jpg"
    with pytest.raises(ValueError, match="not a valid"):
        detect_file_type(b"<html>not a document</html>")


def test_local_quality_accepts_relevant_english_shipping_document():
    features = extract_document_features(_make_pdf(_shipping_text()), "pdf", False)
    quality = assess_local_quality(features)
    assert quality.relevant is True
    assert quality.english is True
    assert quality.score >= 90
    assert set(quality.matched_groups) == set(document_discovery.KEYWORD_GROUPS)


def test_local_quality_rejects_irrelevant_document():
    text = "Restaurant menu, opening hours, food prices, address and reservations. " * 8
    features = extract_document_features(_make_pdf(text), "pdf", False)
    quality = assess_local_quality(features)
    assert quality.relevant is False
    assert "document" not in quality.matched_groups


def test_deepseek_contract_only_checks_topic_and_english():
    prompt = DOCUMENT_RELEVANCE_SYSTEM_PROMPT.casefold()
    assert "topic and language filter" in prompt
    assert "do not judge quality" in prompt
    assert "never correct" in prompt
    assert "do not return scores" in prompt
    payload = build_document_relevance_payload(
        "Sample", "Bill of Lading", "https://example.com/sample.pdf", _shipping_text()
    )
    assert payload["task"] == "topic_and_english_filter_only_no_quality_scoring"
    assert "local_quality" not in payload
    with pytest.raises(ValidationError):
        DocumentRelevanceReview.model_validate({
            "relevant": True,
            "english": True,
            "document_type": "bill_of_lading",
            "reason": "Relevant.",
            "score": 95,
        })


def test_local_only_discovery_places_document_in_pending_review(tmp_path, monkeypatch):
    pdf_content = _make_pdf(_shipping_text())

    class Provider:
        name = "test"

        def search(self, query, count):
            return [SearchCandidate(
                provider="test",
                query=query,
                title="English Bill of Lading",
                url="https://example.com/sample.pdf",
                snippet="Bill of Lading sample",
            )]

    client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, content=pdf_content)
    ))
    monkeypatch.setattr(document_discovery, "_assert_public_url", lambda url: None)
    engine = DiscoveryEngine(Provider(), tmp_path / "discovered", client)
    result = engine.run(["query"], 1, local_only=True, use_ocr=False)
    assert result["pending_review"] == 1
    assert result["accepted"] == 0
    assert len(list((tmp_path / "discovered" / "pending_review").glob("*.pdf"))) == 1


def test_candidate_collection_distributes_budget_across_queries(tmp_path):
    calls = []

    class Provider:
        name = "test"

        def search(self, query, count):
            calls.append((query, count))
            return [
                SearchCandidate(
                    provider="test",
                    query=query,
                    title=f"Document {index}",
                    url=f"https://example.com/{query}-{index}.pdf",
                )
                for index in range(count)
            ]

    queries = ["shipping", "lading", "cargo"]
    engine = DiscoveryEngine(Provider(), tmp_path / "discovered")
    candidates = engine.collect_candidates(queries, 6)
    assert calls == [("shipping", 2), ("lading", 2), ("cargo", 2)]
    assert len(candidates) == 6


def test_deepseek_relevance_gate_accepts_only_english_relevant_document(tmp_path, monkeypatch):
    pdf_content = _make_pdf(_shipping_text())

    class Provider:
        name = "test"

        def search(self, query, count):
            return [SearchCandidate(
                provider="test",
                query=query,
                title="English Shipping Instruction",
                url="https://example.com/si.pdf",
                snippet="Shipping Instruction sample",
            )]

    client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, content=pdf_content)
    ))
    monkeypatch.setattr(document_discovery, "_assert_public_url", lambda url: None)
    monkeypatch.setattr(settings.deepseek, "api_key", "test-key")
    monkeypatch.setattr(
        document_discovery,
        "run_document_relevance_review",
        lambda payload: (
            DocumentRelevanceReview(
                relevant=True,
                english=True,
                document_type="shipping_instruction",
                reason="The English document is a Shipping Instruction.",
            ),
            json.dumps({"relevant": True}),
        ),
    )
    engine = DiscoveryEngine(Provider(), tmp_path / "discovered", client)
    result = engine.run(["query"], 1, local_only=False, use_ocr=False)
    assert result["accepted"] == 1
    assert result["records"][0]["deepseek_used"] is True
    assert "deepseek_relevance" in result["records"][0]
    assert len(list((tmp_path / "discovered" / "accepted").glob("*.pdf"))) == 1


def test_deepseek_language_gate_rejects_non_english_document(tmp_path, monkeypatch):
    pdf_content = _make_pdf(_shipping_text())

    class Provider:
        name = "test"

        def search(self, query, count):
            return [SearchCandidate(
                provider="test",
                query=query,
                title="Shipping Document",
                url="https://example.com/non-english.pdf",
                snippet="Shipping document sample",
            )]

    client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, content=pdf_content)
    ))
    monkeypatch.setattr(document_discovery, "_assert_public_url", lambda url: None)
    monkeypatch.setattr(settings.deepseek, "api_key", "test-key")
    monkeypatch.setattr(
        document_discovery,
        "run_document_relevance_review",
        lambda payload: (
            DocumentRelevanceReview(
                relevant=True,
                english=False,
                document_type="bill_of_lading",
                reason="The document is relevant but not English.",
            ),
            json.dumps({"relevant": True, "english": False}),
        ),
    )
    engine = DiscoveryEngine(Provider(), tmp_path / "discovered", client)
    result = engine.run(["query"], 1, local_only=False, use_ocr=False)
    assert result["accepted"] == 0
    assert result["rejected"] == 1
    assert result["records"][0]["status"] == "rejected"
    assert result["records"][0]["deepseek_relevance"]["english"] is False
    assert not list((tmp_path / "discovered" / "accepted").glob("*.pdf"))


def test_private_download_target_is_rejected():
    with pytest.raises(ValueError, match="Private or non-global"):
        document_discovery._assert_public_url("http://127.0.0.1/private.pdf")
