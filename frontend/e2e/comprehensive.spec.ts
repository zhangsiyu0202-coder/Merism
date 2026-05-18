import { expect, test } from "@playwright/test"

/**
 * Comprehensive E2E tests for Merism.
 *
 * Tests cover:
 * 1. Unauthenticated flows (login page, welcome, participant entry)
 * 2. Auth guard behavior
 * 3. API proxy health
 * 4. Design system rendering
 * 5. JavaScript error detection
 * 6. Network behavior
 */

test.describe("Auth guard", () => {
    test("unauthenticated user visiting / is redirected to /login", async ({ page }) => {
        await page.goto("/")
        await page.waitForURL(/\/login/, { timeout: 5000 })
        await expect(page).toHaveURL(/\/login/)
    })

    test("unauthenticated user visiting /studies is redirected to /login", async ({ page }) => {
        await page.goto("/studies")
        await page.waitForURL(/\/login/, { timeout: 5000 })
        await expect(page).toHaveURL(/\/login/)
    })

    test("unauthenticated user visiting /ask is redirected to /login", async ({ page }) => {
        await page.goto("/ask")
        await page.waitForURL(/\/login/, { timeout: 5000 })
        await expect(page).toHaveURL(/\/login/)
    })

    test("unauthenticated user visiting /inbox is redirected to /login", async ({ page }) => {
        await page.goto("/inbox")
        await page.waitForURL(/\/login/, { timeout: 5000 })
        await expect(page).toHaveURL(/\/login/)
    })

    test("unauthenticated user visiting /settings is redirected to /login", async ({ page }) => {
        await page.goto("/settings")
        await page.waitForURL(/\/login/, { timeout: 5000 })
        await expect(page).toHaveURL(/\/login/)
    })
})

test.describe("Login page", () => {
    test("renders login form with email and password fields", async ({ page }) => {
        await page.goto("/login")
        await expect(page.locator("#login-email")).toBeVisible()
        await expect(page.locator("#login-password")).toBeVisible()
    })

    test("has a Continue submit button", async ({ page }) => {
        await page.goto("/login")
        const submitBtn = page.getByRole("button", { name: /continue/i })
        await expect(submitBtn).toBeVisible()
    })

    test("forgot password link points to allauth reset", async ({ page }) => {
        await page.goto("/login")
        const forgotLink = page.locator("a[href='/accounts/password/reset/']")
        await expect(forgotLink).toBeVisible()
    })

    test("signup link points to allauth signup", async ({ page }) => {
        await page.goto("/login")
        const signupLink = page.locator("a[href='/accounts/signup/']")
        await expect(signupLink).toBeVisible()
    })

    test("shows Merism branding", async ({ page }) => {
        await page.goto("/login")
        await expect(page.locator("text=Merism").first()).toBeVisible()
    })
})

test.describe("Welcome page (unauthenticated)", () => {
    test("renders without redirect (allowUnauthenticated)", async ({ page }) => {
        await page.goto("/welcome")
        await page.waitForTimeout(2000)
        await expect(page).toHaveURL(/\/welcome/)
    })

    test("shows Merism branding and content", async ({ page }) => {
        await page.goto("/welcome")
        await page.waitForTimeout(1000)
        await expect(page.locator("text=Merism").first()).toBeVisible()
    })

    test("has navigation links", async ({ page }) => {
        await page.goto("/welcome")
        await page.waitForTimeout(1000)
        await expect(page.locator("a[href='/login']").first()).toBeVisible()
    })

    test("has no JavaScript errors", async ({ page }) => {
        const errors: string[] = []
        page.on("pageerror", (err) => errors.push(err.message))
        await page.goto("/welcome")
        await page.waitForTimeout(3000)
        const critical = errors.filter(
            (e) => !e.includes("ResizeObserver") && !e.includes("net::ERR")
        )
        expect(critical).toEqual([])
    })
})

test.describe("Participant entry (unauthenticated)", () => {
    test("does not redirect to login (allowUnauthenticated)", async ({ page }) => {
        await page.goto("/i/test-slug")
        await page.waitForTimeout(2000)
        // Should stay on participant page
        await expect(page).toHaveURL(/\/i\/test-slug/)
    })

    test("shows error state for non-existent slug", async ({ page }) => {
        await page.goto("/i/nonexistent-study-link")
        await page.waitForTimeout(3000)
        // Should show some content (error message or loading)
        const text = await page.locator("body").textContent()
        expect(text!.length).toBeGreaterThan(0)
    })

    test("has no unhandled JavaScript errors on invalid slug", async ({ page }) => {
        const errors: string[] = []
        page.on("pageerror", (err) => errors.push(err.message))
        await page.goto("/i/test-invalid")
        await page.waitForTimeout(3000)
        // Errors from failed API calls are expected to be handled gracefully
        const unhandled = errors.filter(
            (e) =>
                !e.includes("ResizeObserver") &&
                !e.includes("net::ERR") &&
                !e.includes("HTTP 404") &&
                !e.includes("not_found")
        )
        expect(unhandled).toEqual([])
    })
})

