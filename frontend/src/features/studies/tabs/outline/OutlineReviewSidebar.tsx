import { useActions, useValues } from "kea";
import { Check, X } from "lucide-react";

import {
  Button,
  ChatPanel,
  Sidebar,
  Tag,
  type ChatMessage,
} from "~/lib/merism";

import { outlineReviewLogic } from "./outlineReviewLogic";
import type { OutlineOp, OutlineReviewChatMessage } from "./types";

/**
 * Outline Review sidebar — opens when the researcher clicks "✨ Let AI
 * review" on the Outline tab. Conversational per PRODUCT.md §5.1.
 *
 * Each assistant turn may include ``proposed_changes``. The researcher
 * clicks Accept / Skip per change. Accept dispatches to the Outline tab
 * callback ``onApplyChanges`` which owns the actual guide mutation.
 */
export interface OutlineReviewSidebarProps {
  onApplyChanges: (messageId: string, changes: OutlineOp[]) => void;
}

export function OutlineReviewSidebar({
  onApplyChanges,
}: OutlineReviewSidebarProps) {
  const { open, messages, isSending } = useValues(outlineReviewLogic);
  const { close, send, markApplied } = useActions(outlineReviewLogic);

  const chatMessages: ChatMessage[] = messages.map((m) =>
    toChatMessage(m, onApplyChanges, markApplied),
  );

  return (
    <Sidebar
      open={open}
      onOpenChange={(next) => (!next ? close() : undefined)}
      title="Let AI review your outline"
      description="Six axes: privacy · ordering · structure · bias · alignment · follow-up depth"
    >
      <ChatPanel
        messages={chatMessages}
        onSend={send}
        isSending={isSending}
        placeholder="Ask me to review anything specific…"
        emptyState={
          <div className="flex flex-col gap-2 text-left">
            <p className="text-merism-text-muted">Try:</p>
            <ul className="space-y-1 text-sm">
              <li>"Check for any PII or bias in the questions."</li>
              <li>"Does Q3 really serve the research goal?"</li>
              <li>"Is the ordering right? Feels heavy at the start."</li>
            </ul>
          </div>
        }
        footer={
          <span>
            AI proposes changes; you accept one-by-one. Nothing is written to
            the outline until you click Apply.
          </span>
        }
        className="min-h-0 flex-1 border-0 shadow-none"
      />
    </Sidebar>
  );
}

function toChatMessage(
  m: OutlineReviewChatMessage,
  onApplyChanges: (messageId: string, changes: OutlineOp[]) => void,
  markApplied: (messageId: string) => void,
): ChatMessage {
  return {
    id: m.id,
    role: m.role === "researcher" ? "user" : "assistant",
    content: m.text,
    footer:
      m.role === "assistant" &&
      m.proposed_changes &&
      m.proposed_changes.length > 0 ? (
        <ProposedChanges
          changes={m.proposed_changes}
          onApplyAll={() => {
            if (m.proposed_changes) {
              onApplyChanges(m.id, m.proposed_changes);
              markApplied(m.id);
            }
          }}
          onDismiss={() => markApplied(m.id)}
        />
      ) : undefined,
  };
}

function ProposedChanges({
  changes,
  onApplyAll,
  onDismiss,
}: {
  changes: OutlineOp[];
  onApplyAll: () => void;
  onDismiss: () => void;
}) {
  return (
    <div className="mt-2 flex flex-col gap-2 rounded-merism-md bg-merism-surface ring-1 ring-[color:var(--merism-hairline)] shadow-merism-xs p-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-merism-text-muted">
          Proposed changes ({changes.length})
        </span>
        <Tag variant="accent">awaiting your decision</Tag>
      </div>
      <ul className="space-y-1 text-xs text-merism-text">
        {changes.map((c, i) => (
          <li key={i} className="flex gap-2">
            <span className="shrink-0 font-medium">{describeOp(c)}</span>
            {c.reason && (
              <span className="text-merism-text-muted">— {c.reason}</span>
            )}
          </li>
        ))}
      </ul>
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          onClick={onApplyAll}
          iconLeft={<Check className="h-4 w-4" />}
        >
          Apply all
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={onDismiss}
          iconLeft={<X className="h-4 w-4" />}
        >
          Skip
        </Button>
      </div>
    </div>
  );
}

function describeOp(op: OutlineOp): string {
  if (op.op === "modify_question") {
    return `Modify ${op.question_id}`;
  }
  if (op.op === "insert_question") {
    return `Insert after ${op.after_question_id}`;
  }
  return `Remove ${op.question_id}`;
}
