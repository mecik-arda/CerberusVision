const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const browseLink = document.getElementById('browseLink');
const fileInfo = document.getElementById('fileInfo');
const fileName = document.getElementById('fileName');
const fileQueue = document.getElementById('fileQueue');
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
const logsBtn = document.getElementById('logsBtn');
const logsPanel = document.getElementById('logsPanel');
const logsOutput = document.getElementById('logsOutput');
let logsEmptyState = document.getElementById('logsEmptyState');
const logsConnectionDot = document.getElementById('logsConnectionDot');
const logsConnectionStatus = document.getElementById('logsConnectionStatus');
const logsAutoScroll = document.getElementById('logsAutoScroll');
const logsClearBtn = document.getElementById('logsClearBtn');
const settingsBtn = document.getElementById('settingsBtn');
const settingsPanel = document.getElementById('settingsPanel');
const settingsRefreshBtn = document.getElementById('settingsRefreshBtn');
const settingsSaveBtn = document.getElementById('settingsSaveBtn');
const settingsStatus = document.getElementById('settingsStatus');
const modelReadyBadge = document.getElementById('modelReadyBadge');
const modelNameValue = document.getElementById('modelNameValue');
const modelDeviceValue = document.getElementById('modelDeviceValue');
const modelTokensValue = document.getElementById('modelTokensValue');
const modelKvValue = document.getElementById('modelKvValue');
const detectedModelCount = document.getElementById('detectedModelCount');
const detectedModelsList = document.getElementById('detectedModelsList');
const selectedModelPath = document.getElementById('selectedModelPath');
const serverApiKeyInput = document.getElementById('serverApiKeyInput');
const deepSeekApiKeyInput = document.getElementById('deepSeekApiKeyInput');
const deepSeekReviewMode = document.getElementById('deepSeekReviewMode');
const deepSeekRiskThreshold = document.getElementById('deepSeekRiskThreshold');
const clearDeepSeekKey = document.getElementById('clearDeepSeekKey');
const nmtEnabled = document.getElementById('nmtEnabled');
const webhookUrlInput = document.getElementById('webhookUrlInput');
const webhookEnabled = document.getElementById('webhookEnabled');
const webhookTestBtn = document.getElementById('webhookTestBtn');
const webhookTestStatus = document.getElementById('webhookTestStatus');
const inferenceMode = document.getElementById('inferenceMode');
const layoutEngine = document.getElementById('layoutEngine');
const loraEnabled = document.getElementById('loraEnabled');
const loraAdapterPath = document.getElementById('loraAdapterPath');
const regionUpperRatio = document.getElementById('regionUpperRatio');
const regionUpperRatioValue = document.getElementById('regionUpperRatioValue');
const regionMiddleRatio = document.getElementById('regionMiddleRatio');
const regionMiddleRatioValue = document.getElementById('regionMiddleRatioValue');
const stageTimeout = document.getElementById('stageTimeout');
const stageTimeoutValue = document.getElementById('stageTimeoutValue');
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
const documentLanguage = document.getElementById('documentLanguage');
const outputLanguage = document.getElementById('outputLanguage');
const translationEnabled = document.getElementById('translationEnabled');
const selectionActions = document.getElementById('selectionActions');
const startProcessingBtn = document.getElementById('startProcessingBtn');
const clearSelectionBtn = document.getElementById('clearSelectionBtn');
const validationSummary = document.getElementById('validationSummary');

