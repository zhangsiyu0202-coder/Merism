import path from "node:path"

import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"

// Vitest config kept separate from vite.config.ts so that (a) the test
// toolchain can be tuned without affecting production builds, (b) Storybook
// Vitest integration has a single import target.
export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            "~": path.resolve(__dirname, "src"),
        },
    },
    test: {
        environment: "jsdom",
        globals: true,
        setupFiles: ["./src/test/setup.ts"],
        css: false,
        include: ["src/**/*.{test,spec}.{ts,tsx}"],
        exclude: ["node_modules", "dist", ".storybook"],
        // Tests should be fast. Anything > 5s is almost certainly a bug
        // (infinite render, forgotten await, unmocked fetch).
        testTimeout: 5000,
        coverage: {
            provider: "v8",
            reporter: ["text", "html", "json-summary"],
            include: ["src/**/*.{ts,tsx}"],
            exclude: [
                "src/**/*.{test,spec,stories}.{ts,tsx}",
                "src/**/index.ts",
                "src/test/**",
                "src/main.tsx",
            ],
            thresholds: {
                lines: 80,
                functions: 80,
                statements: 80,
                branches: 70,
            },
        },
    },
})
