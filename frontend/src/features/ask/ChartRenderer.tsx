import type { EChartsOption } from "echarts";
import ReactECharts from "echarts-for-react";
import { useMemo } from "react";

import type { AskMerismChart } from "./types";

export interface ChartRendererProps {
  chart: AskMerismChart;
  /** Height in px; default 200 — small by design. "克制的放大". */
  height?: number;
}

/**
 * ChartRenderer — tiny, restrained chart.
 *
 * Design choices:
 * - Single accent color; the highest bar stays accent, the rest fade to
 *   a muted token so the eye lands on the answer not the chart.
 * - No legend when there's only one series (the title already tells you).
 * - 200 px default height — a glance, not a dashboard.
 */
export function ChartRenderer({ chart, height = 200 }: ChartRendererProps) {
  const option = useMemo<EChartsOption>(() => buildOption(chart), [chart]);

  return (
    <div className="rounded-merism-md bg-merism-surface ring-1 ring-[color:var(--merism-hairline)] shadow-merism-xs p-3">
      <ReactECharts
        option={option}
        style={{ height, width: "100%" }}
        opts={{ renderer: "svg" }}
        notMerge
        lazyUpdate
      />
    </div>
  );
}

function buildOption(chart: AskMerismChart): EChartsOption {
  const maxY = Math.max(...chart.y);
  const accent = "rgb(var(--m-accent))";
  const muted = "rgb(var(--m-text-muted) / 0.4)";

  if (chart.type === "bar") {
    return {
      title: { text: chart.title, left: "left", textStyle: { fontSize: 12 } },
      grid: { top: 36, bottom: 24, left: 36, right: 8 },
      xAxis: { type: "category", data: chart.x, axisLine: { show: false } },
      yAxis: { type: "value", splitLine: { show: false } },
      tooltip: { trigger: "axis" },
      series: [
        {
          type: "bar",
          data: chart.y.map((v) => ({
            value: v,
            itemStyle: { color: v === maxY ? accent : muted, borderRadius: 2 },
          })),
          label: { show: false },
          barMaxWidth: 24,
        },
      ],
    };
  }

  if (chart.type === "line") {
    return {
      title: { text: chart.title, left: "left", textStyle: { fontSize: 12 } },
      grid: { top: 36, bottom: 24, left: 36, right: 8 },
      xAxis: { type: "category", data: chart.x, axisLine: { show: false } },
      yAxis: { type: "value", splitLine: { show: false } },
      tooltip: { trigger: "axis" },
      series: [
        {
          type: "line",
          data: chart.y,
          smooth: true,
          lineStyle: { color: accent, width: 2 },
          itemStyle: { color: accent },
          symbol: "circle",
          symbolSize: 5,
          areaStyle: { color: accent, opacity: 0.1 },
        },
      ],
    };
  }

  // pie
  return {
    title: {
      text: chart.title,
      left: "center",
      top: 4,
      textStyle: { fontSize: 12 },
    },
    tooltip: { trigger: "item" },
    series: [
      {
        type: "pie",
        radius: ["40%", "65%"],
        data: chart.x.map((name, i) => ({
          name,
          value: chart.y[i] ?? 0,
        })),
        label: { fontSize: 11 },
      },
    ],
  };
}
