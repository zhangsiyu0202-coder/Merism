/**
 * Stats bar — social proof numbers displayed in a horizontal strip.
 */

const STATS = [
  { value: "10×", label: "研究效率提升" },
  { value: "90%", label: "成本降低" },
  { value: "¥15", label: "每场访谈成本" },
  { value: "24h", label: "从目标到洞察" },
] as const;

export function StatsBar(): JSX.Element {
  return (
    <section className="border-y border-[var(--merism-hairline)] bg-merism-surface py-10">
      <div className="mx-auto grid max-w-[1200px] grid-cols-2 gap-8 px-[var(--spacing-merism-fluid-gutter)] md:grid-cols-4">
        {STATS.map((s) => (
          <div key={s.label} className="text-center">
            <p className="font-display text-merism-headline font-bold tracking-merism-display text-merism-accent">
              {s.value}
            </p>
            <p className="mt-1 text-merism-body-sm text-merism-text-muted">
              {s.label}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
