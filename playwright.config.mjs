import { defineConfig } from '@playwright/test';

export default defineConfig({
    testDir: './tests/browser',
    timeout: 30000,
    use: {
        baseURL: 'http://127.0.0.1:8000',
        trace: 'retain-on-failure',
    },
    webServer: {
        command: '.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000',
        url: 'http://127.0.0.1:8000',
        reuseExistingServer: true,
        timeout: 120000,
    },
});
