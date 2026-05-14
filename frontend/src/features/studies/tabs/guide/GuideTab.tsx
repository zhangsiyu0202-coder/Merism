import { useActions, useValues } from "kea"
import {
    ChevronDown,
    GripVertical,
    Mic,
    Monitor,
    Phone,
    Plus,
    Sparkles,
    Trash2,
    Type,
} from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"

import { Button, Card, Input, Select, Tag } from "~/lib/merism"
import { studyLogic } from "~/features/studies/studyLogic"

/**
 * GuideTab — the core study configuration page (Outset.ai "Guide" tab).
 *
 * Layout (two-column on desktop):
 *   Left (main content area):
 *     - General Settings section
 *       - Interview Method (video / voice / text / offline)
 *       - Language
 *       - Intro Message
 *       - End Message
 *       - Context for AI
 *     - Questions section
 *       - Section-based question list (AI-generated + editable)
 *       - Add question / Add section buttons
 *   Right (sticky sidecar):
 *     - Interview Summary card (question count, est. time)
 *     - AI Guide Companion trigger
 */
export default function GuideTab(): JSX.Element {
    const { t } = useTranslation()
    const { study } = useValues(studyLogic)

    if (!study) {
        return <div className="text-merism-text-muted">{t("common.loading")}</div>
    }

    return (
        <div className="flex gap-8">
            {/* ── Left: Main content ─────────────────────────── */}
            <div className="flex min-w-0 flex-1 flex-col gap-10">
                <GeneralSettingsSection />
                <QuestionsSection />
            </div>

            {/* ── Right: Sticky sidecar ──────────────────────── */}
            <aside className="hidden w-[280px] shrink-0 lg:block">
                <div className="sticky top-8 flex flex-col gap-4">
                    <InterviewSummaryCard />
                    <AIGuideCompanionCard />
                </div>
            </aside>
        </div>
    )
}

// ── General Settings ───────────────────────────────────────

function GeneralSettingsSection(): JSX.Element {
    const { t } = useTranslation()
    const { study } = useValues(studyLogic)

    const [interviewMethod, setInterviewMethod] = useState(study?.interview_mode || "voice")
    const [language, setLanguage] = useState("en")
    const [introMessage, setIntroMessage] = useState(
        "Hello! Thanks for participating in this research session, led by AI. Please share your thoughts, ideas and feedback openly. Ready to start?"
    )
    const [endMessage, setEndMessage] = useState(
        "The interview has concluded. Thank you!"
    )
    const [aiContext, setAiContext] = useState(study?.research_goal || "")

    const METHOD_OPTIONS = [
        { value: "voice", label: t("guide.method.voice") },
        { value: "video", label: t("guide.method.video") },
        { value: "text", label: t("guide.method.text") },
        { value: "offline", label: t("guide.method.offline") },
    ]

    const LANGUAGE_OPTIONS = [
        { value: "en", label: "English" },
        { value: "zh", label: "中文" },
        { value: "ja", label: "日本語" },
        { value: "ko", label: "한국어" },
    ]

    return (
        <section className="flex flex-col gap-6">
            <h2 className="text-lg font-semibold text-merism-text">
                {t("guide.general_settings")}
            </h2>

            {/* Interview Method */}
            <SettingsField label={t("guide.interview_method")} hint={t("guide.interview_method_hint")}>
                <Select
                    value={interviewMethod}
                    onValueChange={setInterviewMethod}
                    options={METHOD_OPTIONS}
                    size="sm"
                    className="max-w-[240px]"
                />
                <label className="mt-3 flex items-center gap-2 text-sm text-merism-text-muted">
                    <input type="checkbox" className="h-4 w-4 accent-merism-accent" />
                    {t("guide.allow_fallback_chat")}
                </label>
            </SettingsField>

            {/* Language */}
            <SettingsField label={t("guide.language")}>
                <Select
                    value={language}
                    onValueChange={setLanguage}
                    options={LANGUAGE_OPTIONS}
                    size="sm"
                    className="max-w-[240px]"
                />
            </SettingsField>

            {/* Intro Message */}
            <SettingsField label={t("guide.intro_message")} hint={t("guide.intro_message_hint")}>
                <textarea
                    value={introMessage}
                    onChange={(e) => setIntroMessage(e.target.value)}
                    rows={3}
                    className={
                        "w-full resize-none rounded-merism-lg border border-[color:var(--merism-hairline)] " +
                        "bg-merism-surface p-3 text-sm text-merism-text outline-none " +
                        "focus:border-merism-accent-outline focus:ring-2 focus:ring-merism-accent-outline/40"
                    }
                />
            </SettingsField>

            {/* End Message */}
            <SettingsField label={t("guide.end_message")}>
                <textarea
                    value={endMessage}
                    onChange={(e) => setEndMessage(e.target.value)}
                    rows={2}
                    className={
                        "w-full resize-none rounded-merism-lg border border-[color:var(--merism-hairline)] " +
                        "bg-merism-surface p-3 text-sm text-merism-text outline-none " +
                        "focus:border-merism-accent-outline focus:ring-2 focus:ring-merism-accent-outline/40"
                    }
                />
            </SettingsField>

            {/* Context for AI */}
            <SettingsField label={t("guide.context_for_ai")} hint={t("guide.context_for_ai_hint")}>
                <textarea
                    value={aiContext}
                    onChange={(e) => setAiContext(e.target.value)}
                    rows={4}
                    className={
                        "w-full resize-none rounded-merism-lg border border-[color:var(--merism-hairline)] " +
                        "bg-merism-surface p-3 text-sm text-merism-text outline-none " +
                        "focus:border-merism-accent-outline focus:ring-2 focus:ring-merism-accent-outline/40"
                    }
                />
            </SettingsField>
        </section>
    )
}

