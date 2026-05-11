import { describe, expect, it } from "vitest"

import { StatusDot } from "~/lib/merism"
import { render, screen } from "~/test/render"

describe("StatusDot", () => {
    it("renders with the required accessible label", () => {
        render(<StatusDot status="ok" label="All healthy" />)
        expect(screen.getByRole("img", { name: "All healthy" })).toBeInTheDocument()
    })

    it.each([
        ["ok", "bg-merism-success"],
        ["warn", "bg-merism-warning"],
        ["error", "bg-merism-danger"],
        ["neutral", "bg-merism-text-muted"],
    ] as const)("applies the %s palette", (status, cls) => {
        render(<StatusDot status={status} label="x" />)
        expect(screen.getByRole("img", { name: "x" })).toHaveClass(cls)
    })
})
