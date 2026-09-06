import { test, expect } from '@playwright/test';

test.describe('DriftGuard-X Web Console', () => {
  test('Editorial landing page exposes the core narrative', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'DRIFTGUARDX.' })).toBeVisible();
    await expect(page.getByRole('heading', { name: /An AI agent that works inside your data pipelines/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /DISCOVER MORE/i })).toBeVisible();
  });

  test('Editorial landing remains composed on a mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'DRIFTGUARDX.' })).toBeVisible();
    const dimensions = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
    }));
    expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport + 10);
  });

  test('Overview page loads with correct title and navigation', async ({ page }) => {
    // We mock the API call so the test passes regardless of backend state
    await page.route('**/v1/telemetry/quality', async route => {
      const json = {
        metrics: {
          total_traces: 100,
          total_spans: 500,
          total_errors: 2,
          ingestion_lag_ms: 45
        }
      };
      await route.fulfill({ json });
    });

    await page.route('**/v1/providers/', async route => {
      const json = {
        "OpenAI": { cost_per_1k: 0.01, status: "healthy" }
      };
      await route.fulfill({ json });
    });

    await page.goto('/dashboard');

    // Check title
    await expect(page).toHaveTitle(/DriftGuard-X/);
    await expect(page.getByRole('heading', { name: 'Overview' })).toBeVisible();

    // Check navigation links
    await expect(page.getByRole('link', { name: 'Runs' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Replay Lab' })).toBeVisible();
  });

  test('Runs page lists mock runs correctly', async ({ page }) => {
    await page.route(/\/v1\/runs\?skip=0&limit=20$/, async route => {
      const json = {
        runs: [
          {
            id: 'mock-run-id-1234',
            status: 'failed',
            created_at: new Date().toISOString(),
            total_latency_ms: 1500,
            total_cost_usd: 0.05,
            reliability_score: 0.4,
            evidence_class: 'SYNTHETIC_SIMULATION'
          }
        ],
        total: 1,
        page: 1,
        page_size: 20
      };
      await route.fulfill({ json });
    });

    await page.goto('/runs');
    await expect(page.getByRole('heading', { name: 'Runs' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'mock...' })).toBeVisible();
    await expect(page.getByText('failed')).toBeVisible();
    await expect(page.getByText('SYNTHETIC SIMULATION', { exact: true })).toBeVisible();
  });

  test('Replay Lab handles form submission', async ({ page }) => {
    await page.goto('/replay');
    await expect(page.getByRole('heading', { name: 'Replay Lab' })).toBeVisible();

    const runIdInput = page.getByPlaceholder('e.g. 123e4567-e89b-12d3-a456-426614174000');
    await runIdInput.fill('test-run-123');

    // Route for the replay creation
    await page.route('**/v1/runs/*/replays', async route => {
      await route.fulfill({ json: { status: 'enqueued', job_id: 'job-999' } });
    });

    await page.getByRole('button', { name: 'Trigger Replay Job' }).click();
    
    await expect(page.getByText('Replay Job Enqueued')).toBeVisible();
  });
});
