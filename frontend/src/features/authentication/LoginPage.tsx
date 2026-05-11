import { useActions, useMountedLogic, useValues } from "kea"
import { Form, Field } from "kea-forms"
import { ArrowRight, Sparkles } from "lucide-react"
import { AnimatePresence, motion } from "motion/react"
import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"

import { Button, Illustration, Input, type IllustrationName } from "~/lib/merism"

import { loginLogic } from "./loginLogic"

/**
 * LoginPage — editorial split-screen.
 *
 * Left (desktop only): illustration + rotating pitch. Each pitch is
 * paired with a themed illustration — the visual crossfades when the
 * pitch rotates so the page feels alive on first paint without being
 * noisy. Mobile collapses to form-only.
 *
 * Design notes:
 *   - Illustrations are currentColor-themed; ``text-merism-text``
 *     gives a warm graphite ink over the off-white surface.
 *   - A tiny Coral rule on the right inner edge separates pitch + form
 *     visually without a hard divider.
 */

interface Pitch {
    illustration: IllustrationName
    headline: string
    body: string
}

const PITCHES: Pitch[] = [
    {
        illustration: "peace",
        headline: "Stop drowning in transcripts.",
        body: "Merism reads, codes, and summarises your sessions while you focus on the next study.",
    },
    {
        illustration: "fast-internet",
        headline: "Interviews at the speed of thought.",
        body: "Every participant, every theme, every quote — indexed and ready the moment the conversation ends.",
    },
    {
        illustration: "painting",
        headline: "Research that compounds.",
        body: "Ask any question across every interview your team has ever run — in plain language.",
    },
]

