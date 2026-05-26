import { useActions, useValues } from "kea";
import { useTranslation } from "react-i18next";

import { askLogic } from "~/features/ask/askLogic";
import { ChatPanel, type ChatMessage } from "~/lib/merism";
import type { AskMerismMessage } from "~/features/ask/types";

/**
 * AskSidePanel — in-panel version of Ask Merism chat.
 *
 * Reuses the existing askLogic + ChatPanel but fits into a narrow
 * slide-out container instead of the full-page AskPage layout.
 */
export function AskSidePanel(): JSX.Element {
  const { t } = useTranslation();
  const { messages, isSending } = useValues(askLogic);
  const { askQuestion } = useActions(askLogic);

  const chatMessages: ChatMessage[] = messages.map(toChatMessage);

  return (
    <ChatPanel
      messages={chatMessages}
      onSend={askQuestion}
      isSending={isSending}
      placeholder={t("ask.placeholder")}
      emptyState={
        <div className="flex flex-col items-center gap-3 text-center px-4">
          <p className="text-merism-body-sm text-merism-text-muted">
            {t("ask.empty_hero_title")}
          </p>
        </div>
      }
    />
  );
}

function toChatMessage(m: AskMerismMessage): ChatMessage {
  return {
    id: m.id,
    role: m.role === "user" ? "user" : "assistant",
    content: m.content ?? "",
    streaming: Boolean(m.streaming),
  };
}
