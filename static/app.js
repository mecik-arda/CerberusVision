const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const browseLink = document.getElementById('browseLink');
const fileInfo = document.getElementById('fileInfo');
const fileName = document.getElementById('fileName');
const uploadProgressBar = document.getElementById('uploadProgressBar');
const uploadProgressLabel = document.getElementById('uploadProgressLabel');
const pdfPlaceholder = document.getElementById('pdfPlaceholder');
const pdfIframe = document.getElementById('pdfIframe');
const pdfViewerFileName = document.getElementById('pdfViewerFileName');
const thumbnailSidebar = document.getElementById('thumbnailSidebar');
const pdfFooter = document.getElementById('pdfFooter');
const statusBadge = document.getElementById('statusBadge');
const auditScoreBadge = document.getElementById('auditScoreBadge');
const auditReviewPanel = document.getElementById('auditReviewPanel');
const auditReviewSource = document.getElementById('auditReviewSource');
const auditReviewSummary = document.getElementById('auditReviewSummary');
const statusMessageBar = document.getElementById('statusMessageBar');
const statusMessage = document.getElementById('statusMessage');
const processingSpinner = document.getElementById('processingSpinner');
const xmlOutput = document.getElementById('xmlOutput');
const itemsTableBody = document.getElementById('itemsTableBody');
const copyXmlBtn = document.getElementById('copyXmlBtn');
const saveDraftBtn = document.getElementById('saveDraftBtn');
const approveDataBtn = document.getElementById('approveDataBtn');
const runCloudReviewBtn = document.getElementById('runCloudReviewBtn');
const themeToggle = document.getElementById('themeToggle');
const themeLabel = document.getElementById('themeLabel');
const themeMoonIcon = document.getElementById('themeMoonIcon');
const themeSunIcon = document.getElementById('themeSunIcon');
const globalSearchBtn = document.getElementById('globalSearchBtn');
const globalSearchPanel = document.getElementById('globalSearchPanel');
const globalSearchInput = document.getElementById('globalSearchInput');
const globalSearchResults = document.getElementById('globalSearchResults');
const notificationsBtn = document.getElementById('notificationsBtn');
const notificationsPanel = document.getElementById('notificationsPanel');
const notificationDot = document.getElementById('notificationDot');
const notificationMessage = document.getElementById('notificationMessage');
const notificationMeta = document.getElementById('notificationMeta');
const profileBtn = document.getElementById('profileBtn');
const profilePanel = document.getElementById('profilePanel');
const profileLanguage = document.getElementById('profileLanguage');
const profileTheme = document.getElementById('profileTheme');
const profileSession = document.getElementById('profileSession');
const pdfViewerPanel = document.getElementById('pdfViewerPanel');
const pdfCopyBtn = document.getElementById('pdfCopyBtn');
const pdfZoomBtn = document.getElementById('pdfZoomBtn');
const pdfZoomLevel = document.getElementById('pdfZoomLevel');
const pdfFullscreenBtn = document.getElementById('pdfFullscreenBtn');
const prevPageBtn = document.getElementById('prevPageBtn');
const nextPageBtn = document.getElementById('nextPageBtn');
const currentPageLabel = document.getElementById('currentPage');
const totalPagesLabel = document.getElementById('totalPages');

