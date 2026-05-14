import { useEffect, useRef, useState } from "react"

interface Turn { role: "ai" | "participant"; text: string; delay?: number }

const SCRIPT: Turn[] = [
    { role: "ai", text: "好的,今天想聊聊你最近取消订阅的原因。", delay: 600 },
    { role: "participant", text: "大概是上周三吧,用了一段时间觉得不值。", delay: 800 },
    { role: "ai", text: "\"不值\"这个感觉很具体。能展开说说吗?", delay: 700 },
    { role: "participant", text: "主要是导出报告那块,每次都要等很久。", delay: 800 },
    { role: "ai", text: "如果导出速度提升了,你会重新考虑订阅吗?", delay: 700 },
]

export function HeroDemo(): JSX.Element {
    const [ti, setTi] = useState(0)
    const [ci, setCi] = useState(0)
    const [vis, setVis] = useState<Turn[]>([])
    const ref = useRef<HTMLDivElement>(null)

    useEffect(() => {
        let id: number | undefined
        if (ti >= SCRIPT.length) {
            id = window.setTimeout(() => { setTi(0); setCi(0); setVis([]) }, 4000)
        } else {
            const cur = SCRIPT[ti]!
            if (ci === 0) {
                id = window.setTimeout(() => { setVis(p => [...p, { role: cur.role, text: "" }]); setCi(1) }, cur.delay ?? 400)
            } else if (ci <= cur.text.length) {
                id = window.setTimeout(() => {
                    setVis(p => { const n = [...p]; n[n.length - 1] = { role: cur.role, text: cur.text.slice(0, ci) }; return n })
                    setCi(ci + 1)
                }, 30)
            } else {
                setTi(ti + 1); setCi(0)
            }
        }
        return () => { if (id) window.clearTimeout(id) }
    }, [ti, ci])

    useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight }, [vis])

    return (
        <div className="relative h-[440px] w-full max-w-[420px] overflow-hidden rounded-[24px] bg-white shadow-[0_24px_60px_-20px_rgba(120,80,40,0.18)] ring-1 ring-[color:rgba(120,80,40,0.08)]">
            <div className="flex items-center gap-2 border-b border-[color:rgba(120,80,40,0.08)] px-5 py-3">
                <span className="h-2.5 w-2.5 rounded-full bg-[color:rgba(120,80,40,0.15)]" />
                <span className="h-2.5 w-2.5 rounded-full bg-[color:rgba(120,80,40,0.15)]" />
                <span className="h-2.5 w-2.5 rounded-full bg-[color:rgba(120,80,40,0.15)]" />
                <span className="ml-3 font-mono text-[11px] uppercase tracking-[0.14em] text-[#967864]">Merism · Interview</span>
            </div>
            <div ref={ref} className="flex flex-col gap-3 overflow-y-auto px-5 py-5" style={{ height: "calc(100% - 44px)" }}>
                {vis.map((t, i) => {
                    const typing = i === vis.length - 1 && ti < SCRIPT.length && ci <= (SCRIPT[ti]?.text.length ?? 0)
                    const ai = t.role === "ai"
                    return (
                        <div key={i} className={ai ? "flex justify-start" : "flex justify-end"}>
                            <div className={"max-w-[86%] rounded-[14px] px-4 py-2.5 text-[14px] leading-[1.55] " + (ai ? "bg-[color:rgba(120,80,40,0.06)] text-[#2A1C10]" : "bg-[var(--merism-accent)] text-white")}>
                                {t.text}
                                {typing && <span className="ml-0.5 inline-block h-[14px] w-[2px] animate-pulse bg-current align-middle" />}
                            </div>
                        </div>
                    )
                })}
            </div>
        </div>
    )
}
