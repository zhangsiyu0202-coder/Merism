import type { Meta, StoryObj } from "@storybook/react-vite"
import { useState } from "react"

import { Button, ChatPanel, Sidebar } from "~/lib/merism"

const meta: Meta<typeof Sidebar> = {
    title: "patterns/Sidebar",
    component: Sidebar,
    parameters: {
        docs: {
            description: {
                component:
                    "Non-modal right-side drawer (200ms slide). Hosts the AI Outline Review sidebar and the Custom Report sidebar. Main content stays interactive — this is the critical difference from a modal Dialog.",
            },
        },
    },
}

export default meta
type Story = StoryObj<typeof meta>

function Controlled({ title }: { title: string }) {
    const [open, setOpen] = useState(true)
    return (
        <div className="relative flex h-[520px] w-full items-start gap-6">
            <div className="flex-1 rounded-merism-lg bg-merism-surface ring-1 ring-[color:var(--merism-hairline)] shadow-merism-card p-6">
                <h2 className="font-display text-[length:var(--text-merism-title)] font-[500] text-merism-text">
                    Main content (still interactive)
                </h2>
                <p className="mt-2 max-w-prose text-merism-body text-merism-text-muted">
                    The sidebar lives over the right edge of the viewport but it's
                    non-modal — click here, scroll here, the sidebar stays.
                </p>
                <div className="mt-4">
                    <Button onClick={() => setOpen(true)}>Reopen sidebar</Button>
                </div>
            </div>

            <Sidebar
                open={open}
                onOpenChange={setOpen}
                title={title}
                description="Conversational · you approve each change"
            >
                <ChatPanel
                    messages={[
                        {
                            id: "1",
                            role: "assistant",
                            content:
                                "I noticed Q3 is quite a leading question. Want me to suggest a neutral rephrasing?",
                        },
                    ]}
                    onSend={() => {}}
                    placeholder="Ask me to review anything specific…"
                    className="min-h-0 flex-1 border-0 shadow-none"
                />
            </Sidebar>
        </div>
    )
}

export const OutlineReview: Story = {
    render: () => <Controlled title="Let AI review your outline" />,
}

export const CustomReport: Story = {
    render: () => <Controlled title="Custom report" />,
}
