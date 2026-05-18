import _ReactEChartsCore from "echarts-for-react/lib/core"
const ReactEChartsCore = (_ReactEChartsCore as any).default ?? _ReactEChartsCore
import * as echarts from "echarts/core"
import { BarChart, LineChart, PieChart } from "echarts/charts"
import {
    GridComponent,
    LegendComponent,
    TitleComponent,
    TooltipComponent,
} from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"
import type { EChartsOption } from "echarts"

echarts.use([
    BarChart,
    LineChart,
    PieChart,
    GridComponent,
    LegendComponent,
    TitleComponent,
    TooltipComponent,
    CanvasRenderer,
])

export interface ChartSpec {
    type: "bar" | "pie" | "line"
    title: string
    categories?: string[]
    series?: { name: string; data: number[] }[]
    // Simple x/y format (from ChartSpec pydantic model)
    x?: string[]
    y?: number[]
}

export function AnalysisChart({
    spec,
    height = 280,
}: {
    spec: ChartSpec
    height?: number
}): JSX.Element {
    const option = buildOption(spec)
    return (
        <div className="rounded-merism-lg border border-[color:var(--merism-hairline)] bg-merism-surface p-4">
            {spec.title && (
                <h4 className="mb-3 text-merism-body-sm font-medium text-merism-text">
                    {spec.title}
                </h4>
            )}
            <ReactEChartsCore
                echarts={echarts}
                option={option}
                style={{ height }}
                notMerge
                lazyUpdate
            />
        </div>
    )
}

function buildOption(spec: ChartSpec): EChartsOption {
    const categories = spec.categories ?? spec.x ?? []
    const series = spec.series ?? (spec.y ? [{ name: "Value", data: spec.y }] : [])

    const base: EChartsOption = {
        tooltip: { trigger: spec.type === "pie" ? "item" : "axis" },
        grid: { left: 40, right: 20, top: 20, bottom: 30 },
        color: [
            "var(--merism-accent)",
            "#6366f1",
            "#8b5cf6",
            "#06b6d4",
            "#10b981",
            "#f59e0b",
        ],
    }

    if (spec.type === "pie") {
        return {
            ...base,
            series: [
                {
                    type: "pie",
                    radius: ["40%", "70%"],
                    data: categories.map((name, i) => ({
                        name,
                        value: series[0]?.data[i] ?? 0,
                    })),
                    label: { fontSize: 11 },
                },
            ],
        }
    }

    return {
        ...base,
        xAxis: { type: "category", data: categories, axisLabel: { fontSize: 11 } },
        yAxis: { type: "value", axisLabel: { fontSize: 11 } },
        series: series.map((s) => ({
            type: spec.type,
            name: s.name,
            data: s.data,
            smooth: spec.type === "line",
            barMaxWidth: 32,
        })),
    }
}

export default AnalysisChart
