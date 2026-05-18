import { useActions, useValues } from "kea"
import { useEffect, useState } from "react"

import { Button, Illustration, Input } from "~/lib/merism"

import {
    participantEntryLogic,
    type ParticipantStep,
} from "./participantEntryLogic"

export default function ParticipantEntryPage(): JSX.Element {
    const slug = useSlugFromPath()

    const { setSlug, startSession, submitConsent } = useActions(participantEntryLogic)
    const { context, nextStep, contextLoading, errorCode } = useValues(participantEntryLogic)

    useEffect(() => {
        if (slug) setSlug(slug)
    }, [slug, setSlug])

    if (!slug) return <FullscreenMessage title="链接无效" body="链接格式不正确。" />
    if (contextLoading && !context) return <FullscreenMessage title="加载中…" illustration="loading-time" />

    const linkMode = (context as any)?.link_mode || "anonymous"

    return (
        <main className="min-h-screen bg-merism-bg px-6 py-10">
            <div className="mx-auto max-w-lg">
                <header className="mb-8 flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-merism-sm bg-merism-accent text-white">
                        <span className="font-display text-merism-body-sm font-[600]">M</span>
                    </div>
                    <span className="font-display text-merism-subtitle font-[500]">Merism</span>
                </header>

                <StepView
                    step={nextStep}
                    linkMode={linkMode}
                    errorCode={errorCode}
                    context={context}
                    onConsent={submitConsent}
                    onStart={startSession}
                />
            </div>
        </main>
    )
}

function StepView({
    step,
    linkMode,
    errorCode,
    context,
    onConsent,
    onStart,
}: {
    step: ParticipantStep
    linkMode: string
    errorCode: string | null
    context: any
    onConsent: (data?: any) => void
    onStart: () => void
}): JSX.Element {
    if (step === "error") {
        const { title, body } = errorCopy(errorCode)
        return <FullscreenMessage title={title} body={body} />
    }
    if (step === "thanks") return <FullscreenMessage title="感谢参与" body="你的回答已保存，可以关闭此页面。" illustration="peace" />
    if (step === "dropped") return <FullscreenMessage title="感谢你的关注" body="本研究需要不同的参与者画像，感谢你的时间。" illustration="chill-time" />

    // Named mode: show info form
    if (step === "consent" && linkMode === "named") {
        return <NamedInfoForm context={context} onSubmit={onConsent} />
    }

    // Consent step for anonymous (shouldn't normally reach here since backend auto-consents)
    if (step === "consent") {
        return <ReadyToStart context={context} onStart={() => onConsent()} />
    }

    // Session step: ready to begin
    return <ReadyToStart context={context} onStart={onStart} />
}

function NamedInfoForm({
    context,
    onSubmit,
}: {
    context: any
    onSubmit: (data?: any) => void
}): JSX.Element {
    const [name, setName] = useState("")
    const [contact, setContact] = useState("")

    return (
        <article className="rounded-merism-lg bg-merism-surface p-8 shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
            <h1 className="mb-2 font-display text-merism-headline font-[500] text-merism-text">
                参与访谈
            </h1>
            <p className="mb-6 text-merism-body text-merism-text-muted">
                {context?.study?.research_goal || "请填写以下信息以开始访谈。"}
            </p>
            <form
                className="flex flex-col gap-4"
                onSubmit={(e) => {
                    e.preventDefault()
                    onSubmit({ name, contact })
                }}
            >
                <div className="flex flex-col gap-1">
                    <label className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                        姓名
                    </label>
                    <Input
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="你的姓名"
                        required
                        autoFocus
                    />
                </div>
                <div className="flex flex-col gap-1">
                    <label className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                        联系方式（可选）
                    </label>
                    <Input
                        value={contact}
                        onChange={(e) => setContact(e.target.value)}
                        placeholder="手机号或邮箱"
                    />
                </div>
                <div className="mt-2 rounded-merism-md bg-merism-bg-subtle p-3 text-merism-caption text-merism-text-muted">
                    预计时长约 {context?.study?.estimated_minutes ?? 20} 分钟 · 回答仅用于研究 · 随时可退出
                </div>
                <Button type="submit" size="lg" className="mt-2 w-full">
                    开始访谈
                </Button>
            </form>
        </article>
    )
}

function ReadyToStart({
    context,
    onStart,
}: {
    context: any
    onStart: () => void
}): JSX.Element {
    return (
        <article className="rounded-merism-lg bg-merism-surface p-8 text-center shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
            <Illustration name="fast-internet" size="xl" className="mx-auto mb-6 text-merism-text" />
            <h1 className="mb-3 font-display text-merism-headline font-[500] text-merism-text">
                准备开始
            </h1>
            <p className="mb-6 text-merism-body text-merism-text-muted">
                访谈将在下一个页面开始。请确保你在安静的环境中，麦克风已准备好。
            </p>
            <div className="mb-6 text-merism-caption text-merism-text-subtle">
                预计 {context?.study?.estimated_minutes ?? 20} 分钟
            </div>
            <Button onClick={onStart} size="lg" className="w-full">
                开始访谈
            </Button>
        </article>
    )
}

function FullscreenMessage({
    title,
    body,
    illustration,
}: {
    title: string
    body?: string
    illustration?: "peace" | "chill-time" | "loading-time"
}): JSX.Element {
    return (
        <main className="flex min-h-screen items-center justify-center bg-merism-bg p-6">
            <div className="flex max-w-sm flex-col items-center gap-4 rounded-merism-lg bg-merism-surface p-10 text-center shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
                {illustration && <Illustration name={illustration} size="xl" className="text-merism-text" />}
                <h1 className="font-display text-merism-h2 font-[500] text-merism-text">{title}</h1>
                {body && <p className="text-merism-body text-merism-text-muted">{body}</p>}
            </div>
        </main>
    )
}

function errorCopy(errorCode: string | null): { title: string; body: string } {
    switch (errorCode) {
        case "not_found":
            return { title: "链接无效", body: "找不到此链接，请检查 URL 或联系研究员获取新链接。" }
        case "link_closed":
        case "study_closed":
            return { title: "研究已关闭", body: "此研究已不再接受新参与者。" }
        case "study_full":
            return { title: "名额已满", body: "此研究已达到目标访谈数。" }
        case "link_expired":
            return { title: "链接已过期", body: "此链接已失效。" }
        case "no_session":
            return { title: "会话丢失", body: "请重新打开访谈链接。" }
        case "consent_required":
            return { title: "需要同意", body: "请先完成信息填写再开始访谈。" }
        default:
            return { title: "出了点问题", body: "此链接可能已过期或研究已关闭。" }
    }
}

function useSlugFromPath(): string {
    const [slug, setSlug] = useState("")
    useEffect(() => {
        const match = window.location.pathname.match(/^\/i\/([^/]+)/)
        if (match) setSlug(match[1] ?? "")
    }, [])
    return slug
}
