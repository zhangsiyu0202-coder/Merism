import type { Meta, StoryObj } from "@storybook/react-vite"
import { useState } from "react"

import { TabRail } from "~/lib/merism"

const meta: Meta<typeof TabRail> = {
    title: "patterns/TabRail",
    component: TabRail,
    parameters: {
        docs: {
            description: {
                component:
                    "Tabs-only strip. Pairs with PageHeading so the display title is editorial, and the tabs are their own row below. Used by Study detail (8 tabs) and the Report 4-panel view.",
            },
        },
    },
}

export default meta
type Story = StoryObj<typeof meta>

function Controlled({ tabs }: { tabs: { value: string; label: string }[] }) {
    const [active, setActive] = useState(tabs[0]?.value ?? "")
    return (
        <div className="flex flex-col gap-6">
            <TabRail tabs={tabs} activeTab={active} onTabChange={setActive} />
            <div className="rounded-merism-md border border-dashed border-merism-border p-6 text-merism-text-muted">
                Active tab: <span className="font-mono">{active}</span>
            </div>
        </div>
    )
}

export const StudyTabs: Story = {
    render: () => (
        <Controlled
            tabs={[
                { value: "brief", label: "Brief" },
                { value: "outline", label: "Outline" },
                { value: "screener", label: "Screener" },
                { value: "stimuli", label: "Stimuli" },
                { value: "recruit", label: "Recruit" },
                { value: "analysis", label: "Analysis" },
                { value: "report", label: "Report" },
                { value: "sessions", label: "Sessions" },
            ]}
        />
    ),
}

export const ReportPanels: Story = {
    render: () => (
        <Controlled
            tabs={[
                { value: "summary", label: "Summary" },
                { value: "highlights", label: "Highlights" },
                { value: "personas", label: "Personas" },
                { value: "tasks", label: "Tasks" },
            ]}
        />
    ),
}
