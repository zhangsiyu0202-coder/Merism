import type { Meta, StoryObj } from "@storybook/react-vite"
import { useState } from "react"

import { OrderedList } from "~/lib/merism"

const meta: Meta<typeof OrderedList> = {
    title: "patterns/OrderedList",
    component: OrderedList,
    parameters: {
        docs: {
            description: {
                component:
                    "Numbered editorial list (1. 2. 3.). Read-only by default; supply `onChange` to make it editable. Edit mode turns each item into an auto-growing textarea with hover-reveal remove and an 'Add item' footer. Enter inserts a new row.",
            },
        },
        layout: "padded",
    },
}

export default meta
type Story = StoryObj<typeof meta>

const RESEARCH_OBJECTIVES = [
    "Understand what was confusing or difficult about the Target app's shopping flow.",
    "Understand what was intuitive or easy about the Target app's shopping flow.",
    "Understand how people interpret the Target UI's navigation metaphors.",
]

export const ReadOnly: Story = {
    args: {
        items: RESEARCH_OBJECTIVES,
    },
}

export const Editable: Story = {
    render: () => {
        function Demo(): JSX.Element {
            const [items, setItems] = useState(RESEARCH_OBJECTIVES)
            return <OrderedList items={items} onChange={setItems} />
        }
        return <Demo />
    },
}

export const Empty: Story = {
    render: () => {
        function Demo(): JSX.Element {
            const [items, setItems] = useState<string[]>([])
            return (
                <OrderedList
                    items={items}
                    onChange={setItems}
                    addLabel="Add objective"
                    placeholder="What question should this study answer?"
                />
            )
        }
        return <Demo />
    },
}

export const LongSentences: Story = {
    args: {
        items: [
            "Understand whether participants can complete the checkout flow without external guidance within 3 minutes, and identify the specific friction points that cause drop-off.",
            "Map the decision path participants take from the search results screen to adding an item to their cart, focusing on moments of hesitation that last longer than 4 seconds.",
            "Validate whether the new product categorization (clothing → accessories → shoes) matches users' mental models, or whether participants expect a different hierarchy.",
        ],
    },
}

export const ReadOnlyForced: Story = {
    args: {
        items: RESEARCH_OBJECTIVES,
        onChange: () => undefined,
        readonly: true,
    },
}
