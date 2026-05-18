import { defineConfig, devices } from "@playwright/test"

/**
 * Playwright E2E config.
 *
 * Each test spins up the Django + Vite dev servers via `webServer` and
 * exercises critical user flows against both layers together.
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
        command: "pnpm e2e:server",
        url: "http://localhost:5173",
        reuseExistingServer: false,
        stdout: "ignore",
        stderr: "pipe",
    },
})