const TRANSLATIONS = {
    tr: {
        'page.title': 'CerberusVision — Belge İşleme',
        'nav.languageSelection': 'Dil seçimi',
        'nav.search': 'Arama',
        'nav.notifications': 'Bildirimler',
        'nav.profileMenu': 'Kullanıcı menüsü',
        'search.title': 'Arayüzde Ara',
        'search.placeholder': 'Alan veya bölüm ara...',
        'search.empty': 'Aramak için yazmaya başlayın.',
        'search.noResults': 'Eşleşen alan veya bölüm bulunamadı.',
        'notifications.title': 'Bildirimler',
        'notifications.empty': 'Henüz yeni bildirim yok.',
        'notifications.latest': 'Son durum',
        'profile.localUser': 'Yerel Kullanıcı',
        'profile.privacy': 'Belge işleme WSL içinde yerel olarak çalışır.',
        'profile.language': 'Dil',
        'profile.theme': 'Tema',
        'profile.session': 'Oturum',
        'profile.turkish': 'Türkçe',
        'profile.english': 'İngilizce',
        'theme.dark': 'Koyu tema',
        'theme.light': 'Açık tema',
        'theme.switchDark': 'Koyu temaya geç',
        'theme.switchLight': 'Açık temaya geç',
        'upload.title': 'Belge Yükle',
        'upload.dropPrompt': "PDF'yi sürükleyip bırakın veya",
        'upload.browse': 'Göz Atın',
        'upload.pdfOnly': 'Yalnızca PDF dosyaları desteklenir',
        'upload.invalidPdf': 'Lütfen geçerli bir PDF dosyası seçin.',
        'upload.uploading': 'Dosya yükleniyor...',
        'pdf.noneLoaded': 'Belge yüklenmedi',
        'pdf.previewPrompt': 'Önizlemek için bir PDF yükleyin',
        'pdf.copyLink': 'PDF bağlantısını kopyala',
        'pdf.linkCopied': 'PDF bağlantısı kopyalandı.',
        'pdf.noDocument': 'Önce bir PDF yükleyin.',
        'pdf.zoom': 'Yakınlaştır',
        'pdf.zoomAt': 'Yakınlaştırma: {level}%',
        'pdf.fullscreen': 'Tam ekran',
        'pdf.exitFullscreen': 'Tam ekrandan çık',
        'pdf.previousPage': 'Önceki sayfa',
        'pdf.nextPage': 'Sonraki sayfa',
        'pdf.page': 'Sayfa',
        'common.copy': 'Kopyala',
        'common.copied': 'Kopyalandı!',
        'status.heading': 'İşlem Durumu:',
        'status.PENDING': 'Bekliyor',
        'status.OCR_PROCESSING': 'OCR İşleniyor',
        'status.LLM_ANALYZING': 'LLM Analizi',
        'status.CLOUD_REVIEW': 'Bulut Denetimi',
        'status.XML_VALIDATING': 'XML Doğrulanıyor',
        'status.COMPLETED': 'Tamamlandı',
        'status.DRAFT': 'İnceleme Gerekli',
        'status.ERROR': 'Hata',
        'status.IDLE': 'Boşta',
        'status.timeout': 'İşlem zaman aşımına uğradı.',
        'status.processFirst': 'Önce bir PDF işleyin.',
        'status.cloudRunning': 'DeepSeek kısa denetimi çalıştırılıyor...',
        'status.ocr': 'OCR işleniyor...',
        'status.llm': 'LLM analizi yapılıyor...',
        'status.xml': 'XML doğrulanıyor...',
        'status.cloud': 'Riskli alanlar DeepSeek ile kısa denetimden geçiriliyor...',
        'status.completed': 'İşlem tamamlandı.',
        'status.draft': 'Taslak oluşturuldu; eksik alanlar mevcut.',
        'status.saved': 'Taslak kaydedildi.',
        'status.approved': 'Veriler onaylandı.',
        'status.cloudCompleted': 'DeepSeek kısa denetimi tamamlandı.',
        'audit.confidenceTitle': 'Belge denetim güveni',
        'audit.deepSeek': 'DeepSeek Denetimi',
        'audit.local': 'Yerel Kontrol',
        'audit.localRisk': 'Yerel risk',
        'audit.suspiciousCount': '{count} şüpheli alan',
        'audit.deepSeekSource': 'DeepSeek kısa incelemesi',
        'audit.localSource': 'Yerel deterministik kontroller',
        'audit.completed': 'Denetim tamamlandı.',
        'audit.suspiciousField': 'Bu alan belge denetim kontrolleri tarafından işaretlendi',
        'form.documentInfo': 'Belge Bilgileri',
        'form.documentId': 'Belge Kimliği',
        'form.date': 'Tarih',
        'form.vendor': 'Satıcı',
        'form.vendorAddress': 'Satıcı Adresi',
        'form.taxId': 'Vergi Kimlik No',
        'form.totalAmount': 'Toplam Tutar',
        'form.required': '(Zorunlu)',
        'form.autoExtracted': 'Otomatik çıkarıldı',
        'form.empty': 'Boş',
        'form.shippingDetails': 'Sevkiyat Bilgileri',
        'form.carrierBookingReference': 'Taşıyıcı Rezervasyon Referansı',
        'form.transportDocumentType': 'Taşıma Belgesi Türü',
        'form.portOfLoading': 'Yükleme Limanı',
        'form.portOfDischarge': 'Boşaltma Limanı',
        'form.equipmentReference': 'Ekipman Referansı',
        'form.cargoGrossWeight': 'Brüt Yük Ağırlığı',
        'items.title': 'Kalemler',
        'items.quantity': 'Adet',
        'items.packageType': 'Paket Türü',
        'items.description': 'Açıklama',
        'items.weight': 'Ağırlık',
        'items.volume': 'Hacim',
        'items.none': 'Henüz kalem çıkarılmadı',
        'xml.title': 'XML Çıktısı',
        'xml.placeholder': 'XML çıktısı işlemden sonra burada görünecek...',
        'actions.cloudReview': 'Bulut Denetimini Çalıştır',
        'actions.saveDraft': 'Taslak Kaydet',
        'actions.approve': 'Verileri Onayla',
        'error.prefix': 'Hata',
        'error.uploadFailed': 'Yükleme başarısız',
        'error.requestFailed': 'İstek başarısız',
        'error.approvalBlocked': 'Zorunlu alanlar veya XSD doğrulama hataları onayı engelliyor.',
    },
    en: {
        'page.title': 'CerberusVision — Document Processing',
        'nav.languageSelection': 'Language selection',
        'nav.search': 'Search',
        'nav.notifications': 'Notifications',
        'nav.profileMenu': 'User menu',
        'search.title': 'Search Interface',
        'search.placeholder': 'Search for a field or section...',
        'search.empty': 'Start typing to search.',
        'search.noResults': 'No matching field or section was found.',
        'notifications.title': 'Notifications',
        'notifications.empty': 'No new notifications yet.',
        'notifications.latest': 'Latest status',
        'profile.localUser': 'Local User',
        'profile.privacy': 'Document processing runs locally inside WSL.',
        'profile.language': 'Language',
        'profile.theme': 'Theme',
        'profile.session': 'Session',
        'profile.turkish': 'Turkish',
        'profile.english': 'English',
        'theme.dark': 'Dark theme',
        'theme.light': 'Light theme',
        'theme.switchDark': 'Switch to dark theme',
        'theme.switchLight': 'Switch to light theme',
        'upload.title': 'Upload Document',
        'upload.dropPrompt': 'Drag & drop a PDF or',
        'upload.browse': 'Browse',
        'upload.pdfOnly': 'Only PDF files are supported',
        'upload.invalidPdf': 'Please select a valid PDF file.',
        'upload.uploading': 'Uploading file...',
        'pdf.noneLoaded': 'No document loaded',
        'pdf.previewPrompt': 'Upload a PDF to preview',
        'pdf.copyLink': 'Copy PDF link',
        'pdf.linkCopied': 'PDF link copied.',
        'pdf.noDocument': 'Upload a PDF first.',
        'pdf.zoom': 'Zoom',
        'pdf.zoomAt': 'Zoom: {level}%',
        'pdf.fullscreen': 'Fullscreen',
        'pdf.exitFullscreen': 'Exit fullscreen',
        'pdf.previousPage': 'Previous page',
        'pdf.nextPage': 'Next page',
        'pdf.page': 'Page',
        'common.copy': 'Copy',
        'common.copied': 'Copied!',
        'status.heading': 'Processing Status:',
        'status.PENDING': 'Pending',
        'status.OCR_PROCESSING': 'OCR Processing',
        'status.LLM_ANALYZING': 'LLM Analyzing',
        'status.CLOUD_REVIEW': 'Cloud Review',
        'status.XML_VALIDATING': 'XML Validating',
        'status.COMPLETED': 'Completed',
        'status.DRAFT': 'Needs Review',
        'status.ERROR': 'Error',
        'status.IDLE': 'Idle',
        'status.timeout': 'Processing timed out.',
        'status.processFirst': 'Process a PDF first.',
        'status.cloudRunning': 'Running the short DeepSeek audit...',
        'status.ocr': 'Processing OCR...',
        'status.llm': 'Running LLM analysis...',
        'status.xml': 'Validating XML...',
        'status.cloud': 'Running a short DeepSeek audit on risky fields...',
        'status.completed': 'Processing completed.',
        'status.draft': 'Draft created; required fields are missing.',
        'status.saved': 'Draft saved.',
        'status.approved': 'Data approved.',
        'status.cloudCompleted': 'Short DeepSeek audit completed.',
        'audit.confidenceTitle': 'Document audit confidence',
        'audit.deepSeek': 'DeepSeek Audit',
        'audit.local': 'Local Check',
        'audit.localRisk': 'Local risk',
        'audit.suspiciousCount': '{count} suspicious field(s)',
        'audit.deepSeekSource': 'DeepSeek short review',
        'audit.localSource': 'Local deterministic checks',
        'audit.completed': 'Audit completed.',
        'audit.suspiciousField': 'This field was flagged by document audit checks',
        'form.documentInfo': 'Document Info',
        'form.documentId': 'Document ID',
        'form.date': 'Date',
        'form.vendor': 'Vendor',
        'form.vendorAddress': 'Vendor Address',
        'form.taxId': 'Tax ID',
        'form.totalAmount': 'Total Amount',
        'form.required': '(Required)',
        'form.autoExtracted': 'Auto-extracted',
        'form.empty': 'Empty',
        'form.shippingDetails': 'Shipping Details',
        'form.carrierBookingReference': 'Carrier Booking Reference',
        'form.transportDocumentType': 'Transport Document Type',
        'form.portOfLoading': 'Port of Loading',
        'form.portOfDischarge': 'Port of Discharge',
        'form.equipmentReference': 'Equipment Reference',
        'form.cargoGrossWeight': 'Cargo Gross Weight',
        'items.title': 'Items',
        'items.quantity': 'Qty',
        'items.packageType': 'Package Type',
        'items.description': 'Description',
        'items.weight': 'Weight',
        'items.volume': 'Volume',
        'items.none': 'No items extracted yet',
        'xml.title': 'XML Output',
        'xml.placeholder': 'XML output will appear here after processing...',
        'actions.cloudReview': 'Run Cloud Review',
        'actions.saveDraft': 'Save Draft',
        'actions.approve': 'Approve Data',
        'error.prefix': 'Error',
        'error.uploadFailed': 'Upload failed',
        'error.requestFailed': 'Request failed',
        'error.approvalBlocked': 'Mandatory fields or XSD validation errors prevent approval.',
    },
};