// ── Questions Section ──────────────────────────────────────

interface QuestionItem {
    id: string
    text: string
    type: "conversational" | "rating" | "multiple_choice"
}

interface SectionItem {
    id: string
    title: string
    questions: QuestionItem[]
}

function QuestionsSection(): JSX.Element {
    const { t } = useTranslation()
    const { study } = useValues(studyLogic)

    // TODO: Load from study.guide_sections once backend supports it.
    // For now, show AI-generated placeholder or empty state.
    const [sections, setSections] = useState<SectionItem[]>([
        {
            id: "s1",
            title: "Introduction",
            questions: [
                { id: "q1", text: "To get started, can you please share your name and role?", type: "conversational" },
            ],
        },
        {
            id: "s2",
            title: "Core Questions",
            questions: [
                { id: "q2", text: study?.research_goal || "Tell me about your experience with...", type: "conversational" },
                { id: "q3", text: "What challenges do you face in this area?", type: "conversational" },
            ],
        },
        {
            id: "s3",
            title: "Wrap-up",
            questions: [
                { id: "q4", text: "Is there anything else you'd like to share?", type: "conversational" },
            ],
        },
    ])

    const totalQuestions = sections.reduce((sum, s) => sum + s.questions.length, 0)

    const addSection = (): void => {
        const newId = `s${Date.now()}`
        setSections([...sections, { id: newId, title: "New Section", questions: [] }])
    }

    const addQuestion = (sectionId: string): void => {
        setSections(sections.map((s) => {
            if (s.id !== sectionId) return s
            return {
                ...s,
                questions: [...s.questions, {
                    id: `q${Date.now()}`,
                    text: "",
                    type: "conversational" as const,
                }],
            }
        }))
    }

    const removeQuestion = (sectionId: string, questionId: string): void => {
        setSections(sections.map((s) => {
            if (s.id !== sectionId) return s
            return { ...s, questions: s.questions.filter((q) => q.id !== questionId) }
        }))
    }

    const updateQuestionText = (sectionId: string, questionId: string, text: string): void => {
        setSections(sections.map((s) => {
            if (s.id !== sectionId) return s
            return {
                ...s,
                questions: s.questions.map((q) =>
                    q.id === questionId ? { ...q, text } : q
                ),
            }
        }))
    }

    return (
        <section className="flex flex-col gap-6">
            <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-merism-text">
                    {t("guide.questions")}
                </h2>
                <span className="text-sm text-merism-text-muted">
                    {totalQuestions} {t("guide.questions_count")}
                </span>
            </div>

            {/* Section list */}
            <div className="flex flex-col gap-4">
                {sections.map((section, sIdx) => (
                    <div
                        key={section.id}
                        className="rounded-merism-lg border border-[color:var(--merism-hairline)] bg-merism-surface p-4"
                    >
                        {/* Section header */}
                        <div className="mb-3 flex items-center gap-2">
                            <span className="text-xs font-medium uppercase tracking-wide text-merism-text-subtle">
                                Section {sIdx + 1}
                            </span>
                            <Input
                                value={section.title}
                                onChange={(e) => {
                                    setSections(sections.map((s) =>
                                        s.id === section.id ? { ...s, title: e.target.value } : s
                                    ))
                                }}
                                className="h-8 border-none bg-transparent px-1 text-sm font-medium shadow-none focus-visible:ring-0"
                            />
                        </div>

                        {/* Questions */}
                        <div className="flex flex-col gap-2">
                            {section.questions.map((question, qIdx) => (
                                <div
                                    key={question.id}
                                    className="group flex items-start gap-2 rounded-merism-md bg-merism-bg p-3"
                                >
                                    <GripVertical className="mt-1 h-4 w-4 shrink-0 cursor-grab text-merism-text-subtle opacity-0 transition-opacity group-hover:opacity-100" />
                                    <span className="mt-0.5 shrink-0 text-xs font-medium text-merism-text-muted">
                                        {qIdx + 1}.
                                    </span>
                                    <textarea
                                        value={question.text}
                                        onChange={(e) => updateQuestionText(section.id, question.id, e.target.value)}
                                        rows={1}
                                        className="min-h-[28px] flex-1 resize-none border-none bg-transparent text-sm text-merism-text outline-none"
                                    />
                                    <Tag variant="outline" size="sm" case="normal">
                                        {question.type === "conversational" ? "Conversational" : question.type}
                                    </Tag>
                                    <button
                                        type="button"
                                        onClick={() => removeQuestion(section.id, question.id)}
                                        className="mt-0.5 shrink-0 text-merism-text-subtle opacity-0 transition-opacity hover:text-merism-danger group-hover:opacity-100"
                                    >
                                        <Trash2 className="h-3.5 w-3.5" />
                                    </button>
                                </div>
                            ))}
                        </div>

                        {/* Add question button */}
                        <button
                            type="button"
                            onClick={() => addQuestion(section.id)}
                            className="mt-3 flex items-center gap-1.5 text-xs font-medium text-merism-accent hover:text-merism-accent/80"
                        >
                            <Plus className="h-3.5 w-3.5" />
                            {t("guide.add_question")}
                        </button>
                    </div>
                ))}
            </div>

            {/* Add section */}
            <Button variant="ghost" size="sm" onClick={addSection} iconLeft={<Plus className="h-4 w-4" />}>
                {t("guide.add_section")}
            </Button>
        </section>
    )
}

