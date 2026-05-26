import { Plus, X } from "lucide-react";
import { type KeyboardEvent, useRef } from "react";

/**
 * OrderedList — numbered editorial list (1. 2. 3. ...).
 *
 * Typography:
 *   Number prefix : ``tabular-nums``, muted, 24 px column
 *   Item text     : body, leading-relaxed, wraps naturally
 *
 * Two modes:
 *   Read-only  — ``readonly`` prop (or no ``onChange``): a plain
 *                ordered list. Items are spans, never clip; long
 *                sentences wrap.
 *   Editable   — each item is a ``<textarea>`` auto-sized to its
 *                content. Hover reveals a × remove button; an
 *                "Add item" footer inserts a new empty row.
 *
 * Callback contract:
 *   ``onChange(nextItems)`` fires once per user edit (debounced by
 *   the input's natural event). Caller owns state; we're stateless.
 *
 * Why not ``<ol>``?
 *   We use ``<ol>`` under the hood for semantics, but render the
 *   ``1.``/``2.``/``3.`` manually via a grid so the number column
 *   stays perfectly aligned with ``tabular-nums`` at any digit count.
 */

export interface OrderedListProps {
  items: string[];
  /** Pass to make the list editable. Omit to render read-only. */
  onChange?: (nextItems: string[]) => void;
  /** Force read-only even when ``onChange`` is supplied. */
  readonly?: boolean;
  /** Label for the "add row" footer button. */
  addLabel?: string;
  /** Placeholder shown in an empty new row. */
  placeholder?: string;
  className?: string;
}

export function OrderedList({
  items,
  onChange,
  readonly,
  addLabel = "Add item",
  placeholder = "New objective…",
  className,
}: OrderedListProps): JSX.Element {
  const editable = !!onChange && !readonly;

  function update(index: number, value: string): void {
    if (!onChange) return;
    const next = items.slice();
    next[index] = value;
    onChange(next);
  }

  function remove(index: number): void {
    if (!onChange) return;
    onChange(items.filter((_, i) => i !== index));
  }

  function add(): void {
    if (!onChange) return;
    onChange([...items, ""]);
  }

  return (
    <ol className={"flex flex-col gap-3 " + (className ?? "")}>
      {items.map((item, index) => (
        <li
          key={index}
          className="group grid grid-cols-[1.5rem_minmax(0,1fr)_auto] items-start gap-3"
        >
          <span
            aria-hidden="true"
            className="pt-[1px] text-[14px] tabular-nums text-merism-text-subtle"
          >
            {index + 1}.
          </span>
          {editable ? (
            <EditableItem
              value={item}
              placeholder={placeholder}
              onChange={(value) => update(index, value)}
              onEnter={add}
            />
          ) : (
            <span className="whitespace-pre-wrap text-[14px] leading-relaxed text-merism-text">
              {item}
            </span>
          )}
          {editable && (
            <button
              type="button"
              onClick={() => remove(index)}
              aria-label={`Remove item ${index + 1}`}
              className={
                "flex h-6 w-6 shrink-0 items-center justify-center rounded-merism-full " +
                "text-merism-text-subtle opacity-0 transition-opacity " +
                "duration-[var(--merism-duration-fast)] " +
                "hover:bg-[color:rgba(15,23,42,0.04)] hover:text-merism-text " +
                "group-hover:opacity-100 focus-visible:opacity-100 " +
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-merism-accent-outline"
              }
            >
              <X className="h-3 w-3" strokeWidth={2} />
            </button>
          )}
        </li>
      ))}

      {editable && (
        <li className="grid grid-cols-[1.5rem_minmax(0,1fr)] items-center gap-3">
          <span aria-hidden="true" />
          <button
            type="button"
            onClick={add}
            className={
              "inline-flex items-center gap-2 self-start rounded-merism-md px-2 py-1 " +
              "text-[13px] font-medium text-merism-text-muted transition-colors " +
              "duration-[var(--merism-duration-fast)] " +
              "hover:bg-[color:rgba(15,23,42,0.04)] hover:text-merism-text"
            }
          >
            <Plus className="h-3.5 w-3.5" strokeWidth={2} />
            <span>{addLabel}</span>
          </button>
        </li>
      )}
    </ol>
  );
}

/**
 * Auto-growing textarea for a single ordered-list item.
 *
 * Height follows the scrollHeight of the content. Enter without
 * shift inserts a new list row (via ``onEnter``) instead of a
 * newline inside the current item — matching Notion / Linear.
 */
function EditableItem({
  value,
  placeholder,
  onChange,
  onEnter,
}: {
  value: string;
  placeholder: string;
  onChange: (value: string) => void;
  onEnter: () => void;
}): JSX.Element {
  const ref = useRef<HTMLTextAreaElement>(null);

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>): void {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onEnter();
    }
  }

  function handleInput(event: React.FormEvent<HTMLTextAreaElement>): void {
    const ta = event.currentTarget;
    onChange(ta.value);
    // Auto-grow: reset then match scrollHeight.
    ta.style.height = "auto";
    ta.style.height = `${ta.scrollHeight}px`;
  }

  return (
    <textarea
      ref={ref}
      value={value}
      rows={1}
      placeholder={placeholder}
      onChange={handleInput}
      onKeyDown={handleKeyDown}
      className={
        "w-full resize-none bg-transparent text-[14px] leading-relaxed text-merism-text " +
        "placeholder:text-merism-text-subtle " +
        "border-0 p-0 outline-none ring-0 " +
        "focus:ring-0 focus:outline-none"
      }
    />
  );
}
