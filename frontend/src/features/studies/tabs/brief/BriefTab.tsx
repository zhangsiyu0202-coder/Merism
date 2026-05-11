import { useActions, useMountedLogic, useValues } from "kea"
import { Form, Field } from "kea-forms"
import { ArrowLeft, ArrowRight, Check, Mic, Monitor, Phone, Type } from "lucide-react"
import { useEffect } from "react"

import { Button, Card, Input, SectionLabel, Tag } from "~/lib/merism"
import { studyLogic } from "~/features/studies/studyLogic"

import {
    WIZARD_STEPS,
    briefWizardLogic,
    type WizardStep,
} from "./briefWizardLogic"

/**
 * BriefTab — 5-step research-brief wizard (PRODUCT.md §3.2).
 *
 * Steps:
 *   1. goal    — research_goal + optional background + hypothesis
 *   2. mode    — interview_mode (voice / video / text / offline)
 *   3. plan    — estimated_minutes + barge_in_enabled
 *   4. review  — summary of all values + submit
 *   5. done    — confirmation + CTA to next tab
 *
 * Validation via Zod (see briefWizardLogic). Persistence via PATCH
 * /api/studies/<id>/ on submit; step state is local.
 */
export default function BriefTab(): JSX.Element {
    useMountedLogic(briefWizardLogic)
    const { study } = useValues(studyLogic)
    const { step, currentStepIndex, canGoBack } = useValues(briefWizardLogic)
    const { back, goToStep, hydrateFromStudy } = useActions(briefWizardLogic)

    useEffect(() => {
        if (study) hydrateFromStudy(study)
    }, [study, hydrateFromStudy])

    if (!study) {
        return <div className="text-merism-text-muted">Loading brief…</div>
    }

    return (
        <div className="flex flex-col gap-8">
            <StepIndicator activeIndex={currentStepIndex} onStepClick={goToStep} />

            <Form
                logic={briefWizardLogic}
                formKey="brief"
                className="flex flex-col gap-8"
            >
                {step === "goal" && <StepGoal />}
                {step === "mode" && <StepMode />}
                {step === "plan" && <StepPlan />}
                {step === "review" && <StepReview />}
                {step === "done" && <StepDone />}

                {step !== "done" && (
                    <div className="flex items-center justify-between border-t border-[color:var(--merism-hairline)] pt-4">
                        <Button
                            type="button"
                            variant="ghost"
                            disabled={!canGoBack}
                            onClick={back}
                            iconLeft={<ArrowLeft className="h-4 w-4" />}
                        >
                            Back
                        </Button>
                        <StepForwardButton />
                    </div>
                )}
            </Form>
        </div>
    )
}

// ── Step indicator (editorial: numbered mono chips) ────────

const STEP_LABELS: Record<WizardStep, string> = {
    goal: "Goal",
    mode: "Mode",
    plan: "Plan",
    review: "Review",
    done: "Done",
}

function StepIndicator({
    activeIndex,
    onStepClick,
}: {
    activeIndex: number
    onStepClick: (step: WizardStep) => void
}): JSX.Element {
    return (
        <ol className="flex items-center gap-2">
            {WIZARD_STEPS.map((s, i) => {
                const active = i === activeIndex
                const done = i < activeIndex
                return (
                    <li key={s} className="flex items-center gap-2">
                        <button
                            type="button"
                            onClick={() => onStepClick(s)}
                            disabled={i > activeIndex}
                            className={
                                "flex items-center gap-2 rounded-merism-md px-2 py-1 font-mono text-merism-caption " +
                                "uppercase tracking-merism-caps transition-colors " +
                                (active
                                    ? "bg-merism-accent-soft text-merism-accent"
                                    : done
                                      ? "bg-merism-bg-subtle text-merism-text-muted hover:bg-merism-bg-subtle"
                                      : "text-merism-text-subtle disabled:opacity-50")
                            }
                        >
                            <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-current/15">
                                {done ? <Check className="h-2 w-2" /> : i + 1}
                            </span>
                            {STEP_LABELS[s]}
                        </button>
                        {i < WIZARD_STEPS.length - 1 && (
                            <span className="h-px w-4 bg-merism-border" aria-hidden="true" />
                        )}
                    </li>
                )
            })}
        </ol>
    )
}

function StepForwardButton(): JSX.Element {
    const { step, isLastStep } = useValues(briefWizardLogic)
    const { next, submitBrief } = useActions(briefWizardLogic)
    const { isBriefSubmitting } = useValues(briefWizardLogic)

    if (step === "done") return <span />

    if (isLastStep) {
        return (
            <Button
                type="button"
                onClick={() => submitBrief()}
                isLoading={isBriefSubmitting}
                iconRight={<Check className="h-4 w-4" />}
            >
                Save brief
            </Button>
        )
    }

    return (
        <Button
            type="button"
            onClick={() => next()}
            iconRight={<ArrowRight className="h-4 w-4" />}
        >
            Continue
        </Button>
    )
}

// ── Step bodies ────────────────────────────────────────────

