/**
 * Feature grid — 6 cards showcasing Merism's core capabilities.
 * Each card uses the design system's Card elevation pattern.
 */

const FEATURES = [
    {
        icon: "🎯",
        title: "研究目标驱动",
        description: "写一句研究目标，AI 自动生成访谈提纲、分析维度、报告结构——全程围绕你的核心问题。",
    },
    {
        icon: "🤖",
        title: "AI 访谈主持人",
        description: "实时语音对话，智能追问，自动控制节奏。支持音频和视频模式，每场成本低至 ¥15。",
    },
    {
        icon: "📋",
        title: "提纲智能审查",
        description: "AI 检查隐私风险、引导性表达、结构缺漏，像一位资深研究顾问帮你把关每个问题。",
    },
    {
        icon: "📊",
        title: "自动分析报告",
        description: "访谈结束即出个体洞察，多场汇总生成带图表、带引用的结构化报告。支持自定义追问。",
    },
    {
        icon: "📣",
        title: "多渠道招募",
        description: "飞书、企微、QQ 群发一键触达。公开链接分发，实时追踪招募进度与完成率。",
    },
    {
        icon: "🧠",
        title: "跨研究知识库",
        description: "所有研究自动沉淀为可检索知识。跨项目提问，AI 带引用回答，让洞察不再沉睡。",
    },
] as const

export function FeatureGrid(): JSX.Element {
    return (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
                <div
                    key={f.title}
                    className="group rounded-merism-xl bg-merism-surface p-[var(--spacing-merism-card-pad-lg)] shadow-merism-card ring-1 ring-[var(--merism-hairline)] transition-shadow duration-[var(--merism-duration-base)] ease-[var(--merism-ease)] hover:shadow-merism-float"
                >
                    <span className="mb-4 flex h-10 w-10 items-center justify-center rounded-merism-lg bg-merism-bg-subtle text-[20px]">
                        {f.icon}
                    </span>
                    <h3 className="text-merism-title font-semibold tracking-merism-tight text-merism-text">
                        {f.title}
                    </h3>
                    <p className="mt-2 text-merism-body-sm leading-relaxed text-merism-text-muted">
                        {f.description}
                    </p>
                </div>
            ))}
        </div>
    )
}
