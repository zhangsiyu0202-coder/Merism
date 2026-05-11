import type { ReactNode } from "react"

/**
 * KpiGrid — responsive horizontal grid of ``<KpiCard />``s.
 *
 * Column behaviour:
 *   1 (mobile) → 2 (sm) → ``columns`` (lg+)
 *
 * Gap uses ``spacing-merism-gutter`` (32px) so the row breathes —
 * per the "whitespace-not-dividers" principle.
 *
 * Typical density:
 *   - 2 columns: two masthead numbers (hero size)
 *   - 3 columns: study report overview
 *   - 4 columns: dashboard (default)
 *
 * For 5+ metrics, prefer multiple rows (one ``KpiGrid`` per
 * theme) instead of squeezing everything into a single row.
 */

export interface KpiGridProps {
    children: ReactNode
    /** Target columns on large screens. Defaults to 4. */
    columns?: 2 | 3 | 4 | 5
    /** Add a subtle divider between columns for dense rows. Off by default. */
    withDividers?: boolean
    className?: string
}

const COLUMN_CLASSES: Record<2 | 3 | 4 | 5, string> = {
    2: "lg:grid-cols-2",
    3: "lg:grid-cols-3",
    4: "lg:grid-cols-4",
    5: "lg:grid-cols-5",
}

export function KpiGrid({
    children,
    columns = 4,
    withDividers = false,
    className,
}: KpiGridProps): JSX.Element {
    const base =
        "grid grid-cols-1 sm:grid-cols-2 gap-[var(--spacing-merism-gutter)] " +
        COLUMN_CLASSES[columns]
    const dividers = withDividers
        ? " [&>*]:pr-8 [&>*]:border-r [&>*]:border-merism-border/60 " +
          "[&>*:last-child]:border-r-0 [&>*:last-child]:pr-0"
        : ""
    return (
        <div className={base + dividers + (className ? ` ${className}` : "")}>
            {children}
        </div>
    )
}
