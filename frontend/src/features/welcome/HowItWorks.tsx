/**
 * How-it-works — vertical timeline showing the 4-step research flow.
 */

const STEPS = [
    {
        step: "01",
        title: "写下研究目标",
        description: "一句话描述你想研究什么。AI 基于目标自动生成访谈提纲初稿，你可以编辑、调整追问深度、关联刺激物。",
        accent: false,
    },
    {
        step: "02",
        title: "招募受访者",
        description: "生成公开链接或通过飞书/企微/QQ 群发邀请。受访者点击链接即可进入，无需下载任何 App。",
        accent: false,
    },
    {
        step: "03",
        title: "AI 自动访谈",
        description: "受访者与 AI 主持人实时语音对话。AI 按提纲提问、智能追问、控制节奏，全程无需人工介入。",
        accent: true,
    },
    {
        step: "04",
        title: "获取洞察报告",
        description: "每场访谈自动生成个体分析；多场汇总产出带图表的结构化报告。还能用自然语言追问，AI 带引用回答。",
        accent: false,
    },
] as const

export function HowItWorks(): JSX.Element {
    return (
        <div className="relative mx-auto max-w-[640px]">
            {/* Vertical line */}
            <div
                aria-hidden="true"
                className="absolute left-[23px] top-2 bottom-2 w-px bg-merism-border"
            />
            <ol className="relative flex flex-col gap-12">
                {STEPS.map((s) => (
                    <li key={s.step} className="relative flex gap-6 pl-0">
                        {/* Step number dot */}
                        <div
                            className={
                                "relative z-10 flex h-12 w-12 shrink-0 items-center justify-center rounded-merism-full font-mono text-merism-label font-bold " +
                                (s.accent
                                    ? "bg-merism-accent text-merism-accent-ink shadow-merism-sm"
                                    : "bg-merism-surface text-merism-text ring-1 ring-[var(--merism-hairline-strong)] shadow-merism-xs")
                            }
                        >
                            {s.step}
                        </div>
                        {/* Content */}
                        <div className="pt-1">
                            <h3 className="text-merism-title font-semibold tracking-merism-tight text-merism-text">
                                {s.title}
                            </h3>
                            <p className="mt-2 text-merism-body-sm leading-relaxed text-merism-text-muted">
                                {s.description}
                            </p>
                        </div>
                    </li>
                ))}
            </ol>
        </div>
    )
}
