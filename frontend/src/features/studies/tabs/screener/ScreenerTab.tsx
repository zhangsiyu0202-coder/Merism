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
import { Check, GripVertical, Plus, ShieldCheck, Trash2 } from "lucide-react"
import { useMemo } from "react"

import {
    Button,
    LiveSummaryPanel,
    LogicCard,
    SectionLabel,
    Tag,
    ThreePaneLayout,
    type LiveStat,
} from "~/lib/merism"

import {
    screenerLogic,
    type ScreenerQuestion,
    type ScreenerQuestionType,
} from "./screenerLogic"

/**
 * ScreenerTab — 3-pane screener-question editor.
 *
 * Structure:
 * - LEFT:   nav listing all screener questions (click to scroll).
 * - MIDDLE: one LogicCard per question, containing the text editor
 *           + type selector + options editor + pass-criteria chips.
 *           Drag-reorder via ``@dnd-kit``.
 * - RIGHT:  LiveSummaryPanel recomputing on every edit: total
 *           questions, # with pass criteria, # missing criteria (warn
 *           tone), required count.
 *
 * Save-to-backend wiring lands when the screener endpoint comes
 * online; until then, state is local to the Kea logic.
 */
export default function ScreenerTab(): JSX.Element {
    useMountedLogic(screenerLogic)
    const { questions } = useValues(screenerLogic)
    const { addQuestion, moveQuestion } = useActions(screenerLogic)

    const sensors = useSensors(
        useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
        useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
    )

    const handleDragEnd = (e: DragEndEvent): void => {
        const { active, over } = e
        if (!over || active.id === over.id) return
        const from = questions.findIndex((q) => q.id === active.id)
        const to = questions.findIndex((q) => q.id === over.id)
        if (from === -1 || to === -1) return
        moveQuestion(from, to)
    }

    return (
        <div className="flex flex-col gap-6">
            <div className="flex items-center justify-between">
                <SectionLabel>Screener</SectionLabel>
                <Button
                    variant="secondary"
                    size="sm"
                    iconLeft={<Plus className="h-4 w-4" />}
                    onClick={() => addQuestion("single_choice")}
                >
                    Add question
                </Button>
            </div>

            <ThreePaneLayout
                left={<ScreenerNav questions={questions} />}
                middle={
                    questions.length === 0 ? (
                        <div className="rounded-merism-lg border border-dashed border-merism-border bg-merism-surface p-10 text-center text-sm text-merism-text-muted">
                            No screener questions yet. Add one to start filtering
                            participants.
                        </div>
                    ) : (
                        <DndContext
                            sensors={sensors}
                            collisionDetection={closestCenter}
                            onDragEnd={handleDragEnd}
                        >
                            <SortableContext
                                items={questions.map((q) => q.id)}
                                strategy={verticalListSortingStrategy}
                            >
                                <div className="flex flex-col gap-3">
                                    {questions.map((q, i) => (
                                        <ScreenerCard
                                            key={q.id}
                                            index={i}
                                            question={q}
                                        />
                                    ))}
                                </div>
                            </SortableContext>
                        </DndContext>
                    )
                }
                right={<ScreenerSummary questions={questions} />}
            />
        </div>
    )
}

// ── Left nav ──────────────────────────────────────────────

function ScreenerNav({ questions }: { questions: ScreenerQuestion[] }): JSX.Element {
    return (
        <nav aria-label="Screener questions" className="flex flex-col gap-1">
            <span className="px-2 pb-1 font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                Questions
            </span>
            {questions.map((q, i) => (
                <a
                    key={q.id}
                    href={`#screener-${q.id}`}
                    className="flex items-center gap-2 truncate rounded-merism-md px-2 py-2 text-sm text-merism-text transition-colors hover:bg-merism-bg-subtle"
                >
                    <span className="font-mono text-merism-caption text-merism-text-subtle">
                        {String(i + 1).padStart(2, "0")}
                    </span>
                    <span className="truncate">
                        {q.text || (
                            <span className="italic text-merism-text-subtle">
                                (empty)
                            </span>
                        )}
                    </span>
                </a>
            ))}
            {questions.length === 0 && (
                <span className="px-2 text-xs text-merism-text-subtle">
                    Nothing here yet.
                </span>
            )}
        </nav>
    )
}

// ── Middle: one LogicCard per question ────────────────────

