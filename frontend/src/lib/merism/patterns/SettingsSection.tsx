import { Pencil } from "lucide-react";
import type { ReactNode } from "react";

/**
 * SettingsSection — editable section on a settings-style page.
 *
 * Vertical, strictly left-aligned. No horizontal splits, no cards
 * stacked in rows. Each section is a single logical block:
 *
 *   ┌────────────────────────────────────────────────┐
 *   │ Project details                       [Edit]   │   ← H2 + action
 *   │                                                │
 *   │ (children: text / list / form / etc.)          │
 *   └────────────────────────────────────────────────┘
 *
 * Children are the section body — caller decides whether they're
 * paragraphs (``<p>``), an ``<OrderedList>``, a form, a preview
 * card, etc. The primitive only provides the heading + the edit
 * affordance; it's agnostic about the content.
 *
 * Edit affordance is an ``Edit`` ghost button top-right. When the
 * section is not editable, simply omit ``onEdit``.
 *
 * Works as a ``<section>`` element so heading hierarchy is correct
 * (H2 is the implicit level — if the page needs H3 subsections,
 * the caller can override via ``headingLevel``).
 */

export interface SettingsSectionProps {
  title: string;
  /** Muted description under the heading. */
  description?: ReactNode;
  /** Show "Edit" button top-right. */
  onEdit?: () => void;
  editLabel?: string;
  children: ReactNode;
  /** Tag name for the heading. Defaults to ``h2``. */
  headingLevel?: "h2" | "h3";
  className?: string;
}

export function SettingsSection({
  title,
  description,
  onEdit,
  editLabel = "Edit",
  children,
  headingLevel = "h2",
  className,
}: SettingsSectionProps): JSX.Element {
  const Heading = headingLevel;

  return (
    <section
      className={
        "flex flex-col gap-4 " +
        // Generous vertical gap between sections is achieved by
        // the parent stack (gap-merism-section-y). Inside a
        // section we use 16 px between heading and body.
        (className ?? "")
      }
    >
      <header className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-1">
          <Heading className="text-merism-h2 font-display font-[450] text-merism-text">
            {title}
          </Heading>
          {description && (
            <p className="text-merism-body-sm leading-relaxed text-merism-text-muted">
              {description}
            </p>
          )}
        </div>
        {onEdit && (
          <button
            type="button"
            onClick={onEdit}
            className={
              "inline-flex shrink-0 items-center gap-1.5 rounded-merism-md px-2 py-1 " +
              "text-[13px] font-medium text-merism-text-muted transition-colors " +
              "duration-[var(--merism-duration-fast)] ease-[var(--merism-ease)] " +
              "hover:bg-[color:rgba(15,23,42,0.04)] hover:text-merism-text " +
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-merism-accent-outline"
            }
          >
            <Pencil className="h-3.5 w-3.5" strokeWidth={1.8} />
            <span>{editLabel}</span>
          </button>
        )}
      </header>

      <div className="flex flex-col">{children}</div>
    </section>
  );
}
