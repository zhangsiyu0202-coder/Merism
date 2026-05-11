import type { Meta, StoryObj } from "@storybook/react-vite"
import { Plus, Share } from "lucide-react"
import { useState } from "react"

import { Button, PageTopBar } from "~/lib/merism"

const meta: Meta<typeof PageTopBar> = {
    title: "patterns/PageTopBar",
    component: PageTopBar,
    parameters: {
        docs: {
            description: {
                component:
                    "Every scene's masthead. Title + actions + optional TabRail underneath. Gives the app a single consistent shape across Home / Studies / Ask / Inbox / Repository / Decisions.",
            },
        },
        layout: "padded",
    },
}

export default meta
type Story = StoryObj<typeof meta>

export const TitleOnly: Story = {
    args: {
        title: "Home",
    },
}

export const WithActions: Story = {
    args: {
        title: "Studies",
        actions: (
            <Button iconLeft={<Plus className="h-4 w-4" />} size="sm">
                New study
            </Button>
        ),
    },
}

export const WithTabs: Story = {
    render: () => {
        function Demo(): JSX.Element {
            const [tab, setTab] = useState("overview")
            return (
                <PageTopBar
                    title="Home"
                    actions={
                        <Button
                            iconLeft={<Plus className="h-4 w-4" />}
                            size="sm"
                        >
                            New study
                        </Button>
                    }
                    tabs={[
                        { value: "overview", label: "Overview" },
                        { value: "activity", label: "Activity" },
                        { value: "drafts", label: "Drafts" },
                    ]}
                    activeTab={tab}
                    onTabChange={setTab}
                />
            )
        }
        return <Demo />
    },
}

export const Full: Story = {
    render: () => {
        function Demo(): JSX.Element {
            const [tab, setTab] = useState("all")
            return (
                <PageTopBar
                    eyebrow="Workspace · Merism"
                    title="Studies"
                    lede="Every qualitative study lives here — from research-brief draft to recruiting, live interviews, and closed analysis."
                    actions={
                        <div className="flex gap-2">
                            <Button
                                variant="secondary"
                                iconLeft={<Share className="h-4 w-4" />}
                                size="sm"
                            >
                                Share
                            </Button>
                            <Button
                                iconLeft={<Plus className="h-4 w-4" />}
                                size="sm"
                            >
                                New study
                            </Button>
                        </div>
                    }
                    tabs={[
                        { value: "all", label: "All" },
                        { value: "active", label: "Active" },
                        { value: "drafts", label: "Drafts" },
                        { value: "archived", label: "Archived" },
                    ]}
                    activeTab={tab}
                    onTabChange={setTab}
                />
            )
        }
        return <Demo />
    },
}