// ── Interview Summary sidecar ──────────────────────────────

function InterviewSummaryCard(): JSX.Element {
    const { t } = useTranslation()
    const { study } = useValues(studyLogic)

    return (
        <Card className="bg-merism-accent p-5 text-white">
            <h3 className="text-sm font-semibold">{t("guide.interview_summary")}</h3>
            <div className="mt-3 flex flex-col gap-1 text-sm opacity-90">
                <span>12 {t("guide.questions_count")}</span>
                <span>{study?.estimated_minutes || 26} {t("guide.minutes_estimated")}</span>
            </div>
        </Card>
    )
}

// ── AI Guide Companion trigger ─────────────────────────────

function AIGuideCompanionCard(): JSX.Element {
    const { t } = useTranslation()

    return (
        <Card className="flex flex-col gap-3 p-5">
            <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-merism-accent" />
                <h3 className="text-sm font-semibold text-merism-text">
                    {t("guide.ai_companion_title")}
                </h3>
            </div>
            <p className="text-xs text-merism-text-muted">
                {t("guide.ai_companion_description")}
            </p>
            <Button variant="primary" size="sm">
                {t("guide.ai_companion_cta")}
            </Button>
        </Card>
    )
}

// ── Utility: Settings field wrapper ────────────────────────

function SettingsField({
    label,
    hint,
    children,
}: {
    label: string
    hint?: string
    children: React.ReactNode
}): JSX.Element {
    return (
        <div className="flex flex-col gap-2">
            <label className="text-sm font-semibold text-merism-text">{label}</label>
            {hint && <p className="text-xs text-merism-text-muted">{hint}</p>}
            {children}
        </div>
    )
}
