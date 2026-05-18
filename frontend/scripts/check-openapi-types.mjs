import { mkdtempSync, readFileSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"
import { execFileSync } from "node:child_process"

const scriptDir = dirname(fileURLToPath(import.meta.url))
const frontendDir = join(scriptDir, "..")
const generatedPath = join(frontendDir, "src/generated/api.ts")
const openApiPath = join(frontendDir, "src/generated/openapi.json")
const tempDir = mkdtempSync(join(tmpdir(), "merism-openapi-types-"))
const tempPath = join(tempDir, "api.ts")

try {
    execFileSync(
        "pnpm",
        [
            "exec",
            "openapi-typescript",
            "src/generated/openapi.json",
            "-o",
            tempPath,
            "--enum",
            "--alphabetize",
        ],
        {
            cwd: frontendDir,
            stdio: "inherit",
        },
    )

    const current = readFileSync(generatedPath, "utf8")
    const regenerated = readFileSync(tempPath, "utf8")
    if (current !== regenerated) {
        console.error("frontend/src/generated/api.ts is stale.")
        console.error(`Regenerate it from ${openApiPath} with: make codegen`)
        process.exitCode = 1
    }
} finally {
    rmSync(tempDir, { recursive: true, force: true })
}