const savedLanguage = localStorage.getItem('cerberus-language');
let currentLanguage = Object.hasOwn(TRANSLATIONS, savedLanguage) ? savedLanguage : 'tr';

function t(key, values = {}) {
    const template = TRANSLATIONS[currentLanguage][key] || TRANSLATIONS.tr[key] || key;
    return Object.entries(values).reduce(
        (text, [name, value]) => text.replaceAll(`{${name}}`, String(value)),
        template,
    );
}

let uploadedPdfUrl = null;
let currentPdfFile = null;
let currentPage = 1;
let totalPages = 1;
let currentZoom = 100;
const ZOOM_LEVELS = [100, 125, 150, 200];
let currentSessionId = null;
let currentStructuredData = null;
let currentSuspiciousFields = [];
let currentCloudReviewAvailable = false;
let currentStatus = 'IDLE';
let currentStatusMessageKey = null;
let currentStatusMessageFallback = '';
let currentAuditState = null;
let currentItems = null;
let latestNotification = null;

const STATUS_BADGE_MAP = {
    PENDING: 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-200',
    OCR_PROCESSING: 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300',
    LLM_ANALYZING: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300',
    CLOUD_REVIEW: 'bg-violet-100 text-violet-700 dark:bg-violet-950 dark:text-violet-300',
    XML_VALIDATING: 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300',
    COMPLETED: 'bg-teal-100 text-teal-700 dark:bg-teal-950 dark:text-teal-300',
    DRAFT: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-950 dark:text-yellow-300',
    ERROR: 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300',
    IDLE: 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-200',
};

const SEARCH_TARGETS = [
    { key: 'upload.title', selector: '#dropZone' },
    { key: 'form.documentId', selector: "[data-field='shipping_instruction_reference']" },
    { key: 'form.date', selector: "[data-field='issue_date']" },
    { key: 'form.vendor', selector: "[data-field='parties[0].party_name']" },
    { key: 'form.vendorAddress', selector: "[data-field='parties[0].address.street']" },
    { key: 'form.taxId', selector: "[data-field='parties[0].party_id']" },
    { key: 'form.totalAmount', selector: "[data-field='cargo_items[0].weight.weight_value']" },
    { key: 'form.carrierBookingReference', selector: "[data-field='carrier_booking_reference']" },
    { key: 'form.transportDocumentType', selector: "[data-field='transport_document_type']" },
    { key: 'form.portOfLoading', selector: "[data-field='transport_plans[0].port_of_loading.location_name']" },
    { key: 'form.portOfDischarge', selector: "[data-field='transport_plans[0].port_of_discharge.location_name']" },
    { key: 'form.equipmentReference', selector: "[data-field='equipment_list[0].equipment_reference']" },
    { key: 'form.cargoGrossWeight', selector: "[data-field='equipment_list[0].cargo_gross_weight.weight']" },
    { key: 'items.title', selector: '#itemsTableBody' },
    { key: 'xml.title', selector: '#xmlOutput' },
];

function closeTopPanels(except = null) {
    [
        [globalSearchPanel, globalSearchBtn],
        [notificationsPanel, notificationsBtn],
        [profilePanel, profileBtn],
    ].forEach(([panel, button]) => {
        if (panel !== except) {
            panel.classList.add('hidden');
            button.setAttribute('aria-expanded', 'false');
        }
    });
}

function toggleTopPanel(panel, button) {
    const willOpen = panel.classList.contains('hidden');
    closeTopPanels(panel);
    panel.classList.toggle('hidden', !willOpen);
    button.setAttribute('aria-expanded', String(willOpen));
    return willOpen;
}

function renderSearchResults(query = '') {
    const normalizedQuery = query.trim().toLocaleLowerCase(currentLanguage === 'tr' ? 'tr-TR' : 'en-US');
    if (!normalizedQuery) {
        globalSearchResults.innerHTML = `<p class="px-2 py-3 text-sm text-slate-400">${escapeHtml(t('search.empty'))}</p>`;
        return;
    }
    const results = SEARCH_TARGETS.filter(({ key }) => (
        t(key).toLocaleLowerCase(currentLanguage === 'tr' ? 'tr-TR' : 'en-US').includes(normalizedQuery)
    ));
    if (results.length === 0) {
        globalSearchResults.innerHTML = `<p class="px-2 py-3 text-sm text-slate-400">${escapeHtml(t('search.noResults'))}</p>`;
        return;
    }
    globalSearchResults.innerHTML = results.map(({ key, selector }) => `
        <button type="button" data-search-target="${escapeHtml(selector)}" class="block w-full rounded-lg px-3 py-2 text-left text-sm text-slate-700 transition hover:bg-teal-50 hover:text-teal-800 dark:text-slate-200 dark:hover:bg-teal-950/40 dark:hover:text-teal-200">
            ${escapeHtml(t(key))}
        </button>
    `).join('');
}

