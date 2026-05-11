import { expect, test } from "@playwright/test"

test.describe("smoke", () => {
    test("home page renders the design system showcase", async ({ page }) => {
        await page.goto("/")

        // Brand mark must render.
        await expect(page.getByText("Merism")).toBeVisible()

        // Primitive tab should be clickable + its contents appear.
        await page.getByRole("tab", { name: "Primitives" }).click()
        await expect(page.getByRole("button", { name: "Primary" })).toBeVisible()
    })
})
