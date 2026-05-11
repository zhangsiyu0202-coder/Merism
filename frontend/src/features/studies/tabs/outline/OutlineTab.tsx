import {
    DndContext,
    KeyboardSensor,
    PointerSensor,
    closestCenter,
    useSensor,
    useSensors,
    type DragEndEvent,
} from "@dnd-kit/core"
import {
    SortableContext,
    sortableKeyboardCoordinates,
    useSortable,
    verticalListSortingStrategy,
} from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import { useActions, useMountedLogic, useValues } from "kea"
import {
    GripVertical,
    HelpCircle,
    MessageCircleQuestion,
    Sparkles,
    Trash2,
} from "lucide-react"
import { useMemo } from "react"

import { studyLogic } from "~/features/studies/studyLogic"
import {
    Button,
    LiveSummaryPanel,
    LogicCard,
    SectionLabel,
    Tag,
    ThreePaneLayout,
    type LiveStat,
} from "~/lib/merism"

import { outlineReviewLogic } from "./outlineReviewLogic"
import { OutlineReviewSidebar } from "./OutlineReviewSidebar"
import {
    outlineEditorLogic,
    type OutlineQuestion,
    type OutlineSection,
    type OutlineSectionScope,
} from "./outlineEditorLogic"

/**
 * OutlineTab — 3-pane interview guide editor.
 *
 * Structure (PRODUCT.md §3.3 + 2026-05-10 design-system brief):
 * - LEFT:   section nav — click to scroll to a section, click-active
 *           state reflects viewport.
 * - MIDDLE: one LogicCard per question. Drag-to-reorder within each
 *           section. Scope radio lives on the section header.
 * - RIGHT:  sticky LiveSummaryPanel — recomputes per-render:
 *           total sections, total questions, estimated duration, and
 *           a scope breakdown (global / per_concept / comparative).
 */
export default function OutlineTab(): JSX.Element {
    useMountedLogic(outlineEditorLogic)
    const { study } = useValues(studyLogic)
    const { sections } = useValues(outlineEditorLogic)
    const { openFor } = useActions(outlineReviewLogic)

    const handleOpenReview = (): void => {
        if (!study) return
        openFor(study.id, sections)
    }

    return (
        <div className="flex flex-col gap-6">
            <div className="flex items-center justify-between">
                <SectionLabel>Interview guide</SectionLabel>
                <Button
                    variant="secondary"
                    iconLeft={<Sparkles className="h-4 w-4" />}
                    onClick={handleOpenReview}
                    disabled={!study}
                >
                    Let AI review
                </Button>
            </div>

            <ThreePaneLayout
                left={<SectionNav sections={sections} />}
                middle={
                    <div className="flex flex-col gap-8">
                        {sections.map((section) => (
                            <SectionBlock key={section.id} section={section} />
                        ))}
                    </div>
                }
                right={<OutlineSummary sections={sections} />}
            />

            <OutlineReviewSidebar
                onApplyChanges={(_messageId, _changes) => {
                    // TODO(studies-wizard): apply_proposed_changes on the backend.
                }}
            />
        </div>
    )
}

// ── Left: section nav ──────────────────────────────────────

function SectionNav({ sections }: { sections: OutlineSection[] }): JSX.Element {
    return (
        <nav aria-label="Outline sections" className="flex flex-col gap-1">
            <span className="px-2 pb-1 font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                Sections
            </span>
            {sections.map((s, i) => (
                <a
                    key={s.id}
                    href={`#section-${s.id}`}
                    className="flex items-center justify-between gap-2 rounded-merism-md px-2 py-2 text-sm text-merism-text transition-colors hover:bg-merism-bg-subtle"
                >
                    <span className="inline-flex items-center gap-2 truncate">
                        <span className="font-mono text-merism-caption text-merism-text-subtle">
                            {String(i + 1).padStart(2, "0")}
                        </span>
                        <span className="truncate">{s.title}</span>
                    </span>
                    <span className="shrink-0 font-mono text-merism-caption text-merism-text-subtle">
                        {s.questions.length}Q
                    </span>
                </a>
            ))}
        </nav>
    )
}

// ── Middle: per-section card group ─────────────────────────

