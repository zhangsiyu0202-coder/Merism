import path from "node:path"

import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// Merism frontend Vite config.
//
// Tailwind v4 via the Vite plugin — no postcss.config.js, no
// tailwind.config.js. Theme lives inside src/lib/merism/tokens/theme.css
// with `@theme` directives, read directly at compile time.
//
// Ships as a plain SPA served by the Django ASGI server in prod; Vite dev
// server proxies /api and /admin to Django on :8000.
export default defineConfig({
    plugins: [react(), tailwindcss()],
    resolve: {
        alias: {
            "~": path.resolve(__dirname, "src"),
        },
    },
    css: {
        // Pin PostCSS config discovery to THIS package so we don't
        // accidentally pick up a parent repo's postcss.config.js.
        postcss: { plugins: [] },
    },
    server: {
        port: 5173,
        strictPort: false,
        proxy: {
            "/api": { target: "http://localhost:8000", changeOrigin: true },
            "/accounts": { target: "http://localhost:8000", changeOrigin: true },
            "/ws": { target: "ws://localhost:8000", ws: true, changeOrigin: true },
        },
    },
    build: {
        outDir: "dist",
        emptyOutDir: true,
        sourcemap: true,
        // Reject builds that exceed 250 KB per chunk (gzipped ~80 KB). Keeps
        // the "克制的放大" aesthetic honest at runtime too.
        chunkSizeWarningLimit: 250,
        rollupOptions: {
            output: {
                // Split heavy third-party code into named vendor chunks so the
                // app shell stays <100 KB and browsers can cache/parallelise
                // the big deps independently. Rolldown (Vite 8) requires the
                // function signature — object literal is rejected at build.
                manualChunks(id: string): string | undefined {
                    if (!id.includes("node_modules")) return undefined
                    if (id.includes("/react/") || id.includes("/react-dom/")) return "vendor-react"
                    if (id.includes("echarts")) return "vendor-echarts"
                    if (id.includes("/kea")) return "vendor-kea"
                    if (id.includes("@radix-ui")) return "vendor-radix"
                    if (id.includes("@dnd-kit")) return "vendor-dnd"
                    if (id.includes("react-markdown") || id.includes("remark-")) return "vendor-markdown"
                    if (id.includes("/motion/")) return "vendor-motion"
                    if (id.includes("i18next") || id.includes("react-i18next")) return "vendor-i18n"
                    if (id.includes("@tanstack")) return "vendor-tanstack"
                    if (id.includes("lucide-react")) return "vendor-icons"
                    return "vendor-misc"
                },
            },
        },
    },
})