const TRANSLATIONS = {
    tr: {
        'page.title': 'CerberusVision — Belge İşleme',
        'nav.languageSelection': 'Dil seçimi',
        'nav.search': 'Arama',
        'nav.logs': 'Canlı sistem logları',
        'nav.settings': 'Model ayarları',
        'nav.notifications': 'Bildirimler',
        'nav.profileMenu': 'Kullanıcı menüsü',
        'search.title': 'Arayüzde Ara',
        'search.placeholder': 'Alan veya bölüm ara...',
        'search.empty': 'Aramak için yazmaya başlayın.',
        'search.noResults': 'Eşleşen alan veya bölüm bulunamadı.',
        'logs.title': 'CerberusVision Terminal',
        'logs.connecting': 'Bağlanıyor',
        'logs.connected': 'Canlı',
        'logs.disconnected': 'Bağlı değil',
        'logs.autoScroll': 'Otomatik kaydır',
        'logs.clear': 'Temizle',
        'logs.empty': 'Log akışı açıldığında kayıtlar burada görünecek.',
        'logs.streamError': 'Log bağlantısı kesildi: {message}',
        'logs.clearError': 'Loglar temizlenemedi: {message}',
        'settings.title': 'Model ve API Ayarları',
        'settings.memoryNotice': 'DeepSeek anahtarı yalnızca sunucu belleğinde tutulur.',
        'settings.refresh': 'Bilgileri yenile',
        'settings.localModel': 'Yerel Model',
        'settings.modelName': 'Model',
        'settings.device': 'Aygıt',
        'settings.maxTokens': 'Azami çıktı',
        'settings.kvCache': 'KV önbellek',
        'settings.detectedModels': "WSL'de Bulunan Modeller",
        'settings.noModels': 'Yüklü yerel model bulunamadı.',
        'settings.modelsFound': '{count} model',
        'settings.selectModel': 'Bu modeli etkinleştir',
        'settings.notSelectable': 'Bu biçim doğrudan çalıştırılamaz',
        'settings.active': 'Etkin',
        'settings.ready': 'Hazır',
        'settings.notReady': 'Hazır değil',
        'settings.loraActive': 'LoRA aktif',
        'settings.serverApiKey': 'Cerberus sunucu API anahtarı',
        'settings.deepSeekApiKey': 'DeepSeek API anahtarı',
        'settings.sessionOnly': 'Yalnızca bu tarayıcı oturumu',
        'settings.leaveBlank': 'Mevcut anahtarı korumak için boş bırakın',
        'settings.reviewMode': 'Denetim modu',
        'settings.riskThreshold': 'Risk eşiği',
        'settings.modeOff': 'Kapalı',
        'settings.modeManual': 'Manuel',
        'settings.modeRisk': 'Riske göre',
        'settings.modeAlways': 'Her zaman',
        'settings.clearKey': 'Kayıtlı DeepSeek anahtarını kaldır',
        'settings.nmt': 'NMT çeviri (MarianMT, daha hızlı)',
        'settings.webhook': 'Webhook Entegrasyonu',
        'settings.webhookUrl': 'Hedef URL',
        'settings.webhookPlaceholder': 'https://erp-sisteminiz.com/api/dcsa-webhook',
        'settings.webhookEnable': 'Etkin',
        'settings.webhookTest': 'Test Et',
        'settings.webhookTesting': 'Test ediliyor...',
        'settings.webhookTestOk': 'Bağlantı başarılı (HTTP 200)',
        'settings.webhookTestFail': 'Bağlantı başarısız',
        'settings.save': 'Ayarları Kaydet',
        'settings.loading': 'Model bilgileri yükleniyor...',
        'settings.saving': 'Ayarlar kaydediliyor...',
        'settings.saved': 'Ayarlar kaydedildi. DeepSeek: {state}',
        'settings.configured': 'yapılandırıldı',
        'settings.notConfigured': 'yapılandırılmadı',
        'settings.loadFailed': 'Ayarlar alınamadı',
        'settings.inferenceHeading': 'Çıkarım Motoru',
        'settings.inferenceMode': 'Çıkarım Modu',
        'settings.modeMultiStage': '3 Aşamalı Modüler (Önerilen - %95 Doğruluk)',
        'settings.modeSinglePass': 'Tek Geçişli (Hızlı / Legacy)',
        'settings.layoutEngine': 'Mizanpaj Algılama Yöntemi',
        'settings.engineYRatio': 'Y-Oranı Ayrıştırması (%35 / %65 Statik)',
        'settings.engineHybrid': 'Hibrit (Florence-2 VLM + Akıllı Fallback)',
        'settings.engineOff': 'Kapalı (Düz OCR)',
        'settings.loraHeading': 'LoRA İnce Ayar',
        'settings.loraEnable': 'LoRA İnce Ayarını Etkinleştir',
        'settings.loraAdapter': 'LoRA Adapter Seçimi',
        'settings.loraNone': 'Yüklü adapter yok',
        'settings.advancedHeading': 'Gelişmiş Parametreler',
        'settings.upperBoundary': 'Üst Bölge Sınırı',
        'settings.middleBoundary': 'Orta Bölge Sınırı',
        'settings.stageTimeout': 'Aşama Zaman Aşımı',
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
        'upload.dropPrompt': 'Belgeleri sürükleyip bırakın veya',
        'upload.browse': 'Göz Atın',
        'upload.supported': 'PDF, DOCX, XML, PNG ve JPEG · en fazla 10 dosya',
        'upload.invalidDocument': 'Desteklenmeyen dosya var. PDF, DOCX, XML, PNG veya JPEG seçin.',
        'upload.tooMany': 'Tek seferde en fazla 10 dosya seçebilirsiniz.',
        'upload.queue': '{done}/{total} belge tamamlandı',
        'upload.previewUnavailable': 'Bu DOCX belgesi için tarayıcı önizlemesi kullanılamıyor.',
        'upload.uploading': 'Dosya yükleniyor...',
        'upload.ready': 'Dosyalar hazır. Ayarları kontrol edip analizi başlatın.',
        'processing.documentLanguage': 'Belge dili',
        'processing.languageAuto': 'Otomatik / Çok dilli',
        'processing.translationEnabled': 'XML açıklama alanlarını hedef dile çevir',
        'processing.outputLanguage': 'XML içerik dili',
        'processing.outputHint': 'DCSA XML etiketleri standart gereği sabit kalır; açıklama ve not değerleri seçilen dilde üretilir.',
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
        'status.ocr': 'Belge içeriği işleniyor...',
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
        'form.instructionDateTime': 'Talimat Tarih/Saati',
        'form.placeOfIssue': 'Düzenlenme Yeri',
        'form.shipperCity': 'Gönderici Şehri',
        'form.shipperCountry': 'Gönderici Ülke Kodu',
        'form.consigneeName': 'Alıcı Adı',
        'form.consigneeAddress': 'Alıcı Adresi',
        'form.consigneeCity': 'Alıcı Şehri',
        'form.consigneeCountry': 'Alıcı Ülke Kodu',
        'form.packageQuantity': 'Paket Adedi',
        'form.goodsDescription': 'Mal Açıklaması',
        'form.vendor': 'Satıcı',
        'form.vendorAddress': 'Satıcı Adresi',
        'form.taxId': 'Vergi Kimlik No',
        'form.totalAmount': 'Net Yük Ağırlığı',
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
        'actions.startProcessing': 'Analizi Başlat',
        'actions.exportAll': 'ZIP İndir',
        'actions.clearSelection': 'Seçimi Temizle',
        'validation.heading': 'Onay için düzeltilmesi gereken alanlar',
        'validation.xsdHeading': 'XML doğrulama sorunları',
        'error.prefix': 'Hata',
        'error.uploadFailed': 'Yükleme başarısız',
        'error.requestFailed': 'İstek başarısız',
        'error.approvalBlocked': 'Zorunlu alanlar veya XSD doğrulama hataları onayı engelliyor.',
        'auth.apiKeyPrompt': 'Sunucu erişimi için CerberusVision API anahtarını girin:',
    },
    en: {
        'page.title': 'CerberusVision — Document Processing',
        'nav.languageSelection': 'Language selection',
        'nav.search': 'Search',
        'nav.logs': 'Live system logs',
        'nav.settings': 'Model settings',
        'nav.notifications': 'Notifications',
        'nav.profileMenu': 'User menu',
        'search.title': 'Search Interface',
        'search.placeholder': 'Search for a field or section...',
        'search.empty': 'Start typing to search.',
        'search.noResults': 'No matching field or section was found.',
        'logs.title': 'CerberusVision Terminal',
        'logs.connecting': 'Connecting',
        'logs.connected': 'Live',
        'logs.disconnected': 'Disconnected',
        'logs.autoScroll': 'Auto-scroll',
        'logs.clear': 'Clear',
        'logs.empty': 'Logs will appear here when the stream opens.',
        'logs.streamError': 'Log connection closed: {message}',
        'logs.clearError': 'Could not clear logs: {message}',
        'settings.title': 'Model and API Settings',
        'settings.memoryNotice': 'The DeepSeek key is kept only in server memory.',
        'settings.refresh': 'Refresh information',
        'settings.localModel': 'Local Model',
        'settings.modelName': 'Model',
        'settings.device': 'Device',
        'settings.maxTokens': 'Maximum output',
        'settings.kvCache': 'KV cache',
        'settings.detectedModels': 'Models Detected in WSL',
        'settings.noModels': 'No installed local model was found.',
        'settings.modelsFound': '{count} model(s)',
        'settings.selectModel': 'Activate this model',
        'settings.notSelectable': 'This format cannot run directly',
        'settings.active': 'Active',
        'settings.ready': 'Ready',
        'settings.notReady': 'Not ready',
        'settings.loraActive': 'LoRA active',
        'settings.serverApiKey': 'Cerberus server API key',
        'settings.deepSeekApiKey': 'DeepSeek API key',
        'settings.sessionOnly': 'This browser session only',
        'settings.leaveBlank': 'Leave blank to keep the existing key',
        'settings.reviewMode': 'Review mode',
        'settings.riskThreshold': 'Risk threshold',
        'settings.modeOff': 'Off',
        'settings.modeManual': 'Manual',
        'settings.modeRisk': 'Risk based',
        'settings.modeAlways': 'Always',
        'settings.clearKey': 'Remove the stored DeepSeek key',
        'settings.nmt': 'NMT translation (MarianMT, faster)',
        'settings.webhook': 'Webhook Integration',
        'settings.webhookUrl': 'Target URL',
        'settings.webhookPlaceholder': 'https://your-erp.com/api/dcsa-webhook',
        'settings.webhookEnable': 'Enabled',
        'settings.webhookTest': 'Test',
        'settings.webhookTesting': 'Testing...',
        'settings.webhookTestOk': 'Connection successful (HTTP 200)',
        'settings.webhookTestFail': 'Connection failed',
        'audit.refinementUsed': '2. geçiş düzeltmesi uygulandı',
        'audit.deepSeek': 'DeepSeek',
        'audit.local': 'Yerel',
        'settings.save': 'Save Settings',
        'settings.loading': 'Loading model information...',
        'settings.saving': 'Saving settings...',
        'settings.saved': 'Settings saved. DeepSeek: {state}',
        'settings.configured': 'configured',
        'settings.notConfigured': 'not configured',
        'settings.loadFailed': 'Could not load settings',
        'settings.inferenceHeading': 'Inference Engine',
        'settings.inferenceMode': 'Inference Mode',
        'settings.modeMultiStage': '3-Stage Modular (Recommended - 95% Accuracy)',
        'settings.modeSinglePass': 'Single-Pass (Fast / Legacy)',
        'settings.layoutEngine': 'Layout Detection Method',
        'settings.engineYRatio': 'Y-Ratio Segmentation (35% / 65% Static)',
        'settings.engineHybrid': 'Hybrid (Florence-2 VLM + Smart Fallback)',
        'settings.engineOff': 'Off (Plain OCR)',
        'settings.loraHeading': 'LoRA Fine-Tuning',
        'settings.loraEnable': 'Enable LoRA Fine-Tuning',
        'settings.loraAdapter': 'LoRA Adapter Selection',
        'settings.loraNone': 'No adapters installed',
        'settings.advancedHeading': 'Advanced Parameters',
        'settings.upperBoundary': 'Upper Region Boundary',
        'settings.middleBoundary': 'Middle Region Boundary',
        'settings.stageTimeout': 'Stage Timeout',
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
        'upload.dropPrompt': 'Drag & drop documents or',
        'upload.browse': 'Browse',
        'upload.supported': 'PDF, DOCX, XML, PNG and JPEG · up to 10 files',
        'upload.invalidDocument': 'An unsupported file was selected. Choose PDF, DOCX, XML, PNG or JPEG.',
        'upload.tooMany': 'You can select up to 10 files at once.',
        'upload.queue': '{done}/{total} documents completed',
        'upload.previewUnavailable': 'Browser preview is unavailable for this DOCX document.',
        'upload.uploading': 'Uploading file...',
        'upload.ready': 'Files are ready. Check the settings and start analysis.',
        'processing.documentLanguage': 'Document language',
        'processing.languageAuto': 'Automatic / Multilingual',
        'processing.translationEnabled': 'Translate XML descriptive fields to the target language',
        'processing.outputLanguage': 'XML content language',
        'processing.outputHint': 'DCSA XML element names remain fixed by the standard; descriptions and remarks are generated in the selected language.',
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
        'status.ocr': 'Processing document content...',
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
        'form.instructionDateTime': 'Instruction Date/Time',
        'form.placeOfIssue': 'Place of Issue',
        'form.shipperCity': 'Shipper City',
        'form.shipperCountry': 'Shipper Country Code',
        'form.consigneeName': 'Consignee Name',
        'form.consigneeAddress': 'Consignee Address',
        'form.consigneeCity': 'Consignee City',
        'form.consigneeCountry': 'Consignee Country Code',
        'form.packageQuantity': 'Package Quantity',
        'form.goodsDescription': 'Description of Goods',
        'form.vendor': 'Vendor',
        'form.vendorAddress': 'Vendor Address',
        'form.taxId': 'Tax ID',
        'form.totalAmount': 'Net Cargo Weight',
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
        'actions.startProcessing': 'Start Analysis',
        'actions.exportAll': 'Download ZIP',
        'actions.clearSelection': 'Clear Selection',
        'validation.heading': 'Fields that must be corrected before approval',
        'validation.xsdHeading': 'XML validation issues',
        'error.prefix': 'Error',
        'error.uploadFailed': 'Upload failed',
        'error.requestFailed': 'Request failed',
        'error.approvalBlocked': 'Mandatory fields or XSD validation errors prevent approval.',
        'auth.apiKeyPrompt': 'Enter the CerberusVision API key to access the server:',
    },
};