function focusSearchTarget(selector) {
    const target = document.querySelector(selector);
    if (!target) return;
    closeTopPanels();
    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    if (typeof target.focus === 'function') target.focus({ preventScroll: true });
    target.classList.add('ring-2', 'ring-teal-400');
    setTimeout(() => target.classList.remove('ring-2', 'ring-teal-400'), 1600);
}

function renderNotification() {
    if (!latestNotification) {
        notificationMessage.textContent = t('notifications.empty');
        notificationMeta.textContent = '';
        return;
    }
    notificationMessage.textContent = latestNotification.key
        ? t(latestNotification.key)
        : translateServerMessage(latestNotification.message);
    notificationMeta.textContent = `${t('notifications.latest')} · ${latestNotification.time.toLocaleTimeString(currentLanguage === 'tr' ? 'tr-TR' : 'en-US', { hour: '2-digit', minute: '2-digit' })}`;
}

function publishNotification(message, key = null) {
    latestNotification = { message: message || '', key, time: new Date() };
    renderNotification();
    if (notificationsPanel.classList.contains('hidden')) notificationDot.classList.remove('hidden');
}

function updateProfileSummary() {
    profileLanguage.textContent = t(currentLanguage === 'tr' ? 'profile.turkish' : 'profile.english');
    profileTheme.textContent = t(getCurrentTheme() === 'dark' ? 'theme.dark' : 'theme.light');
    profileSession.textContent = currentSessionId || '--';
    profileSession.title = currentSessionId || '';
}

async function estimatePdfPageCount(file) {
    const source = new TextDecoder('latin1').decode(new Uint8Array(await file.arrayBuffer()));
    const pageObjects = source.match(/\/Type\s*\/Page(?!s)\b/g)?.length || 0;
    let maximumCount = 0;
    for (const match of source.matchAll(/\/Count\s+(\d+)/g)) {
        maximumCount = Math.max(maximumCount, Number(match[1]));
    }
    const detectedCount = Math.max(pageObjects, maximumCount, 1);
    return Number.isFinite(detectedCount) ? Math.min(detectedCount, 10000) : 1;
}

function renderPageThumbnails() {
    thumbnailSidebar.innerHTML = Array.from({ length: totalPages }, (_, index) => {
        const pageNumber = index + 1;
        const selected = pageNumber === currentPage;
        return `<button type="button" data-pdf-page="${pageNumber}" aria-label="${escapeHtml(`${t('pdf.page')} ${pageNumber}`)}" aria-current="${selected ? 'page' : 'false'}" class="flex aspect-[3/4] w-full items-center justify-center rounded-lg border text-xs font-semibold transition ${selected
            ? 'border-teal-500 bg-teal-50 text-teal-700 dark:bg-teal-950/50 dark:text-teal-300'
            : 'border-slate-200 bg-white text-slate-500 hover:border-teal-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300'}">${pageNumber}</button>`;
    }).join('');
}

function updatePdfControls() {
    const hasPdf = Boolean(uploadedPdfUrl);
    currentPage = Math.min(Math.max(currentPage, 1), totalPages);
    currentPageLabel.textContent = String(currentPage);
    totalPagesLabel.textContent = String(totalPages);
    pdfZoomLevel.textContent = `${currentZoom}%`;
    pdfCopyBtn.disabled = !hasPdf;
    pdfZoomBtn.disabled = !hasPdf;
    pdfFullscreenBtn.disabled = !hasPdf;
    prevPageBtn.disabled = !hasPdf || currentPage <= 1;
    nextPageBtn.disabled = !hasPdf || currentPage >= totalPages;
    pdfZoomBtn.title = t('pdf.zoomAt', { level: currentZoom });
    pdfZoomBtn.setAttribute('aria-label', pdfZoomBtn.title);
    const isFullscreen = document.fullscreenElement === pdfViewerPanel;
    pdfFullscreenBtn.title = t(isFullscreen ? 'pdf.exitFullscreen' : 'pdf.fullscreen');
    pdfFullscreenBtn.setAttribute('aria-label', pdfFullscreenBtn.title);
    if (hasPdf) renderPageThumbnails();
}

function refreshPdfViewer() {
    if (!uploadedPdfUrl) return;
    pdfIframe.src = `${uploadedPdfUrl}#page=${currentPage}&zoom=${currentZoom}`;
    updatePdfControls();
}

function goToPdfPage(pageNumber) {
    if (!uploadedPdfUrl) return;
    const nextPage = Math.min(Math.max(Number(pageNumber) || 1, 1), totalPages);
    if (nextPage === currentPage) return;
    currentPage = nextPage;
    refreshPdfViewer();
}

function cyclePdfZoom() {
    if (!uploadedPdfUrl) return;
    const currentIndex = ZOOM_LEVELS.indexOf(currentZoom);
    currentZoom = ZOOM_LEVELS[(currentIndex + 1) % ZOOM_LEVELS.length];
    refreshPdfViewer();
}

async function copyPdfLink() {
    if (!uploadedPdfUrl) {
        showStatusMessage('', true, 'pdf.noDocument');
        return;
    }
    try {
        await navigator.clipboard.writeText(`${uploadedPdfUrl}#page=${currentPage}&zoom=${currentZoom}`);
        showStatusMessage('', true, 'pdf.linkCopied');
    } catch (error) {
        showStatusMessage(`${t('error.prefix')}: ${error.message}`, true);
    }
}

async function togglePdfFullscreen() {
    if (!uploadedPdfUrl) return;
    try {
        if (document.fullscreenElement === pdfViewerPanel) {
            await document.exitFullscreen();
        } else {
            await pdfViewerPanel.requestFullscreen();
        }
    } catch (error) {
        showStatusMessage(`${t('error.prefix')}: ${error.message}`, true);
    }
}

function updateAuditDisplay(score, cloudReviewUsed, localRiskScore, summary, suspiciousFields = []) {
    if (typeof score !== 'number') {
        currentAuditState = null;
        auditScoreBadge.classList.add('hidden');
        auditReviewPanel.classList.add('hidden');
        return;
    }
    currentAuditState = { score, cloudReviewUsed, localRiskScore, summary, suspiciousFields };
    const colorClass = score >= 90
        ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
        : score >= 75
            ? 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
            : 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300';
    auditScoreBadge.className = `px-3 py-1 text-xs font-semibold rounded-full ${colorClass}`;
    auditScoreBadge.textContent = `${cloudReviewUsed ? t('audit.deepSeek') : t('audit.local')}: ${score.toFixed(2)}%`;
    auditScoreBadge.title = `${t('audit.localRisk')}: ${typeof localRiskScore === 'number' ? localRiskScore.toFixed(2) : '--'}%; ${t('audit.suspiciousCount', { count: suspiciousFields.length })}`;
    auditReviewSource.textContent = cloudReviewUsed ? t('audit.deepSeekSource') : t('audit.localSource');
    auditReviewSummary.textContent = translateServerMessage(summary) || t('audit.completed');
    auditReviewPanel.classList.remove('hidden');
}

