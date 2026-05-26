import type { ReactNode } from "react";

/**
 * ThreePaneLayout — system-level 3-column shell.
 *
 * - ``left``   (optional) system / global navigation rail
 * - ``middle`` infinite-scroll config area (card stack)
 * - ``right``  **sticky** live-summary panel — updates in real time
 *
 * Intended as the canonical shell for any "configure + stats" surface
 * (Outline · Screener · anywhere with real-time metadata). The right
 * column uses ``position: sticky`` so the summary stays in view while
 * the middle scrolls.
 *
 * Grid template (desktop, ≥1280px):
 *
 *     [nav 14rem] [config 1fr] [summary 20rem]
 *
 * On narrower viewports the layout collapses to single-column stacked.
 * No token usage shortcuts — everything routes through ``merism-*``
 * tokens so dark mode + high-contrast stay consistent.
 */
export interface ThreePaneLayoutProps {
  left?: ReactNode;
  middle: ReactNode;
  right?: ReactNode;
  /** Optional classname for outer container (e.g. custom min-height). */
  className?: string;
}

export function ThreePaneLayout({
  left,
  middle,
  right,
  className,
}: ThreePaneLayoutProps): JSX.Element {
  return (
    <div
      className={
        "grid min-h-0 gap-6 " +
        (left
          ? "xl:grid-cols-[14rem_minmax(0,1fr)_20rem] lg:grid-cols-[12rem_minmax(0,1fr)] "
          : "xl:grid-cols-[minmax(0,1fr)_20rem] lg:grid-cols-[minmax(0,1fr)] ") +
        "grid-cols-1 " +
        (className ?? "")
      }
    >
      {left && (
        <aside className="hidden lg:block">
          <div className="sticky top-6 flex flex-col gap-2">{left}</div>
        </aside>
      )}
      <main className="flex min-h-0 flex-col gap-4">{middle}</main>
      <aside className="hidden xl:block">
        <div className="sticky top-6">{right}</div>
      </aside>
    </div>
  );
}
