import type { Meta, StoryObj } from "@storybook/react-vite"
import { Plus, Sparkles } from "lucide-react"

import { Button, PageHeading, Tag } from "~/lib/merism"

const meta: Meta<typeof PageHeading> = {
    title: "patterns/PageHeading",
    component: PageHeading,
    parameters: {
        docs: {
            description: {
                component:
                    "Editorial page header. Mono eyebrow · display title (44px Geist) · optional lede · trailing actions. Every main scene starts with one.",
            },
        },
    },
}

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
    args: {
        eyebrow: "Workspace",
        title: "Studies",
        lede: "Every qualitative study lives here — from research-brief draft to recruiting, live interviews, and closed analysis.",
        actions: (
            <Button iconLeft={<Plus className="h-4 w-4" />}>New study</Button>
        ),
    },
}

export const WithoutLede: Story = {
    args: {
        eyebrow: "Library",
        title: "Repository",
    },
}

export const StudyDetail: Story = {
    args: {
        eyebrow: "Study · b3f12a9d",
        title: "Why do power users churn after day 14?",
        lede: "Understand the usage patterns and psychological friction points that drive advanced users to cancel in the second week.",
        actions: (
            <div className="flex items-center gap-2">
                <Tag variant="accent">Recruiting</Tag>
                <Tag variant="outline">voice</Tag>
                <Button
                    variant="secondary"
                    iconLeft={<Sparkles className="h-4 w-4" />}
                >
                    Let AI review
                </Button>
            </div>
        ),
    },
}

export const MinimumViable: Story = {
    args: {
        title: "Ask Merism",
    },
}
