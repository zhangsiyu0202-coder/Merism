import type { Meta, StoryObj } from "@storybook/react-vite"
import { useState } from "react"

import { OrderedList, SettingsSection } from "~/lib/merism"

const meta: Meta<typeof SettingsSection> = {
    title: "patterns/SettingsSection",
    component: SettingsSection,
    parameters: {
        docs: {
            description: {
                component:
                    "Editable section for a settings-style page (Project settings, Profile, Workspace, etc.). H2 heading + optional description + optional Edit button + any body. Stack multiple sections with generous vertical gap.",
            },
        },
        layout: "padded",
    },
}

export default meta
type Story = StoryObj<typeof meta>

const OBJECTIVES = [
    "Understand what was confusing or difficult about the Target app's shopping flow.",
    "Understand what was intuitive or easy about the Target app's shopping flow.",
    "Understand how people interpret the Target UI's navigation metaphors.",
]

export const ProjectDetails: Story = {
    render: () => (
        <SettingsSection title="Project details" onEdit={() => console.log("edit")}>
            <p className="text-merism-body text-merism-text">
                DEMO - Usability Test (Phone Cord Search)
            </p>
            <p className="text-merism-body-sm text-merism-text-muted">Outset</p>
        </SettingsSection>
    ),
}

export const ResearchObjectives: Story = {
    render: () => (
        <SettingsSection
            title="Research objectives"
            description="What questions does this study aim to answer?"
            onEdit={() => console.log("edit")}
        >
            <OrderedList items={OBJECTIVES} />
        </SettingsSection>
    ),
}

// This is the showcase: combined "Project settings" page archetype.
export const FullSettingsPage: Story = {
    render: () => {
        function Demo(): JSX.Element {
            const [objectives, setObjectives] = useState(OBJECTIVES)
            const [editingObjectives, setEditingObjectives] = useState(false)

            return (
                <div className="mx-auto flex max-w-3xl flex-col gap-[var(--spacing-merism-section-y)]">
                    <h1 className="text-merism-headline font-display font-[450] text-merism-text">
                        Project settings
                    </h1>

                    <SettingsSection title="Project details" onEdit={() => {}}>
                        <p className="text-merism-body text-merism-text">
                            DEMO - Usability Test (Phone Cord Search)
                        </p>
                        <p className="text-merism-body-sm text-merism-text-muted">
                            Outset
                        </p>
                    </SettingsSection>

                    <SettingsSection
                        title="Research objectives"
                        onEdit={
                            editingObjectives
                                ? undefined
                                : () => setEditingObjectives(true)
                        }
                    >
                        <OrderedList
                            items={objectives}
                            onChange={editingObjectives ? setObjectives : undefined}
                        />
                        {editingObjectives && (
                            <div className="mt-4 flex gap-2">
                                <button
                                    type="button"
                                    onClick={() => setEditingObjectives(false)}
                                    className="rounded-merism-md bg-merism-text px-3 py-1.5 text-[13px] font-medium text-merism-surface"
                                >
                                    Save
                                </button>
                                <button
                                    type="button"
                                    onClick={() => {
                                        setObjectives(OBJECTIVES)
                                        setEditingObjectives(false)
                                    }}
                                    className="rounded-merism-md px-3 py-1.5 text-[13px] font-medium text-merism-text-muted hover:bg-[color:rgba(15,23,42,0.04)] hover:text-merism-text"
                                >
                                    Cancel
                                </button>
                            </div>
                        )}
                    </SettingsSection>
                </div>
            )
        }
        return <Demo />
    },
}