const savedLanguage = localStorage.getItem('cerberus-language');
let currentLanguage = Object.hasOwn(TRANSLATIONS, savedLanguage) ? savedLanguage : 'tr';
const savedDocumentLanguage = localStorage.getItem('cerberus-document-language');
const savedOutputLanguage = localStorage.getItem('cerberus-output-language');
const savedTranslationEnabled = localStorage.getItem('cerberus-translation-enabled');
documentLanguage.value = ['auto', 'tr', 'en'].includes(savedDocumentLanguage) ? savedDocumentLanguage : 'auto';
outputLanguage.value = ['tr', 'en'].includes(savedOutputLanguage) ? savedOutputLanguage : 'en';
translationEnabled.checked = savedTranslationEnabled === null ? true : savedTranslationEnabled === 'true';
outputLanguage.disabled = !translationEnabled.checked;

function t(key, values = {}) {
    const template = TRANSLATIONS[currentLanguage][key] || TRANSLATIONS.tr[key] || key;
    return Object.entries(values).reduce(
        (text, [name, value]) => text.replaceAll(`{${name}}`, String(value)),
        template,
    );
}

async function apiFetch(resource, options = {}, allowCredentialRetry = true) {
    const headers = new Headers(options.headers || {});
    const apiKey = sessionStorage.getItem('cerberus-api-key');
    if (apiKey) headers.set('Authorization', `Bearer ${apiKey}`);
    const response = await fetch(resource, { ...options, headers });
    if (response.status !== 401 || !allowCredentialRetry) return response;
    const suppliedKey = window.prompt(t('auth.apiKeyPrompt'));
    if (!suppliedKey) return response;
    sessionStorage.setItem('cerberus-api-key', suppliedKey.trim());
    if (options.body instanceof FormData) {
        const originalForm = options.body;
        const yeniForm = new FormData();
        for (const [key, value] of originalForm.entries()) { yeniForm.append(key, value); }
        return apiFetch(resource, { ...options, body: yeniForm }, false);
    }
    return apiFetch(resource, options, false);
}

function renderDetectedModels(models = []) {
    detectedModelCount.textContent = t('settings.modelsFound', { count: models.length });
    if (!models.length) {
        detectedModelsList.innerHTML = `<p class="text-xs text-slate-400">${escapeHtml(t('settings.noModels'))}</p>`;
        return;
    }
    detectedModelsList.innerHTML = models.map((model) => `
        <label class="block rounded-lg bg-slate-50 px-2.5 py-2 dark:bg-slate-950/60 ${model.selectable ? 'cursor-pointer' : 'opacity-60'}" title="${escapeHtml(model.path || '')}">
            <div class="flex items-center justify-between gap-2">
                <span class="flex min-w-0 items-center gap-2">
                    <input type="radio" name="local-model" value="${escapeHtml(model.path || '')}" ${model.active ? 'checked' : ''} ${model.selectable ? '' : 'disabled'} class="border-slate-300 text-teal-600 focus:ring-teal-500">
                    <span class="truncate text-xs font-medium text-slate-700 dark:text-slate-200">${escapeHtml(model.name || '--')}</span>
                </span>
                ${model.active ? `<span class="rounded-full bg-teal-100 px-1.5 py-0.5 text-[10px] font-semibold text-teal-700 dark:bg-teal-950 dark:text-teal-300">${escapeHtml(t('settings.active'))}</span>` : ''}
            </div>
            <p class="mt-0.5 truncate text-[10px] text-slate-400">${escapeHtml(model.source || '')} · ${escapeHtml(model.format || '')}</p>
            <p class="mt-0.5 text-[10px] text-slate-400">${escapeHtml(t(model.selectable ? 'settings.selectModel' : 'settings.notSelectable'))}</p>
        </label>
    `).join('');
    const activeModel = models.find((model) => model.active);
    selectedModelPath.value = activeModel?.path || '';
}

function renderRuntimeSettings(data) {
    currentRuntimeSettings = data;
    const localModel = data.local_model || {};
    modelNameValue.textContent = localModel.name || '--';
    modelNameValue.title = localModel.path || '';
    modelDeviceValue.textContent = localModel.device || '--';
    modelTokensValue.textContent = localModel.max_new_tokens ?? '--';
    modelKvValue.textContent = localModel.kv_cache_precision || '--';
    const inferenceConfig = data.inference || {};
    const loraActive = inferenceConfig.lora_enabled || localModel.lora_available;
    if (loraActive) {
        modelReadyBadge.textContent = t('settings.loraActive');
        modelReadyBadge.className = 'rounded-full bg-violet-100 px-2 py-0.5 text-[11px] font-semibold text-violet-700 dark:bg-violet-950 dark:text-violet-300';
    } else {
        modelReadyBadge.textContent = t(localModel.ready ? 'settings.ready' : 'settings.notReady');
        modelReadyBadge.className = localModel.ready
            ? 'rounded-full bg-teal-100 px-2 py-0.5 text-[11px] font-semibold text-teal-700 dark:bg-teal-950 dark:text-teal-300'
            : 'rounded-full bg-red-100 px-2 py-0.5 text-[11px] font-semibold text-red-700 dark:bg-red-950 dark:text-red-300';
    }
    inferenceMode.value = inferenceConfig.mode || 'multi_stage';
    layoutEngine.value = inferenceConfig.layout_engine || 'y_ratio';
    loraEnabled.checked = inferenceConfig.lora_enabled || false;
    const adapterList = inferenceConfig.lora_adapters || [];
    loraAdapterPath.innerHTML = adapterList.length
        ? adapterList.map(function (a) { return '<option value="' + escapeHtml(a.path || '') + '">' + escapeHtml(a.name || a.path || '') + '</option>'; }).join('')
        : '<option value="">' + t('settings.loraNone') + '</option>';
    if (inferenceConfig.lora_adapter_path && adapterList.some(function (a) { return a.path === inferenceConfig.lora_adapter_path; })) {
        loraAdapterPath.value = inferenceConfig.lora_adapter_path;
    }
    var upperPct = Math.round((inferenceConfig.region_upper_ratio || 0.35) * 100);
    var middlePct = Math.round((inferenceConfig.region_middle_ratio || 0.65) * 100);
    regionUpperRatio.value = upperPct;
    regionUpperRatioValue.textContent = '%' + upperPct;
    regionMiddleRatio.value = middlePct;
    regionMiddleRatioValue.textContent = '%' + middlePct;
    stageTimeout.value = inferenceConfig.stage_timeout_seconds || 300;
    stageTimeoutValue.textContent = (inferenceConfig.stage_timeout_seconds || 300) + ' sn';
    deepSeekReviewMode.value = data.deepseek?.review_mode || 'risk';
    deepSeekRiskThreshold.value = data.deepseek?.risk_threshold ?? 30;
    renderDetectedModels(data.installed_models || []);
    settingsStatus.textContent = `DeepSeek: ${t(data.deepseek?.configured ? 'settings.configured' : 'settings.notConfigured')}`;
    if (!runtimePreferencesHydrated) {
        runtimePreferencesHydrated = true;
        const preferences = data.interface || {};
        if (!localStorage.getItem('cerberus-language') && preferences.interface_language) {
            applyLanguage(preferences.interface_language, false);
        }
        if (!localStorage.getItem('cerberus-theme') && ['light', 'dark'].includes(preferences.theme)) {
            applyTheme(preferences.theme, false);
        }
        if (!localStorage.getItem('cerberus-document-language') && preferences.document_language) {
            documentLanguage.value = preferences.document_language;
        }
        if (!localStorage.getItem('cerberus-output-language') && preferences.output_language) {
            outputLanguage.value = preferences.output_language;
        }
        if (!localStorage.getItem('cerberus-translation-enabled') && typeof preferences.translation_enabled === 'boolean') {
            translationEnabled.checked = preferences.translation_enabled;
            outputLanguage.disabled = !translationEnabled.checked;
        }
    }
}

