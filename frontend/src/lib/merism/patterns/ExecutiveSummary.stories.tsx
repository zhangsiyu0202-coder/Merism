import type { Meta, StoryObj } from "@storybook/react-vite"

import { ExecutiveSummary } from "~/lib/merism"

const meta: Meta<typeof ExecutiveSummary> = {
    title: "patterns/ExecutiveSummary",
    component: ExecutiveSummary,
    parameters: {
        docs: {
            description: {
                component:
                    "Narrative hero block for research reports. The summary body is rendered in Geist (font-display) at subtitle size, with a max-width of 700 px so the measure stays readable. Pass `isLoading` to render a shimmer skeleton while the LLM streams.",
            },
        },
        layout: "padded",
    },
}

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
    args: {
        eyebrow: "EXECUTIVE SUMMARY · MAY 10",
        summary:
            "Participants consistently valued Concept B's emotional warmth over Concept A's functional efficiency. Purchase intent for B was 2.4× higher across first-time buyers, and even among participants who rated A as \"more useful,\" 7 of 9 said they would recommend B to a friend first.",
        byline: "Generated from 42 interviews",
        updatedAt: "Updated 3 min ago",
    },
}

export const WithTitle: Story = {
    args: {
        eyebrow: "EXECUTIVE SUMMARY · Q2 2026",
        title: "Emotional warmth beats functional efficiency",
        summary:
            "B wins on every emotional dimension we scored — appeal, memorability, recommendation — while A only leads on perceived usefulness. This suggests the category is maturing past the feature-comparison stage; users are now optimising for identification.",
        byline: "Generated from 42 interviews",
        updatedAt: "Updated 3 min ago",
    },
}

export const Loading: Story = {
    args: {
        eyebrow: "EXECUTIVE SUMMARY · MAY 10",
        summary: "",
        isLoading: true,
        byline: "Generating narrative…",
    },
}

export const NoAccent: Story = {
    args: {
        eyebrow: "RESEARCH NOTES",
        summary:
            "This is a reduced variant — no accent rule on the left. Use when the block appears mid-page or inside another framed container (e.g. a LogicCard body) where a second rule would compete visually.",
        byline: "Internal note",
        accent: false,
    },
}

export const NoEyebrow: Story = {
    args: {
        summary:
            "Just the prose. Use when the surrounding page already establishes the ``EXECUTIVE SUMMARY`` context (e.g. in a dedicated ``/report`` route) and a second eyebrow would be redundant.",
        byline: "Generated from 42 interviews",
        updatedAt: "3 min ago",
    },
}
