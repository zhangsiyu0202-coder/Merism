import { Plus } from "lucide-react";
import { motion } from "motion/react";
import type { ReactNode } from "react";

/**
 * LogicCard — card-based configuration unit.
 *
 * Header ::= sequence number (monospace) + icon + title
 * Body   ::= key parameter preview / editable content
 * Footer ::= "Add logic" entry (onClick handler required when shown)
 *
 * Used for any item where the user edits parameters AND needs a
 * visual sense of sequence: outline questions, screener rules,
 * stimulus rotation blocks, analytical steps, etc.
 *
 * Motion: 200ms fade-up via design-system ease.
 */
export interface LogicCardProps {
  /** 1-based sequence number rendered in the header corner. */
  index: number;
  /** Icon element placed next to the number. */
  icon?: ReactNode;
  /** Card title (editable by caller if they wrap in a contenteditable). */
  title: ReactNode;
  /** Right-aligned slot in the header — e.g. meta tag / delete button. */
  actions?: ReactNode;
  /** Main body content — preview of key configuration parameters. */
  children: ReactNode;
  /** Optional footer — typically renders an "Add …" button via onAddLogic. */
  onAddLogic?: () => void;
  addLogicLabel?: string;
  className?: string;
}

export function LogicCard({
  index,
  icon,
  title,
  actions,
  children,
  onAddLogic,
  addLogicLabel = "Add logic",
  className,
}: LogicCardProps): JSX.Element {
  return (
    <motion.article
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: [0.22, 0.61, 0.36, 1] }}
      className={
        "group flex flex-col overflow-hidden rounded-merism-lg bg-merism-surface " +
        "ring-1 ring-[color:var(--merism-hairline)] shadow-merism-card " +
        "transition-shadow duration-[var(--merism-duration-base)] " +
        "ease-[var(--merism-ease)] hover:shadow-merism-float " +
        (className ?? "")
      }
    >
      <header className="flex items-center gap-3 border-b border-[color:var(--merism-hairline)] px-6 py-4">
        <span
          aria-hidden="true"
          className="inline-flex h-6 min-w-[1.5rem] items-center justify-center rounded-merism-full bg-merism-bg-subtle px-2 font-mono text-merism-caption font-medium uppercase tracking-merism-caps-tight text-merism-text-subtle"
        >
          {String(index).padStart(2, "0")}
        </span>
        {icon && (
          <span className="text-merism-accent" aria-hidden="true">
            {icon}
          </span>
        )}
        <span className="min-w-0 flex-1 truncate text-sm font-medium text-merism-text">
          {title}
        </span>
        {actions && <span className="flex items-center gap-1">{actions}</span>}
      </header>

      <div className="flex flex-col gap-3 px-6 py-4">{children}</div>

      {onAddLogic && (
        <footer className="border-t border-dashed border-[color:var(--merism-hairline-strong)] bg-merism-bg-subtle/50">
          <button
            type="button"
            onClick={onAddLogic}
            className="flex w-full items-center gap-2 px-4 py-2 text-left font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle transition-colors hover:bg-merism-accent/5 hover:text-merism-accent"
          >
            <Plus className="h-4 w-4" />
            <span>{addLogicLabel}</span>
          </button>
        </footer>
      )}
    </motion.article>
  );
}
