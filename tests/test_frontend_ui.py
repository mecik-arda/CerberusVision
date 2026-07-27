from pathlib import Path
from html.parser import HTMLParser


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = (PROJECT_ROOT / "static" / "index.html").read_text(encoding="utf-8")
APP_JS = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")
TAILWIND_CONFIG = (PROJECT_ROOT / "tailwind.config.js").read_text(encoding="utf-8")
APP_CSS = (PROJECT_ROOT / "static" / "app.css").read_text(encoding="utf-8")
WORKSPACE_CSS = (PROJECT_ROOT / "static" / "workspace.css").read_text(encoding="utf-8")
THEME_BOOTSTRAP = (PROJECT_ROOT / "static" / "theme-bootstrap.js").read_text(encoding="utf-8")


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
    assert "localStorage.getItem('cerberus-theme')" in THEME_BOOTSTRAP
    assert "localStorage.setItem('cerberus-theme', theme)" in APP_JS
    assert "dark:bg-slate-950" in INDEX_HTML
    assert "prefers-color-scheme: dark" in APP_JS


def test_frontend_assets_are_local_and_precompiled():
    assert "cdn.tailwindcss.com" not in INDEX_HTML
    assert "fonts.googleapis.com" not in INDEX_HTML
    assert '<link rel="stylesheet" href="/static/app.css?v=17">' in INDEX_HTML
    assert '<link rel="stylesheet" href="/static/workspace.css?v=7">' in INDEX_HTML
    assert '<script src="/static/theme-bootstrap.js?v=1"></script>' in INDEX_HTML
    assert '<script src="/static/app.js' in INDEX_HTML
    assert '<script src="/static/app.js?v=27"></script>' in INDEX_HTML
    assert len(APP_CSS) > 10000


def test_multifile_multiformat_queue_is_available():
    assert 'accept=".pdf,.docx,.xml,.png,.jpg,.jpeg" multiple' in INDEX_HTML
    assert 'id="fileQueue"' in INDEX_HTML
    assert "const MAX_BATCH_FILES = 50" in APP_JS
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


def test_inference_controls_persist_before_processing_starts():
    assert "async function persistInferenceSelection(" in APP_JS
    assert "layoutEngine.addEventListener('change'" in APP_JS
    assert "inferenceMode.addEventListener('change'" in APP_JS
    assert "body: JSON.stringify({ [requestField]: selectedValue })" in APP_JS
    assert "runtimeInferenceSavePromise = runtimeInferenceSavePromise.then(" in APP_JS
    assert "runtimeInferenceSavePromise," in APP_JS
    assert "nmtEnabled.checked = inferenceConfig.nmt_enabled ?? true" in APP_JS


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
        "batchDownloadBtn",
        "batchCancelBtn",
        "sendToErpBtn",
        "correctionCancelBtn",
        "correctionSaveBtn",
        "discoveryBtn",
        "benchmarkBtn",
        "diagnosticsBtn",
        "discoveryStartBtn",
        "benchmarkStartBtn",
        "benchmarkDownloadHtml",
        "benchmarkDownloadJson",
        "diagnosticsRunBtn",
    }
    for button_id in interactive_button_ids:
        assert f'id="{button_id}"' in INDEX_HTML
        assert (
            f"{button_id}.addEventListener('click'" in APP_JS
            or f"{button_id}?.addEventListener('click'" in APP_JS
        )

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


def test_v30_frontend_lifecycle_guards_are_present():
    assert "function trimLiveLogOutput()" in APP_JS
    assert APP_JS.count("trimLiveLogOutput();") >= 2
    assert "LIVE_LOG_RECONNECT_MAX_MS" in APP_JS
    assert "liveLogReconnectAttempts += 1" in APP_JS
    assert "runtimeSettingsEditRevision !== submittedRevision" in APP_JS
    assert "runtimeSettingsEditRevision !== requestedRevision" in APP_JS
    assert "serverKey || null" in APP_JS
    assert "sessionStorage.removeItem('cerberus-api-key')" in APP_JS
    assert "erpTransferredSessionId === currentSessionId" in APP_JS
    assert "event.zip_ready" in APP_JS
    assert "event.zip_error" in APP_JS
    assert "setupOcrHighlightListeners" not in APP_JS
    assert "/ocr-boxes" not in APP_JS
    assert 'id="ocrHighlightOverlay"' not in INDEX_HTML


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


