import type { Meta, StoryObj } from "@storybook/react-vite"
import { Clock, Gauge, Users } from "lucide-react"

import { KpiCard, KpiGrid } from "~/lib/merism"

const meta: Meta<typeof KpiCard> = {
    title: "patterns/KpiCard",
    component: KpiCard,
    parameters: {
        docs: {
            description: {
                component:
                    "Editorial big-number card. Borderless variant is the default for dashboard masthead rows; card variant is for sub-sections where more structure helps scanning.",
            },
        },
        layout: "padded",
    },
}

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
    args: {
        label: "AVG SESSION TIME",
        value: "20:56",
        subtitle: "across 42 completed sessions",
        trend: { value: "+12%", direction: "up", label: "vs last month" },
        icon: <Clock className="h-3 w-3" />,
    },
}

export const Hero: Story = {
    args: {
        label: "COMPLETED SESSIONS",
        value: "142",
        size: "hero",
        accent: true,
        subtitle: "4 in the last 24 hours",
        trend: { value: "+24", direction: "up", label: "this week" },
        icon: <Users className="h-3 w-3" />,
    },
}

export const Card: Story = {
    args: {
        label: "COMPLETION RATE",
        value: "86%",
        variant: "card",
        subtitle: "of recruited participants finished",
        trend: { value: "-2pp", direction: "down", positive: false, label: "vs last week" },
    },
}

export const Compact: Story = {
    args: {
        label: "ASR LATENCY",
        value: "312ms",
        size: "title",
        variant: "card",
        trend: { value: "-18ms", direction: "down", label: "P95" },
        icon: <Gauge className="h-3 w-3" />,
    },
}

export const BounceRateInverted: Story = {
    args: {
        label: "DROP-OFF RATE",
        value: "8%",
        subtitle: "participants who abandoned mid-way",
        // Up arrow is BAD for drop-off rate — invert colour.
        trend: { value: "+2pp", direction: "up", positive: false },
    },
}

export const Flat: Story = {
    args: {
        label: "AVG TURNS PER SESSION",
        value: "18.4",
        size: "title",
        trend: { value: "0", direction: "flat", label: "stable" },
    },
}

export const DashboardRow: Story = {
    render: () => (
        <KpiGrid>
            <KpiCard
                label="COMPLETED SESSIONS"
                value="142"
                accent
                trend={{ value: "+24", direction: "up", label: "this week" }}
                icon={<Users className="h-3 w-3" />}
            />
            <KpiCard
                label="AVG SESSION TIME"
                value="20:56"
                subtitle="across 42 sessions"
                trend={{ value: "+12%", direction: "up" }}
                icon={<Clock className="h-3 w-3" />}
            />
            <KpiCard
                label="COMPLETION RATE"
                value="86%"
                trend={{
                    value: "-2pp",
                    direction: "down",
                    positive: false,
                }}
            />
            <KpiCard
                label="WINNER"
                value="Concept B"
                subtitle="highest purchase intent"
                trend={{ value: "+2.4×", direction: "up", label: "over A" }}
            />
        </KpiGrid>
    ),
}

export const DenseGridWithDividers: Story = {
    render: () => (
        <KpiGrid columns={4} withDividers>
            <KpiCard label="STUDIES" value="12" size="title" />
            <KpiCard label="SESSIONS" value="142" size="title" />
            <KpiCard label="HOURS" value="48.2" size="title" />
            <KpiCard label="AVG COVERAGE" value="72%" size="title" />
        </KpiGrid>
    ),
}
