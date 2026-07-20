from pathlib import Path
from html.parser import HTMLParser


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = (PROJECT_ROOT / "static" / "index.html").read_text(encoding="utf-8")
APP_JS = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")
TAILWIND_CONFIG = (PROJECT_ROOT / "tailwind.config.js").read_text(encoding="utf-8")
APP_CSS = (PROJECT_ROOT / "static" / "app.css").read_text(encoding="utf-8")


class _ButtonCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.buttons = []

    def handle_starttag(self, tag, attrs):
        if tag == "button":
            self.buttons.append(dict(attrs))


def test_turkish_is_the_default_interface_language():
    assert '<html lang="tr"' in INDEX_HTML
    assert "Belge Yükle" in INDEX_HTML
    assert "Sevkiyat Bilgileri" in INDEX_HTML
    assert "Verileri Onayla" in INDEX_HTML
    assert "let currentLanguage = Object.hasOwn(TRANSLATIONS, savedLanguage) ? savedLanguage : 'tr';" in APP_JS


def test_english_is_available_as_an_optional_persistent_language():
    assert 'data-language="tr"' in INDEX_HTML
    assert 'data-language="en"' in INDEX_HTML
    assert "'upload.title': 'Upload Document'" in APP_JS
    assert "localStorage.setItem('cerberus-language', currentLanguage)" in APP_JS
    assert "document.documentElement.lang = currentLanguage" in APP_JS


def test_dark_theme_is_class_based_and_persistent():
    assert 'darkMode: "class"' in TAILWIND_CONFIG
    assert 'id="themeToggle"' in INDEX_HTML
    assert "localStorage.getItem('cerberus-theme')" in INDEX_HTML
    assert "localStorage.setItem('cerberus-theme', theme)" in APP_JS
    assert "dark:bg-slate-950" in INDEX_HTML
    assert "prefers-color-scheme: dark" in APP_JS


def test_frontend_assets_are_local_and_precompiled():
    assert "cdn.tailwindcss.com" not in INDEX_HTML
    assert "fonts.googleapis.com" not in INDEX_HTML
    assert '<link rel="stylesheet" href="/static/app.css?v=17">' in INDEX_HTML
    assert '<link rel="stylesheet" href="/static/workspace.css?v=2">' in INDEX_HTML
    assert '<script src="/static/app.js?v=17"></script>' in INDEX_HTML
    assert len(APP_CSS) > 10000


def test_multifile_multiformat_queue_is_available():
    assert 'accept=".pdf,.docx,.xml,.png,.jpg,.jpeg" multiple' in INDEX_HTML
    assert 'id="fileQueue"' in INDEX_HTML
    assert "const MAX_BATCH_FILES = 10" in APP_JS
    assert "async function handleFiles(fileList)" in APP_JS
    assert "const pendingJobs = documentQueue.filter" in APP_JS
    assert "for (const job of pendingJobs)" in APP_JS
    assert "await processQueuedFile(job, controller, requestId)" in APP_JS
    assert 'id="startProcessingBtn"' in INDEX_HTML
    assert "startProcessingBtn.addEventListener('click', startSelectedFiles)" in APP_JS
    assert "await previewSelectedFile(files[0])" in APP_JS
    assert "handleFiles(e.dataTransfer.files)" in APP_JS
    assert "handleFiles(e.target.files)" in APP_JS


def test_runtime_messages_and_generated_rows_use_translations():
    assert "t('audit.suspiciousCount'" in APP_JS
    assert "t('form.empty')" in APP_JS
    assert "t('items.none')" in APP_JS
    assert "translateServerMessage(summary)" in APP_JS
    assert "refreshSuspiciousFieldTitles()" in APP_JS
    assert "xmlOutput.removeAttribute('data-i18n')" in APP_JS


def test_every_static_button_has_an_explicit_behavior_contract():
    interactive_button_ids = {
        "globalSearchBtn",
        "logsBtn",
        "logsClearBtn",
        "settingsBtn",
        "settingsRefreshBtn",
        "settingsSaveBtn",
        "notificationsBtn",
        "themeToggle",
        "profileBtn",
        "pdfCopyBtn",
        "pdfZoomBtn",
        "pdfFullscreenBtn",
        "prevPageBtn",
        "nextPageBtn",
        "copyXmlBtn",
        "runCloudReviewBtn",
        "saveDraftBtn",
        "approveDataBtn",
        "startProcessingBtn",
        "clearSelectionBtn",
        "exportAllBtn",
        "webhookTestBtn",
    }
    for button_id in interactive_button_ids:
        assert f'id="{button_id}"' in INDEX_HTML
        assert f"{button_id}.addEventListener('click'" in APP_JS

    collector = _ButtonCollector()
    collector.feed(INDEX_HTML)
    for button in collector.buttons:
        assert button.get("type") == "button"
        if "data-language" not in button:
            assert button.get("id") in interactive_button_ids

    assert "document.querySelectorAll('[data-language]')" in APP_JS
    assert "fileInput.addEventListener('change'" in APP_JS
    assert "globalSearchInput.addEventListener('input'" in APP_JS
    assert "document.querySelectorAll('[data-field]')" in APP_JS


