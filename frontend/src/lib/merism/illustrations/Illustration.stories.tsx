import type { Meta, StoryObj } from "@storybook/react-vite"

import { ILLUSTRATIONS, Illustration } from "~/lib/merism"

const meta: Meta<typeof Illustration> = {
    title: "illustrations/Illustration",
    component: Illustration,
    parameters: {
        docs: {
            description: {
                component:
                    "Monochrome hand-drawn SVGs from the Notioly pack. Each illustration's stroke/fill is `currentColor` so it inherits any `text-*` class on the wrapper. Ideal for empty states, 404, onboarding, success celebrations — anywhere the UI needs a human touch without colour clashing with the brand.",
            },
        },
        layout: "padded",
    },
}

export default meta
type Story = StoryObj<typeof meta>

const NAMES = Object.keys(ILLUSTRATIONS) as (keyof typeof ILLUSTRATIONS)[]

export const Catalog: Story = {
    render: () => (
        <div className="grid grid-cols-2 gap-8 sm:grid-cols-3 lg:grid-cols-4">
            {NAMES.map((name) => (
                <div
                    key={name}
                    className="flex flex-col items-center gap-3 rounded-merism-lg bg-merism-surface p-6 shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]"
                >
                    <Illustration name={name} size="md" className="text-merism-text" />
                    <span className="font-mono text-merism-caption uppercase tracking-merism-caps-tight text-merism-text-muted">
                        {name}
                    </span>
                </div>
            ))}
        </div>
    ),
}

export const SizeLadder: Story = {
    render: () => (
        <div className="flex items-end gap-6">
            {(["sm", "md", "lg", "xl"] as const).map((size) => (
                <div key={size} className="flex flex-col items-center gap-3">
                    <Illustration
                        name="planning-a-trip"
                        size={size}
                        className="text-merism-text"
                    />
                    <span className="font-mono text-merism-caption uppercase tracking-merism-caps-tight text-merism-text-muted">
                        {size}
                    </span>
                </div>
            ))}
        </div>
    ),
}

export const Theming: Story = {
    render: () => (
        <div className="grid grid-cols-3 gap-8">
            <div className="flex flex-col items-center gap-3">
                <Illustration name="peace" size="lg" className="text-merism-text" />
                <span className="text-merism-caption text-merism-text-muted">
                    text-merism-text (default ink)
                </span>
            </div>
            <div className="flex flex-col items-center gap-3">
                <Illustration name="peace" size="lg" className="text-merism-accent" />
                <span className="text-merism-caption text-merism-text-muted">
                    text-merism-accent (Coral)
                </span>
            </div>
            <div className="flex flex-col items-center gap-3">
                <Illustration
                    name="peace"
                    size="lg"
                    className="text-merism-text-subtle"
                />
                <span className="text-merism-caption text-merism-text-muted">
                    text-merism-text-subtle (muted)
                </span>
            </div>
        </div>
    ),
}

export const InEmptyState: Story = {
    render: () => (
        <div className="mx-auto max-w-md flex flex-col items-center gap-6 rounded-merism-lg bg-merism-surface p-12 text-center shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
            <Illustration
                name="planning-a-trip"
                size="xl"
                className="text-merism-text"
            />
            <div className="flex flex-col gap-2">
                <h2 className="font-display text-merism-h2 font-[450] text-merism-text">
                    Start your first study
                </h2>
                <p className="text-merism-body text-merism-text-muted">
                    Set a goal, build an outline, invite participants — every piece
                    of research begins here.
                </p>
            </div>
            <button
                type="button"
                className="rounded-merism-md bg-merism-accent px-5 py-2 text-merism-body-sm font-medium text-merism-accent-ink hover:bg-merism-accent-hover"
            >
                Create a study
            </button>
        </div>
    ),
}
