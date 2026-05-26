import { AnimatePresence, motion } from "motion/react";
import { ArrowUp } from "lucide-react";
import {
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
  useRef,
  useState,
} from "react";

import { cn } from "../utils/cn";
import { StreamingMarkdown } from "./StreamingMarkdown";

export type ChatRole = "user" | "assistant" | "system";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: ReactNode;
  /** Optional trailing element (citations, chart, inline actions). */
  footer?: ReactNode;
  /** Streaming indicator — shows a subtle typing dot after content. */
  streaming?: boolean;
}

export interface ChatPanelProps {
  title?: ReactNode;
  messages: ChatMessage[];
  onSend: (text: string) => void | Promise<void>;
  placeholder?: string;
  isSending?: boolean;
  emptyState?: ReactNode;
  className?: string;
  footer?: ReactNode;
}

/**
 * ChatPanel — the shared chat column (Ask Merism / review drawers).
 *
 * 2026-05-10 Outset.ai-grade polish:
 *   - Panel surface: hairline ring + shadow-card (no solid border).
 *   - AI bubble: ``bg-white/70`` + ``backdrop-blur-sm`` — a subtle
 *     glass pane "floating" above the panel.
 *   - User bubble: soft-coral tint, aligned right.
 *   - Input: no outline; nested inside a rounded ``bg-bg-subtle/80``
 *     container. Send button is a 24×24 arrow glyph that flips
 *     from gray (disabled) → ink (ready) on content change.
 *
 * Interaction:
 *   - Enter = send, Shift+Enter = newline.
 *   - Messages render newest-at-bottom; ``flex-col-reverse`` pins
 *     the scroll to the bottom by default.
 */

export function ChatPanel({
  title,
  messages,
  onSend,
  placeholder = "Ask me anything…",
  isSending = false,
  emptyState,
  className,
  footer,
}: ChatPanelProps) {
  const [draft, setDraft] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const hasContent = draft.trim().length > 0;
  const canSend = hasContent && !isSending;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = draft.trim();
    if (!trimmed || isSending) {
      return;
    }
    setDraft("");
    await onSend(trimmed);
    textareaRef.current?.focus();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  return (
    <section
      className={cn(
        "flex h-full min-h-0 flex-col rounded-merism-lg bg-merism-surface " +
          "ring-1 ring-[color:var(--merism-hairline)] shadow-merism-card",
        className,
      )}
      aria-label="Chat panel"
    >
      {title && (
        <header className="shrink-0 border-b border-[color:var(--merism-hairline)] px-4 py-3 text-sm font-medium text-merism-text">
          {title}
        </header>
      )}

      <div className="flex min-h-0 flex-1 flex-col-reverse overflow-y-auto px-4 py-4">
        <AnimatePresence initial={false}>
          {messages.length === 0 && emptyState && (
            <motion.div
              key="empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="m-auto max-w-sm text-center text-merism-body-sm"
            >
              {emptyState}
            </motion.div>
          )}

          <div className="flex flex-col gap-3">
            {messages.map((msg) => (
              <ChatBubble key={msg.id} msg={msg} />
            ))}
          </div>
        </AnimatePresence>
      </div>

      {footer && (
        <div className="shrink-0 border-t border-[color:var(--merism-hairline)] px-4 py-2 text-merism-caption text-merism-text-muted">
          {footer}
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="shrink-0 border-t border-[color:var(--merism-hairline)] p-3"
      >
        {/* Immersive input: rounded subtle container, no outline on textarea. */}
        <div
          className={cn(
            "group flex items-end gap-2 rounded-merism-lg bg-merism-bg-subtle/70 px-4 py-3",
            "ring-1 ring-[color:var(--merism-hairline)]",
            "transition-[box-shadow,background-color] duration-[var(--merism-duration-base)] ease-[var(--merism-ease)]",
            "focus-within:bg-merism-surface focus-within:ring-[color:var(--merism-hairline-strong)]",
            "focus-within:shadow-merism-card",
          )}
        >
          <textarea
            ref={textareaRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            rows={1}
            disabled={isSending}
            aria-label="Message"
            className={cn(
              "min-h-[24px] max-h-[9rem] flex-1 resize-none bg-transparent",
              "border-0 outline-none ring-0 p-0",
              "text-merism-body text-merism-text placeholder:text-merism-text-subtle",
              "disabled:cursor-not-allowed disabled:opacity-60",
            )}
          />
          <button
            type="submit"
            disabled={!canSend}
            aria-label="Send"
            className={cn(
              "flex h-6 w-6 shrink-0 items-center justify-center rounded-merism-full",
              "transition-[background-color,color,transform] duration-[var(--merism-duration-fast)] ease-[var(--merism-ease)]",
              canSend
                ? "bg-merism-text text-merism-surface hover:bg-merism-accent active:scale-95"
                : "bg-transparent text-merism-text-subtle cursor-not-allowed",
            )}
          >
            <ArrowUp className="h-4 w-4" strokeWidth={2.5} aria-hidden="true" />
          </button>
        </div>
      </form>
    </section>
  );
}

function ChatBubble({ msg }: { msg: ChatMessage }): JSX.Element {
  const isUser = msg.role === "user";
  const isSystem = msg.role === "system";

  if (isSystem) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.2 }}
        className="mx-auto font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle"
      >
        {msg.content}
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: [0.22, 0.61, 0.36, 1] }}
      className={cn(
        "max-w-[85%] rounded-merism-lg px-4 py-3 text-merism-body-sm leading-relaxed",
        isUser
          ? // User: soft coral tint, right-aligned
            "self-end bg-merism-accent-soft text-merism-text"
          : // Assistant: glass pane, left-aligned
            "self-start bg-white/70 text-merism-text " +
              "ring-1 ring-[color:var(--merism-hairline)] shadow-merism-xs " +
              "backdrop-blur-[8px]",
      )}
    >
      <div className="whitespace-pre-wrap">
        {typeof msg.content === "string" && msg.role === "assistant" ? (
          <StreamingMarkdown text={msg.content} streaming={!!msg.streaming} />
        ) : (
          <>
            {msg.content}
            {msg.streaming && (
              <span
                aria-label="Generating"
                className="ml-1 inline-flex gap-1 align-middle"
              >
                <span className="h-1 w-1 animate-pulse rounded-full bg-merism-text-muted" />
                <span className="h-1 w-1 animate-pulse rounded-full bg-merism-text-muted [animation-delay:120ms]" />
                <span className="h-1 w-1 animate-pulse rounded-full bg-merism-text-muted [animation-delay:240ms]" />
              </span>
            )}
          </>
        )}
      </div>
      {msg.footer && <div className="mt-2">{msg.footer}</div>}
    </motion.div>
  );
}
