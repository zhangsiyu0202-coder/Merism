import { spawn, spawnSync } from "node:child_process"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const scriptDir = dirname(fileURLToPath(import.meta.url))
const frontendDir = join(scriptDir, "..")
const repoRoot = join(frontendDir, "..")
const pythonBin = join(repoRoot, ".venv/bin/python")
const managePy = join(repoRoot, "manage.py")
const clearPortsScript = join(repoRoot, "bin/clear-dev-ports.sh")

const children = []
let shuttingDown = false

function cleanup() {
    shuttingDown = true
    while (children.length > 0) {
        const child = children.pop()
        if (!child || child.killed) continue
        child.kill("SIGTERM")
    }
}

function waitForUrl(url, label) {
    return new Promise((resolve, reject) => {
        const deadline = Date.now() + 120_000
        const tick = async () => {
            try {
                const response = await fetch(url)
                if (response.ok) {
                    resolve()
                    return
                }
            } catch {
                // Keep polling until the process is ready.
            }
            if (Date.now() > deadline) {
                reject(new Error(`Timed out waiting for ${label} at ${url}`))
                return
            }
            setTimeout(() => {
                void tick()
            }, 500)
        }
        void tick()
    })
}

function spawnManaged(
    command,
    args,
    options,
){
    const child = spawn(command, args, {
        cwd: options.cwd,
        env: options.env,
        stdio: "inherit",
    })
    children.push(child)
    child.on("exit", (code, signal) => {
        if (shuttingDown) {
            return
        }
        console.error(`[e2e] ${options.label} exited unexpectedly (${code ?? signal})`)
        cleanup()
        process.exit(typeof code === "number" && code !== 0 ? code : 1)
    })
    return child
}

async function main() {
    const clear = spawnSync("bash", [clearPortsScript, "8000", "5173"], {
        cwd: repoRoot,
        stdio: "inherit",
    })
    if (clear.status !== 0) {
        process.exit(clear.status ?? 1)
    }

    spawnManaged(
        pythonBin,
        [managePy, "runserver", "8000"],
        {
            cwd: repoRoot,
            env: {
                ...process.env,
                DJANGO_SETTINGS_MODULE: "merism.settings.dev",
            },
            label: "Django",
        },
    )

    spawnManaged(
        "pnpm",
        ["dev"],
        {
            cwd: frontendDir,
            env: process.env,
            label: "Vite",
        },
    )

    await Promise.all([
        waitForUrl("http://127.0.0.1:8000/healthz", "Django health"),
        waitForUrl("http://127.0.0.1:5173/", "Vite dev server"),
    ])

    process.on("SIGINT", () => {
        cleanup()
        process.exit(130)
    })
    process.on("SIGTERM", () => {
        cleanup()
        process.exit(143)
    })

    await new Promise(() => {
        // Keep the launcher alive until Playwright terminates the server.
    })
}

void main().catch((error) => {
    console.error(error)
    cleanup()
    process.exit(1)
})