function ScreenerCard({
    index,
    question,
}: {
    index: number
    question: ScreenerQuestion
}): JSX.Element {
    const {
        updateText,
        setType,
        toggleRequired,
        removeQuestion,
        setOptions,
        togglePassOption,
    } = useActions(screenerLogic)
    const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
        useSortable({ id: question.id })

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.6 : 1,
    }

    const updateOption = (i: number, value: string): void => {
        const next = [...question.options]
        next[i] = value
        setOptions(question.id, next)
    }

    const addOption = (): void => {
        setOptions(question.id, [
            ...question.options,
            `Option ${String.fromCharCode(65 + question.options.length)}`,
        ])
    }

    const removeOption = (i: number): void => {
        const next = [...question.options]
        next.splice(i, 1)
        setOptions(question.id, next)
    }

    const typeOptions: Array<{ value: ScreenerQuestionType; label: string }> = [
        { value: "single_choice", label: "Single" },
        { value: "multi_choice", label: "Multi" },
        { value: "free_text", label: "Text" },
    ]

    return (
        <div id={`screener-${question.id}`} ref={setNodeRef} style={style} className="scroll-mt-6">
            <LogicCard
                index={index + 1}
                icon={<ShieldCheck className="h-4 w-4" />}
                title={
                    <textarea
                        value={question.text}
                        onChange={(e) => updateText(question.id, e.target.value)}
                        rows={1}
                        placeholder="Screener question…"
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
                            onClick={() => removeQuestion(question.id)}
                            className="text-merism-text-subtle opacity-0 transition-opacity group-hover:opacity-100 hover:text-merism-danger"
                        >
                            <Trash2 className="h-4 w-4" />
                        </button>
                    </>
                }
            >
                <div className="flex flex-wrap items-center gap-2">
                    <div
                        role="radiogroup"
                        aria-label="Answer type"
                        className="inline-flex items-center gap-1 rounded-merism-full ring-1 ring-[color:var(--merism-hairline-strong)] bg-merism-bg-subtle p-1"
                    >
                        {typeOptions.map((t) => {
                            const active = question.type === t.value
                            return (
                                <button
                                    key={t.value}
                                    type="button"
                                    role="radio"
                                    aria-checked={active}
                                    onClick={() => setType(question.id, t.value)}
                                    className={
                                        "rounded-merism-full px-2 py-1 font-mono text-merism-caption uppercase tracking-merism-caps-tight transition-colors " +
                                        (active
                                            ? "bg-merism-accent text-white"
                                            : "text-merism-text-subtle hover:text-merism-text")
                                    }
                                >
                                    {t.label}
                                </button>
                            )
                        })}
                    </div>
                    <label className="inline-flex items-center gap-2 text-xs text-merism-text-muted">
                        <input
                            type="checkbox"
                            checked={question.required}
                            onChange={() => toggleRequired(question.id)}
                            className="accent-merism-accent"
                        />
                        required
                    </label>
                    {question.type !== "free_text" && (
                        <Tag
                            variant={
                                question.pass_option_indices.length === 0
                                    ? "outline"
                                    : "accent"
                            }
                            size="sm"
                        >
                            {question.pass_option_indices.length === 0
                                ? "no pass criteria"
                                : `${question.pass_option_indices.length} pass`}
                        </Tag>
                    )}
                </div>

                {question.type !== "free_text" && (
                    <ul className="flex flex-col gap-2">
                        {question.options.map((opt, i) => {
                            const passes = question.pass_option_indices.includes(i)
                            return (
                                <li
                                    key={i}
                                    className="group/opt flex items-center gap-2 rounded-merism-md bg-merism-bg-subtle/50 ring-1 ring-[color:var(--merism-hairline)] px-2 py-1"
                                >
                                    <button
                                        type="button"
                                        aria-label={passes ? "Unmark pass" : "Mark pass"}
                                        aria-pressed={passes}
                                        onClick={() => togglePassOption(question.id, i)}
                                        className={
                                            "flex h-5 w-5 shrink-0 items-center justify-center rounded-merism-sm border transition-colors " +
                                            (passes
                                                ? "border-merism-accent bg-merism-accent text-white"
                                                : "border-merism-border bg-merism-surface text-transparent hover:border-merism-accent")
                                        }
                                    >
                                        <Check className="h-3 w-3" />
                                    </button>
                                    <input
                                        value={opt}
                                        onChange={(e) => updateOption(i, e.target.value)}
                                        className="flex-1 bg-transparent text-sm text-merism-text outline-none"
                                    />
                                    <button
                                        type="button"
                                        aria-label="Remove option"
                                        onClick={() => removeOption(i)}
                                        className="text-merism-text-subtle opacity-0 transition-opacity group-hover/opt:opacity-100 hover:text-merism-danger"
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </button>
                                </li>
                            )
                        })}
                        <button
                            type="button"
                            onClick={addOption}
                            className="inline-flex items-center gap-2 self-start rounded-merism-md px-2 py-1 font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle transition-colors hover:text-merism-accent"
                        >
                            <Plus className="h-3 w-3" /> Add option
                        </button>
                    </ul>
                )}

                {question.type === "free_text" && (
                    <p className="text-xs text-merism-text-muted">
                        Free-text answers are saved but not auto-scored by the screener.
                        Reviewers see them in the participation queue.
                    </p>
                )}
            </LogicCard>
        </div>
    )
}

// ── Right live summary ────────────────────────────────────

function ScreenerSummary({ questions }: { questions: ScreenerQuestion[] }): JSX.Element {
    const stats = useMemo<LiveStat[]>(() => {
        const total = questions.length
        const withCriteria = questions.filter(
            (q) => q.type === "free_text" || q.pass_option_indices.length > 0,
        ).length
        const missingCriteria = total - withCriteria
        const required = questions.filter((q) => q.required).length

        return [
            { label: "Questions", value: total },
            {
                label: "With pass logic",
                value: withCriteria,
                hint: total ? `${Math.round((withCriteria / total) * 100)}%` : undefined,
                tone: withCriteria === total && total > 0 ? "ok" : "neutral",
            },
            {
                label: "Missing logic",
                value: missingCriteria,
                tone: missingCriteria > 0 ? "warn" : "ok",
            },
            { label: "Required", value: required },
        ]
    }, [questions])

    return (
        <LiveSummaryPanel
            title="Screener summary"
            subtitle="Pass criteria close the loop before save."
            stats={stats}
        />
    )
}
