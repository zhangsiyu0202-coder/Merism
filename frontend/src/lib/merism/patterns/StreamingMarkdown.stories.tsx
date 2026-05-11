import type { Meta, StoryObj } from "@storybook/react-vite"
import { useEffect, useState } from "react"

import { StreamingMarkdown } from "~/lib/merism"

const meta: Meta<typeof StreamingMarkdown> = {
    title: "patterns/StreamingMarkdown",
    component: StreamingMarkdown,
    parameters: {
        docs: {
            description: {
                component:
                    "Renders LLM output as Merism-styled Markdown. GFM tables + lists + blockquotes + code. `streaming={true}` adds a blinking cursor for in-progress responses.",
            },
        },
        layout: "padded",
    },
}

export default meta
type Story = StoryObj<typeof meta>

const SAMPLE_RICH = `## Key findings

Participants consistently valued **emotional warmth** over functional
efficiency. This is the headline observation from 12 interviews.

### Themes

1. **Pricing concerns** — 7 of 12 mentioned the monthly cost is too high.
2. **Onboarding friction** — 5 got stuck on the third screen.
3. **Feature discoverability** — most couldn't find the export option.

> "I don't know where anything is. It's like every button is a mystery." — P7

#### Tasks extracted

| Priority | Task                                  | Source |
|----------|---------------------------------------|--------|
| **P0**   | Rework pricing page                   | P3, P7 |
| **P1**   | Simplify onboarding step 3            | P2     |
| **P2**   | Surface export action in main menu    | P5     |

---

Code examples are rendered in-place:

\`\`\`typescript
function analyze(session: Session) {
    return session.quotes.filter(q => q.importance > 0.7)
}
\`\`\`

Inline \`code\` keeps the mono treatment.
`

export const Rich: Story = {
    args: { text: SAMPLE_RICH },
}

export const Streaming: Story = {
    render: () => {
        function Demo(): JSX.Element {
            const [text, setText] = useState("")
            useEffect(() => {
                let i = 0
                const id = window.setInterval(() => {
                    i = Math.min(SAMPLE_RICH.length, i + 12)
                    setText(SAMPLE_RICH.slice(0, i))
                    if (i >= SAMPLE_RICH.length) window.clearInterval(id)
                }, 30)
                return () => window.clearInterval(id)
            }, [])
            return (
                <StreamingMarkdown
                    text={text}
                    streaming={text.length < SAMPLE_RICH.length}
                />
            )
        }
        return <Demo />
    },
}

export const Plain: Story = {
    args: {
        text:
            "A single paragraph of plain prose, no markdown, renders as merism body text with proper leading.",
    },
}