async function loadRuntimeSettings(allowCredentialRetry = true) {
    settingsRefreshBtn.disabled = true;
    settingsStatus.textContent = t('settings.loading');
    try {
        const response = await apiFetch('/api/runtime-settings', {}, allowCredentialRetry);
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || response.statusText);
        renderRuntimeSettings(data);
    } catch (error) {
        settingsStatus.textContent = `${t('settings.loadFailed')}: ${error.message}`;
    } finally {
        settingsRefreshBtn.disabled = false;
    }
}

async function saveRuntimeSettings() {
    settingsSaveBtn.disabled = true;
    settingsStatus.textContent = t('settings.saving');
    const serverKey = serverApiKeyInput.value.trim();
    if (serverKey) sessionStorage.setItem('cerberus-api-key', serverKey);
    const payload = {
        clear_deepseek_api_key: clearDeepSeekKey.checked,
        deepseek_review_mode: deepSeekReviewMode.value,
        deepseek_risk_threshold: Number(deepSeekRiskThreshold.value),
        theme: getCurrentTheme(),
        interface_language: currentLanguage,
        document_language: documentLanguage.value,
        output_language: outputLanguage.value,
        translation_enabled: translationEnabled.checked,
        nmt_enabled: nmtEnabled.checked,
        inference_mode: inferenceMode.value,
        layout_engine: layoutEngine.value,
        lora_enabled: loraEnabled.checked,
        lora_adapter_path: loraEnabled.checked ? loraAdapterPath.value : '',
        region_upper_ratio: Number(regionUpperRatio.value) / 100,
        region_middle_ratio: Number(regionMiddleRatio.value) / 100,
        stage_timeout_seconds: Number(stageTimeout.value),
    };
    if (selectedModelPath.value) payload.local_model_path = selectedModelPath.value;
    const deepSeekKey = deepSeekApiKeyInput.value.trim();
    if (deepSeekKey && !clearDeepSeekKey.checked) payload.deepseek_api_key = deepSeekKey;
    try {
        const response = await apiFetch('/api/runtime-settings', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || response.statusText);
        deepSeekApiKeyInput.value = '';
        clearDeepSeekKey.checked = false;
        renderRuntimeSettings(data);
        settingsStatus.textContent = t('settings.saved', {
            state: t(data.deepseek?.configured ? 'settings.configured' : 'settings.notConfigured'),
        });
        currentCloudReviewAvailable = Boolean(data.deepseek?.configured && data.deepseek?.review_mode !== 'off');
        updateResultActionAvailability();
    } catch (error) {
        settingsStatus.textContent = `${t('error.prefix')}: ${error.message}`;
    } finally {
        settingsSaveBtn.disabled = false;
    }
}

let uploadedPdfUrl = null;
let currentPdfFile = null;
let currentPreviewKind = null;
let documentQueue = [];
const SUPPORTED_DOCUMENT_EXTENSIONS = new Set(['pdf', 'docx', 'xml', 'png', 'jpg', 'jpeg']);
const MAX_BATCH_FILES = 50;
let activeBatchId = null;
let activeBatchController = null;
let currentPage = 1;
let totalPages = 1;
let currentZoom = 100;
const ZOOM_LEVELS = [100, 125, 150, 200];
let currentSessionId = null;
let currentStructuredData = null;
let currentXmlContent = '';
let currentSuspiciousFields = [];
let currentCloudReviewAvailable = false;
let currentStatus = 'IDLE';
let currentStatusMessageKey = null;
let currentStatusMessageFallback = '';
let currentAuditState = null;
let currentItems = null;
let activeUploadController = null;
let activeUploadRequestId = 0;
let latestNotification = null;
let currentRuntimeSettings = null;
let runtimePreferencesHydrated = false;
let currentApprovalReady = false;
let selectionProcessing = false;
let liveLogAbortController = null;
let liveLogReconnectTimer = null;
let liveLogStreamingEnabled = false;
let lastLiveLogEventId = 0;

const MAX_RENDERED_LOGS = 500;

const MANDATORY_EDITABLE_PATHS = [
    'shipping_instruction_reference',
    'shipping_instruction_date_time',
    'carrier_booking_reference',
    'issue_date',
    'place_of_issue.location_name',
    'parties[0].party_name',
    'parties[0].address.street',
    'parties[0].address.city',
    'parties[0].address.country_code',
    'parties[1].party_name',
    'parties[1].address.street',
    'parties[1].address.city',
    'parties[1].address.country_code',
    'transport_plans[0].port_of_loading.location_name',
    'transport_plans[0].port_of_discharge.location_name',
    'equipment_list[0].equipment_reference',
    'equipment_list[0].cargo_gross_weight.weight',
    'cargo_items[0].package_quantity',
    'cargo_items[0].description_of_goods',
    'cargo_items[0].weight.weight_value',
];

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
        [logsPanel, logsBtn],
        [settingsPanel, settingsBtn],
        [notificationsPanel, notificationsBtn],
        [profilePanel, profileBtn],
    ].forEach(([panel, button]) => {
        if (panel !== except) {
            panel.classList.add('hidden');
            button.setAttribute('aria-expanded', 'false');
        }
    });
}

function updateLiveLogConnectionState(state) {
    const stateClasses = {
        connecting: 'bg-amber-400',
        connected: 'bg-teal-400',
        disconnected: 'bg-slate-500',
    };
    logsConnectionDot.className = `h-2 w-2 rounded-full ${stateClasses[state] || stateClasses.disconnected}`;
    logsConnectionStatus.textContent = t(`logs.${state}`);
}

function appendLiveLogEntry(entry) {
    if (!entry || !Number.isFinite(Number(entry.id))) return;
    lastLiveLogEventId = Math.max(lastLiveLogEventId, Number(entry.id));
    if (logsEmptyState) {
        logsEmptyState.remove();
        logsEmptyState = null;
    }
    const level = String(entry.level || 'INFO').toUpperCase();
    const levelClasses = {
        ERROR: 'text-red-300',
        CRITICAL: 'text-red-300',
        WARNING: 'text-amber-300',
        WARN: 'text-amber-300',
        DEBUG: 'text-slate-500',
        INFO: 'text-slate-300',
    };
    const timestamp = new Date(entry.timestamp);
    const timeText = Number.isNaN(timestamp.getTime())
        ? '--:--:--'
        : timestamp.toLocaleTimeString(currentLanguage === 'tr' ? 'tr-TR' : 'en-US', { hour12: false });
    const line = document.createElement('div');
    line.className = levelClasses[level] || levelClasses.INFO;
    line.textContent = `[${timeText}] ${level.padEnd(8)} ${entry.source || 'cerberus'}  ${entry.message || ''}`;
    logsOutput.appendChild(line);
    while (logsOutput.children.length > MAX_RENDERED_LOGS) {
        logsOutput.firstElementChild.remove();
    }
    if (logsAutoScroll.checked) logsOutput.scrollTop = logsOutput.scrollHeight;
}

function appendLiveLogError(message, translationKey = 'logs.streamError') {
    const line = document.createElement('div');
    line.className = 'text-red-300';
    line.textContent = t(translationKey, { message });
    logsOutput.appendChild(line);
    if (logsAutoScroll.checked) logsOutput.scrollTop = logsOutput.scrollHeight;
}

function processLiveLogEventBlock(block) {
    const data = block.split(/\r?\n/)
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trimStart())
        .join('\n');
    if (!data) return;
    try {
        appendLiveLogEntry(JSON.parse(data));
    } catch (error) {
        appendLiveLogError(error.message);
    }
}

async function connectLiveLogs() {
    if (liveLogAbortController) return;
    if (liveLogReconnectTimer) {
        clearTimeout(liveLogReconnectTimer);
        liveLogReconnectTimer = null;
    }
    const controller = new AbortController();
    liveLogAbortController = controller;
    updateLiveLogConnectionState('connecting');
    try {
        const headers = {};
        if (lastLiveLogEventId > 0) headers['Last-Event-ID'] = String(lastLiveLogEventId);
        const response = await apiFetch('/api/logs/stream', {
            headers,
            signal: controller.signal,
        });
        if (!response.ok) throw new Error(response.statusText || String(response.status));
        if (!response.body) throw new Error('Readable stream is unavailable');
        updateLiveLogConnectionState('connected');
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let bufferedText = '';
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            bufferedText += decoder.decode(value, { stream: true });
            const blocks = bufferedText.split(/\r?\n\r?\n/);
            bufferedText = blocks.pop() || '';
            blocks.forEach(processLiveLogEventBlock);
        }
        bufferedText += decoder.decode();
        if (bufferedText.trim()) processLiveLogEventBlock(bufferedText);
        if (!controller.signal.aborted) throw new Error('Stream ended');
    } catch (error) {
        if (!controller.signal.aborted) appendLiveLogError(error.message);
    } finally {
        if (liveLogAbortController === controller) liveLogAbortController = null;
        if (!controller.signal.aborted && liveLogStreamingEnabled) {
            updateLiveLogConnectionState('disconnected');
            liveLogReconnectTimer = setTimeout(connectLiveLogs, 2000);
        }
    }
}