function updateStatusBadge(status) {
    currentStatus = STATUS_BADGE_MAP[status] ? status : 'PENDING';
    statusBadge.textContent = t(`status.${currentStatus}`);
    statusBadge.className = `px-3 py-1 text-xs font-semibold rounded-full ${STATUS_BADGE_MAP[currentStatus]}`;
}

function showStatusMessage(message, isVisible = true, translationKey = null, notify = true) {
    currentStatusMessageKey = translationKey;
    currentStatusMessageFallback = message || '';
    if (isVisible) {
        statusMessage.textContent = translationKey ? t(translationKey) : translateServerMessage(message);
        statusMessageBar.classList.remove('hidden');
        if (notify) publishNotification(message, translationKey);
    } else {
        statusMessageBar.classList.add('hidden');
    }
}

function translateServerMessage(message) {
    if (!message) return '';
    const normalized = String(message).trim();
    const messageKeys = {
        'OCR Isleniyor...': 'status.ocr',
        'LLM Analizi...': 'status.llm',
        'XML Dogrulaniyor...': 'status.xml',
        'Riskli alanlar DeepSeek ile kisa denetimden geciriliyor...': 'status.cloud',
        'Islem tamamlandi.': 'status.completed',
        'Taslak (Draft) - Eksik alanlar mevcut.': 'status.draft',
        'Taslak kaydedildi.': 'status.saved',
        'Veriler onaylandi.': 'status.approved',
        'DeepSeek kisa denetimi tamamlandi.': 'status.cloudCompleted',
        'Mandatory fields or XSD validation errors prevent approval.': 'error.approvalBlocked',
    };
    if (messageKeys[normalized]) return t(messageKeys[normalized]);

    const summaryKeys = {
        'Yerel kontroller tamamlandi; DeepSeek yapilandirilmadigi icin kullanilmadi.': {
            tr: 'Yerel kontroller tamamlandı; DeepSeek yapılandırılmadığı için kullanılmadı.',
            en: 'Local checks completed; DeepSeek was not configured and was not used.',
        },
        'Yerel kontroller tamamlandi; bulut denetimi kapali.': {
            tr: 'Yerel kontroller tamamlandı; bulut denetimi kapalı.',
            en: 'Local checks completed; cloud review is disabled.',
        },
        'Yerel kontroller tamamlandi; DeepSeek yalnizca manuel istekle kullanilir.': {
            tr: 'Yerel kontroller tamamlandı; DeepSeek yalnızca manuel istekle kullanılır.',
            en: 'Local checks completed; DeepSeek is only used on manual request.',
        },
        'Yerel kontroller yeterli bulundu; DeepSeek cagrilmadi.': {
            tr: 'Yerel kontroller yeterli bulundu; DeepSeek çağrılmadı.',
            en: 'Local checks were sufficient; DeepSeek was not called.',
        },
        'Yerel kontroller tamamlandi; bulut denetimi kullanilamadi.': {
            tr: 'Yerel kontroller tamamlandı; bulut denetimi kullanılamadı.',
            en: 'Local checks completed; cloud review was unavailable.',
        },
        'Veri duzenlendi; DeepSeek yeniden cagrilmadi. Yerel kontroller guncellendi.': {
            tr: 'Veri düzenlendi; DeepSeek yeniden çağrılmadı. Yerel kontroller güncellendi.',
            en: 'Data was edited; DeepSeek was not called again. Local checks were updated.',
        },
    };
    return summaryKeys[normalized]?.[currentLanguage] || normalized;
}