function SectionBlock({ section }: { section: OutlineSection }): JSX.Element {
    const { addQuestion, moveQuestion } = useActions(outlineEditorLogic)

    const sensors = useSensors(
        useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
        useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
    )

    const handleDragEnd = (event: DragEndEvent): void => {
        const { active, over } = event
        if (!over || active.id === over.id) return
        const from = section.questions.findIndex((q) => q.id === active.id)
        const to = section.questions.findIndex((q) => q.id === over.id)
        if (from === -1 || to === -1) return
        moveQuestion(section.id, from, to)
    }

    return (
        <section id={`section-${section.id}`} className="flex flex-col gap-3 scroll-mt-6">
            <div className="flex flex-wrap items-center gap-3">
                <h3 className="font-display text-[length:var(--text-merism-title)] font-[500] text-merism-text">
                    {section.title}
                </h3>
                <Tag variant="outline">{section.questions.length} questions</Tag>
                <ScopeRadio section={section} />
            </div>

            <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragEnd={handleDragEnd}
            >
                <SortableContext
                    items={section.questions.map((q) => q.id)}
                    strategy={verticalListSortingStrategy}
                >
                    <div className="flex flex-col gap-3">
                        {section.questions.map((q, i) => (
                            <QuestionCard
                                key={q.id}
                                sectionId={section.id}
                                index={i}
                                question={q}
                            />
                        ))}
                    </div>
                </SortableContext>
            </DndContext>

            <button
                type="button"
                onClick={() => addQuestion(section.id)}
                className="group inline-flex items-center gap-2 self-start rounded-merism-md px-2 py-1 font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle transition-colors hover:text-merism-accent"
            >
                <Sparkles className="h-4 w-4 opacity-60 group-hover:opacity-100" />
                Add question
            </button>
        </section>
    )
}

// ── Each question is a LogicCard ───────────────────────────

function QuestionCard({
    sectionId,
    index,
    question,
}: {
    sectionId: string
    index: number
    question: OutlineQuestion
}): JSX.Element {
    const {
        updateQuestionText,
        updateQuestionIntent,
        updateQuestionProbePolicy,
        updateQuestionMaxProbes,
        toggleQuestionRequired,
        removeQuestion,
    } = useActions(outlineEditorLogic)
    const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
        useSortable({ id: question.id })

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.6 : 1,
    }

    return (
        <div ref={setNodeRef} style={style}>
            <LogicCard
                index={index + 1}
                icon={<MessageCircleQuestion className="h-4 w-4" />}
                title={
                    <textarea
                        value={question.text}
                        onChange={(e) =>
                            updateQuestionText(sectionId, question.id, e.target.value)
                        }
                        rows={1}
                        placeholder="Write the question participants will hear."
                        className="w-full resize-none bg-transparent text-sm font-medium text-merism-text outline-none placeholder:text-merism-text-subtle"
                    />
                }
                actions={
                    <>
                        <button
                            {...attributes}
                            {...listeners}
                            type="button"
                            aria-label="Drag to reorder"
                            className="cursor-grab touch-none text-merism-text-subtle opacity-0 transition-opacity group-hover:opacity-100 hover:text-merism-text"
                        >
                            <GripVertical className="h-4 w-4" />
                        </button>
                        <button
                            type="button"
                            aria-label="Remove question"
                            onClick={() => removeQuestion(sectionId, question.id)}
                            className="text-merism-text-subtle opacity-0 transition-opacity group-hover:opacity-100 hover:text-merism-danger"
                        >
                            <Trash2 className="h-4 w-4" />
                        </button>
                    </>
                }
            >
                <div className="flex flex-col gap-4">
                    {/* Intent — what this question should yield */}
                    <div className="flex flex-col gap-1">
                        <label
                            htmlFor={`intent-${question.id}`}
                            className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle"
                        >
                            Intent · what to learn + probing direction
                        </label>
                        <textarea
                            id={`intent-${question.id}`}
                            value={question.intent}
                            onChange={(e) =>
                                updateQuestionIntent(sectionId, question.id, e.target.value)
                            }
                            rows={2}
                            placeholder="e.g. Map the day-10 moment that triggered the cancel intent; if a specific trigger is mentioned, have them recall what they tried next."
                            className="w-full resize-y rounded-merism-md bg-merism-bg-subtle/60 px-3 py-2 text-merism-body-sm leading-relaxed text-merism-text outline-none ring-1 ring-[color:var(--merism-hairline)] placeholder:text-merism-text-subtle focus:ring-[color:var(--merism-hairline-strong)]"
                        />
                    </div>

                    {/* Probe policy segmented + max_probes + required */}
                    <div className="flex flex-wrap items-center gap-4">
                        <ProbePolicySegmented
                            sectionId={sectionId}
                            question={question}
                            onChange={(policy) =>
                                updateQuestionProbePolicy(sectionId, question.id, policy)
                            }
                        />
                        <MaxProbesStepper
                            value={question.max_probes}
                            onChange={(next) =>
                                updateQuestionMaxProbes(sectionId, question.id, next)
                            }
                        />
                        <label className="ml-auto inline-flex shrink-0 items-center gap-2 text-merism-label text-merism-text-muted">
                            <input
                                type="checkbox"
                                checked={!!question.required}
                                onChange={() =>
                                    toggleQuestionRequired(sectionId, question.id)
                                }
                                className="h-4 w-4 rounded-merism-sm"
                            />
                            <span>Required</span>
                        </label>
                    </div>

                    {/* ID footer — mono, subtle */}
                    <div className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                        Q{index + 1} · {question.id}
                    </div>
                </div>
            </LogicCard>
        </div>
    )
}