async function clearLiveLogs() {
    logsClearBtn.disabled = true;
    try {
        const response = await apiFetch('/api/logs', { method: 'DELETE' });
        if (!response.ok) throw new Error(response.statusText || String(response.status));
        logsOutput.replaceChildren();
        const emptyState = document.createElement('p');
        emptyState.id = 'logsEmptyState';
        emptyState.className = 'text-slate-500';
        emptyState.textContent = t('logs.empty');
        logsOutput.appendChild(emptyState);
        logsEmptyState = emptyState;
    } catch (error) {
        appendLiveLogError(error.message, 'logs.clearError');
    } finally {
        logsClearBtn.disabled = false;
    }
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
    const hasPreview = Boolean(uploadedPdfUrl) && currentPreviewKind !== 'docx';
    const hasPdf = hasPreview && currentPreviewKind === 'pdf';
    currentPage = Math.min(Math.max(currentPage, 1), totalPages);
    currentPageLabel.textContent = String(currentPage);
    totalPagesLabel.textContent = String(totalPages);
    pdfZoomLevel.textContent = `${currentZoom}%`;
    pdfCopyBtn.disabled = !hasPreview;
    pdfZoomBtn.disabled = !hasPdf;
    pdfFullscreenBtn.disabled = !hasPreview;
    prevPageBtn.disabled = !hasPdf || currentPage <= 1;
    nextPageBtn.disabled = !hasPdf || currentPage >= totalPages;
    pdfZoomBtn.title = t('pdf.zoomAt', { level: currentZoom });
    pdfZoomBtn.setAttribute('aria-label', pdfZoomBtn.title);
    const isFullscreen = document.fullscreenElement === pdfViewerPanel;
    pdfFullscreenBtn.title = t(isFullscreen ? 'pdf.exitFullscreen' : 'pdf.fullscreen');
    pdfFullscreenBtn.setAttribute('aria-label', pdfFullscreenBtn.title);
    if (hasPdf) renderPageThumbnails();
    else thumbnailSidebar.innerHTML = '';
}