function applyLanguage(language, persist = true) {
    currentLanguage = Object.hasOwn(TRANSLATIONS, language) ? language : 'tr';
    document.documentElement.lang = currentLanguage;
    document.title = t('page.title');
    document.querySelectorAll('[data-i18n]').forEach((element) => {
        element.textContent = t(element.dataset.i18n);
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach((element) => {
        element.placeholder = t(element.dataset.i18nPlaceholder);
    });
    document.querySelectorAll('[data-i18n-title]').forEach((element) => {
        element.title = t(element.dataset.i18nTitle);
    });
    document.querySelectorAll('[data-i18n-aria-label]').forEach((element) => {
        element.setAttribute('aria-label', t(element.dataset.i18nAriaLabel));
    });
    document.querySelectorAll('[data-language]').forEach((button) => {
        const active = button.dataset.language === currentLanguage;
        button.setAttribute('aria-pressed', String(active));
        button.className = `language-option rounded-md px-2.5 py-1.5 text-xs font-semibold transition-colors ${active
            ? 'bg-white text-teal-700 shadow-sm dark:bg-slate-700 dark:text-teal-300'
            : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100'}`;
    });
    if (persist) localStorage.setItem('cerberus-language', currentLanguage);
    updateStatusBadge(currentStatus);
    if (currentStatusMessageKey || currentStatusMessageFallback) {
        showStatusMessage(currentStatusMessageFallback, true, currentStatusMessageKey, false);
    }
    if (currentAuditState) {
        const audit = currentAuditState;
        updateAuditDisplay(audit.score, audit.cloudReviewUsed, audit.localRiskScore, audit.summary, audit.suspiciousFields);
    }
    if (currentItems) populateItemsTable(currentItems);
    refreshSuspiciousFieldTitles();
    renderSearchResults(globalSearchInput.value);
    renderNotification();
    updateThemeControl();
    updateProfileSummary();
    updatePdfControls();
}

function getCurrentTheme() {
    return document.documentElement.classList.contains('dark') ? 'dark' : 'light';
}

function updateThemeControl() {
    const isDark = getCurrentTheme() === 'dark';
    themeMoonIcon.classList.toggle('hidden', isDark);
    themeSunIcon.classList.toggle('hidden', !isDark);
    themeLabel.textContent = t(isDark ? 'theme.light' : 'theme.dark');
    const actionLabel = t(isDark ? 'theme.switchLight' : 'theme.switchDark');
    themeToggle.title = actionLabel;
    themeToggle.setAttribute('aria-label', actionLabel);
    updateProfileSummary();
}

function applyTheme(theme, persist = true) {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    if (persist) localStorage.setItem('cerberus-theme', theme);
    updateThemeControl();
}

function showSpinner(show) {
    if (show) {
        processingSpinner.classList.remove('hidden');
    } else {
        processingSpinner.classList.add('hidden');
    }
}

function setUploadProgress(percent) {
    uploadProgressBar.style.width = `${percent}%`;
    uploadProgressLabel.textContent = `${percent}%`;
    if (percent > 0 && percent < 100) {
        uploadProgressLabel.classList.remove('hidden');
    } else if (percent === 100) {
        uploadProgressLabel.classList.remove('hidden');
    } else {
        uploadProgressLabel.classList.add('hidden');
    }
}

function updateResultActionAvailability() {
    const hasStructuredData = Boolean(currentStructuredData);
    saveDraftBtn.disabled = !hasStructuredData;
    approveDataBtn.disabled = !hasStructuredData;
    copyXmlBtn.disabled = xmlOutput.hasAttribute('data-i18n');
}

function resetDocumentResults() {
    document.querySelectorAll('[data-field]').forEach((input) => {
        input.value = '';
        input.dataset.i18nPlaceholder = 'form.autoExtracted';
        input.placeholder = t('form.autoExtracted');
    });
    resetFieldValidationStyles();
    highlightMissingFields([
        { field_path: 'parties[0].address.street' },
        { field_path: 'parties[0].party_id' },
        { field_path: 'cargo_items[0].weight.weight_value' },
    ]);
    populateItemsTable([]);
    xmlOutput.dataset.i18n = 'xml.placeholder';
    xmlOutput.textContent = t('xml.placeholder');
    updateResultActionAvailability();
}

function handleFile(file) {
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
        alert(t('upload.invalidPdf'));
        return;
    }

    pdfViewerFileName.removeAttribute('data-i18n');
    fileName.textContent = file.name;
    currentPdfFile = file;
    currentPage = 1;
    totalPages = 1;
    currentZoom = 100;
    currentSessionId = null;
    currentStructuredData = null;
    currentSuspiciousFields = [];
    currentCloudReviewAvailable = false;
    resetDocumentResults();
    updateProfileSummary();
    updateAuditDisplay(null);
    clearSuspiciousHighlights();
    runCloudReviewBtn.disabled = true;
    fileInfo.classList.remove('hidden');
    pdfViewerFileName.textContent = file.name;

    if (uploadedPdfUrl) {
        URL.revokeObjectURL(uploadedPdfUrl);
    }

    uploadedPdfUrl = URL.createObjectURL(file);
    pdfPlaceholder.classList.add('hidden');
    refreshPdfViewer();
    pdfIframe.classList.remove('hidden');
    thumbnailSidebar.classList.remove('hidden');
    pdfFooter.classList.remove('hidden');
    pdfFooter.classList.add('flex');

    setUploadProgress(100);

    estimatePdfPageCount(file).then((count) => {
        if (currentPdfFile !== file) return;
        totalPages = count;
        updatePdfControls();
    }).catch(() => {
        totalPages = 1;
        updatePdfControls();
    });

    uploadAndStream(file);
}

async function uploadAndStream(file) {
    updateStatusBadge('PENDING');
    showStatusMessage('', true, 'upload.uploading');
    showSpinner(true);

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/upload-and-stream', {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error(`${t('error.uploadFailed')}: ${response.statusText}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const jsonStr = line.slice(6).trim();
                    if (jsonStr) {
                        try {
                            handleSseEvent(JSON.parse(jsonStr));
                        } catch (e) {
                            console.error('SSE parse error:', e, jsonStr);
                        }
                    }
                }
            }
        }
    } catch (error) {
        updateStatusBadge('ERROR');
        showStatusMessage(`${t('error.prefix')}: ${error.message}`, true);
        showSpinner(false);
    }
}

function handleSseEvent(event) {
    if (event.session_id) {
        currentSessionId = event.session_id;
        updateProfileSummary();
    }
    if (event.status === 'COMPLETE') {
        showSpinner(false);
        return;
    }

    if (event.status === 'TIMEOUT') {
        showSpinner(false);
        updateStatusBadge('ERROR');
        showStatusMessage('', true, 'status.timeout');
        return;
    }

    if (event.status) {
        updateStatusBadge(event.status);
    }

    if (event.message) {
        showStatusMessage(event.message, true);
    }

    if (event.status === 'OCR_PROCESSING') {
        setUploadProgress(30);
    } else if (event.status === 'LLM_ANALYZING') {
        setUploadProgress(60);
    } else if (event.status === 'XML_VALIDATING') {
        setUploadProgress(80);
    } else if (event.status === 'COMPLETED' || event.status === 'DRAFT') {
        setUploadProgress(100);
        showSpinner(false);

        if (event.data) {
            if (event.data.xml_content) {
                xmlOutput.removeAttribute('data-i18n');
                xmlOutput.textContent = event.data.xml_content;
                copyXmlBtn.disabled = false;
            }
            if (event.data.missing_fields) {
                highlightMissingFields(event.data.missing_fields);
            }
            if (event.data.structured_data) {
                currentStructuredData = event.data.structured_data;
                populateFormFields(currentStructuredData);
                populateItemsTable(currentStructuredData.cargo_items);
                updateResultActionAvailability();
            } else if (event.data.raw_llm_json) {
                try {
                    const parsed = JSON.parse(event.data.raw_llm_json);
                    currentStructuredData = parsed;
                    populateFormFields(parsed);
                    populateItemsTable(parsed.cargo_items);
                    updateResultActionAvailability();
                } catch (e) {
                    console.error('JSON parse error:', e);
                }
            }
            currentSuspiciousFields = event.data.suspicious_fields || [];
            updateAuditDisplay(
                event.data.audit_confidence_score,
                event.data.cloud_review_used,
                event.data.local_risk_score,
                event.data.audit_summary,
                currentSuspiciousFields,
            );
            highlightSuspiciousFields(currentSuspiciousFields);
            currentCloudReviewAvailable = Boolean(event.data.cloud_review_available);
            runCloudReviewBtn.disabled = !currentCloudReviewAvailable;
        }
    } else if (event.status === 'ERROR') {
        showSpinner(false);
    }
}

function getNestedValue(obj, path) {
    const parts = path.replace(/\]/g, '').split(/[.[]/).filter(p => p !== '');
    let current = obj;
    for (const part of parts) {
        if (current === null || current === undefined) return null;
        current = current[part];
    }
    return current;
}

function setNestedValue(obj, path, value) {
    const parts = path.replace(/\]/g, '').split(/[.[]/).filter(p => p !== '');
    let current = obj;
    for (let index = 0; index < parts.length - 1; index += 1) {
        const part = parts[index];
        const nextPart = parts[index + 1];
        if (current[part] === null || current[part] === undefined) {
            current[part] = /^\d+$/.test(nextPart) ? [] : {};
        }
        current = current[part];
    }
    current[parts[parts.length - 1]] = value;
}

