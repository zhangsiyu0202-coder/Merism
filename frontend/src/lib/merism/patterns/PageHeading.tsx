import type { ReactNode } from "react"

import { cn } from "../utils/cn"

/**
 * PageHeading — scene masthead.
 *
 * 2026-05-10 compact rebalance (post-screenshot feedback):
 *
 *   ┌─────────────────────────────────────────────────────┐
 *   │ EYEBROW · mono caps 12 px                           │
 *   │   ↓ 8 px                                            │
 *   │ Page title · 32 px · weight 500   [status]   [CTA]  │  ← single row
 *   │   ↓ 8 px                                            │
 *   │ Lede · 14 px · muted · max-w 64ch                   │
 *   │   ↓ 24 px (pb-6)                                    │
 *   │ ——————————————————————————————————  hairline        │
 *   └─────────────────────────────────────────────────────┘
 *
 * Title row carries three slots on one line, left → right:
 *   1. ``title``   — the H1 (always).
 *   2. ``status``  — optional inline tag (e.g. ``<Tag>paused</Tag>``).
 *                    Baseline-aligns with the title so the tag reads as
 *                    "metadata of the title" rather than "extra UI".
 *   3. ``actions`` — optional CTA cluster, pushed to the far right via
 *                    ``ml-auto``. Typical use: 1-2 buttons (``+ New``,
 *                    ``Share``, etc.).
 *
 * Why the numbers:
 *   - 32 px title at weight 500 reads as an H1 without dominating the
 *     canvas. Larger (48 px / display) made a 4× jump off the 12 px
 *     TopBar breadcrumb — a visual cliff. Smaller (24 px / h2) leaves
 *     the page identity underweight.
 *   - Eyebrow → title is now 8 px (tighter than before). The eyebrow
 *     is identity metadata; it should hug the title, not float above.
 *   - Title → lede 8 px (unchanged). The lede IS the title's longer
 *     form — tight coupling preserves that relationship.
 *   - Bottom pb-6 (24 px). The block below (tabs / KPIs / content)
 *     adds its own top margin via the scene's ``gap-section-y``.
 */

export interface PageHeadingProps {
    eyebrow?: ReactNode
    title: ReactNode
    /** Inline tag baseline-aligned with the title — ideal for status. */
    status?: ReactNode
    /** Right-aligned action cluster (CTAs). */
    actions?: ReactNode
    lede?: ReactNode
    className?: string
}

export function PageHeading({
    eyebrow,
    title,
    status,
    actions,
    lede,
    className,
}: PageHeadingProps): JSX.Element {
    return (
        <header
            className={cn(
                "flex flex-col border-b border-[color:var(--merism-hairline)] pb-6",
                className,
            )}
        >
            {eyebrow && (
                <div className="mb-2 font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                    {eyebrow}
                </div>
            )}

            {/* Title row: title + optional status + optional actions — one line */}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                <h1 className="font-display text-[length:var(--text-merism-headline)] font-[500] leading-[var(--text-merism-headline--line-height)] tracking-[var(--text-merism-headline--letter-spacing)] text-merism-text">
                    {title}
                </h1>
                {status && (
                    <div className="flex items-center gap-2">{status}</div>
                )}
                {actions && (
                    <div className="ml-auto flex shrink-0 items-center gap-2">
                        {actions}
                    </div>
                )}
            </div>

            {lede && (
                <p className="mt-2 max-w-[64ch] text-merism-body-sm leading-relaxed text-merism-text-muted">
                    {lede}
                </p>
            )}
        </header>
    )
}
