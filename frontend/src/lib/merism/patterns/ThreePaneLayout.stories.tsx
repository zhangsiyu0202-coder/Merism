import type { Meta, StoryObj } from "@storybook/react-vite"

import {
    LiveSummaryPanel,
    LogicCard,
    SectionLabel,
    ThreePaneLayout,
} from "~/lib/merism"

const meta: Meta<typeof ThreePaneLayout> = {
    title: "patterns/ThreePaneLayout",
    component: ThreePaneLayout,
    parameters: {
        docs: {
            description: {
                component:
                    "3-column configure-and-summarise shell. Left: nav rail. Middle: infinite-scroll card stack. Right: sticky LiveSummaryPanel. Collapses to a single column below 1280px.",
            },
        },
        layout: "fullscreen",
    },
}

export default meta
type Story = StoryObj<typeof meta>

export const Full: Story = {
    render: () => (
        <div className="p-8">
            <ThreePaneLayout
                left={
                    <nav className="flex flex-col gap-1">
                        <span className="px-3 pb-1 font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                            Sections
                        </span>
                        {["Warmup", "Core", "Closing"].map((t, i) => (
                            <a
                                key={t}
                                className={
                                    "rounded-merism-md px-3 py-2 text-merism-label " +
                                    (i === 0
                                        ? "bg-merism-accent-soft text-merism-text"
                                        : "text-merism-text-muted hover:bg-merism-bg-subtle hover:text-merism-text")
                                }
                                href="#"
                            >
                                {t}
                            </a>
                        ))}
                    </nav>
                }
                middle={
                    <div className="flex flex-col gap-4">
                        <SectionLabel>Warmup</SectionLabel>
                        <LogicCard
                            index={1}
                            title="Tell me about your role."
                        >
                            <p className="text-merism-body-sm text-merism-text-muted">
                                Builds rapport; captures context for later
                                probes.
                            </p>
                        </LogicCard>
                        <LogicCard
                            index={2}
                            title="What took you to our product recently?"
                        >
                            <p className="text-merism-body-sm text-merism-text-muted">
                                First-impression anchor.
                            </p>
                        </LogicCard>
                    </div>
                }
                right={
                    <LiveSummaryPanel
                        title="Outline summary"
                        subtitle="Recalculates as you edit."
                        stats={[
                            { label: "Sections", value: 3 },
                            { label: "Questions", value: 8 },
                            { label: "Est. minutes", value: 12, hint: "~90s/Q" },
                        ]}
                    />
                }
            />
        </div>
    ),
}

export const WithoutRight: Story = {
    render: () => (
        <div className="p-8">
            <ThreePaneLayout
                left={
                    <nav className="flex flex-col gap-1">
                        <span className="px-3 pb-1 font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                            Settings
                        </span>
                        <a className="rounded-merism-md px-3 py-2 text-merism-label bg-merism-accent-soft text-merism-text" href="#">
                            Profile
                        </a>
                        <a className="rounded-merism-md px-3 py-2 text-merism-label text-merism-text-muted" href="#">
                            Workspace
                        </a>
                    </nav>
                }
                middle={
                    <div className="rounded-merism-lg bg-merism-surface p-6 shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
                        <p className="text-merism-body text-merism-text">
                            Middle content when no right column is needed.
                        </p>
                    </div>
                }
            />
        </div>
    ),
}