function refreshPdfViewer() {
    if (!uploadedPdfUrl) return;
    pdfIframe.src = currentPreviewKind === 'pdf'
        ? `${uploadedPdfUrl}#page=${currentPage}&zoom=${currentZoom}`
        : uploadedPdfUrl;
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

function updateAuditDisplay(score, cloudReviewUsed, localRiskScore, summary, suspiciousFields = [], refinementUsed = false) {
    if (typeof score !== 'number') {
        currentAuditState = null;
        auditScoreBadge.classList.add('hidden');
        auditReviewPanel.classList.add('hidden');
        return;
    }
    currentAuditState = { score, cloudReviewUsed, localRiskScore, summary, suspiciousFields, refinementUsed };
    const colorClass = score >= 90
        ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
        : score >= 75
            ? 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
            : 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300';
    auditScoreBadge.className = `px-3 py-1 text-xs font-semibold rounded-full ${colorClass}`;
    let badgeText = `${cloudReviewUsed ? t('audit.deepSeek') : t('audit.local')}: ${score.toFixed(2)}%`;
    if (refinementUsed) badgeText += ' · 2P';
    auditScoreBadge.textContent = badgeText;
    auditScoreBadge.title = `${t('audit.localRisk')}: ${typeof localRiskScore === 'number' ? localRiskScore.toFixed(2) : '--'}%; ${t('audit.suspiciousCount', { count: suspiciousFields.length })}`;
    let kaynakMetin = cloudReviewUsed ? t('audit.deepSeekSource') : t('audit.localSource');
    if (refinementUsed) kaynakMetin += ' (' + t('audit.refinementUsed') + ')';
    auditReviewSource.textContent = kaynakMetin;
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
        'Belge icerigi isleniyor...': 'status.ocr',
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
    if (currentRuntimeSettings) renderRuntimeSettings(currentRuntimeSettings);
    renderDocumentQueue();
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
    const formReady = MANDATORY_EDITABLE_PATHS.every((path) => {
        const input = document.querySelector(`[data-field="${path}"]`);
        return input && input.value.trim() !== '';
    });
    approveDataBtn.disabled = !hasStructuredData || !formReady;
    currentApprovalReady = hasStructuredData && formReady;
    copyXmlBtn.disabled = !currentXmlContent;
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
    currentXmlContent = '';
    currentApprovalReady = false;
    validationSummary.classList.add('hidden');
    validationSummary.innerHTML = '';
    xmlOutput.dataset.i18n = 'xml.placeholder';
    xmlOutput.textContent = t('xml.placeholder');
    updateResultActionAvailability();
}

function renderValidationSummary(missingFields = [], validationErrors = []) {
    const missingLabels = missingFields.map((field) => field.field_label || field.field_path).filter(Boolean);
    const xmlErrors = validationErrors.filter(Boolean);
    if (!missingLabels.length && !xmlErrors.length) {
        validationSummary.classList.add('hidden');
        validationSummary.innerHTML = '';
        return;
    }
    const sections = [];
    if (missingLabels.length) {
        sections.push(`<div><p class="font-semibold">${escapeHtml(t('validation.heading'))}</p><ul class="mt-1 list-disc space-y-0.5 pl-5">${missingLabels.map((label) => `<li>${escapeHtml(label)}</li>`).join('')}</ul></div>`);
    }
    if (xmlErrors.length) {
        sections.push(`<div class="mt-2"><p class="font-semibold">${escapeHtml(t('validation.xsdHeading'))}</p><ul class="mt-1 list-disc space-y-0.5 pl-5">${xmlErrors.map((error) => `<li>${escapeHtml(error)}</li>`).join('')}</ul></div>`);
    }
    validationSummary.innerHTML = sections.join('');
    validationSummary.classList.remove('hidden');
}

function documentExtension(file) {
    return file?.name?.split('.').pop()?.toLowerCase() || '';
}

function renderDocumentQueue() {
    if (!documentQueue.length) {
        fileQueue.classList.add('hidden');
        fileQueue.innerHTML = '';
        selectionActions.classList.add('hidden');
        selectionActions.classList.remove('flex');
        return;
    }
    const completeCount = documentQueue.filter((job) => ['COMPLETED', 'DRAFT'].includes(job.status)).length;
    fileQueue.classList.remove('hidden');
    selectionActions.classList.remove('hidden');
    selectionActions.classList.add('flex');
    startProcessingBtn.disabled = selectionProcessing || !documentQueue.some((job) => job.status === 'PENDING');
    clearSelectionBtn.disabled = selectionProcessing;
    exportAllBtn.disabled = !documentQueue.some((job) => ['COMPLETED', 'DRAFT'].includes(job.status) && job.sessionId);
    fileQueue.innerHTML = `
        <p class="px-1 text-[11px] font-semibold text-slate-500 dark:text-slate-400">${escapeHtml(t('upload.queue', { done: completeCount, total: documentQueue.length }))}</p>
        ${documentQueue.map((job) => {
            const status = STATUS_BADGE_MAP[job.status] ? job.status : 'PENDING';
            let ekBilgi = '';
            if (job.riskScore !== undefined && job.riskScore !== null) ekBilgi += ` · risk:${job.riskScore}`;
            if (job.elapsedSeconds) ekBilgi += ` · ${job.elapsedSeconds}s`;
            return `<div class="flex items-center justify-between gap-2 rounded-md bg-white px-2 py-1.5 text-xs dark:bg-slate-900">
                <div class="min-w-0 flex-1">
                    <span class="truncate block text-slate-700 dark:text-slate-200" title="${escapeHtml(job.file.name)}">${escapeHtml(job.file.name)}</span>
                    ${job.sessionId ? `<span class="block text-[10px] text-slate-400 dark:text-slate-500 truncate">${escapeHtml(job.sessionId)}${escapeHtml(ekBilgi)}</span>` : ''}
                </div>
                <span class="shrink-0 rounded-full px-2 py-0.5 font-semibold ${STATUS_BADGE_MAP[status]}">${escapeHtml(t(`status.${status}`))}</span>
            </div>`;
        }).join('')}`;
}

async function handleFiles(fileList) {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    if (files.length > MAX_BATCH_FILES) {
        alert(t('upload.tooMany'));
        return;
    }
    if (files.some((file) => !SUPPORTED_DOCUMENT_EXTENSIONS.has(documentExtension(file)))) {
        alert(t('upload.invalidDocument'));
        return;
    }

    if (activeUploadController) activeUploadController.abort();
    const requestId = ++activeUploadRequestId;
    documentQueue = files.map((file, index) => ({ id: `${requestId}-${index}`, file, status: 'PENDING' }));
    selectionProcessing = false;
    renderDocumentQueue();
    await previewSelectedFile(files[0]);
    showStatusMessage('', true, 'upload.ready', false);
    fileInput.value = '';
}

function handleFile(file) {
    return handleFiles(file ? [file] : []);
}

async function previewSelectedFile(file) {
    currentPreviewKind = documentExtension(file);
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
    const canPreview = currentPreviewKind !== 'docx';
    const isPdf = currentPreviewKind === 'pdf';
    pdfPlaceholder.classList.toggle('hidden', canPreview);
    pdfIframe.classList.toggle('hidden', !canPreview);
    thumbnailSidebar.classList.toggle('hidden', !isPdf);
    pdfFooter.classList.toggle('hidden', !isPdf);
    pdfFooter.classList.toggle('flex', isPdf);
    if (canPreview) {
        refreshPdfViewer();
    } else {
        const previewMessage = pdfPlaceholder.querySelector('p');
        previewMessage.removeAttribute('data-i18n');
        previewMessage.textContent = t('upload.previewUnavailable');
        updatePdfControls();
    }

    setUploadProgress(0);

    const pageCountPromise = isPdf ? estimatePdfPageCount(file) : Promise.resolve(1);
    pageCountPromise.then((count) => {
        if (currentPdfFile !== file) return;
        totalPages = count;
        updatePdfControls();
    }).catch(() => {
        totalPages = 1;
        updatePdfControls();
    });

}

async function processQueuedFile(job, controller, requestId) {
    await previewSelectedFile(job.file);
    await uploadAndStream(job.file, controller, requestId, job);
}

async function startSelectedFiles() {
    const pendingJobs = documentQueue.filter((job) => job.status === 'PENDING');
    if (!pendingJobs.length || selectionProcessing) return;
    const requestId = activeUploadRequestId;
    selectionProcessing = true;
    renderDocumentQueue();

    // Batch mod: 1'den fazla dosya varsa toplu yukleme kullan
    if (pendingJobs.length > 1) {
        await startBatchUpload(pendingJobs, requestId);
    } else {
        for (const job of pendingJobs) {
            if (requestId !== activeUploadRequestId) break;
            const controller = new AbortController();
            activeUploadController = controller;
            await processQueuedFile(job, controller, requestId);
        }
    }
    if (requestId === activeUploadRequestId) activeUploadController = null;
    selectionProcessing = false;
    renderDocumentQueue();
}

// ---------------------------------------------------------------------------
// Batch (toplu isleme) fonksiyonlari
// ---------------------------------------------------------------------------

async function startBatchUpload(pendingJobs, requestId) {
    const batchProgressPanel = document.getElementById('batchProgressPanel');
    const batchProgressBar = document.getElementById('batchProgressBar');
    const batchProgressLabel = document.getElementById('batchProgressLabel');
    const batchCurrentFile = document.getElementById('batchCurrentFile');
    const batchDownloadBtn = document.getElementById('batchDownloadBtn');
    const batchCancelBtn = document.getElementById('batchCancelBtn');

    batchProgressPanel.classList.remove('hidden');
    batchDownloadBtn.disabled = true;
    batchCancelBtn.disabled = false;
    updateBatchProgress(0, 0, pendingJobs.length);

    const formData = new FormData();
    for (const job of pendingJobs) {
        formData.append('files', job.file);
    }
    formData.append('document_language', documentLanguage.value);
    formData.append('output_language', outputLanguage.value);
    formData.append('translation_enabled', String(translationEnabled.checked));

    try {
        showStatusMessage('', true, '', false);
        const statusMsg = document.getElementById('statusMessage');
        statusMsg.classList.remove('status-hidden');
        statusMsg.querySelector('span').textContent = 'Batch yukleniyor ve dogrulaniyor...';
        showSpinner(true);

        const response = await apiFetch('/api/batch/upload', {
            method: 'POST',
            body: formData,
        });
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Batch upload failed (${response.status})`);
        }
        const result = await response.json();
        activeBatchId = result.batch_id;

        // Rejected dosyalari goster
        if (result.rejected_count > 0) {
            for (const rejected of result.rejected_items) {
                const job = pendingJobs.find(j => j.file.name === rejected.original_filename);
                if (job) {
                    job.status = 'REJECTED';
                    job._rejectReason = rejected.error_message;
                }
            }
        }

        // Batch SSE'ye baglan
        await connectBatchStream(result.batch_id, pendingJobs, requestId);
    } catch (e) {
        console.error('Batch upload error:', e);
        showStatusMessage(e.message, false, '', true);
        showSpinner(false);
    } finally {
        batchCancelBtn.disabled = true;
    }
}

async function connectBatchStream(batchId, pendingJobs, requestId) {
    const batchProgressBar = document.getElementById('batchProgressBar');
    const batchProgressLabel = document.getElementById('batchProgressLabel');
    const batchCurrentFile = document.getElementById('batchCurrentFile');
    const batchDownloadBtn = document.getElementById('batchDownloadBtn');

    try {
        const response = await apiFetch(`/api/batch/${batchId}/stream`);
        if (!response.ok) throw new Error('Batch stream failed');

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (requestId === activeUploadRequestId) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const jsonStr = line.slice(6);
                try {
                    const event = JSON.parse(jsonStr);
                    if (event.status === 'COMPLETE') {
                        // Batch tamamlandi
                        updateBatchProgress(100, event.completed_count || pendingJobs.length, pendingJobs.length);
                        batchCurrentFile.textContent = 'Islem tamamlandi.';
                        batchDownloadBtn.disabled = false;
                        showSpinner(false);
                        showStatusMessage('Batch isleme tamamlandi!', true, '', false);
                        // Pending job'lari guncelle
                        try {
                            const statusResp = await apiFetch(`/api/batch/${batchId}/status`);
                            const status = await statusResp.json();
                            syncBatchItemsToQueue(status.items, pendingJobs);
                        } catch (_) {}
                        return;
                    }
                    if (event.timeout) {
                        showStatusMessage('Batch islemi zaman asimina ugradi.', false, '', true);
                        showSpinner(false);
                        return;
                    }
                    // Ilerleme guncellemesi
                    updateBatchProgress(event.percent, event.completed_count, event.total_count);
                    if (event.current_file) {
                        batchCurrentFile.textContent = `Isleniyor: ${event.current_file}`;
                    }
                    if (event.item) {
                        const job = pendingJobs.find(
                            j => j.file.name === event.item.original_filename
                        );
                        if (job) {
                            job.status = event.item.status;
                            job.sessionId = event.item.session_id;
                            job.riskScore = event.item.risk_score;
                            if (event.item.error_message) {
                                job._errorMessage = event.item.error_message;
                            }
                        }
                        renderDocumentQueue();
                    }
                    if (event.zip_ready) {
                        batchDownloadBtn.disabled = false;
                        batchCurrentFile.textContent = 'ZIP hazir! Indirebilirsiniz.';
                    }
                } catch (_) {}
            }
        }
    } catch (e) {
        console.error('Batch stream error:', e);
        showStatusMessage('Batch SSE baglantisi koptu.', false, '', true);
        showSpinner(false);
    }
}

function updateBatchProgress(percent, completed, total) {
    const batchProgressBar = document.getElementById('batchProgressBar');
    const batchProgressLabel = document.getElementById('batchProgressLabel');
    if (batchProgressBar) batchProgressBar.style.width = `${percent}%`;
    if (batchProgressLabel) batchProgressLabel.textContent = `%${Math.round(percent)} — ${completed}/${total}`;
}

function syncBatchItemsToQueue(batchItems, pendingJobs) {
    for (const item of batchItems) {
        const job = pendingJobs.find(j => j.file.name === item.original_filename);
        if (job) {
            job.status = item.status;
            job.sessionId = item.session_id;
            job.riskScore = item.risk_score;
            job._errorMessage = item.error_message;
        }
    }
    renderDocumentQueue();
}

async function downloadBatchZip() {
    if (!activeBatchId) return;
    try {
        const batchDownloadBtn = document.getElementById('batchDownloadBtn');
        batchDownloadBtn.disabled = true;
        const response = await apiFetch(`/api/batch/${activeBatchId}/download`);
        if (!response.ok) throw new Error('ZIP download failed');
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `batch_results_${activeBatchId}.zip`;
        a.click();
        URL.revokeObjectURL(url);
        batchDownloadBtn.disabled = false;
    } catch (e) {
        console.error('Batch ZIP download error:', e);
    }
}

async function cancelBatch() {
    if (!activeBatchId) return;
    try {
        await apiFetch(`/api/batch/${activeBatchId}`, { method: 'DELETE' });
    } catch (_) {}
    activeBatchId = null;
    document.getElementById('batchProgressPanel').classList.add('hidden');
    selectionProcessing = false;
    renderDocumentQueue();
}


function clearFileSelection() {
    if (activeUploadController) activeUploadController.abort();
    activeUploadRequestId += 1;
    documentQueue = [];
    selectionProcessing = false;
    currentPdfFile = null;
    currentPreviewKind = null;
    if (uploadedPdfUrl) URL.revokeObjectURL(uploadedPdfUrl);
    uploadedPdfUrl = null;
    pdfIframe.src = '';
    pdfIframe.classList.add('hidden');
    pdfPlaceholder.classList.remove('hidden');
    thumbnailSidebar.classList.add('hidden');
    pdfFooter.classList.add('hidden');
    pdfFooter.classList.remove('flex');
    fileInfo.classList.add('hidden');
    pdfViewerFileName.setAttribute('data-i18n', 'pdf.noneLoaded');
    pdfViewerFileName.textContent = t('pdf.noneLoaded');
    renderDocumentQueue();
    resetDocumentResults();
    updatePdfControls();
}

async function uploadAndStream(file, controller, requestId, job = null) {
    updateStatusBadge('PENDING');
    showStatusMessage('', true, 'upload.uploading');
    showSpinner(true);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_language', documentLanguage.value);
    formData.append('output_language', outputLanguage.value);
    formData.append('translation_enabled', String(translationEnabled.checked));

    try {
        const response = await apiFetch('/api/upload-and-stream', {
            method: 'POST',
            body: formData,
            signal: controller.signal,
        });

        if (!response.ok) {
            const errorPayload = await response.json().catch(() => ({}));
            throw new Error(errorPayload.error || `${t('error.uploadFailed')}: ${response.statusText}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            if (requestId !== activeUploadRequestId) {
                await reader.cancel();
                return;
            }

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const jsonStr = line.slice(6).trim();
                    if (jsonStr) {
                        try {
                            handleSseEvent(JSON.parse(jsonStr), requestId, job);
                        } catch (e) {
                            console.error('SSE parse error:', e, jsonStr);
                        }
                    }
                }
            }
        }
    } catch (error) {
        if (error.name === 'AbortError' || requestId !== activeUploadRequestId) return;
        updateStatusBadge('ERROR');
        showStatusMessage(`${t('error.prefix')}: ${error.message}`, true);
        showSpinner(false);
        if (job) {
            job.status = 'ERROR';
            renderDocumentQueue();
        }
    } finally {
        if (requestId === activeUploadRequestId) activeUploadController = null;
    }
}