// ── Probe-policy segmented control ─────────────────────────

const PROBE_POLICIES: Array<{ value: OutlineQuestion["probe_policy"]; label: string; hint: string }> = [
    { value: "none", label: "No probe", hint: "Ask once, move on" },
    { value: "light", label: "If needed", hint: "Probe when answer is vague" },
    { value: "deep", label: "Always probe", hint: "At least one follow-up" },
]

function ProbePolicySegmented({
    sectionId: _sectionId,
    question,
    onChange,
}: {
    sectionId: string
    question: OutlineQuestion
    onChange: (policy: OutlineQuestion["probe_policy"]) => void
}): JSX.Element {
    return (
        <div className="flex flex-col gap-1">
            <span className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                Probing
            </span>
            <div
                role="radiogroup"
                aria-label="Probe policy"
                className="inline-flex items-center gap-1 rounded-merism-full bg-merism-bg-subtle/70 p-1 ring-1 ring-[color:var(--merism-hairline)]"
            >
                {PROBE_POLICIES.map((opt) => {
                    const active = opt.value === question.probe_policy
                    return (
                        <button
                            key={opt.value}
                            type="button"
                            role="radio"
                            aria-checked={active}
                            title={opt.hint}
                            onClick={() => onChange(opt.value)}
                            className={
                                "rounded-merism-full px-3 py-1 text-merism-label transition-colors " +
                                (active
                                    ? "bg-merism-accent text-white shadow-merism-xs"
                                    : "text-merism-text-muted hover:text-merism-text")
                            }
                        >
                            {opt.label}
                        </button>
                    )
                })}
            </div>
        </div>
    )
}

// ── Max-probes stepper ───────────────────────────────────

function MaxProbesStepper({
    value,
    onChange,
}: {
    value: number
    onChange: (next: number) => void
}): JSX.Element {
    return (
        <div className="flex flex-col gap-1">
            <span className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                Max probes
            </span>
            <div className="inline-flex items-center gap-2 rounded-merism-full bg-merism-bg-subtle/70 px-2 py-1 ring-1 ring-[color:var(--merism-hairline)]">
                <button
                    type="button"
                    aria-label="Decrease max probes"
                    onClick={() => onChange(value - 1)}
                    disabled={value <= 1}
                    className="inline-flex h-5 w-5 items-center justify-center rounded-merism-full text-merism-text-muted transition-colors hover:bg-merism-surface hover:text-merism-text disabled:opacity-40"
                >
                    −
                </button>
                <span className="w-4 text-center font-mono text-merism-label tabular-nums text-merism-text">
                    {value}
                </span>
                <button
                    type="button"
                    aria-label="Increase max probes"
                    onClick={() => onChange(value + 1)}
                    disabled={value >= 5}
                    className="inline-flex h-5 w-5 items-center justify-center rounded-merism-full text-merism-text-muted transition-colors hover:bg-merism-surface hover:text-merism-text disabled:opacity-40"
                >
                    +
                </button>
            </div>
        </div>
    )
}

// ── Right: live summary ───────────────────────────────────