function resetFieldValidationStyles() {
    document.querySelectorAll('[data-field]').forEach(input => {
        input.classList.remove('bg-red-50', 'border-red-300', 'dark:bg-red-950/30', 'dark:border-red-700', 'dark:placeholder-red-400');
        input.classList.add('bg-white', 'border-slate-300', 'dark:bg-slate-950', 'dark:border-slate-600', 'dark:placeholder-slate-500');
        const label = input.previousElementSibling;
        const marker = label ? label.querySelector('[data-required-marker="true"]') : null;
        if (marker) marker.remove();
    });
}

function populateFormFields(data) {
    resetFieldValidationStyles();
    const inputs = document.querySelectorAll('[data-field]');
    inputs.forEach(input => {
        const fieldPath = input.getAttribute('data-field');
        const value = getNestedValue(data, fieldPath);
        if (value !== null && value !== undefined) {
            if (typeof value === 'object') {
                if (value.value !== undefined && typeof value.value !== 'object') {
                    input.value = value.value;
                }
            } else {
                input.value = value;
            }
            input.classList.remove('bg-red-50', 'border-red-300');
            input.classList.add('bg-white', 'border-slate-300');
            input.dataset.i18nPlaceholder = 'form.autoExtracted';
            input.placeholder = t('form.autoExtracted');
        }
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

function populateItemsTable(cargoItems) {
    currentItems = cargoItems || [];
    if (!cargoItems || cargoItems.length === 0) {
        itemsTableBody.innerHTML = `<tr><td colspan="5" class="px-3 py-4 text-center text-slate-400 dark:text-slate-500">${escapeHtml(t('items.none'))}</td></tr>`;
        return;
    }

    itemsTableBody.innerHTML = '';
    cargoItems.forEach((item) => {
        const row = document.createElement('tr');
        const hasMissing = !item.package_quantity || !item.description_of_goods;

        if (hasMissing) {
            row.className = 'bg-red-50 dark:bg-red-950/30';
        }

        const weight = item.weight ? (item.weight.weight_value || '') : '';
        const volume = item.volume ? (item.volume.volume_value || '') : '';

        const safeQty = item.package_quantity ? escapeHtml(item.package_quantity) : `<span class="text-red-400">${escapeHtml(t('form.empty'))}</span>`;
        const safeKind = escapeHtml(item.package_kind_code || '');
        const safeDesc = item.description_of_goods ? escapeHtml(item.description_of_goods) : `<span class="text-red-400">${escapeHtml(t('form.empty'))}</span>`;
        const safeWeight = escapeHtml(weight);
        const safeVolume = escapeHtml(volume);

        row.innerHTML = `
            <td class="px-3 py-2 text-slate-700 dark:text-slate-300">${safeQty}</td>
            <td class="px-3 py-2 text-slate-700 dark:text-slate-300">${safeKind}</td>
            <td class="px-3 py-2 text-slate-700 dark:text-slate-300">${safeDesc}</td>
            <td class="px-3 py-2 text-slate-700 dark:text-slate-300">${safeWeight}</td>
            <td class="px-3 py-2 text-slate-700 dark:text-slate-300">${safeVolume}</td>
        `;
        itemsTableBody.appendChild(row);
    });
}

function highlightMissingFields(missingFields) {
    if (!missingFields || missingFields.length === 0) return;

    const missingPaths = missingFields.map(f => f.field_path);

    document.querySelectorAll('[data-field]').forEach(input => {
        const fieldPath = input.getAttribute('data-field');
        if (missingPaths.includes(fieldPath)) {
            input.classList.add('bg-red-50', 'border-red-300', 'dark:bg-red-950/30', 'dark:border-red-700', 'dark:placeholder-red-400');
            input.classList.remove('bg-white', 'border-slate-300', 'dark:bg-slate-950', 'dark:border-slate-600', 'dark:placeholder-slate-500');
            input.dataset.i18nPlaceholder = 'form.empty';
            input.placeholder = t('form.empty');

            const label = input.previousElementSibling;
            if (label && !label.querySelector('.text-red-500')) {
                const requiredSpan = document.createElement('span');
                requiredSpan.className = 'text-red-500 font-semibold';
                requiredSpan.dataset.requiredMarker = 'true';
                requiredSpan.dataset.i18n = 'form.required';
                requiredSpan.textContent = ` ${t('form.required')}`;
                label.appendChild(requiredSpan);
            }
        }
    });
}

function clearSuspiciousHighlights() {
    document.querySelectorAll('[data-field]').forEach(input => {
        input.classList.remove('ring-2', 'ring-amber-300');
        input.removeAttribute('data-audit-suspicious');
        input.removeAttribute('title');
    });
}

function highlightSuspiciousFields(suspiciousFields) {
    clearSuspiciousHighlights();
    document.querySelectorAll('[data-field]').forEach(input => {
        const path = input.getAttribute('data-field');
        const differs = suspiciousFields.some(field => field === path || field.startsWith(`${path}.`));
        if (differs) {
            input.classList.add('ring-2', 'ring-amber-300');
            input.dataset.auditSuspicious = 'true';
            input.title = t('audit.suspiciousField');
        }
    });
}

function refreshSuspiciousFieldTitles() {
    document.querySelectorAll('[data-audit-suspicious="true"]').forEach((input) => {
        input.title = t('audit.suspiciousField');
    });
}

function collectEditedData() {
    if (!currentStructuredData) return null;
    const edited = JSON.parse(JSON.stringify(currentStructuredData));
    document.querySelectorAll('[data-field]').forEach(input => {
        const path = input.getAttribute('data-field');
        const oldValue = getNestedValue(edited, path);
        let value = input.value.trim() === '' ? null : input.value.trim();
        if (value !== null && typeof oldValue === 'number') {
            const numericValue = Number(value);
            value = Number.isNaN(numericValue) ? value : numericValue;
        } else if (value !== null && typeof oldValue === 'boolean') {
            value = value.toLowerCase() === 'true';
        }
        setNestedValue(edited, path, value);
    });
    return edited;
}

async function persistInstruction(approve) {
    if (!currentSessionId || !currentStructuredData) {
        showStatusMessage('', true, 'status.processFirst');
        return;
    }
    const editedData = collectEditedData();
    const button = approve ? approveDataBtn : saveDraftBtn;
    button.disabled = true;
    button.classList.add('opacity-60', 'cursor-not-allowed');
    try {
        const endpoint = approve
            ? `/api/sessions/${encodeURIComponent(currentSessionId)}/approve`
            : `/api/sessions/${encodeURIComponent(currentSessionId)}/draft`;
        const response = await fetch(endpoint, {
            method: approve ? 'POST' : 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ shipping_instruction: editedData }),
        });
        const result = await response.json();
        if (!response.ok) {
            if (result.missing_fields) highlightMissingFields(result.missing_fields);
            throw new Error(translateServerMessage(result.error) || `${t('error.requestFailed')} (${response.status})`);
        }
        currentStructuredData = result.structured_data;
        populateFormFields(currentStructuredData);
        populateItemsTable(currentStructuredData.cargo_items);
        xmlOutput.removeAttribute('data-i18n');
        xmlOutput.textContent = result.xml_content;
        copyXmlBtn.disabled = false;
        highlightMissingFields(result.missing_fields || []);
        updateStatusBadge(result.status);
        showStatusMessage(result.message, true);
        currentSuspiciousFields = result.suspicious_fields || [];
        updateAuditDisplay(
            result.audit_confidence_score,
            result.cloud_review_used,
            result.local_risk_score,
            result.audit_summary,
            currentSuspiciousFields,
        );
        highlightSuspiciousFields(currentSuspiciousFields);
        currentCloudReviewAvailable = Boolean(result.cloud_review_available);
        runCloudReviewBtn.disabled = !currentCloudReviewAvailable;
        updateResultActionAvailability();
    } catch (error) {
        updateStatusBadge(approve ? 'DRAFT' : 'ERROR');
        showStatusMessage(`${t('error.prefix')}: ${error.message}`, true);
    } finally {
        button.disabled = false;
        button.classList.remove('opacity-60', 'cursor-not-allowed');
    }
}

async function runManualCloudReview() {
    if (!currentSessionId) {
        showStatusMessage('', true, 'status.processFirst');
        return;
    }
    runCloudReviewBtn.disabled = true;
    showSpinner(true);
    showStatusMessage('', true, 'status.cloudRunning');
    try {
        const response = await fetch(
            `/api/sessions/${encodeURIComponent(currentSessionId)}/cloud-review`,
            { method: 'POST' },
        );
        const result = await response.json();
        if (!response.ok) throw new Error(translateServerMessage(result.error) || `${t('error.requestFailed')} (${response.status})`);
        currentSuspiciousFields = result.suspicious_fields || [];
        updateAuditDisplay(
            result.audit_confidence_score,
            result.cloud_review_used,
            result.local_risk_score,
            result.audit_summary,
            currentSuspiciousFields,
        );
        highlightSuspiciousFields(currentSuspiciousFields);
        currentCloudReviewAvailable = Boolean(result.cloud_review_available);
        runCloudReviewBtn.disabled = !currentCloudReviewAvailable;
        showStatusMessage(result.message, true);
    } catch (error) {
        showStatusMessage(`${t('error.prefix')}: ${error.message}`, true);
    } finally {
        showSpinner(false);
        runCloudReviewBtn.disabled = !currentCloudReviewAvailable;
    }
}

dropZone.addEventListener('click', () => fileInput.click());
browseLink.addEventListener('click', (e) => {
    e.stopPropagation();
    fileInput.click();
});

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('border-teal-500', 'bg-teal-50/30', 'dark:bg-teal-950/30');
});