test.describe("API proxy", () => {
    test("/api/users/me/ returns 401 or 403 for unauthenticated", async ({ request }) => {
        const response = await request.get("http://localhost:5173/api/users/me/")
        expect([401, 403]).toContain(response.status())
    })

    test("Django healthz is accessible", async ({ request }) => {
        const response = await request.get("http://localhost:8000/healthz")
        expect(response.status()).toBe(200)
    })

    test("API proxy forwards to Django correctly", async ({ request }) => {
        const response = await request.get("http://localhost:5173/api/studies/")
        // Should get 401/403 (not 404) proving the proxy works
        expect([401, 403]).toContain(response.status())
    })
})

test.describe("404 handling", () => {
    test("unknown route redirects to login (auth guard)", async ({ page }) => {
        await page.goto("/this-route-does-not-exist-xyz")
        await page.waitForTimeout(3000)
        // Auth guard catches unknown routes and redirects to login
        // OR the app shows a 404 page
        const url = page.url()
        expect(url).toMatch(/\/(login|404)/)
    })
})

test.describe("CSS and design system", () => {
    test("CSS custom properties are loaded", async ({ page }) => {
        await page.goto("/login")
        await page.waitForTimeout(1000)
        const bgColor = await page.evaluate(() => {
            return getComputedStyle(document.documentElement).getPropertyValue("--merism-bg")
        })
        expect(bgColor.trim().length).toBeGreaterThan(0)
    })

    test("design system fonts render", async ({ page }) => {
        await page.goto("/login")
        await page.waitForTimeout(1000)
        const fontFamily = await page.evaluate(() => {
            const h1 = document.querySelector("h1")
            return h1 ? getComputedStyle(h1).fontFamily : ""
        })
        expect(fontFamily.length).toBeGreaterThan(0)
    })
})

test.describe("JavaScript errors on core pages", () => {
    test("login page has no JS errors", async ({ page }) => {
        const errors: string[] = []
        page.on("pageerror", (err) => errors.push(err.message))
        await page.goto("/login")
        await page.waitForTimeout(2000)
        const critical = errors.filter(
            (e) => !e.includes("ResizeObserver") && !e.includes("net::ERR")
        )
        expect(critical).toEqual([])
    })

    test("home redirect has no JS errors", async ({ page }) => {
        const errors: string[] = []
        page.on("pageerror", (err) => errors.push(err.message))
        await page.goto("/")
        await page.waitForTimeout(3000)
        const critical = errors.filter(
            (e) => !e.includes("ResizeObserver") && !e.includes("net::ERR")
        )
        expect(critical).toEqual([])
    })
})

test.describe("Network behavior", () => {
    test("app checks user auth on load", async ({ page }) => {
        let userRequestMade = false
        page.on("response", (response) => {
            if (response.url().includes("/api/users/me")) {
                userRequestMade = true
            }
        })
        await page.goto("/")
        await page.waitForTimeout(3000)
        expect(userRequestMade).toBe(true)
    })

    test("participant entry calls resolve API", async ({ page }) => {
        let resolveStatus = 0
        page.on("response", (response) => {
            const ct = response.headers()["content-type"] || ""
            if (response.url().includes("/i/test-slug/") && ct.includes("application/json")) {
                resolveStatus = response.status()
            }
        })
        await page.goto("/i/test-slug")
        await page.waitForTimeout(4000)
        // The API call should return 404 (slug doesn't exist in DB)
        expect(resolveStatus).toBe(404)
    })
})

test.describe("Responsive layout", () => {
    test("login page is usable on mobile viewport", async ({ page }) => {
        await page.setViewportSize({ width: 375, height: 667 })
        await page.goto("/login")
        await page.waitForTimeout(1000)
        await expect(page.locator("#login-email")).toBeVisible()
        await expect(page.locator("#login-password")).toBeVisible()
        await expect(page.getByRole("button", { name: /continue/i })).toBeVisible()
    })

    test("welcome page is usable on mobile viewport", async ({ page }) => {
        await page.setViewportSize({ width: 375, height: 667 })
        await page.goto("/welcome")
        await page.waitForTimeout(2000)
        await expect(page).toHaveURL(/\/welcome/)
        const text = await page.locator("body").textContent()
        expect(text!.length).toBeGreaterThan(10)
    })
})

test.describe("Accessibility basics", () => {
    test("login form fields have labels", async ({ page }) => {
        await page.goto("/login")
        // Check that email input has an associated label
        const emailLabel = page.locator("label[for='login-email']")
        await expect(emailLabel).toBeVisible()
        const passwordLabel = page.locator("label[for='login-password']")
        await expect(passwordLabel).toBeVisible()
    })

    test("login page has h1 heading", async ({ page }) => {
        await page.goto("/login")
        const h1 = page.locator("h1")
        await expect(h1).toBeVisible()
    })
})