function StepGoal(): JSX.Element {
    return (
        <section className="flex flex-col gap-6">
            <header>
                <SectionLabel>Step 1 · Research goal</SectionLabel>
                <h2 className="mt-2 font-display text-[length:var(--text-merism-title)] font-[500] text-merism-text">
                    What one question anchors this study?
                </h2>
                <p className="mt-2 max-w-[64ch] text-merism-body text-merism-text-muted">
                    A sharp research goal is the single most important input to every AI step.
                    Write it as a question your team would ask in a meeting — specific enough to
                    say "we answered it" at the end.
                </p>
            </header>

            <FieldBlock
                name="research_goal"
                label="Research goal"
                hint={'E.g. "Why do advanced users cancel after day 14?"'}
            >
                {({ value, onChange, error }) => (
                    <textarea
                        value={value}
                        onChange={(e) => onChange(e.target.value)}
                        rows={3}
                        className={
                            "w-full resize-none rounded-merism-md border border-[color:var(--merism-hairline-strong)] bg-merism-bg " +
                            "p-3 text-merism-body text-merism-text outline-none " +
                            "focus:border-merism-accent-outline focus:ring-2 focus:ring-merism-accent-outline/40 " +
                            (error ? "border-merism-danger" : "")
                        }
                        placeholder="Why do advanced users cancel after day 14?"
                    />
                )}
            </FieldBlock>

            <FieldBlock
                name="research_background"
                label="Background (optional)"
                hint="Anything the moderator should know before asking the first question."
            >
                {({ value, onChange }) => (
                    <textarea
                        value={value}
                        onChange={(e) => onChange(e.target.value)}
                        rows={2}
                        className="w-full resize-none rounded-merism-md border border-[color:var(--merism-hairline-strong)] bg-merism-bg p-3 text-merism-body text-merism-text outline-none focus:border-merism-accent-outline"
                    />
                )}
            </FieldBlock>

            <FieldBlock
                name="hypothesis"
                label="Hypothesis (optional)"
                hint="Your best current guess — will be challenged, never pre-biased into questions."
            >
                {({ value, onChange }) => (
                    <textarea
                        value={value}
                        onChange={(e) => onChange(e.target.value)}
                        rows={2}
                        className="w-full resize-none rounded-merism-md border border-[color:var(--merism-hairline-strong)] bg-merism-bg p-3 text-merism-body text-merism-text outline-none focus:border-merism-accent-outline"
                    />
                )}
            </FieldBlock>
        </section>
    )
}

function StepMode(): JSX.Element {
    const modes: Array<{
        value: "voice" | "video" | "text" | "offline"
        label: string
        description: string
        icon: typeof Mic
    }> = [
        { value: "voice", label: "Voice", description: "Paraformer + CosyVoice streaming audio interview.", icon: Mic },
        { value: "video", label: "Video", description: "Voice + facial / behavioural signals via Qwen-VL.", icon: Monitor },
        { value: "text", label: "Text", description: "Typeform-style form; no AI follow-ups.", icon: Type },
        { value: "offline", label: "Offline", description: "Upload recordings for post-hoc analysis.", icon: Phone },
    ]

    return (
        <section className="flex flex-col gap-6">
            <header>
                <SectionLabel>Step 2 · Interview mode</SectionLabel>
                <h2 className="mt-2 font-display text-[length:var(--text-merism-title)] font-[500] text-merism-text">
                    How will participants answer?
                </h2>
                <p className="mt-2 max-w-[64ch] text-merism-body text-merism-text-muted">
                    A study picks exactly one format — voice and video go through the full
                    conductor loop, text is pure form, offline is post-hoc annotation.
                </p>
            </header>

            <Field name="interview_mode">
                {({ value, onChange }) => (
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                        {modes.map((m) => {
                            const Icon = m.icon
                            const active = value === m.value
                            return (
                                <button
                                    key={m.value}
                                    type="button"
                                    onClick={() => onChange(m.value)}
                                    className={
                                        "flex items-start gap-3 rounded-merism-lg border p-4 text-left transition-colors " +
                                        (active
                                            ? "border-merism-accent bg-merism-accent-soft"
                                            : "border-merism-border bg-merism-surface hover:border-merism-border-strong")
                                    }
                                >
                                    <Icon
                                        className={
                                            "mt-1 h-5 w-5 shrink-0 " +
                                            (active ? "text-merism-accent" : "text-merism-text-muted")
                                        }
                                    />
                                    <div className="flex flex-col gap-1">
                                        <span className="font-[500] text-merism-text">{m.label}</span>
                                        <span className="text-merism-label text-merism-text-muted">
                                            {m.description}
                                        </span>
                                    </div>
                                </button>
                            )
                        })}
                    </div>
                )}
            </Field>
        </section>
    )
}

