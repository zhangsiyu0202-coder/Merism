import { useEffect, useRef, useState } from "react"

import { urls } from "~/app/routes"
import { sceneLogic } from "~/app/sceneLogic"
import { useValues } from "kea"
import { Button, Input, Tag } from "~/lib/merism"

interface Message {
    id: string
    role: "user" | "assistant"
    content: string
    streaming?: boolean
    toolCalls?: ToolCallResult[]
}

interface ToolCallResult {
    name: string
    result: Record<string, unknown>
}

interface ConversationItem {
    id: string
    title: string
    updated_at: string
    study_id: string | null
}

const SUGGESTIONS = [
    "帮我创建一个关于用户定价感知的访谈研究",
    "参与者对注册流程有什么反馈？",
    "分析一下最近研究的访谈进度",
]

export default function DecisionsPage(): JSX.Element {
    const [messages, setMessages] = useState<Message[]>([])
    const [input, setInput] = useState("")
    const [sending, setSending] = useState(false)
    const [thinking, setThinking] = useState<string | null>(null)
    const [title, setTitle] = useState<string | null>(null)
    const [conversationId, setConversationId] = useState<string | null>(null)
    const [history, setHistory] = useState<ConversationItem[]>([])
    const [sidebarOpen, setSidebarOpen] = useState(true)
    const scrollRef = useRef<HTMLDivElement>(null)
    const inputRef = useRef<HTMLInputElement>(null)

    // Context awareness: detect study_id from URL params
    const { sceneParams } = useValues(sceneLogic)
    const contextStudyId = (sceneParams?.searchParams as Record<string, string>)?.study ?? null

    const hasMessages = messages.length > 0

    // Load conversation history on mount
    useEffect(() => {
        fetch("/api/conversations/", { credentials: "include" })
            .then((r) => r.json())
            .then((d) => setHistory(d.conversations || []))
            .catch(() => {})
    }, [])

    // Auto-scroll
    useEffect(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
    }, [messages])

    // Save conversation after each assistant reply
    useEffect(() => {
        if (messages.length < 2) return
        const last = messages[messages.length - 1]
        if (last.role === "assistant" && !last.streaming) {
            const id = conversationId || crypto.randomUUID()
            if (!conversationId) setConversationId(id)
            fetch("/api/conversations/save/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({
                    id,
                    title: title || messages[0]?.content.slice(0, 30) || "新对话",
                    messages: messages.filter((m) => !m.streaming).map((m) => ({ role: m.role, content: m.content })),
                    study_id: contextStudyId,
                }),
            }).then(() => {
                // Refresh history
                fetch("/api/conversations/", { credentials: "include" })
                    .then((r) => r.json())
                    .then((d) => setHistory(d.conversations || []))
            }).catch(() => {})
        }
    }, [messages])

    const loadConversation = async (id: string) => {
        const res = await fetch(`/api/conversations/${id}/`, { credentials: "include" })
        if (!res.ok) return
        const data = await res.json()
        setConversationId(id)
        setTitle(data.title)
        setMessages(data.messages.map((m: any, i: number) => ({ id: `${id}-${i}`, role: m.role, content: m.content })))
    }

    const startNew = () => {
        setConversationId(null)
        setTitle(null)
        setMessages([])
    }

    const send = async (text?: string) => {
        const question = (text ?? input).trim()
        if (!question || sending) return
        setInput("")

        const userId = crypto.randomUUID()
        const assistantId = crypto.randomUUID()
        setMessages((prev) => [...prev, { id: userId, role: "user", content: question }, { id: assistantId, role: "assistant", content: "", streaming: true }])
        setSending(true)

        const chatHistory = messages.filter((m) => !m.streaming).map((m) => ({ role: m.role, content: m.content }))
        // Inject study context if available
        const contextPrefix = contextStudyId ? `[当前研究上下文: study_id=${contextStudyId}] ` : ""

        try {
            const res = await fetch("/api/ask/stream/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({ question: contextPrefix + question, history: chatHistory }),
            })
            if (!res.ok || !res.body) throw new Error(`${res.status}`)

            const reader = res.body.getReader()
            const decoder = new TextDecoder()
            let buffer = ""
            let toolCalls: ToolCallResult[] = []

            while (true) {
                const { value, done } = await reader.read()
                if (done) break
                buffer += decoder.decode(value, { stream: true })
                const parts = buffer.split("\n\n")
                buffer = parts.pop() ?? ""
                for (const raw of parts) {
                    let event = "", data = ""
                    for (const line of raw.split("\n")) {
                        if (line.startsWith("event:")) event = line.slice(6).trim()
                        else if (line.startsWith("data:")) data += line.slice(5).trim()
                    }
                    if (!data) continue
                    const parsed = JSON.parse(data)
                    if (event === "delta") { setThinking(null); setMessages((prev) => prev.map((m) => m.id === assistantId ? { ...m, content: parsed.partial } : m)) }
                    else if (event === "thinking") { setThinking(parsed.status) }
                    else if (event === "tool_result") { toolCalls.push({ name: parsed.name, result: parsed.result }) }
                    else if (event === "done") { setThinking(null); if (parsed.title) setTitle(parsed.title); setMessages((prev) => prev.map((m) => m.id === assistantId ? { ...m, content: parsed.answer_markdown || m.content, streaming: false, toolCalls: toolCalls.length > 0 ? toolCalls : undefined } : m)) }
                }
            }
        } catch { setMessages((prev) => prev.map((m) => m.id === assistantId ? { ...m, content: "请求失败，请重试。", streaming: false } : m)) }
        finally { setSending(false); inputRef.current?.focus() }
    }

    return (
        <div className="flex h-full overflow-hidden">
            {/* Sidebar - conversation history */}
            {sidebarOpen && (
                <div className="w-64 shrink-0 border-r border-[color:var(--merism-hairline)] bg-merism-surface flex flex-col">
                    <div className="flex items-center justify-between px-3 py-3 border-b border-[color:var(--merism-hairline)]">
                        <span className="font-mono text-[11px] uppercase tracking-merism-caps text-merism-text-subtle">对话历史</span>
                        <button type="button" onClick={startNew} className="rounded-merism-sm bg-merism-accent px-2 py-0.5 text-[11px] font-medium text-white">新对话</button>
                    </div>
                    <div className="flex-1 overflow-y-auto">
                        {history.map((c) => (
                            <button key={c.id} type="button" onClick={() => loadConversation(c.id)} className={`w-full px-3 py-2.5 text-left border-b border-[color:var(--merism-hairline)]/50 hover:bg-merism-bg-subtle transition-colors ${conversationId === c.id ? "bg-merism-accent/5" : ""}`}>
                                <p className="text-merism-body-sm text-merism-text truncate">{c.title}</p>
                                <p className="text-[10px] text-merism-text-subtle">{new Date(c.updated_at).toLocaleDateString("zh-CN")}</p>
                            </button>
                        ))}
                        {history.length === 0 && <p className="px-3 py-4 text-merism-body-sm text-merism-text-muted">暂无历史对话</p>}
                    </div>
                </div>
            )}

            {/* Main chat area */}
            <div className="flex flex-1 flex-col overflow-hidden">
                {/* Header */}
                {(title || contextStudyId) && (
                    <div className="shrink-0 flex items-center gap-2 border-b border-[color:var(--merism-hairline)] px-4 py-2">
                        <button type="button" onClick={() => setSidebarOpen(!sidebarOpen)} className="text-merism-text-muted hover:text-merism-text text-sm">☰</button>
                        {title && <span className="text-merism-body-sm font-medium text-merism-text">{title}</span>}
                        {contextStudyId && <Tag variant="accent">研究上下文</Tag>}
                    </div>
                )}

                {/* Scrollable */}
                <div ref={scrollRef} className="flex flex-1 flex-col overflow-y-auto">
                    <div className={`transition-[flex-grow] duration-300 ${hasMessages ? "grow-0" : "grow"}`} />
                    {!hasMessages && (
                        <div className="flex flex-col items-center gap-6 px-4 pb-4">
                            <h1 className="font-display text-[1.75rem] font-[500] text-merism-text">有什么我能帮你的？</h1>
                            <p className="text-merism-body-sm text-merism-text-muted">我可以帮你创建研究、搜索访谈内容、生成报告、分析数据。</p>
                            <div className="flex flex-wrap justify-center gap-2">
                                {SUGGESTIONS.map((s) => (<button key={s} type="button" onClick={() => send(s)} className="rounded-merism-md border border-[color:var(--merism-hairline)] bg-merism-surface px-3 py-2 text-merism-body-sm text-merism-text-muted hover:border-merism-accent hover:text-merism-accent">{s}</button>))}
                            </div>
                        </div>
                    )}
                    {hasMessages && (<div className="mx-auto w-full max-w-3xl space-y-3 px-4 py-4">{messages.map((m) => <MessageBubble key={m.id} message={m} />)}</div>)}
                    <div className={`transition-[flex-grow] duration-300 ${hasMessages ? "grow-0" : "grow"}`} />
                </div>

                {/* Thinking */}
                {thinking && (<div className="px-4 py-2"><div className="mx-auto max-w-3xl"><span className="inline-flex items-center gap-2 text-merism-body-sm text-merism-text-muted"><span className="inline-block h-2 w-2 animate-pulse rounded-full bg-merism-accent" />{thinking}</span></div></div>)}

                {/* Input */}
                <div className="border-t border-[color:var(--merism-hairline)] bg-merism-bg px-4 py-3">
                    <div className="mx-auto flex max-w-3xl items-center gap-2">
                        <Input ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send() } }} placeholder="输入你的问题…" className="flex-1" autoFocus />
                        <Button onClick={() => send()} disabled={!input.trim() || sending} size="sm">发送</Button>
                    </div>
                </div>
            </div>
        </div>
    )
}