dropZone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    dropZone.classList.remove('border-teal-500', 'bg-teal-50/30', 'dark:bg-teal-950/30');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('border-teal-500', 'bg-teal-50/30', 'dark:bg-teal-950/30');
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
});

fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) handleFile(file);
});

copyXmlBtn.addEventListener('click', () => {
    const text = xmlOutput.textContent;
    navigator.clipboard.writeText(text).then(() => {
        copyXmlBtn.textContent = t('common.copied');
        setTimeout(() => { copyXmlBtn.textContent = t('common.copy'); }, 2000);
    }).catch((error) => {
        showStatusMessage(`${t('error.prefix')}: ${error.message}`, true);
    });
});

saveDraftBtn.addEventListener('click', () => persistInstruction(false));

approveDataBtn.addEventListener('click', () => persistInstruction(true));

runCloudReviewBtn.addEventListener('click', runManualCloudReview);

document.querySelectorAll('[data-language]').forEach((button) => {
    button.addEventListener('click', () => applyLanguage(button.dataset.language));
});

themeToggle.addEventListener('click', () => {
    applyTheme(getCurrentTheme() === 'dark' ? 'light' : 'dark');
});

globalSearchBtn.addEventListener('click', () => {
    if (toggleTopPanel(globalSearchPanel, globalSearchBtn)) {
        renderSearchResults(globalSearchInput.value);
        globalSearchInput.focus();
    }
});

globalSearchInput.addEventListener('input', () => renderSearchResults(globalSearchInput.value));

globalSearchResults.addEventListener('click', (event) => {
    const resultButton = event.target.closest('[data-search-target]');
    if (resultButton) focusSearchTarget(resultButton.dataset.searchTarget);
});

notificationsBtn.addEventListener('click', () => {
    if (toggleTopPanel(notificationsPanel, notificationsBtn)) {
        notificationDot.classList.add('hidden');
        renderNotification();
    }
});

profileBtn.addEventListener('click', () => {
    if (toggleTopPanel(profilePanel, profileBtn)) updateProfileSummary();
});

pdfCopyBtn.addEventListener('click', copyPdfLink);
pdfZoomBtn.addEventListener('click', cyclePdfZoom);
pdfFullscreenBtn.addEventListener('click', togglePdfFullscreen);
prevPageBtn.addEventListener('click', () => goToPdfPage(currentPage - 1));
nextPageBtn.addEventListener('click', () => goToPdfPage(currentPage + 1));

thumbnailSidebar.addEventListener('click', (event) => {
    const pageButton = event.target.closest('[data-pdf-page]');
    if (pageButton) goToPdfPage(pageButton.dataset.pdfPage);
});

document.addEventListener('fullscreenchange', updatePdfControls);

document.addEventListener('click', (event) => {
    if (!event.target.closest('#globalSearchPanel') && !event.target.closest('#globalSearchBtn')
        && !event.target.closest('#notificationsPanel') && !event.target.closest('#notificationsBtn')
        && !event.target.closest('#profilePanel') && !event.target.closest('#profileBtn')) {
        closeTopPanels();
    }
});

document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
        closeTopPanels();
        if (document.fullscreenElement === pdfViewerPanel) document.exitFullscreen();
    }
});

const systemTheme = window.matchMedia('(prefers-color-scheme: dark)');
systemTheme.addEventListener('change', (event) => {
    if (!localStorage.getItem('cerberus-theme')) {
        applyTheme(event.matches ? 'dark' : 'light', false);
    }
});

applyLanguage(currentLanguage, false);
updateThemeControl();
updatePdfControls();
