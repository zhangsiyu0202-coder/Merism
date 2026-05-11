import { useActions, useValues } from "kea"
import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"

import { Button, Illustration } from "~/lib/merism"

import { participantEntryLogic, type ParticipantStep } from "./participantEntryLogic"

/**
 * ParticipantEntryPage — orchestrates the /i/:slug flow.
 *
 * Slug comes from the URL. Everything else is driven by the backend's
 * ``next_step`` response.
 */
export default function ParticipantEntryPage(): JSX.Element {
    const { t } = useTranslation()

    // Parse slug from URL. kea-router doesn't know about /i/:slug since
    // it's served by the same SPA shell without being registered in the
    // main Scene enum — we read the pathname directly.
    const slug = useSlugFromPath()

    const { setSlug, startSession, submitConsent, submitScreener } = useActions(participantEntryLogic)
    const { context, nextStep, screenerQuestions, contextLoading } =
        useValues(participantEntryLogic)

    useEffect(() => {
        if (slug) setSlug(slug)
    }, [slug, setSlug])

    if (!slug) return <FullscreenMessage title="Invalid link" body="Your invite URL is missing its code." />
    if (contextLoading && !context) return <FullscreenMessage title={t("interview.loading")} illustration="loading-time" />

    return (
        <main className="min-h-screen bg-merism-bg px-6 py-10">
            <div className="mx-auto max-w-lg">
                <header className="mb-8 flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-merism-sm bg-merism-accent text-white">
                        <span className="font-display text-merism-body-sm font-[600]">M</span>
                    </div>
                    <span className="font-display text-merism-subtitle font-[500]">Merism</span>
                </header>

                <Step context={context} step={nextStep} screenerQuestions={screenerQuestions}
                      onConsent={submitConsent} onScreener={submitScreener} onStart={startSession} />
            </div>
        </main>
    )
}

function Step({
    context,
    step,
    screenerQuestions,
    onConsent,
    onScreener,
    onStart,
}: {
    context: ReturnType<typeof useValues<typeof participantEntryLogic>>["context"]
    step: ParticipantStep
    screenerQuestions: Array<{ id: string; text: string; kind?: string; options?: string[] }>
    onConsent: () => void
    onScreener: (answers: Record<string, unknown>) => void
    onStart: () => void
}): JSX.Element {
    const { t } = useTranslation()
    if (step === "error") return <FullscreenMessage title="Something went wrong" body="This invitation link may have expired or the study has closed." />
    if (step === "thanks") return <FullscreenMessage title="Thank you" body="Your session has been recorded." illustration="peace" />
    if (step === "dropped") return <FullscreenMessage title="Thanks for your interest" body="We appreciate your time — this particular study was looking for a different profile." illustration="chill-time" />

    if (step === "consent") {
        return (
            <article className="rounded-merism-lg bg-merism-surface p-8 shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
                <h1 className="mb-3 font-display text-merism-headline font-[500] text-merism-text">
                    You're invited to participate
                </h1>
                <p className="mb-6 text-merism-body text-merism-text-muted">{context?.study.research_goal}</p>
                <div className="mb-6 rounded-merism-md bg-merism-bg-subtle p-4 text-merism-body-sm text-merism-text">
                    <p className="mb-3 font-medium">About your participation</p>
                    <ul className="list-disc space-y-1 pl-5 text-merism-text-muted">
                        <li>This session takes about {context?.study.estimated_minutes ?? 20} minutes.</li>
                        <li>Your responses are used for research only.</li>
                        <li>We store transcripts; we do <strong>not</strong> store raw audio.</li>
                        <li>You can leave at any time.</li>
                    </ul>
                </div>
                <Button onClick={onConsent} size="lg" className="w-full">
                    I agree — continue
                </Button>
            </article>
        )
    }

    if (step === "screener") {
        return <ScreenerForm questions={screenerQuestions} onSubmit={onScreener} />
    }

    // step === "session"
    return (
        <article className="rounded-merism-lg bg-merism-surface p-8 text-center shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
            <Illustration name="fast-internet" size="xl" className="mx-auto mb-6 text-merism-text" />
            <h1 className="mb-3 font-display text-merism-headline font-[500] text-merism-text">
                Ready to begin
            </h1>
            <p className="mb-6 text-merism-body text-merism-text-muted">
                The session opens in the next screen. Make sure you're in a quiet place with your microphone ready.
            </p>
            <Button onClick={onStart} size="lg" className="w-full">
                {t("interview.start_cta")}
            </Button>
        </article>
    )
}

function ScreenerForm({
    questions,
    onSubmit,
}: {
    questions: Array<{ id: string; text: string; kind?: string; options?: string[] }>
    onSubmit: (answers: Record<string, unknown>) => void
}): JSX.Element {
    const [answers, setAnswers] = useState<Record<string, unknown>>({})
    return (
        <form
            className="rounded-merism-lg bg-merism-surface p-8 shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]"
            onSubmit={(e) => {
                e.preventDefault()
                onSubmit(answers)
            }}
        >
            <h1 className="mb-6 font-display text-merism-headline font-[500] text-merism-text">
                A few quick questions
            </h1>
            <div className="flex flex-col gap-6">
                {questions.map((q) => (
                    <div key={q.id} className="flex flex-col gap-2">
                        <label className="text-merism-body font-medium text-merism-text">{q.text}</label>
                        {q.kind === "single" && q.options ? (
                            <div className="flex flex-col gap-2">
                                {q.options.map((opt) => (
                                    <label key={opt} className="flex items-center gap-2 text-merism-body-sm text-merism-text">
                                        <input
                                            type="radio"
                                            name={q.id}
                                            value={opt}
                                            checked={answers[q.id] === opt}
                                            onChange={() => setAnswers((a) => ({ ...a, [q.id]: opt }))}
                                        />
                                        {opt}
                                    </label>
                                ))}
                            </div>
                        ) : q.kind === "number" ? (
                            <input
                                type="number"
                                className="rounded-merism-md bg-merism-bg-subtle px-3 py-2 text-merism-body ring-1 ring-[color:var(--merism-hairline-strong)]"
                                value={(answers[q.id] as number) ?? ""}
                                onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: Number(e.target.value) }))}
                            />
                        ) : (
                            <input
                                type="text"
                                className="rounded-merism-md bg-merism-bg-subtle px-3 py-2 text-merism-body ring-1 ring-[color:var(--merism-hairline-strong)]"
                                value={(answers[q.id] as string) ?? ""}
                                onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
                            />
                        )}
                    </div>
                ))}
            </div>
            <Button type="submit" size="lg" className="mt-8 w-full">
                Continue
            </Button>
        </form>
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

function useSlugFromPath(): string | null {
    const [slug, setSlug] = useState<string | null>(null)
    useEffect(() => {
        const match = window.location.pathname.match(/^\/i\/([a-z0-9]+)\/?$/i)
        setSlug(match?.[1] ?? null)
    }, [])
    return slug
}
