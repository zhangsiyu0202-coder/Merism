import ReactECharts from "echarts-for-react";

import type { SentimentTrendPoint } from "./analysisLogic";

/**
 * SentimentTrendChart — stacked-area over date buckets.
 *
 * Positive = emerald · Negative = crimson · Neutral = slate · Mixed = amber.
 * All four colours come from the status-palette tokens so the chart
 * stays on-brand even as tokens evolve.
 */
export function SentimentTrendChart({
  points,
}: {
  points: SentimentTrendPoint[];
}): JSX.Element {
  if (points.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-merism-lg bg-merism-surface text-merism-body-sm text-merism-text-muted shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
        Sentiment trend will appear once tagging runs on more sessions.
      </div>
    );
  }

  const option = {
    grid: { left: 40, right: 20, top: 32, bottom: 28 },
    tooltip: { trigger: "axis" },
    legend: {
      icon: "circle",
      itemWidth: 8,
      itemHeight: 8,
      textStyle: {
        color: "#64748B",
        fontSize: 12,
        fontFamily: "Inter Variable, sans-serif",
      },
      top: 0,
    },
    xAxis: {
      type: "category",
      data: points.map((p) => p.date),
      axisLine: { lineStyle: { color: "#E2E8F0" } },
      axisLabel: { color: "#94A3B8", fontSize: 11 },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { color: "#F1F5F9" } },
      axisLabel: { color: "#94A3B8", fontSize: 11 },
    },
    series: [
      {
        name: "Positive",
        type: "line",
        stack: "sentiment",
        smooth: true,
        areaStyle: { opacity: 0.18 },
        lineStyle: { width: 2 },
        itemStyle: { color: "#1B5F3A" },
        data: points.map((p) => p.positive),
      },
      {
        name: "Neutral",
        type: "line",
        stack: "sentiment",
        smooth: true,
        areaStyle: { opacity: 0.18 },
        lineStyle: { width: 2 },
        itemStyle: { color: "#64748B" },
        data: points.map((p) => p.neutral),
      },
      {
        name: "Mixed",
        type: "line",
        stack: "sentiment",
        smooth: true,
        areaStyle: { opacity: 0.18 },
        lineStyle: { width: 2 },
        itemStyle: { color: "#7A4C10" },
        data: points.map((p) => p.mixed),
      },
      {
        name: "Negative",
        type: "line",
        stack: "sentiment",
        smooth: true,
        areaStyle: { opacity: 0.18 },
        lineStyle: { width: 2 },
        itemStyle: { color: "#9A2310" },
        data: points.map((p) => p.negative),
      },
    ],
  };

  return (
    <ReactECharts
      option={option}
      style={{ height: 240, width: "100%" }}
      opts={{ renderer: "svg" }}
    />
  );
}