function StepPlan(): JSX.Element {
    return (
        <section className="flex flex-col gap-6">
            <header>
                <SectionLabel>Step 3 · Plan</SectionLabel>
                <h2 className="mt-2 font-display text-[length:var(--text-merism-title)] font-[500] text-merism-text">
                    How long, and how interruptible?
                </h2>
            </header>

            <FieldBlock
                name="estimated_minutes"
                label="Estimated duration (minutes)"
                hint="Most qualitative interviews land at 20–45 min."
            >
                {({ value, onChange, error }) => (
                    <Input
                        type="number"
                        min={5}
                        max={90}
                        step={5}
                        value={String(value)}
                        onChange={(e) => onChange(Number(e.target.value))}
                        aria-invalid={error ? "true" : undefined}
                        className="max-w-[160px]"
                    />
                )}
            </FieldBlock>

            <Field name="barge_in_enabled">
                {({ value, onChange }) => (
                    <label className="flex cursor-pointer items-start gap-3 rounded-merism-lg bg-merism-surface ring-1 ring-[color:var(--merism-hairline)] shadow-merism-card p-4">
                        <input
                            type="checkbox"
                            checked={Boolean(value)}
                            onChange={(e) => onChange(e.target.checked)}
                            className="mt-1 h-4 w-4 accent-merism-accent"
                        />
                        <div className="flex flex-col gap-1">
                            <span className="font-[500] text-merism-text">
                                Allow participants to interrupt the moderator
                            </span>
                            <span className="text-merism-label text-merism-text-muted">
                                Barge-in (ADR 0002). Default off — turn-by-turn is simpler and more
                                predictable. Flip on only once you've tested voice latency in prod.
                            </span>
                        </div>
                    </label>
                )}
            </Field>
        </section>
    )
}

function StepReview(): JSX.Element {
    const { brief: briefValues } = useValues(briefWizardLogic)
    return (
        <section className="flex flex-col gap-6">
            <header>
                <SectionLabel>Step 4 · Review</SectionLabel>
                <h2 className="mt-2 font-display text-[length:var(--text-merism-title)] font-[500] text-merism-text">
                    Looks right?
                </h2>
            </header>

            <Card className="flex flex-col gap-4 p-6">
                <ReviewRow label="Research goal">{briefValues.research_goal || "—"}</ReviewRow>
                {briefValues.research_background && (
                    <ReviewRow label="Background">{briefValues.research_background}</ReviewRow>
                )}
                {briefValues.hypothesis && (
                    <ReviewRow label="Hypothesis">{briefValues.hypothesis}</ReviewRow>
                )}
                <ReviewRow label="Mode">
                    <Tag variant="accent">{briefValues.interview_mode}</Tag>
                </ReviewRow>
                <ReviewRow label="Duration">
                    {briefValues.estimated_minutes} min
                </ReviewRow>
                <ReviewRow label="Barge-in">
                    <Tag variant={briefValues.barge_in_enabled ? "accent" : "neutral"}>
                        {briefValues.barge_in_enabled ? "enabled" : "disabled"}
                    </Tag>
                </ReviewRow>
            </Card>
        </section>
    )
}

function StepDone(): JSX.Element {
    const { goToStep } = useActions(briefWizardLogic)
    return (
        <section className="flex flex-col items-center gap-6 rounded-merism-lg bg-merism-surface ring-1 ring-[color:var(--merism-hairline)] shadow-merism-card p-10 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-merism-accent-soft">
                <Check className="h-6 w-6 text-merism-accent" />
            </div>
            <div className="flex flex-col gap-2">
                <div className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                    Saved
                </div>
                <h2 className="font-display text-[length:var(--text-merism-headline)] font-[450] tracking-tight text-merism-text">
                    Brief is set.
                </h2>
                <p className="max-w-[48ch] text-merism-body text-merism-text-muted">
                    Next: draft the interview outline. The AI reviewer is ready on the Outline
                    tab — just open it and ask.
                </p>
            </div>
            <Button variant="ghost" onClick={() => goToStep("goal")}>
                Edit again
            </Button>
        </section>
    )
}

// ── Reusable bits ──────────────────────────────────────────

function FieldBlock({
    name,
    label,
    hint,
    children,
}: {
    name: "research_goal" | "research_background" | "hypothesis" | "estimated_minutes"
    label: string
    hint?: string
    children: (props: {
        value: string | number
        onChange: (v: string | number) => void
        error: string | undefined
    }) => JSX.Element
}): JSX.Element {
    return (
        <Field name={name}>
            {({ value, onChange, error }) => (
                <div className="flex flex-col gap-2">
                    <span className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                        {label}
                    </span>
                    {children({ value, onChange, error })}
                    {error ? (
                        <span className="font-mono text-merism-caption text-merism-danger">
                            {error}
                        </span>
                    ) : hint ? (
                        <span className="text-merism-caption text-merism-text-muted">
                            {hint}
                        </span>
                    ) : null}
                </div>
            )}
        </Field>
    )
}

function ReviewRow({
    label,
    children,
}: {
    label: string
    children: React.ReactNode
}): JSX.Element {
    return (
        <div className="grid grid-cols-[8rem_1fr] items-start gap-3">
            <span className="pt-1 font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                {label}
            </span>
            <div className="text-merism-body text-merism-text">{children}</div>
        </div>
    )
}
