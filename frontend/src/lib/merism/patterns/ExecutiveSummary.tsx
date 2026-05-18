import { motion } from "motion/react"
import type { ReactNode } from "react"

import { StreamingMarkdown } from "./StreamingMarkdown"

/**
 * ExecutiveSummary — editorial hero block.
 *
 * Structure (top → bottom):
 *   1. ``eyebrow``   — mono caps metadata, e.g. ``EXECUTIVE SUMMARY · MAY 10``
 *   2. ``title``     — optional headline (h2 size)
 *   3. ``summary``   — the narrative body, rendered in ``font-display``
 *                      at subtitle size (18 px). Max-width uses the
 *                      ``spacing-merism-reading-max`` (~700 px) so the
 *                      measure never becomes unreadable.
 *   4. ``byline``    — mono caption under a hair-rule.
 *
 * LLM integration:
 *   Pass ``isLoading`` while DeepSeek streams. A 3-line skeleton is
 *   rendered in place. Once the final text arrives, the component
 *   fades the real summary in over 300 ms (design-system slow ease).
 *
 * Accent:
 *   The optional 2 px Coral rule on the left edge acts as a visual
 *   anchor — used when the summary is the first thing on the page.
 */

export interface ExecutiveSummaryProps {
    /** Caption line above the summary. */
    eyebrow?: string
    /** Optional h2-style headline between eyebrow and summary. */
    title?: ReactNode
    /** The narrative body — string or custom nodes (e.g. rendered markdown). */
    summary: ReactNode
    /** "Generated from N interviews" style attribution. */
    byline?: string
    /** "Updated 3 min ago" style timestamp. */
    updatedAt?: string
    /** Left Coral rule — on by default since this block is typically the hero. */
    accent?: boolean
    /** While true, render a shimmer skeleton instead of the summary. */
    isLoading?: boolean
    className?: string
}

export function ExecutiveSummary({
    eyebrow,
    title,
    summary,
    byline,
    updatedAt,
    accent = true,
    isLoading = false,
    className,
}: ExecutiveSummaryProps): JSX.Element {
    return (
        <section
            className={
                "relative flex flex-col gap-4 " +
                (accent ? "pl-6 " : "") +
                (className ?? "")
            }
        >
            {accent && (
                <span
                    aria-hidden="true"
                    className="absolute left-0 top-1 h-full w-[2px] rounded-full bg-merism-accent"
                />
            )}

            {eyebrow && (
                <div className="flex items-center gap-2 font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                    <span
                        aria-hidden="true"
                        className="inline-block h-1 w-1 rounded-full bg-merism-accent"
                    />
                    <span>{eyebrow}</span>
                </div>
            )}

            {title && (
                <h2 className="text-merism-h2 font-display font-[450] text-merism-text">
                    {title}
                </h2>
            )}

            {isLoading ? (
                <SummarySkeleton />
            ) : (
                <motion.div
                    key="summary"
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{
                        duration: 0.3,
                        ease: [0.22, 0.61, 0.36, 1],
                    }}
                    className={
                        "font-display text-merism-body leading-relaxed " +
                        "" +
                        "max-w-[var(--spacing-merism-reading-max)] text-merism-text"
                    }
                >
                    {typeof summary === "string" ? (
                        <StreamingMarkdown text={summary} />
                    ) : (
                        summary
                    )}
                </motion.div>
            )}

            {(byline || updatedAt) && (
                <div className="mt-2 flex items-center gap-3 border-t border-[color:var(--merism-hairline)] pt-3 font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                    {byline && <span>{byline}</span>}
                    {byline && updatedAt && (
                        <span aria-hidden="true" className="opacity-50">
                            ·
                        </span>
                    )}
                    {updatedAt && <span>{updatedAt}</span>}
                </div>
            )}
        </section>
    )
}

function SummarySkeleton(): JSX.Element {
    // Three-line shimmer sized to subtitle line-height (~1.35 × 18 = 24px).
    return (
        <div
            role="status"
            aria-label="Summary loading"
            className="flex max-w-[var(--spacing-merism-reading-max)] flex-col gap-2"
        >
            {[100, 96, 72].map((w) => (
                <span
                    key={w}
                    className="block h-6 animate-pulse rounded-merism-xs bg-merism-bg-subtle"
                    style={{ width: `${w}%` }}
                />
            ))}
        </div>
    )
}
