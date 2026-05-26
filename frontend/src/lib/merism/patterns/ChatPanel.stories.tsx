import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";

import type { ChatMessage } from "~/lib/merism";
import { ChatPanel } from "~/lib/merism";

const meta: Meta<typeof ChatPanel> = {
  title: "patterns/ChatPanel",
  component: ChatPanel,
  parameters: {
    docs: {
      description: {
        component:
          "Shared chat column (Ask Merism, Outline Review drawer, Custom Report sidebar). Panel surface is hairline-ring + shadow (no solid border). AI bubble uses a backdrop-blur glass pane; user bubble uses soft-Coral. Input is an immersive rounded container with a 24px icon send button that flips to ink when there is content.",
      },
    },
    layout: "padded",
  },
};

export default meta;
type Story = StoryObj<typeof meta>;

const SEED_MESSAGES: ChatMessage[] = [
  {
    id: "1",
    role: "user",
    content:
      "What's the single strongest signal across the 42 interviews so far?",
  },
  {
    id: "2",
    role: "assistant",
    content:
      'Emotional warmth from Concept B beats Concept A on purchase intent by roughly 2.4×. Even participants who rated A as "more functional" said they\'d recommend B first (7 of 9).',
  },
  {
    id: "3",
    role: "user",
    content: "Any drop-off patterns worth flagging?",
  },
  {
    id: "4",
    role: "assistant",
    content:
      "Yes — the 18-24 age segment had a 14% higher abandonment rate on the third screener question (price sensitivity). Worth piloting a shorter variant.",
    streaming: true,
  },
];

function Wrapper({
  initial,
  ...rest
}: {
  initial: ChatMessage[];
  title?: string;
  emptyState?: string;
}): JSX.Element {
  const [messages, setMessages] = useState<ChatMessage[]>(initial);
  const [sending, setSending] = useState(false);

  async function handleSend(text: string): Promise<void> {
    setSending(true);
    setMessages((prev) => [
      ...prev,
      { id: String(Date.now()), role: "user", content: text },
    ]);
    // Fake assistant echo
    await new Promise((resolve) => setTimeout(resolve, 600));
    setMessages((prev) => [
      ...prev,
      {
        id: String(Date.now() + 1),
        role: "assistant",
        content:
          "Noted. I'll cross-reference that against the session transcripts and come back with a quote-backed pattern.",
      },
    ]);
    setSending(false);
  }

  return (
    <div className="h-[600px] w-[400px]">
      <ChatPanel
        {...rest}
        messages={messages}
        onSend={handleSend}
        isSending={sending}
      />
    </div>
  );
}

export const Default: Story = {
  render: () => <Wrapper title="Ask Merism" initial={SEED_MESSAGES} />,
};

export const Empty: Story = {
  render: () => (
    <Wrapper
      title="Ask Merism"
      initial={[]}
      emptyState="No messages yet. Ask about winners, drop-off, or individual sessions."
    />
  ),
};

export const NoTitle: Story = {
  render: () => (
    <Wrapper
      initial={[
        {
          id: "sys",
          role: "system",
          content: "Conversation started · 3 min ago",
        },
        {
          id: "a",
          role: "assistant",
          content:
            'I reread the last 12 transcripts. Three participants used the exact phrase "feels like a friend" about Concept B — none did for A.',
        },
      ]}
    />
  ),
};