function handleSseEvent(event, requestId = activeUploadRequestId, job = null) {
    if (requestId !== activeUploadRequestId) return;
    if (job && event.session_id) job.sessionId = event.session_id;
    if (job && event.data) job.result = event.data;
    if (job && event.status && event.status !== 'COMPLETE') {
        job.status = event.status === 'TIMEOUT' ? 'ERROR' : event.status;
        if (event.data) {
            if (event.data.local_risk_score !== undefined) job.riskScore = event.data.local_risk_score;
            if (event.data.elapsed_seconds) job.elapsedSeconds = event.data.elapsed_seconds;
        }
        renderDocumentQueue();
    }
    if (event.session_id) {
        currentSessionId = event.session_id;
        updateProfileSummary();
    }
    if (event.status === 'COMPLETE') {
        showSpinner(false);
        return;
    }

    if (event.status === 'TIMEOUT') {
        if (job) job.status = 'ERROR';
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
                currentXmlContent = event.data.xml_content;
                xmlOutput.removeAttribute('data-i18n');
                xmlOutput.textContent = currentXmlContent;
                copyXmlBtn.disabled = false;
            }
            if (event.data.missing_fields) {
                highlightMissingFields(event.data.missing_fields);
            }
            renderValidationSummary(
                event.data.missing_fields || [],
                event.data.validation_errors || [],
            );
            if (event.data.structured_data) {
                currentStructuredData = normalizeEditableStructure(event.data.structured_data);
                populateFormFields(currentStructuredData);
                populateItemsTable(currentStructuredData.cargo_items);
                setupOcrHighlightListeners();
                if (event.session_id) { loadOcrBoxes(event.session_id); currentOcrText = event.data.raw_ocr_text || ''; }
                updateResultActionAvailability();
            } else if (event.data.raw_llm_json) {
                try {
                    const parsed = JSON.parse(event.data.raw_llm_json);
                    currentStructuredData = normalizeEditableStructure(parsed);
                    populateFormFields(currentStructuredData);
                    populateItemsTable(currentStructuredData.cargo_items);
                    setupOcrHighlightListeners();
                    if (event.session_id) { loadOcrBoxes(event.session_id); currentOcrText = event.data.raw_ocr_text || ''; }
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
                event.data.local_refinement_used || false,
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

function normalizeEditableStructure(data) {
    const normalized = JSON.parse(JSON.stringify(data || {}));
    const parties = Array.isArray(normalized.parties) ? normalized.parties : [];
    const shipper = parties.find((party) => party.party_role_code === 'SHI') || { party_role_code: 'SHI' };
    const consignee = parties.find((party) => party.party_role_code === 'CON') || { party_role_code: 'CON' };
    const remainingParties = parties.filter((party) => !['SHI', 'CON'].includes(party.party_role_code));
    shipper.address = shipper.address || {};
    consignee.address = consignee.address || {};
    normalized.parties = [shipper, consignee, ...remainingParties];
    normalized.place_of_issue = normalized.place_of_issue || {};
    normalized.transport_plans = Array.isArray(normalized.transport_plans) && normalized.transport_plans.length
        ? normalized.transport_plans
        : [{ leg_sequence_number: 1 }];
    normalized.transport_plans[0].port_of_loading = normalized.transport_plans[0].port_of_loading || {};
    normalized.transport_plans[0].port_of_discharge = normalized.transport_plans[0].port_of_discharge || {};
    normalized.equipment_list = Array.isArray(normalized.equipment_list) && normalized.equipment_list.length
        ? normalized.equipment_list
        : [{}];
    normalized.equipment_list[0].cargo_gross_weight = normalized.equipment_list[0].cargo_gross_weight || { unit: 'KGM' };
    normalized.cargo_items = Array.isArray(normalized.cargo_items) && normalized.cargo_items.length
        ? normalized.cargo_items
        : [{}];
    normalized.cargo_items[0].weight = normalized.cargo_items[0].weight || { unit: 'KGM' };
    return normalized;
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

let currentOcrBoxes = null;
let currentOcrText = '';
const ocrOverlay = document.getElementById('ocrHighlightOverlay');

async function loadOcrBoxes(sessionId) {
    try {
        const response = await apiFetch(`/api/sessions/${sessionId}/ocr-boxes`);
        if (!response.ok) { currentOcrBoxes = null; return; }
        const data = await response.json();
        currentOcrBoxes = data.pages || [];
    } catch { currentOcrBoxes = null; }
}

function clearOcrHighlight() {
    if (ocrOverlay) ocrOverlay.innerHTML = '';
    ocrOverlay.classList.add('hidden');
}

function showOcrHighlightForField(fieldPath) {
    clearOcrHighlight();
    if (!currentOcrBoxes || !currentOcrBoxes.length) return;
    if (!currentOcrText && currentStructuredData) {
        currentOcrText = (currentStructuredData.raw_ocr_text || '').toLowerCase();
    }

    const keywords = {
        'shipping_instruction_reference': ['si no', 'si reference', 'talimat no', 'sevkiyat talimati'],
        'carrier_booking_reference': ['booking', 'bkg ref', 'rezervasyon'],
        'issue_date': ['issue date', 'date of issue', 'tarih', 'düzenleme'],
        'parties': ['shipper', 'consignee', 'gönderici', 'alici'],
        'shipper': ['shipper', 'exporter', 'gönderici', 'ihracatçi'],
        'consignee': ['consignee', 'buyer', 'receiver', 'alici', 'ithalatçi'],
        'port_of_loading': ['port of loading', 'pol', 'yükleme limani'],
        'port_of_discharge': ['port of discharge', 'pod', 'boşaltma limani'],
        'equipment_reference': ['container', 'equipment', 'konteyner'],
        'cargo_gross_weight': ['gross weight', 'brüt'],
        'description_of_goods': ['description of goods', 'cargo', 'goods', 'mal', 'esya'],
    };

    let matchedKeywords = [];
    for (const [key, words] of Object.entries(keywords)) {
        if (fieldPath.includes(key)) { matchedKeywords = words; break; }
    }
    if (!matchedKeywords.length) return;

    const bestPage = 0;
    const pageBoxes = currentOcrBoxes[bestPage] || [];
    if (!pageBoxes.length) return;

    const matchedBoxes = [];
    for (const box of pageBoxes) {
        const boxText = (box.text || '').toLowerCase();
        if (matchedKeywords.some(kw => boxText.includes(kw))) {
            matchedBoxes.push(box);
        }
    }
    if (!matchedBoxes.length) return;

    const overlay = ocrOverlay;
    const displayArea = document.getElementById('pdfDisplayArea');
    const areaRect = displayArea.getBoundingClientRect();

    overlay.classList.remove('hidden');
    overlay.style.width = areaRect.width + 'px';
    overlay.style.height = areaRect.height + 'px';

    const dpi = 200;
    const scaleX = areaRect.width / (pageBoxes[0]?.x_max || 2480) * 0.5;
    const scaleY = areaRect.height / (pageBoxes[0]?.y_max || 3508) * 0.5;

    for (const box of matchedBoxes.slice(0, 3)) {
        const div = document.createElement('div');
        div.className = 'ocr-highlight-box';
        div.style.left = (box.x_min * scaleX) + 'px';
        div.style.top = (box.y_min * scaleY) + 'px';
        div.style.width = ((box.x_max - box.x_min) * scaleX) + 'px';
        div.style.height = ((box.y_max - box.y_min) * scaleY) + 'px';
        overlay.appendChild(div);
    }
}

function setupOcrHighlightListeners() {
    document.querySelectorAll('[data-field]').forEach(input => {
        input.addEventListener('focus', () => {
            const fieldPath = input.getAttribute('data-field');
            if (fieldPath) showOcrHighlightForField(fieldPath);
        });
        input.addEventListener('blur', clearOcrHighlight);
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
        if (value !== null && (typeof oldValue === 'number' || input.type === 'number')) {
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
        const response = await apiFetch(endpoint, {
            method: approve ? 'POST' : 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ shipping_instruction: editedData }),
        });
        const result = await response.json();
        if (!response.ok) {
            if (result.missing_fields) highlightMissingFields(result.missing_fields);
            renderValidationSummary(result.missing_fields || [], result.validation_errors || []);
            throw new Error(translateServerMessage(result.error) || `${t('error.requestFailed')} (${response.status})`);
        }
        currentStructuredData = normalizeEditableStructure(result.structured_data);
        populateFormFields(currentStructuredData);
        populateItemsTable(currentStructuredData.cargo_items);
        setupOcrHighlightListeners();
        if (result.session_id) { loadOcrBoxes(result.session_id); }
        currentXmlContent = result.xml_content;
        xmlOutput.removeAttribute('data-i18n');
        xmlOutput.textContent = currentXmlContent;
        copyXmlBtn.disabled = false;
        highlightMissingFields(result.missing_fields || []);
        renderValidationSummary(result.missing_fields || [], result.validation_errors || []);
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
        button.classList.remove('opacity-60', 'cursor-not-allowed');
        updateResultActionAvailability();
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
        const response = await apiFetch(
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
    handleFiles(e.dataTransfer.files);
});

fileInput.addEventListener('change', (e) => {
    handleFiles(e.target.files);
});

copyXmlBtn.addEventListener('click', () => {
    navigator.clipboard.writeText(currentXmlContent).then(() => {
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

logsBtn.addEventListener('click', () => {
    if (toggleTopPanel(logsPanel, logsBtn)) {
        liveLogStreamingEnabled = true;
        connectLiveLogs();
    }
});

logsClearBtn.addEventListener('click', clearLiveLogs);

settingsBtn.addEventListener('click', () => {
    if (toggleTopPanel(settingsPanel, settingsBtn) && !currentRuntimeSettings) loadRuntimeSettings();
});

settingsRefreshBtn.addEventListener('click', () => loadRuntimeSettings(true));
settingsSaveBtn.addEventListener('click', saveRuntimeSettings);

detectedModelsList.addEventListener('change', (event) => {
    const modelInput = event.target.closest('input[name="local-model"]');
    if (modelInput) selectedModelPath.value = modelInput.value;
});

clearDeepSeekKey.addEventListener('change', () => {
    deepSeekApiKeyInput.disabled = clearDeepSeekKey.checked;
});

webhookTestBtn.addEventListener('click', async () => {
    webhookTestStatus.textContent = t('settings.webhookTesting');
    webhookTestStatus.className = 'mt-1 min-h-3 text-[10px] text-slate-400';
    try {
        const response = await apiFetch('/api/runtime-settings/webhook-test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: webhookUrlInput.value.trim(),
                enabled: webhookEnabled.checked,
            }),
        });
        if (response.ok) {
            webhookTestStatus.textContent = t('settings.webhookTestOk');
            webhookTestStatus.className = 'mt-1 min-h-3 text-[10px] text-teal-600 dark:text-teal-400';
        } else {
            const err = await response.json().catch(() => ({}));
            webhookTestStatus.textContent = `${t('settings.webhookTestFail')}: ${err.error || response.status}`;
            webhookTestStatus.className = 'mt-1 min-h-3 text-[10px] text-red-500';
        }
    } catch (e) {
        webhookTestStatus.textContent = `${t('settings.webhookTestFail')}: ${e.message}`;
        webhookTestStatus.className = 'mt-1 min-h-3 text-[10px] text-red-500';
    }
});

regionUpperRatio.addEventListener('input', function () {
    regionUpperRatioValue.textContent = '%' + regionUpperRatio.value;
});
regionMiddleRatio.addEventListener('input', function () {
    regionMiddleRatioValue.textContent = '%' + regionMiddleRatio.value;
});
stageTimeout.addEventListener('input', function () {
    stageTimeoutValue.textContent = stageTimeout.value + ' sn';
});

documentLanguage.addEventListener('change', () => {
    localStorage.setItem('cerberus-document-language', documentLanguage.value);
});

outputLanguage.addEventListener('change', () => {
    localStorage.setItem('cerberus-output-language', outputLanguage.value);
});

translationEnabled.addEventListener('change', () => {
    localStorage.setItem('cerberus-translation-enabled', String(translationEnabled.checked));
    outputLanguage.disabled = !translationEnabled.checked;
});

document.getElementById('formContainer').addEventListener('input', updateResultActionAvailability);

startProcessingBtn.addEventListener('click', startSelectedFiles);
clearSelectionBtn.addEventListener('click', clearFileSelection);

const exportAllBtn = document.getElementById('exportAllBtn');
exportAllBtn.addEventListener('click', exportApprovedSessions);

const batchDownloadBtn = document.getElementById('batchDownloadBtn');
if (batchDownloadBtn) batchDownloadBtn.addEventListener('click', downloadBatchZip);

const batchCancelBtn = document.getElementById('batchCancelBtn');
if (batchCancelBtn) batchCancelBtn.addEventListener('click', cancelBatch);

async function exportApprovedSessions() {
    const approvedJobs = documentQueue.filter(
        (job) => ['COMPLETED', 'DRAFT'].includes(job.status) && job.sessionId
    );
    if (!approvedJobs.length) return;
    const sessionIds = approvedJobs.map((job) => job.sessionId);
    try {
        const response = await apiFetch('/api/sessions/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_ids: sessionIds }),
        });
        if (!response.ok) throw new Error('Export failed');
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `cerberus_export_${new Date().toISOString().slice(0, 10)}.zip`;
        a.click();
        URL.revokeObjectURL(url);
    } catch (e) {
        console.error('Export error:', e);
    }
}

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
        && !event.target.closest('#logsPanel') && !event.target.closest('#logsBtn')
        && !event.target.closest('#settingsPanel') && !event.target.closest('#settingsBtn')
        && !event.target.closest('#notificationsPanel') && !event.target.closest('#notificationsBtn')
        && !event.target.closest('#profilePanel') && !event.target.closest('#profileBtn')) {
        closeTopPanels();
    }
});

window.addEventListener('beforeunload', () => {
    liveLogStreamingEnabled = false;
    if (liveLogAbortController) liveLogAbortController.abort();
    if (liveLogReconnectTimer) clearTimeout(liveLogReconnectTimer);
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
loadRuntimeSettings(false);
