import { expect, test } from "@playwright/test"

test.describe("smoke", () => {
    test("app loads and redirects unauthenticated user to login", async ({ page }) => {
        await page.goto("/")

        // Auth guard redirects to login.
        await page.waitForURL(/\/login/, { timeout: 5000 })

        // Brand mark must render.
        await expect(page.locator("text=Merism").first()).toBeVisible()

        // Login form is functional.
        await expect(page.locator("#login-email")).toBeVisible()
        await expect(page.locator("#login-password")).toBeVisible()
        await expect(page.getByRole("button", { name: /continue/i })).toBeVisible()
    })
})
