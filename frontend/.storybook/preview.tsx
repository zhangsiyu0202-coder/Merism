import { Provider as TooltipProvider } from "@radix-ui/react-tooltip"
import type { Preview } from "@storybook/react-vite"
import { type ReactNode } from "react"

import "../src/globals.css"

const preview: Preview = {
    parameters: {
        backgrounds: {
            default: "merism-paper",
            values: [
                { name: "merism-paper", value: "oklch(0.98 0.005 80)" },
                { name: "merism-ink", value: "oklch(0.18 0.012 40)" },
            ],
        },
        layout: "padded",
        controls: {
            matchers: {
                color: /(background|color)$/i,
                date: /Date$/i,
            },
        },
    },
    decorators: [
        (Story: () => ReactNode) => (
            <TooltipProvider delayDuration={200}>
                <div className="min-h-screen bg-merism-bg p-8 font-sans text-merism-text">
                    <Story />
                </div>
            </TooltipProvider>
        ),
    ],
}

export default preview