def test_review_panel_presents_only_xml_output():
    hidden_review_sections = (
        'data-i18n="form.documentInfo"',
        'data-i18n="form.shippingDetails"',
        'data-i18n="items.title"',
    )
    for section_heading in hidden_review_sections:
        heading_position = INDEX_HTML.index(section_heading)
        section_position = INDEX_HTML.rfind("<div", 0, heading_position)
        section_opening_end = INDEX_HTML.index(">", section_position)
        section_opening = INDEX_HTML[section_position:section_opening_end]
        assert 'class="hidden"' in section_opening
        assert 'aria-hidden="true"' in section_opening
        assert "inert" in section_opening
    assert 'data-i18n="xml.title"' in INDEX_HTML
    assert 'id="xmlOutput" class="min-h-0 flex-1 overflow-auto' in INDEX_HTML
    assert "{ key: 'xml.title', selector: '#xmlOutput' }" in APP_JS
    assert "selector: \"[data-field=" not in APP_JS
    assert 'id="validationSummary"' in INDEX_HTML
    assert "renderValidationSummary" in APP_JS


def test_pdf_viewer_fills_available_desktop_height():
    assert "#pdfViewerPanel {\n    min-height: 0;\n}" in WORKSPACE_CSS
    assert "#pdfViewerPanel {\n        min-height: 32rem;\n    }" in WORKSPACE_CSS
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in WORKSPACE_CSS
    assert "@media (max-width: 760px)" in WORKSPACE_CSS
    assert 'class="upload-panel ' in INDEX_HTML
    assert '/static/workspace.css?v=7' in INDEX_HTML
    assert '/static/app.js?v=27' in INDEX_HTML


def test_pdf_toolbar_supports_zoom_fullscreen_and_pages():
    assert "estimatePdfPageCount" in APP_JS
    assert "pdfCopyBtn" not in INDEX_HTML
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


def test_batch_flow_uses_safe_status_updates_unique_ids_and_real_abort():
    assert "statusMsg.querySelector('span')" not in APP_JS
    assert "showStatusMessage('', true, 'batch.uploading', false)" in APP_JS
    assert "batchItemId: `item-${index + 1}`" in APP_JS
    assert "j.batchItemId === event.item.item_id" in APP_JS
    assert "j.batchItemId === item.item_id" in APP_JS
    assert "activeBatchController = controller" in APP_JS
    assert "apiFetch(`/api/batch/${batchId}/stream`, { signal })" in APP_JS
    assert "if (activeBatchController) activeBatchController.abort()" in APP_JS


def test_upload_limits_and_pdf_scan_are_bounded():
    assert "const MAX_BATCH_FILES = 50" in APP_JS
    assert "const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024" in APP_JS
    assert "file.size > MAX_FILE_SIZE_BYTES" in APP_JS
    assert "const PDF_PAGE_SCAN_BYTES = 2 * 1024 * 1024" in APP_JS
    assert "file.slice(0, headEnd).arrayBuffer()" in APP_JS
    assert "file.arrayBuffer()" not in APP_JS
    assert "en fazla 50 dosya" in INDEX_HTML


def test_xml_only_missing_fields_have_an_accessible_correction_flow():
    assert 'id="correctionDialog"' in INDEX_HTML
    assert 'role="dialog"' in INDEX_HTML
    assert 'aria-modal="true"' in INDEX_HTML
    assert "function openCorrectionDialog()" in APP_JS
    assert "async function saveCorrections()" in APP_JS
    assert "await persistInstruction(false)" in APP_JS
    assert "currentMissingFields.length === 0 && currentValidationErrors.length === 0" in APP_JS
    assert "MANDATORY_EDITABLE_PATHS" not in APP_JS
    assert "correctionContext" in APP_JS
    assert "correctionSaving" in APP_JS
    assert "appMain.inert = true" in APP_JS
    assert "event.key === 'Tab'" in APP_JS


def test_role_paths_preview_types_and_batch_failures_are_safely_handled():
    assert "resolveStructuredPath" in APP_JS
    assert "PARTY_ROLE_ALIASES" in APP_JS
    assert "['CZ', 'SHI']" in APP_JS
    assert 'id="pdfIframe"' in INDEX_HTML
    assert '<iframe id="pdfIframe" class="w-full h-full hidden" title=' in INDEX_HTML
    assert '<iframe id="pdfIframe" class="w-full h-full hidden" sandbox' not in INDEX_HTML
    assert 'id="imagePreview"' in INDEX_HTML
    assert 'id="documentTextPreview"' in INDEX_HTML
    assert "documentTextPreview.textContent = xmlText" in APP_JS
    assert "batch.cancelFailed" in APP_JS
    assert "if (!response.ok) throw new Error" in APP_JS
    assert "job._errorMessage || job._rejectReason" in APP_JS
    assert "function stopLiveLogs()" in APP_JS
    assert 'id="validationSummary" class="review-scroll-panel' in INDEX_HTML
    assert 'id="auditReviewPanel" class="review-scroll-panel' in INDEX_HTML
    assert "review-action-bar" in INDEX_HTML
    assert ".review-scroll-panel" in WORKSPACE_CSS
    assert "max-height: min(11rem, 24vh)" in WORKSPACE_CSS
    assert ".review-action-bar" in WORKSPACE_CSS
    assert "flex-shrink: 0" in WORKSPACE_CSS
    assert "position: sticky" in WORKSPACE_CSS
    assert "bottom: 0" in WORKSPACE_CSS
    assert "height: calc(100dvh - 5rem)" in WORKSPACE_CSS


