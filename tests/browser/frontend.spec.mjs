import { expect, test } from '@playwright/test';

test('review workspace exposes only XML and isolates document previews', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('#xmlOutput')).toBeVisible();
    await expect(page.locator('[data-i18n="form.documentInfo"]').locator('..')).toBeHidden();
    expect(await page.locator('#pdfIframe').getAttribute('sandbox')).toBeNull();
    await expect(page.locator('#imagePreview')).toBeHidden();
    await expect(page.locator('#documentTextPreview')).toBeHidden();
});

test('PDF upload opens in the native viewer without a rendering sandbox', async ({ page }) => {
    await page.goto('/');
    const pdfIframe = page.locator('#pdfIframe');
    await page.locator('#fileInput').setInputFiles('veriler/konsimentotalimatornek3s.pdf');
    await expect(pdfIframe).toBeVisible();
    expect(await pdfIframe.getAttribute('sandbox')).toBeNull();
    const previewSource = await pdfIframe.getAttribute('src');
    expect(previewSource).toMatch(/^blob:/);
    expect(previewSource).toContain('#page=1&zoom=100');
});

test('review actions remain in the viewport with long validation results', async ({ page }) => {
    await page.setViewportSize({ width: 1000, height: 900 });
    await page.goto('/');
    await page.locator('#validationSummary').evaluate((element) => {
        element.classList.remove('hidden');
        element.textContent = Array.from({ length: 40 }, (_, index) => `Eksik alan ${index + 1}`).join('\n');
    });
    await page.locator('#auditReviewPanel').evaluate((element) => {
        element.classList.remove('hidden');
        element.textContent = Array.from({ length: 40 }, (_, index) => `Şüpheli alan ${index + 1}`).join('\n');
    });
    await page.locator('#xmlOutput').evaluate((element) => {
        element.textContent = Array.from({ length: 200 }, (_, index) => `<Item>${index + 1}</Item>`).join('\n');
    });
    await page.locator('.review-pane').scrollIntoViewIfNeeded();
    await expect(page.locator('.review-action-bar')).toBeInViewport();
    await expect(page.locator('#validationSummary')).toHaveCSS('overflow-y', 'auto');
    await expect(page.locator('#auditReviewPanel')).toHaveCSS('overflow-y', 'auto');
    await expect(page.locator('.review-action-bar')).toHaveCSS('position', 'sticky');
});

test('XML upload is rendered as text outside the iframe', async ({ page }) => {
    await page.goto('/');
    const xmlContent = '<ShippingInstruction><Notes><script>blocked()</script></Notes></ShippingInstruction>';
    await page.locator('#fileInput').setInputFiles({
        name: 'instruction.xml',
        mimeType: 'application/xml',
        buffer: Buffer.from(xmlContent),
    });
    await expect(page.locator('#documentTextPreview')).toBeVisible();
    await expect(page.locator('#documentTextPreview')).toHaveText(xmlContent);
    await expect(page.locator('#pdfIframe')).toBeHidden();
    await expect(page.locator('#documentTextPreview script')).toHaveCount(0);
});

test('batch upload failure remains visible to the user', async ({ page }) => {
    await page.route('**/api/batch/upload', async (route) => {
        await route.fulfill({
            status: 500,
            contentType: 'application/json',
            body: JSON.stringify({ detail: 'Denetimli test hatası' }),
        });
    });
    await page.goto('/');
    await page.locator('#fileInput').setInputFiles([
        {
            name: 'first.xml',
            mimeType: 'application/xml',
            buffer: Buffer.from('<a/>'),
        },
        {
            name: 'second.xml',
            mimeType: 'application/xml',
            buffer: Buffer.from('<b/>'),
        },
    ]);
    await page.locator('#startProcessingBtn').click();
    await expect(page.locator('#statusMessageBar')).toBeVisible();
    await expect(page.locator('#statusMessage')).toContainText('Denetimli test hatası');
});

test('real correction flow isolates the background and traps keyboard focus', async ({ page }) => {
    await page.route('**/api/upload-and-stream', async (route) => {
        const event = {
            status: 'DRAFT',
            session_id: '20260726_120000_000001',
            data: {
                xml_content: '<ShippingInstruction/>',
                structured_data: {
                    parties: [],
                    transport_plans: [],
                    equipment_list: [],
                    cargo_items: [],
                },
                missing_fields: [
                    {
                        field_path: 'parties[role=CZ].party_name',
                        field_label: 'Gönderici',
                    },
                ],
                validation_errors: [],
                cloud_review_available: false,
            },
        };
        await route.fulfill({
            status: 200,
            contentType: 'text/event-stream',
            body: `data: ${JSON.stringify(event)}\n\n`,
        });
    });
    await page.goto('/');
    await page.locator('#fileInput').setInputFiles({
        name: 'draft.xml',
        mimeType: 'application/xml',
        buffer: Buffer.from('<draft/>'),
    });
    await page.locator('#startProcessingBtn').click();
    await page.locator('#correctionOpenBtn').click();
    await expect(page.locator('main')).toHaveAttribute('aria-hidden', 'true');
    await expect(page.locator('[data-correction-field]')).toBeFocused();
    await page.keyboard.press('Shift+Tab');
    await expect(page.locator('#correctionSaveBtn')).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(page.locator('[data-correction-field]')).toBeFocused();
});

test('failed batch cancellation preserves the active queue and rejects replacement', async ({ page }) => {
    await page.route('**/api/batch/upload', async (route) => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
                batch_id: 'batch_test',
                rejected_count: 0,
                rejected_items: [],
            }),
        });
    });
    await page.route('**/api/batch/batch_test/stream', async (route) => {
        await route.fulfill({
            status: 200,
            contentType: 'text/event-stream',
            body: 'data: {"batch_id":"batch_test","percent":0,"completed_count":0,"total_count":2}\n\n',
        });
    });
    await page.route('**/api/batch/batch_test', async (route) => {
        await route.fulfill({
            status: 500,
            contentType: 'application/json',
            body: JSON.stringify({ detail: 'İptal reddedildi' }),
        });
    });
    await page.goto('/');
    await page.locator('#fileInput').setInputFiles([
        {
            name: 'first.xml',
            mimeType: 'application/xml',
            buffer: Buffer.from('<a/>'),
        },
        {
            name: 'second.xml',
            mimeType: 'application/xml',
            buffer: Buffer.from('<b/>'),
        },
    ]);
    await page.locator('#startProcessingBtn').click();
    await expect(page.locator('#statusMessage')).toContainText('tamamlanma olayı gelmeden kapandı');
    await page.locator('#fileInput').setInputFiles({
        name: 'replacement.xml',
        mimeType: 'application/xml',
        buffer: Buffer.from('<replacement/>'),
    });
    await expect(page.locator('#statusMessage')).toContainText('Toplu işlem iptal edilemedi');
    await expect(page.locator('#fileQueue')).toContainText('first.xml');
    await expect(page.locator('#fileQueue')).toContainText('second.xml');
    await expect(page.locator('#fileQueue')).not.toContainText('replacement.xml');
});
