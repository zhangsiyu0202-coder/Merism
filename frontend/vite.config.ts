import path from "node:path"

import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig, loadEnv } from "vite"

// Merism frontend Vite config.
//
// Tailwind v4 via the Vite plugin — no postcss.config.js, no
// tailwind.config.js. Theme lives inside src/lib/merism/tokens/theme.css
// with `@theme` directives, read directly at compile time.
//
// Ships as a plain SPA served by the Django ASGI server in prod; Vite dev
// server proxies /api and /admin to Django on a configurable local port.
export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, process.cwd(), "MERISM_")
    const vitePort = Number(env.MERISM_VITE_PORT || "5173")
    const backendHost = env.MERISM_BACKEND_HOST || "localhost"
    const backendPort = Number(env.MERISM_BACKEND_PORT || "8000")
    const backendHttp = `http://${backendHost}:${backendPort}`
    const backendWs = `ws://${backendHost}:${backendPort}`

    return {
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
            host: true,
            port: vitePort,
            strictPort: true,
            proxy: {
                "/api": {
                    target: backendHttp,
                    changeOrigin: true,
                    configure: (proxy) => {
                        proxy.on("error", (err) => {
                            console.error("\x1b[31m[proxy /api] 后端未就绪:\x1b[0m", err.message)
                        })
                    },
                },
                "/accounts": { target: backendHttp, changeOrigin: true },
                "/i/": {
                    target: backendHttp,
                    changeOrigin: true,
                    // Only proxy XHR/fetch requests (Accept: application/json),
                    // not browser navigations (Accept: text/html). This lets the
                    // SPA handle /i/:slug page rendering while API calls like
                    // fetch("/i/slug/") reach Django.
                    bypass(req) {
                        const accept = req.headers.accept || ""
                        if (accept.includes("text/html")) {
                            return req.url
                        }
                    },
                },
                "/ws": { target: backendWs, ws: true, changeOrigin: true },
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
    }
})