function MessageBubble({ message }: { message: Message }): JSX.Element {
    const isUser = message.role === "user"
    return (
        <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[80%] rounded-merism-lg px-4 py-3 ${isUser ? "bg-merism-accent/10 text-merism-text" : "bg-merism-surface ring-1 ring-[color:var(--merism-hairline)]"}`}>
                <p className="whitespace-pre-wrap text-[15px] leading-[1.8]">
                    {message.content}
                    {message.streaming && <span className="ml-1 inline-block h-3 w-1 animate-pulse bg-merism-accent" />}
                </p>
                {message.toolCalls?.map((tc, i) => <ToolCallCard key={i} toolCall={tc} />)}
            </div>
        </div>
    )
}

function ToolCallCard({ toolCall }: { toolCall: ToolCallResult }): JSX.Element {
    const result = toolCall.result
    const artifact = result.artifact as { type: string; id: string; data: Record<string, unknown> } | undefined
    if (artifact) return <ArtifactCard artifact={artifact} result={result} />

    if (toolCall.name === "search_transcripts" && Array.isArray(result.results)) {
        const results = result.results as Array<{ content: string; session_id: string; score: number }>
        if (results.length === 0) return <div className="mt-3 rounded-merism-md border border-[color:var(--merism-hairline)] bg-merism-bg p-3 text-merism-body-sm text-merism-text-muted">未找到相关转写内容</div>
        return (
            <div className="mt-3 space-y-2">
                {results.map((r, i) => (
                    <div key={i} className="rounded-merism-md border border-[color:var(--merism-hairline)] bg-merism-bg p-3">
                        <div className="flex items-center gap-2 mb-1"><Tag variant="neutral">引用</Tag><span className="font-mono text-[10px] text-merism-text-subtle">session:{r.session_id?.slice(0, 8)} · {r.score}</span></div>
                        <p className="text-merism-body-sm text-merism-text whitespace-pre-wrap">{r.content}</p>
                    </div>
                ))}
            </div>
        )
    }

    if (result.error) return <div className="mt-3 rounded-merism-md border border-merism-danger/30 bg-merism-danger/5 p-3"><Tag variant="danger">失败</Tag><p className="mt-1 text-merism-body-sm text-merism-danger">{String(result.error)}</p></div>
    return <div className="mt-3 rounded-merism-md border border-[color:var(--merism-hairline)] bg-merism-bg p-3"><pre className="text-xs overflow-auto">{JSON.stringify(result, null, 2)}</pre></div>
}

function ArtifactCard({ artifact, result }: { artifact: { type: string; id: string; data: Record<string, unknown> }; result: Record<string, unknown> }): JSX.Element {
    const data = artifact.data
    if (artifact.type === "study_card") {
        return (
            <div className="mt-3 rounded-merism-lg border-2 border-merism-accent/30 bg-gradient-to-br from-merism-accent/5 to-transparent p-4">
                <div className="flex items-center justify-between"><div className="flex items-center gap-2"><Tag variant="success">已创建</Tag><span className="font-medium text-merism-text">{String(data.name)}</span></div><Tag variant="outline">{String(data.mode)}</Tag></div>
                <p className="mt-2 text-merism-body-sm text-merism-text-muted">{String(data.goal)}</p>
                <a href={String(result.url)} className="mt-3 inline-flex items-center gap-1 rounded-merism-md bg-merism-accent px-3 py-1.5 text-merism-body-sm font-medium text-white hover:opacity-90">打开研究设置 →</a>
            </div>
        )
    }
    if (artifact.type === "report_section") {
        return (
            <div className="mt-3 rounded-merism-lg border border-[color:var(--merism-hairline)] bg-merism-surface p-4">
                <div className="flex items-center justify-between mb-3"><div className="flex items-center gap-2"><Tag variant="accent">{String(data.section_type)}</Tag><span className="text-merism-body-sm text-merism-text-muted">{String(data.study_name)}</span></div><button type="button" className="rounded-merism-md border border-[color:var(--merism-hairline)] px-2 py-1 text-[11px] font-medium text-merism-text-muted hover:border-merism-accent hover:text-merism-accent">保存到报告</button></div>
                <div className="text-merism-body-sm text-merism-text whitespace-pre-wrap leading-relaxed">{String(data.content)}</div>
            </div>
        )
    }
    if (artifact.type === "chart") {
        const categories = (data.categories as string[]) || []
        const values = (data.values as number[]) || []
        const maxVal = Math.max(...values, 1)
        return (
            <div className="mt-3 rounded-merism-lg border border-[color:var(--merism-hairline)] bg-merism-surface p-4">
                <h4 className="mb-3 text-merism-body-sm font-medium text-merism-text">{String(data.title)}</h4>
                <div className="flex items-end gap-3 h-32">
                    {categories.map((cat, i) => (<div key={i} className="flex flex-1 flex-col items-center gap-1"><span className="text-[11px] font-medium text-merism-text">{values[i]}</span><div className="w-full rounded-t-merism-sm bg-merism-accent/70" style={{ height: `${(values[i] / maxVal) * 100}%`, minHeight: 4 }} /><span className="text-[10px] text-merism-text-muted">{cat}</span></div>))}
                </div>
            </div>
        )
    }
    return <div className="mt-3 rounded-merism-md border border-[color:var(--merism-hairline)] bg-merism-bg p-3"><pre className="text-xs">{JSON.stringify(artifact, null, 2)}</pre></div>
}