def test_header_search_notifications_and_profile_are_functional():
    assert 'id="globalSearchPanel"' in INDEX_HTML
    assert 'id="notificationsPanel"' in INDEX_HTML
    assert 'id="profilePanel"' in INDEX_HTML
    assert 'id="settingsPanel"' in INDEX_HTML
    assert "renderSearchResults" in APP_JS
    assert "publishNotification" in APP_JS
    assert "updateProfileSummary" in APP_JS
    assert "aria-expanded" in INDEX_HTML


def test_live_log_terminal_is_streamed_and_bounded():
    assert 'id="logsBtn"' in INDEX_HTML
    assert 'id="logsPanel"' in INDEX_HTML
    assert 'id="logsOutput"' in INDEX_HTML
    assert "'/api/logs/stream'" in APP_JS
    assert "'Last-Event-ID'" in APP_JS
    assert "const MAX_RENDERED_LOGS = 500" in APP_JS
    assert "logsOutput.children.length > MAX_RENDERED_LOGS" in APP_JS
    assert "logsAutoScroll.checked" in APP_JS


def test_processing_languages_and_runtime_model_settings_are_functional():
    assert 'id="documentLanguage"' in INDEX_HTML
    assert 'id="outputLanguage"' in INDEX_HTML
    assert '<option value="auto"' in INDEX_HTML
    assert 'id="translationEnabled"' in INDEX_HTML
    assert "formData.append('document_language', documentLanguage.value)" in APP_JS
    assert "formData.append('output_language', outputLanguage.value)" in APP_JS
    assert "formData.append('translation_enabled', String(translationEnabled.checked))" in APP_JS
    assert "cerberus-document-language" in APP_JS
    assert "cerberus-output-language" in APP_JS
    assert 'id="deepSeekApiKeyInput"' in INDEX_HTML
    assert 'id="serverApiKeyInput"' in INDEX_HTML
    assert 'id="detectedModelsList"' in INDEX_HTML
    assert "'/api/runtime-settings'" in APP_JS
    assert "renderDetectedModels" in APP_JS
    assert 'name="local-model"' in APP_JS
    assert "payload.local_model_path" in APP_JS


def test_all_mandatory_approval_fields_are_editable():
    required_paths = {
        "shipping_instruction_reference",
        "shipping_instruction_date_time",
        "carrier_booking_reference",
        "issue_date",
        "place_of_issue.location_name",
        "parties[0].party_name",
        "parties[0].address.street",
        "parties[0].address.city",
        "parties[0].address.country_code",
        "parties[1].party_name",
        "parties[1].address.street",
        "parties[1].address.city",
        "parties[1].address.country_code",
        "transport_plans[0].port_of_loading.location_name",
        "transport_plans[0].port_of_discharge.location_name",
        "equipment_list[0].equipment_reference",
        "equipment_list[0].cargo_gross_weight.weight",
        "cargo_items[0].package_quantity",
        "cargo_items[0].description_of_goods",
        "cargo_items[0].weight.weight_value",
    }
    for path in required_paths:
        assert f'data-field="{path}"' in INDEX_HTML
        assert f"'{path}'" in APP_JS
    assert 'id="validationSummary"' in INDEX_HTML
    assert "renderValidationSummary" in APP_JS


def test_pdf_toolbar_supports_copy_zoom_fullscreen_and_pages():
    assert "estimatePdfPageCount" in APP_JS
    assert "copyPdfLink" in APP_JS
    assert "cyclePdfZoom" in APP_JS
    assert "togglePdfFullscreen" in APP_JS
    assert "goToPdfPage" in APP_JS
    assert "renderPageThumbnails" in APP_JS
    assert "document.addEventListener('fullscreenchange'" in APP_JS


def test_result_actions_are_disabled_until_processing_data_exists():
    assert 'id="copyXmlBtn" type="button" disabled' in INDEX_HTML
    assert 'id="saveDraftBtn" type="button" disabled' in INDEX_HTML
    assert 'id="approveDataBtn" type="button" disabled' in INDEX_HTML
    assert "updateResultActionAvailability" in APP_JS
    assert "copyXmlBtn.disabled = false" in APP_JS
    assert "copyXmlBtn.disabled = !currentXmlContent" in APP_JS


def test_upload_replaces_previous_stream_and_api_auth_can_retry():
    assert "new AbortController()" in APP_JS
    assert "activeUploadController.abort()" in APP_JS
    assert "requestId !== activeUploadRequestId" in APP_JS
    assert "async function apiFetch" in APP_JS
    assert "Authorization" in APP_JS
