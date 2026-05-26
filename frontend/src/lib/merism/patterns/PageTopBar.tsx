import type { ReactNode } from "react";

import { PageHeading } from "./PageHeading";
import { TabRail, type TabRailItem } from "./TabRail";

/**
 * PageTopBar — the per-scene masthead.
 *
 * Composes :pattern:`PageHeading` with an optional :pattern:`TabRail`
 * right below it. Keeps the whole header zone as one visual unit
 * so every top-level scene wears the same crown.
 *
 * Structure:
 *   ┌──────────────────────────────────────────────┐
 *   │ EYEBROW                                      │
 *   │ Title  [status]                   [actions]  │   ← PageHeading
 *   │ Optional lede                                │
 *   │ ──────────────────────────────── (hairline)  │
 *   │   ↓ 16 px                                    │
 *   │ [tab] [tab] [tab] [tab]                      │   ← TabRail
 *   └──────────────────────────────────────────────┘
 *
 * The ``status`` prop is forwarded to PageHeading so callers can
 * render an inline Tag (e.g. study status) next to the title without
 * knowing the heading's internal slots.
 */

export interface PageTopBarProps {
  eyebrow?: ReactNode;
  title: ReactNode;
  /** Inline status tag baseline-aligned with title. */
  status?: ReactNode;
  /** Right-aligned CTA actions. */
  actions?: ReactNode;
  lede?: ReactNode;

  tabs?: TabRailItem[];
  activeTab?: string;
  onTabChange?: (value: string) => void;

  className?: string;
}

export function PageTopBar({
  eyebrow,
  title,
  status,
  actions,
  lede,
  tabs,
  activeTab,
  onTabChange,
  className,
}: PageTopBarProps): JSX.Element {
  return (
    <div className={"flex flex-col gap-4 " + (className ?? "")}>
      <PageHeading
        eyebrow={eyebrow}
        title={title}
        status={status}
        actions={actions}
        lede={lede}
      />
      {tabs && activeTab && onTabChange && (
        <TabRail tabs={tabs} activeTab={activeTab} onTabChange={onTabChange} />
      )}
    </div>
  );
}
