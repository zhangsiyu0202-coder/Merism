import { AnimatePresence, motion } from "motion/react";
import type { ReactNode } from "react";

/**
 * LiveSummaryPanel — sticky real-time metadata panel.
 *
 * Used in the right column of :class:`ThreePaneLayout`. When the
 * caller passes new ``stats`` on every config change, the affected
 * value crossfades to communicate "I saw your change" — the "feedback
 * description" in the design brief.
 *
 * All values are plain strings/numbers — callers format (e.g.
 * ``"4 min 20 s"``, ``"87%"``) so the panel stays presentation-only.
 */
export interface LiveStat {
  label: string;
  value: string | number;
  /** Optional right-aligned hint — percentage, delta, etc. */
  hint?: string;
  /** Subtle tone — ok / warn / danger influence the value colour. */
  tone?: "neutral" | "ok" | "warn" | "danger";
}

export interface LiveSummaryPanelProps {
  /** Header rendered above the stats (e.g. "Outline summary"). */
  title: ReactNode;
  /** Optional secondary text. */
  subtitle?: ReactNode;
  stats: LiveStat[];
  /** Optional slot for a larger breakdown (chart / list) under the stats. */
  footer?: ReactNode;
}

export function LiveSummaryPanel({
  title,
  subtitle,
  stats,
  footer,
}: LiveSummaryPanelProps): JSX.Element {
  return (
    <section className="flex flex-col gap-4 rounded-merism-lg bg-merism-surface ring-1 ring-[color:var(--merism-hairline)] shadow-merism-card p-6">
      <header className="flex flex-col gap-1">
        <span className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
          Live summary
        </span>
        <h3 className="font-display text-base font-[500] text-merism-text">
          {title}
        </h3>
        {subtitle && (
          <p className="text-xs text-merism-text-muted">{subtitle}</p>
        )}
      </header>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
        {stats.map((s) => (
          <Stat key={s.label} stat={s} />
        ))}
      </dl>

      {footer && (
        <div className="border-t border-[color:var(--merism-hairline)] pt-3">
          {footer}
        </div>
      )}
    </section>
  );
}

function Stat({ stat }: { stat: LiveStat }): JSX.Element {
  const toneClass = {
    neutral: "text-merism-text",
    ok: "text-[oklch(0.62_0.14_160)]",
    warn: "text-[oklch(0.72_0.16_70)]",
    danger: "text-merism-danger",
  }[stat.tone ?? "neutral"];

  return (
    <div className="flex flex-col gap-1">
      <dt className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
        {stat.label}
      </dt>
      <dd className="flex items-baseline gap-2">
        <AnimatePresence mode="popLayout">
          <motion.span
            key={String(stat.value)}
            initial={{ opacity: 0, y: -3 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 3 }}
            transition={{ duration: 0.12, ease: [0.22, 0.61, 0.36, 1] }}
            className={
              "font-display text-lg font-medium tabular-nums " + toneClass
            }
          >
            {stat.value}
          </motion.span>
        </AnimatePresence>
        {stat.hint && (
          <span className="font-mono text-merism-caption text-merism-text-muted">
            {stat.hint}
          </span>
        )}
      </dd>
    </div>
  );
}
