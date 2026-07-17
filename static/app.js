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
const statusMessageBar = document.getElementById('statusMessageBar');
const statusMessage = document.getElementById('statusMessage');
const processingSpinner = document.getElementById('processingSpinner');
const xmlOutput = document.getElementById('xmlOutput');
const itemsTableBody = document.getElementById('itemsTableBody');
const copyXmlBtn = document.getElementById('copyXmlBtn');
const saveDraftBtn = document.getElementById('saveDraftBtn');
const approveDataBtn = document.getElementById('approveDataBtn');

let uploadedPdfUrl = null;
let currentPage = 1;
let totalPages = 1;

const STATUS_BADGE_MAP = {
    PENDING: { text: 'Pending', class: 'bg-slate-100 text-slate-600' },
    OCR_PROCESSING: { text: 'OCR Processing', class: 'bg-blue-100 text-blue-700' },
    LLM_ANALYZING: { text: 'LLM Analyzing', class: 'bg-indigo-100 text-indigo-700' },
    XML_VALIDATING: { text: 'XML Validating', class: 'bg-amber-100 text-amber-700' },
    COMPLETED: { text: 'Completed', class: 'bg-teal-100 text-teal-700' },
    DRAFT: { text: 'Needs Review', class: 'bg-yellow-100 text-yellow-800' },
    ERROR: { text: 'Error', class: 'bg-red-100 text-red-700' },
};

function updateStatusBadge(status) {
    const config = STATUS_BADGE_MAP[status] || STATUS_BADGE_MAP.PENDING;
    statusBadge.textContent = config.text;
    statusBadge.className = `px-3 py-1 text-xs font-semibold rounded-full ${config.class}`;
}

function showStatusMessage(message, isVisible = true) {
    if (isVisible) {
        statusMessage.textContent = message;
        statusMessageBar.classList.remove('hidden');
    } else {
        statusMessageBar.classList.add('hidden');
    }
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

function handleFile(file) {
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
        alert('Lutfen gecerli bir PDF dosyasi secin.');
        return;
    }

    fileName.textContent = file.name;
    fileInfo.classList.remove('hidden');
    pdfViewerFileName.textContent = file.name;

    if (uploadedPdfUrl) {
        URL.revokeObjectURL(uploadedPdfUrl);
    }

    uploadedPdfUrl = URL.createObjectURL(file);
    pdfPlaceholder.classList.add('hidden');
    pdfIframe.src = uploadedPdfUrl;
    pdfIframe.classList.remove('hidden');
    thumbnailSidebar.classList.remove('hidden');
    pdfFooter.classList.remove('hidden');
    pdfFooter.classList.add('flex');

    setUploadProgress(100);

    uploadAndStream(file);
}

async function uploadAndStream(file) {
    updateStatusBadge('PENDING');
    showStatusMessage('Dosya yukleniyor...', true);
    showSpinner(true);

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/upload-and-stream', {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error(`Upload failed: ${response.statusText}`);
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
        showStatusMessage(`Hata: ${error.message}`, true);
        showSpinner(false);
    }
}

function handleSseEvent(event) {
    if (event.status === 'COMPLETE') {
        showSpinner(false);
        return;
    }

    if (event.status === 'TIMEOUT') {
        showSpinner(false);
        updateStatusBadge('ERROR');
        showStatusMessage('Islem zaman asimina ugradi.', true);
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
                xmlOutput.textContent = event.data.xml_content;
            }
            if (event.data.missing_fields) {
                highlightMissingFields(event.data.missing_fields);
            }
            if (event.data.raw_llm_json) {
                try {
                    const parsed = JSON.parse(event.data.raw_llm_json);
                    populateFormFields(parsed);
                    populateItemsTable(parsed.cargo_items);
                } catch (e) {
                    console.error('JSON parse error:', e);
                }
            }
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

function populateFormFields(data) {
    const inputs = document.querySelectorAll('[data-field]');
    inputs.forEach(input => {
        const fieldPath = input.getAttribute('data-field');
        const value = getNestedValue(data, fieldPath);
        if (value !== null && value !== undefined) {
            if (typeof value === 'object' && value.value) {
                input.value = value.value;
            } else {
                input.value = value;
            }
            input.classList.remove('bg-red-50', 'border-red-300');
            input.classList.add('bg-white', 'border-slate-300');
            input.placeholder = 'Auto-extracted';
        }
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

function populateItemsTable(cargoItems) {
    if (!cargoItems || cargoItems.length === 0) {
        return;
    }

    itemsTableBody.innerHTML = '';
    cargoItems.forEach((item) => {
        const row = document.createElement('tr');
        const hasMissing = !item.package_quantity || !item.description_of_goods;

        if (hasMissing) {
            row.className = 'bg-red-50';
        }

        const weight = item.weight ? (item.weight.weight_value || '') : '';
        const volume = item.volume ? (item.volume.volume_value || '') : '';

        const safeQty = item.package_quantity ? escapeHtml(item.package_quantity) : '<span class="text-red-400">Empty</span>';
        const safeKind = escapeHtml(item.package_kind_code || '');
        const safeDesc = item.description_of_goods ? escapeHtml(item.description_of_goods) : '<span class="text-red-400">Empty</span>';
        const safeWeight = escapeHtml(weight);
        const safeVolume = escapeHtml(volume);

        row.innerHTML = `
            <td class="px-3 py-2 text-slate-700">${safeQty}</td>
            <td class="px-3 py-2 text-slate-700">${safeKind}</td>
            <td class="px-3 py-2 text-slate-700">${safeDesc}</td>
            <td class="px-3 py-2 text-slate-700">${safeWeight}</td>
            <td class="px-3 py-2 text-slate-700">${safeVolume}</td>
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
            input.classList.add('bg-red-50', 'border-red-300');
            input.classList.remove('bg-white', 'border-slate-300');
            input.placeholder = 'Empty';

            const label = input.previousElementSibling;
            if (label && !label.querySelector('.text-red-500')) {
                const requiredSpan = document.createElement('span');
                requiredSpan.className = 'text-red-500 font-semibold';
                requiredSpan.textContent = ' (Required)';
                label.appendChild(requiredSpan);
            }
        }
    });
}

dropZone.addEventListener('click', () => fileInput.click());
browseLink.addEventListener('click', (e) => {
    e.stopPropagation();
    fileInput.click();
});

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('border-teal-500', 'bg-teal-50/30');
});

dropZone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    dropZone.classList.remove('border-teal-500', 'bg-teal-50/30');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('border-teal-500', 'bg-teal-50/30');
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
        copyXmlBtn.textContent = 'Copied!';
        setTimeout(() => { copyXmlBtn.textContent = 'Copy'; }, 2000);
    });
});

saveDraftBtn.addEventListener('click', () => {
    showStatusMessage('Draft kaydedildi.', true);
});

approveDataBtn.addEventListener('click', () => {
    updateStatusBadge('COMPLETED');
    showStatusMessage('Veriler onaylandi.', true);
});