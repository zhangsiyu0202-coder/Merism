import type { Meta, StoryObj } from "@storybook/react-vite"
import { useEffect, useState } from "react"

import { LiveSummaryPanel } from "~/lib/merism"

const meta: Meta<typeof LiveSummaryPanel> = {
    title: "patterns/LiveSummaryPanel",
    component: LiveSummaryPanel,
    parameters: {
        docs: {
            description: {
                component:
                    "Right-rail stats panel with 120 ms crossfade on value change. Four tones (neutral/ok/warn/danger) colour the value to signal health at a glance.",
            },
        },
        layout: "padded",
    },
}

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
    args: {
        title: "Outline summary",
        subtitle: "Updates on every edit.",
        stats: [
            { label: "Sections", value: 3 },
            { label: "Questions", value: 8 },
            { label: "Est. minutes", value: 12, hint: "~90s/Q" },
            { label: "Per concept", value: 5, tone: "ok", hint: "× rotation" },
        ],
    },
}

export const LiveUpdate: Story = {
    render: () => {
        function Demo(): JSX.Element {
            const [count, setCount] = useState(0)
            useEffect(() => {
                const id = window.setInterval(() => setCount((c) => c + 1), 1500)
                return () => window.clearInterval(id)
            }, [])
            return (
                <LiveSummaryPanel
                    title="Live metrics"
                    subtitle="Ticks every 1.5s to demo the crossfade."
                    stats={[
                        { label: "Sessions", value: count },
                        {
                            label: "Completion",
                            value: `${Math.min(100, count * 5)}%`,
                            tone: count > 10 ? "ok" : "neutral",
                        },
                        {
                            label: "Failing",
                            value: count > 15 ? 2 : 0,
                            tone: count > 15 ? "danger" : "neutral",
                        },
                    ]}
                />
            )
        }
        return <Demo />
    },
}

export const WithFooter: Story = {
    args: {
        title: "Scope split",
        stats: [
            { label: "Global", value: 4 },
            { label: "Per concept", value: 3 },
            { label: "Comparative", value: 1 },
        ],
        footer: (
            <div className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                Last updated · just now
            </div>
        ),
    },
}