export default function LoginPage(): JSX.Element {
    const { t } = useTranslation()
    useMountedLogic(loginLogic)
    const { isLoginSubmitting } = useValues(loginLogic)
    const { submitLogin } = useActions(loginLogic)
    const [serverError, setServerError] = useState<string | null>(null)
    const [pitchIndex, setPitchIndex] = useState<number>(
        () => new Date().getDate() % PITCHES.length,
    )

    // Rotate the pitch every 7 s so users who linger see all three;
    // pause while the form is being submitted (keeps focus intact).
    useEffect(() => {
        if (isLoginSubmitting) return
        const id = window.setInterval(() => {
            setPitchIndex((i) => (i + 1) % PITCHES.length)
        }, 7000)
        return () => window.clearInterval(id)
    }, [isLoginSubmitting])

    const pitch = PITCHES[pitchIndex] ?? PITCHES[0]!

    return (
        <div className="grid min-h-screen grid-cols-1 bg-merism-bg lg:grid-cols-[minmax(0,1fr)_minmax(0,480px)]">
            {/* LEFT · editorial pane */}
            <aside className="relative hidden flex-col justify-between overflow-hidden bg-merism-surface p-12 lg:flex">
                <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-merism-sm bg-merism-accent text-merism-accent-ink">
                        <span className="font-display text-merism-body-sm font-[600] leading-none">
                            M
                        </span>
                    </div>
                    <span className="font-display text-merism-subtitle font-[500] tracking-tight text-merism-text">
                        Merism
                    </span>
                </div>

                <div className="flex flex-col gap-10">
                    <AnimatePresence mode="wait" initial={false}>
                        <motion.div
                            key={pitch.illustration}
                            initial={{ opacity: 0, y: 8 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -8 }}
                            transition={{
                                duration: 0.4,
                                ease: [0.22, 0.61, 0.36, 1],
                            }}
                            className="flex flex-col gap-10"
                        >
                            <Illustration
                                name={pitch.illustration}
                                size="2xl"
                                className="text-merism-text"
                            />
                            <div className="flex max-w-md flex-col gap-4">
                                <h2 className="font-display text-merism-headline font-[500] text-merism-text">
                                    {pitch.headline}
                                </h2>
                                <p className="text-merism-body leading-relaxed text-merism-text-muted">
                                    {pitch.body}
                                </p>
                            </div>
                        </motion.div>
                    </AnimatePresence>

                    {/* Tiny dot-nav so users know there's more */}
                    <div
                        className="flex items-center gap-1.5"
                        aria-label="Pitch indicator"
                    >
                        {PITCHES.map((p, i) => (
                            <button
                                key={p.illustration}
                                type="button"
                                onClick={() => setPitchIndex(i)}
                                aria-label={`Show pitch ${i + 1}`}
                                className={
                                    "h-1.5 w-4 rounded-merism-full transition-colors " +
                                    "duration-[var(--merism-duration-fast)] " +
                                    (i === pitchIndex
                                        ? "bg-merism-accent"
                                        : "bg-merism-border hover:bg-merism-border-strong")
                                }
                            />
                        ))}
                    </div>
                </div>

                <div className="flex items-center gap-2 font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                    <Sparkles className="h-3 w-3" />
                    <span>AI-moderated · structured insights · trusted pipeline</span>
                </div>

                <span
                    aria-hidden="true"
                    className="absolute inset-y-12 right-0 w-[2px] rounded-full bg-merism-accent/30"
                />
            </aside>

            {/* RIGHT · form pane */}
            <main className="flex flex-col items-center justify-center px-6 py-12 sm:px-12">
                <Form
                    logic={loginLogic}
                    formKey="login"
                    enableFormOnSubmit
                    className="flex w-full max-w-sm flex-col gap-8"
                >
                    <header className="flex flex-col gap-2">
                        <div className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                            {t("login.eyebrow")}
                        </div>
                        <h1 className="font-display text-merism-headline font-[500] text-merism-text">
                            {t("login.heading")}
                        </h1>
                        <p className="text-merism-body-sm text-merism-text-muted">
                            {t("login.sub")}
                        </p>
                    </header>

                    <div className="flex flex-col gap-4">
                        <Field name="email">
                            {({ value, onChange, error }) => (
                                <div className="flex flex-col gap-1">
                                    <label
                                        htmlFor="login-email"
                                        className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle"
                                    >
                                        {t("login.email")}
                                    </label>
                                    <Input
                                        id="login-email"
                                        type="email"
                                        autoComplete="email"
                                        placeholder="name@team.com"
                                        value={value}
                                        onChange={(e) => onChange(e.target.value)}
                                        aria-invalid={error ? "true" : undefined}
                                        required
                                        autoFocus
                                    />
                                    {error && (
                                        <span className="font-mono text-merism-caption text-merism-danger">
                                            {error}
                                        </span>
                                    )}
                                </div>
                            )}
                        </Field>

                        <Field name="password">
                            {({ value, onChange, error }) => (
                                <div className="flex flex-col gap-1">
                                    <div className="flex items-center justify-between">
                                        <label
                                            htmlFor="login-password"
                                            className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle"
                                        >
                                            {t("login.password")}
                                        </label>
                                        <a
                                            href="/accounts/password/reset/"
                                            className="font-mono text-merism-caption text-merism-text-muted transition-colors hover:text-merism-accent"
                                        >
                                            {t("login.forgot")}
                                        </a>
                                    </div>
                                    <Input
                                        id="login-password"
                                        type="password"
                                        autoComplete="current-password"
                                        placeholder="••••••••"
                                        value={value}
                                        onChange={(e) => onChange(e.target.value)}
                                        aria-invalid={error ? "true" : undefined}
                                        required
                                    />
                                    {error && (
                                        <span className="font-mono text-merism-caption text-merism-danger">
                                            {error}
                                        </span>
                                    )}
                                </div>
                            )}
                        </Field>
                    </div>

                    {serverError && (
                        <div className="rounded-merism-md bg-[color:var(--merism-status-danger-bg)] px-3 py-2 text-merism-label text-[color:var(--merism-status-danger)] ring-1 ring-[color:var(--merism-hairline)]">
                            {serverError}
                        </div>
                    )}

                    <Button
                        type="submit"
                        size="lg"
                        isLoading={isLoginSubmitting}
                        iconRight={<ArrowRight className="h-4 w-4" />}
                        onClick={async (e) => {
                            e.preventDefault()
                            setServerError(null)
                            try {
                                await Promise.resolve(submitLogin())
                            } catch (err) {
                                setServerError(
                                    err instanceof Error ? err.message : t("login.submitting"),
                                )
                            }
                        }}
                    >
                        {t("login.continue")}
                    </Button>

                    <div className="flex flex-col gap-4 border-t border-[color:var(--merism-hairline)] pt-6 text-center">
                        <p className="text-merism-body-sm text-merism-text-muted">
                            {t("login.new_workspace_prompt")}{" "}
                            <a
                                href="/accounts/signup/"
                                className="font-medium text-merism-accent transition-colors hover:text-merism-accent-hover"
                            >
                                {t("login.new_workspace_cta")}
                            </a>
                        </p>
                        <p className="font-mono text-merism-caption text-merism-text-subtle">
                            {t("login.dev_hint")}
                        </p>
                    </div>
                </Form>
            </main>
        </div>
    )
}
