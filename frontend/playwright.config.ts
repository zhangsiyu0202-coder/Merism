import { defineConfig, devices } from "@playwright/test"

/**
 * Playwright E2E config.
 *
 * Each test spins up the Vite dev server on port 5173 (see `webServer`) and
 * exercises critical user flows. Tests live under `e2e/` at the repo root
 * of the frontend package — colocated with the source they exercise.
 *
 * Run with: `pnpm test:e2e` or `pnpm test:e2e:ui` for the inspector.
 */
export default defineConfig({
    testDir: "./e2e",
    fullyParallel: true,
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 2 : 0,
    reporter: process.env.CI ? "github" : "list",

    use: {
        baseURL: "http://localhost:5173",
        trace: "retain-on-failure",
        screenshot: "only-on-failure",
        video: "retain-on-failure",
    },

    projects: [
        { name: "chromium", use: { ...devices["Desktop Chrome"] } },
        // Add firefox / webkit once the UI is stable; skipping initially to
        // keep CI green + fast.
    ],

    webServer: {
        command: "pnpm dev",
        url: "http://localhost:5173",
        reuseExistingServer: !process.env.CI,
        stdout: "ignore",
        stderr: "pipe",
    },
})
