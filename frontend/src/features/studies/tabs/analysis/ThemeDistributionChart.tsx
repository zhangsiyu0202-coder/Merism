import ReactECharts from "echarts-for-react";

import type { ThemeEntry } from "./analysisLogic";

/**
 * ThemeDistributionChart — horizontal bar of top codebook themes.
 *
 * Colours: Coral monochrome ramp (heaviest at top). No gridlines, no
 * axis labels on the count axis — the labels themselves carry the
 * count.
 */
export function ThemeDistributionChart({
  themes,
}: {
  themes: ThemeEntry[];
}): JSX.Element {
  if (themes.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-merism-lg bg-merism-surface text-merism-body-sm text-merism-text-muted shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
        Themes will appear once sessions are coded.
      </div>
    );
  }

  const sorted = [...themes].sort((a, b) => a.count - b.count);
  const max = Math.max(...sorted.map((t) => t.count));

  const option = {
    grid: { left: 140, right: 40, top: 8, bottom: 8, containLabel: false },
    xAxis: { type: "value", show: false, max },
    yAxis: {
      type: "category",
      data: sorted.map((t) => t.name),
      axisTick: { show: false },
      axisLine: { show: false },
      axisLabel: {
        color: "#64748B",
        fontSize: 12,
        fontFamily: "Inter Variable, sans-serif",
      },
    },
    series: [
      {
        type: "bar",
        data: sorted.map((t) => t.count),
        barWidth: 14,
        itemStyle: {
          color: "#B54A22", // merism-status-accent core
          borderRadius: [0, 4, 4, 0],
        },
        label: {
          show: true,
          position: "right",
          color: "#334155",
          fontFamily: "Geist Mono Variable, monospace",
          fontSize: 12,
        },
      },
    ],
  };

  // Chart height scales with theme count (28px per row + padding).
  const height = Math.max(200, sorted.length * 28 + 32);
  return (
    <ReactECharts
      option={option}
      style={{ height, width: "100%" }}
      opts={{ renderer: "svg" }}
    />
  );
}
