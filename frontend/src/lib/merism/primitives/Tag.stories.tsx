import type { Meta, StoryObj } from "@storybook/react-vite"
import { CheckCircle2, Clock, Sparkles } from "lucide-react"

import { Tag } from "~/lib/merism"

const meta: Meta<typeof Tag> = {
    title: "primitives/Tag",
    component: Tag,
    parameters: {
        docs: {
            description: {
                component:
                    "Stripe-grade status chip. Sans + Capitalize + optional 6 px dot. Semantic variants come with the dot on by default; structural variants (neutral / outline / inverse / glass) render dot-less unless `withDot` is passed.",
            },
        },
        layout: "padded",
    },
}

export default meta
type Story = StoryObj<typeof meta>

// Single-variant showcases ---------------------------------------

export const Neutral: Story = { args: { children: "draft", variant: "neutral" } }
export const Accent: Story = { args: { children: "recruiting", variant: "accent" } }
export const Success: Story = { args: { children: "completed", variant: "success" } }
export const Warning: Story = { args: { children: "paused", variant: "warning" } }
export const Danger: Story = { args: { children: "abandoned", variant: "danger" } }
export const Info: Story = { args: { children: "scheduled", variant: "info" } }
export const Outline: Story = { args: { children: "voice", variant: "outline" } }
export const Glass: Story = {
    args: { children: "beta", variant: "glass" },
    parameters: {
        backgrounds: {
            default: "gradient",
            values: [
                {
                    name: "gradient",
                    value:
                        "linear-gradient(135deg, oklch(0.92 0.05 28), oklch(0.90 0.06 220))",
                },
            ],
        },
    },
}

// Full ladders --------------------------------------------------

export const AllVariants: Story = {
    render: () => (
        <div className="flex flex-wrap gap-2">
            <Tag variant="neutral">draft</Tag>
            <Tag variant="accent">recruiting</Tag>
            <Tag variant="success">completed</Tag>
            <Tag variant="warning">paused</Tag>
            <Tag variant="danger">abandoned</Tag>
            <Tag variant="info">scheduled</Tag>
            <Tag variant="outline">voice</Tag>
        </div>
    ),
}

export const SizeLadder: Story = {
    render: () => (
        <div className="flex items-center gap-3">
            <Tag variant="accent" size="sm">
                small
            </Tag>
            <Tag variant="accent" size="md">
                medium
            </Tag>
            <Tag variant="accent" size="lg">
                large
            </Tag>
        </div>
    ),
}

export const WithExplicitDot: Story = {
    render: () => (
        <div className="flex items-center gap-3">
            <Tag variant="neutral" withDot>
                neutral + dot
            </Tag>
            <Tag variant="outline" withDot>
                outline + dot
            </Tag>
            <Tag variant="info" withDot={false}>
                info − dot
            </Tag>
        </div>
    ),
}

export const WithIcon: Story = {
    render: () => (
        <div className="flex flex-wrap items-center gap-3">
            <Tag variant="accent" icon={<Sparkles className="h-3 w-3" />}>
                new
            </Tag>
            <Tag variant="success" icon={<CheckCircle2 className="h-3 w-3" />}>
                shipped
            </Tag>
            <Tag variant="warning" icon={<Clock className="h-3 w-3" />}>
                pending
            </Tag>
        </div>
    ),
}

// Glass on gradient backdrop — shows backdrop-blur effect ----

export const GlassOnGradient: Story = {
    render: () => (
        <div
            className="flex h-48 items-center justify-center gap-3 rounded-merism-lg p-8"
            style={{
                background:
                    "linear-gradient(135deg, oklch(0.85 0.08 28), oklch(0.86 0.1 220))",
            }}
        >
            <Tag variant="glass" size="md">
                beta
            </Tag>
            <Tag variant="glass" size="md" withDot>
                enterprise
            </Tag>
            <Tag variant="glass" size="lg" icon={<Sparkles className="h-3 w-3" />}>
                ai-powered
            </Tag>
        </div>
    ),
}

// Functional — ID / time / tokens use normal-case ----------------

export const IdStyle: Story = {
    render: () => (
        <div className="flex gap-2">
            <Tag variant="outline" case="normal">
                b3f12a9d
            </Tag>
            <Tag variant="outline" case="normal">
                session-47
            </Tag>
            <Tag variant="outline" case="normal" size="sm">
                2m 12s
            </Tag>
        </div>
    ),
}

export const Removable: Story = {
    args: {
        children: "pricing",
        variant: "outline",
        removable: true,
        onRemove: () => console.log("removed"),
    },
}

// Dense filter-chip row with counts -----------------------------

export const FilterRow: Story = {
    render: () => (
        <div className="flex flex-wrap gap-2">
            <Tag variant="neutral" size="sm">
                all
            </Tag>
            <Tag variant="accent" size="sm">
                active · 12
            </Tag>
            <Tag variant="outline" size="sm">
                voice · 8
            </Tag>
            <Tag variant="outline" size="sm">
                text · 4
            </Tag>
            <Tag variant="outline" size="sm">
                archived
            </Tag>
        </div>
    ),
}