function OutlineSummary({ sections }: { sections: OutlineSection[] }): JSX.Element {
    const stats = useMemo<LiveStat[]>(() => {
        const totalQuestions = sections.reduce((a, s) => a + s.questions.length, 0)
        const totalSections = sections.length
        const byScope: Record<OutlineSectionScope, number> = {
            global: 0,
            per_concept: 0,
            comparative: 0,
        }
        for (const s of sections) {
            byScope[s.scope ?? "global"] += s.questions.length
        }
        // Rough estimate: 90s per question (question + one follow-up avg).
        const minutes = Math.round((totalQuestions * 90) / 60)
        return [
            { label: "Sections", value: totalSections },
            { label: "Questions", value: totalQuestions },
            { label: "Est. minutes", value: minutes, hint: "~90s/Q" },
            {
                label: "Per-concept",
                value: byScope.per_concept,
                hint: byScope.per_concept > 0 ? "× rotation" : undefined,
                tone: byScope.per_concept > 0 ? "ok" : "neutral",
            },
        ]
    }, [sections])

    const scopeBreakdown = useMemo(() => {
        const total = sections.reduce((a, s) => a + s.questions.length, 0) || 1
        const counts: Record<OutlineSectionScope, number> = {
            global: 0,
            per_concept: 0,
            comparative: 0,
        }
        for (const s of sections) counts[s.scope ?? "global"] += s.questions.length
        return { counts, total }
    }, [sections])

    return (
        <LiveSummaryPanel
            title="Outline summary"
            subtitle="Recalculates as you edit."
            stats={stats}
            footer={
                <div className="flex flex-col gap-2 text-xs">
                    <span className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                        Scope split
                    </span>
                    <ScopeBar breakdown={scopeBreakdown} />
                </div>
            }
        />
    )
}

function ScopeBar({
    breakdown,
}: {
    breakdown: {
        counts: Record<OutlineSectionScope, number>
        total: number
    }
}): JSX.Element {
    const pct = (n: number): string => `${Math.round((n / breakdown.total) * 100)}%`

    return (
        <div className="flex flex-col gap-2">
            <div className="flex h-2 overflow-hidden rounded-merism-full bg-merism-bg-subtle">
                <span
                    className="bg-merism-text-subtle/50"
                    style={{ width: pct(breakdown.counts.global) }}
                    aria-label={`Global ${pct(breakdown.counts.global)}`}
                />
                <span
                    className="bg-merism-accent"
                    style={{ width: pct(breakdown.counts.per_concept) }}
                    aria-label={`Per concept ${pct(breakdown.counts.per_concept)}`}
                />
                <span
                    className="bg-[oklch(0.72_0.18_60)]"
                    style={{ width: pct(breakdown.counts.comparative) }}
                    aria-label={`Comparative ${pct(breakdown.counts.comparative)}`}
                />
            </div>
            <div className="flex justify-between text-merism-caption text-merism-text-muted">
                <LegendDot color="bg-merism-text-subtle/50" label="Global" count={breakdown.counts.global} />
                <LegendDot color="bg-merism-accent" label="Per concept" count={breakdown.counts.per_concept} />
                <LegendDot color="bg-[oklch(0.72_0.18_60)]" label="Compare" count={breakdown.counts.comparative} />
            </div>
        </div>
    )
}

function LegendDot({ color, label, count }: { color: string; label: string; count: number }) {
    return (
        <span className="inline-flex items-center gap-1">
            <span className={"inline-block h-2 w-2 rounded-full " + color} aria-hidden="true" />
            <span className="font-mono tabular-nums">{label} · {count}</span>
        </span>
    )
}

// ── Scope radio (unchanged) ────────────────────────────────

const SCOPE_OPTIONS: Array<{ value: OutlineSectionScope; label: string }> = [
    { value: "global", label: "Global" },
    { value: "per_concept", label: "Per concept" },
    { value: "comparative", label: "Comparative" },
]

function ScopeRadio({ section }: { section: OutlineSection }): JSX.Element {
    const { setSectionScope } = useActions(outlineEditorLogic)
    const current = section.scope ?? "global"
    return (
        <div
            role="radiogroup"
            aria-label="Section scope"
            className="ml-auto inline-flex items-center gap-1 rounded-merism-full ring-1 ring-[color:var(--merism-hairline-strong)] bg-merism-surface p-1 text-merism-caption"
        >
            {SCOPE_OPTIONS.map((opt) => {
                const active = opt.value === current
                return (
                    <button
                        key={opt.value}
                        type="button"
                        role="radio"
                        aria-checked={active}
                        onClick={() => setSectionScope(section.id, opt.value, null)}
                        className={
                            "rounded-merism-full px-3 py-1 font-mono uppercase tracking-merism-caps-tight transition-colors " +
                            (active
                                ? "bg-merism-accent text-white"
                                : "text-merism-text-subtle hover:text-merism-text")
                        }
                    >
                        {opt.label}
                    </button>
                )
            })}
        </div>
    )
}

// Help icon unused now — keep import list clean
void HelpCircle