def test_batch_lifecycle_cannot_be_replaced_or_unlocked_before_confirmed_cancel():
    handle_files_start = APP_JS.index("async function handleFiles")
    handle_files_end = APP_JS.index("\nfunction handleFile", handle_files_start)
    handle_files = APP_JS[handle_files_start:handle_files_end]
    cancel_batch = APP_JS[APP_JS.index("async function cancelBatch"):APP_JS.index("async function clearFileSelection")]
    assert "if (batchUploadPending)" in handle_files
    assert "if (activeBatchId || activeBatchController)" in handle_files
    assert "const cancelled = await cancelBatch()" in handle_files
    assert cancel_batch.index("await apiFetch") < cancel_batch.index("activeUploadRequestId += 1")
    assert "batchCancellationPending" in cancel_batch
    assert "activeBatchRunning || batchUploadPending || batchCancellationPending" in APP_JS


def test_session_scoped_requests_are_aborted_and_ignore_stale_responses():
    assert "function cancelSessionScopedRequests()" in APP_JS
    assert "cloudReviewAbortController" in APP_JS
    assert "erpAbortController" in APP_JS
    assert "instructionPersistAbortController" in APP_JS
    assert "ocrBoxesAbortController" not in APP_JS
    assert "if (currentSessionId !== sessionId) return" in APP_JS
    assert "{ method: 'POST', signal: controller.signal }" in APP_JS
    assert "signal: controller.signal" in APP_JS
    assert "activeUploadRequestId !== requestId" in APP_JS


def test_xml_only_audit_panel_lists_suspicious_field_paths():
    assert 'id="auditSuspiciousFields"' in INDEX_HTML
    assert 'aria-live="polite"' in INDEX_HTML
    assert "function renderSuspiciousFields(suspiciousFields = [])" in APP_JS
    assert "item.textContent = fieldPath" in APP_JS
    assert "auditSuspiciousFields.append(heading, list)" in APP_JS
    assert "'audit.suspiciousHeading': 'Şüpheli alanlar'" in APP_JS
    assert "'audit.suspiciousHeading': 'Suspicious fields'" in APP_JS


def test_all_runtime_settings_finish_before_processing_starts():
    assert "let runtimeSettingsSavePromise = Promise.resolve(true)" in APP_JS
    assert "runtimeSettingsSavePromise = runtimeSettingsSavePromise.then(" in APP_JS
    assert "runtimeSettingsSavePromise," in APP_JS
    assert "if (!inferenceSettingsReady || !runtimeSettingsReady) return" in APP_JS


def test_stream_eof_pdf_thumbnails_attributes_and_export_are_bounded():
    assert "terminalEventReceived" in APP_JS
    assert "error.streamEnded" in APP_JS
    assert "batch.streamEnded" in APP_JS
    assert "async function waitForBatchTerminal(" in APP_JS
    assert "if (status.terminal)" in APP_JS
    assert "activeBatchRunning = false" in APP_JS
    assert "throw new Error(" in APP_JS
    assert "t('batch.invalidEvent')" in APP_JS
    assert "const MAX_RENDERED_THUMBNAILS = 200" in APP_JS
    assert "Math.min(totalPages, MAX_RENDERED_THUMBNAILS)" in APP_JS
    assert ".replaceAll('\"', '&quot;')" in APP_JS
    assert ".replaceAll(\"'\", '&#39;')" in APP_JS
    export_flow = APP_JS[APP_JS.index("async function exportApprovedSessions"):]
    assert "exportAllBtn.disabled = true" in export_flow
    assert "showStatusMessage(t('export.failed'" in export_flow
    assert "setTimeout(() => URL.revokeObjectURL(url), 1000)" in export_flow


def test_upload_and_status_controls_are_keyboard_and_screen_reader_accessible():
    assert 'id="dropZone" role="button" tabindex="0"' in INDEX_HTML
    assert "dropZone.addEventListener('keydown'" in APP_JS
    assert "event.key === 'Enter' || event.key === ' '" in APP_JS
    assert 'id="statusMessageBar" role="status" aria-live="polite" aria-atomic="true"' in INDEX_HTML
