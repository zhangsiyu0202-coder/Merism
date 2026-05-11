import { describe, expect, it } from "vitest"

import {
    Card,
    CardContent,
    CardDescription,
    CardFooter,
    CardHeader,
    CardTitle,
} from "~/lib/merism"
import { render, screen } from "~/test/render"

describe("Card sub-parts", () => {
    it("renders a full card composition", () => {
        render(
            <Card>
                <CardHeader>
                    <CardTitle>Study alpha</CardTitle>
                    <CardDescription>Pricing research</CardDescription>
                </CardHeader>
                <CardContent>Body</CardContent>
                <CardFooter>Footer</CardFooter>
            </Card>,
        )
        expect(screen.getByRole("heading", { name: "Study alpha" })).toBeInTheDocument()
        expect(screen.getByText("Pricing research")).toBeInTheDocument()
        expect(screen.getByText("Body")).toBeInTheDocument()
        expect(screen.getByText("Footer")).toBeInTheDocument()
    })

    it("CardTitle defaults to an h3", () => {
        render(<CardTitle>Title</CardTitle>)
        expect(screen.getByRole("heading", { level: 3, name: "Title" })).toBeInTheDocument()
    })
})
