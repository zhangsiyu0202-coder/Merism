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
    Copy,
    CopyPlus,
    GripVertical,
    Hash,
    Info,
    ListTodo,
    MessageCircleQuestion,
    MoreHorizontal,
    Plus,
    Star,
    Trash2,
    WandSparkles,
    CheckSquare2,
} from "lucide-react"
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react"

import {
    Button,
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
    Input,
    InputHelperText,
    InputLabel,
    Select,
    SectionLabel,
    Tag,
    Textarea,
    Tooltip,
    cn,
    functional,
} from "~/lib/merism"

import { studyLogic } from "~/features/studies/studyLogic"

import {
    outlineEditorLogic,
    type GuideOption,
    type GuideQuestion,
    type GuideQuestionType,
    type GuideSection,
    type ProbeAmount,
    type SectionRandomizationMode,
    type SelectionType,
} from "./outlineEditorLogic"

const MODULE_TABS = [
    { value: "overview", label: "Overview" },
    { value: "guide", label: "Guide" },
    { value: "screener", label: "Screener" },
    { value: "recruit", label: "Recruit" },
    { value: "results", label: "Results" },
] as const

const QUESTION_TYPE_META: Record<
    GuideQuestionType,
    { label: string; icon: JSX.Element; hint: string }
> = {
    conversational: {
        label: "Conversational",
        icon: <MessageCircleQuestion className="h-4 w-4" />,
        hint: "Open discussion prompt with probing controls.",
    },
    multiple_choice: {
        label: "Multiple Choice",
        icon: <CheckSquare2 className="h-4 w-4" />,
        hint: "Single- or multi-select response options.",
    },
    rating: {
        label: "Rating",
        icon: <Star className="h-4 w-4" />,
        hint: "Scaled judgement with labels and explanation follow-up.",
    },
    number_input: {
        label: "Number Input",
        icon: <Hash className="h-4 w-4" />,
        hint: "Numeric answer with unit and bounds.",
    },
    task: {
        label: "Task",
        icon: <ListTodo className="h-4 w-4" />,
        hint: "Goal-directed task flow with post-task probing.",
    },
}

const QUESTION_TYPE_OPTIONS = (
    Object.entries(QUESTION_TYPE_META) as Array<
        [GuideQuestionType, (typeof QUESTION_TYPE_META)[GuideQuestionType]]
    >
).map(([value, meta]) => ({
    value,
    label: (
        <span className="inline-flex items-center gap-2">
            {meta.icon}
            <span>{meta.label}</span>
        </span>
    ),
    description: meta.hint,
}))

const PROBE_AMOUNT_OPTIONS: Array<{ value: ProbeAmount; label: string }> = [
    { value: "light", label: "Light" },
    { value: "standard", label: "Standard" },
    { value: "deep", label: "Deep" },
]

const SELECTION_TYPE_OPTIONS: Array<{ value: SelectionType; label: string }> = [
    { value: "single_select", label: "Single select" },
    { value: "multi_select", label: "Multi select" },
]

const RATING_SCALE_OPTIONS: Array<{ value: GuideQuestion["scaleRange"]; label: string }> = [
    { value: "1-5", label: "1 - 5" },
    { value: "1-7", label: "1 - 7" },
    { value: "0-10", label: "0 - 10" },
]

const RANDOMIZATION_OPTIONS: Array<{ value: SectionRandomizationMode; label: string }> = [
    { value: "ordered", label: "Ordered" },
    { value: "shuffle_sections", label: "Shuffle sections" },
    { value: "shuffle_questions", label: "Shuffle questions" },
]

export default function OutlineTab(): JSX.Element {
    useMountedLogic(outlineEditorLogic)

    const { study } = useValues(studyLogic)
    const outlineState = useValues(outlineEditorLogic) as {
        sections: GuideSection[]
        selectedSectionId: string | null
        selectedQuestionId: string | null
        sectionRandomizationEnabled: boolean
        sectionRandomizationMode: SectionRandomizationMode
        draftRevision: number
        savedRevision: number
        isSavingGuide: boolean
        guideError: string | null
    }
    const {
        addSection,
        updateSectionTitle,
        duplicateSection,
        removeSection,
        moveQuestion,
        selectQuestion,
        addQuestion,
        duplicateQuestion,
        removeQuestion,
        updateQuestion,
        setQuestionType,
        addStimulusToQuestion,
        removeStimulusFromQuestion,
        addQuestionOption,
        updateQuestionOption,
        removeQuestionOption,
        moveQuestionOption,
        setSectionRandomizationEnabled,
        setSectionRandomizationMode,
    } = useActions(outlineEditorLogic) as {
        addSection: (
            sectionId: string,
            title: string,
            questionId: string | null,
        ) => void
        updateSectionTitle: (sectionId: string, title: string) => void
        duplicateSection: (sectionId: string, newSectionId: string, questionId: string) => void
        removeSection: (sectionId: string) => void
        moveQuestion: (sectionId: string, fromIndex: number, toIndex: number) => void
        selectQuestion: (sectionId: string, questionId: string) => void
        addQuestion: (sectionId: string, questionType: GuideQuestionType, questionId: string) => void
        duplicateQuestion: (
            sectionId: string,
            questionId: string,
            newQuestionId: string,
        ) => void
        removeQuestion: (sectionId: string, questionId: string) => void
        updateQuestion: (
            sectionId: string,
            questionId: string,
            patch: Partial<GuideQuestion>,
        ) => void
        setQuestionType: (
            sectionId: string,
            questionId: string,
            questionType: GuideQuestionType,
        ) => void
        addStimulusToQuestion: (sectionId: string, questionId: string, stimulusId: string) => void
        removeStimulusFromQuestion: (
            sectionId: string,
            questionId: string,
            stimulusId: string,
        ) => void
        addQuestionOption: (
            sectionId: string,
            questionId: string,
            optionId: string,
            text: string,
        ) => void
        updateQuestionOption: (
            sectionId: string,
            questionId: string,
            optionId: string,
            text: string,
        ) => void
        removeQuestionOption: (
            sectionId: string,
            questionId: string,
            optionId: string,
        ) => void
        moveQuestionOption: (
            sectionId: string,
            questionId: string,
            fromIndex: number,
            toIndex: number,
        ) => void
        setSectionRandomizationEnabled: (enabled: boolean) => void
        setSectionRandomizationMode: (mode: SectionRandomizationMode) => void
    }

    const {
        sections,
        selectedSectionId,
        selectedQuestionId,
        sectionRandomizationEnabled,
        sectionRandomizationMode,
        draftRevision,
        savedRevision,
        isSavingGuide,
        guideError,
    } =
        outlineState
    const isDirty = draftRevision !== savedRevision

    const orderedQuestionIds = useMemo(() => {
        const ids: string[] = []
        for (const section of sections) {
            for (const question of section.questions) {
                ids.push(question.id)
            }
        }
        return ids
    }, [sections])

    const questionIndexById = useMemo(() => {
        const map = new Map<string, number>()
        orderedQuestionIds.forEach((id, index) => {
            map.set(id, index + 1)
        })
        return map
    }, [orderedQuestionIds])

    const selectedLocation = useMemo(() => {
        for (const section of sections) {
            const question = section.questions.find((item) => item.id === selectedQuestionId)
            if (question) {
                return { section, question }
            }
        }
        return null
    }, [sections, selectedQuestionId])

    const handleAddSection = (): void => {
        const sectionId = makeId("section")
        const questionId = makeId("question")
        const nextIndex = sections.length + 1
        addSection(sectionId, `Section ${nextIndex}`, questionId)
    }

    const handleAddQuestion = (sectionId: string, type: GuideQuestionType): void => {
        addQuestion(sectionId, type, makeId("question"))
    }

    const handleDuplicateQuestion = (sectionId: string, questionId: string): void => {
        duplicateQuestion(sectionId, questionId, makeId("question"))
    }

    const handleDuplicateSection = (sectionId: string): void => {
        duplicateSection(sectionId, makeId("section"), makeId("question"))
    }

    const summary = useMemo(
        () => buildSummary(sections, selectedLocation?.question ?? null),
        [sections, selectedLocation],
    )

    const topStatus = isSavingGuide
        ? "Saving..."
        : guideError
          ? "Save failed"
          : isDirty
            ? "Unsaved changes"
            : "Saved"

    return (
        <div className="flex min-h-0 flex-col gap-6">
            <header className="rounded-merism-lg border border-[color:var(--merism-hairline)] bg-merism-surface px-5 py-4 shadow-merism-card">
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="min-w-0">
                        <div className="flex items-center gap-2">
                            <SectionLabel>Research Guide Builder</SectionLabel>
                            <Tag
                                variant={guideError ? "danger" : isDirty ? "warning" : "success"}
                                case="normal"
                            >
                                {topStatus}
                            </Tag>
                        </div>
                        <h1 className="mt-2 truncate font-display text-[length:var(--text-merism-title)] font-[500] text-merism-text">
                            {study?.name ?? "Untitled project"}
                        </h1>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                        {study && (
                            <Tag variant="outline" case="normal">
                                {study.status}
                            </Tag>
                        )}
                    </div>
                </div>

                <nav
                    aria-label="Project modules"
                    className="mt-4 flex gap-6 overflow-x-auto border-b border-[color:var(--merism-hairline)]"
                >
                    {MODULE_TABS.map((tab) => {
                        const active = tab.value === "guide"
                        return (
                            <button
                                key={tab.value}
                                type="button"
                                disabled={!active}
                                className={cn(
                                    "relative -mb-px border-b-2 px-1 pb-3 text-sm font-medium transition-colors",
                                    active
                                        ? "border-current text-merism-text"
                                        : "border-transparent text-merism-text-muted",
                                )}
                                style={active ? { borderBottomColor: functional.quote[500], color: functional.quote[500] } : undefined}
                                aria-current={active ? "page" : undefined}
                            >
                                {tab.label}
                            </button>
                        )
                    })}
                </nav>
            </header>

            <div className="grid min-h-0 gap-6 lg:grid-cols-[19rem_minmax(0,1fr)_18rem]">
                <aside className="min-h-0">
                    <GuideOutlinePanel
                        sections={sections}
                        selectedQuestionId={selectedQuestionId}
                        selectedSectionId={selectedSectionId}
                        questionIndexById={questionIndexById}
                        onSelectQuestion={selectQuestion}
                        onAddSection={handleAddSection}
                        onUpdateSectionTitle={updateSectionTitle}
                        onDuplicateSection={handleDuplicateSection}
                        onRemoveSection={removeSection}
                        onAddQuestion={handleAddQuestion}
                        onDuplicateQuestion={handleDuplicateQuestion}
                        onRemoveQuestion={removeQuestion}
                        onMoveQuestion={moveQuestion}
                    />
                </aside>

                <main className="min-h-0">
                    <DynamicQuestionEditor
                        section={selectedLocation?.section ?? null}
                        question={selectedLocation?.question ?? null}
                        questionNumber={selectedQuestionId ? questionIndexById.get(selectedQuestionId) ?? null : null}
                        onUpdateQuestion={updateQuestion}
                        onSetQuestionType={setQuestionType}
                        onAddStimulus={addStimulusToQuestion}
                        onRemoveStimulus={removeStimulusFromQuestion}
                        onAddQuestionOption={addQuestionOption}
                        onUpdateQuestionOption={updateQuestionOption}
                        onRemoveQuestionOption={removeQuestionOption}
                        onMoveQuestionOption={moveQuestionOption}
                        onDuplicateQuestion={handleDuplicateQuestion}
                        onDeleteQuestion={removeQuestion}
                    />
                </main>

                <aside className="min-h-0">
                    <SettingsAndSummaryPanel
                        sections={sections}
                        summary={summary}
                        randomizationEnabled={sectionRandomizationEnabled}
                        randomizationMode={sectionRandomizationMode}
                        onToggleRandomization={setSectionRandomizationEnabled}
                        onChangeRandomizationMode={setSectionRandomizationMode}
                    />
                </aside>
            </div>

        </div>
    )
}

function GuideOutlinePanel({
    sections,
    selectedQuestionId,
    selectedSectionId,
    questionIndexById,
    onSelectQuestion,
    onAddSection,
    onUpdateSectionTitle,
    onDuplicateSection,
    onRemoveSection,
    onAddQuestion,
    onDuplicateQuestion,
    onRemoveQuestion,
    onMoveQuestion,
}: {
    sections: GuideSection[]
    selectedQuestionId: string | null
    selectedSectionId: string | null
    questionIndexById: Map<string, number>
    onSelectQuestion: (sectionId: string, questionId: string) => void
    onAddSection: () => void
    onUpdateSectionTitle: (sectionId: string, title: string) => void
    onDuplicateSection: (sectionId: string) => void
    onRemoveSection: (sectionId: string) => void
    onAddQuestion: (sectionId: string, type: GuideQuestionType) => void
    onDuplicateQuestion: (sectionId: string, questionId: string) => void
    onRemoveQuestion: (sectionId: string, questionId: string) => void
    onMoveQuestion: (sectionId: string, fromIndex: number, toIndex: number) => void
}): JSX.Element {
    return (
        <Card className="flex h-full min-h-0 flex-col">
            <CardHeader className="gap-3 border-b border-[color:var(--merism-hairline)]">
                <div className="flex items-center justify-between gap-3">
                    <div>
                        <CardTitle className="text-base font-medium">Guide Outline</CardTitle>
                        <CardDescription>
                            Structure first: sections, questions, and type-specific controls.
                        </CardDescription>
                    </div>
                    <Button size="sm" variant="secondary" iconLeft={<Plus className="h-4 w-4" />} onClick={onAddSection}>
                        Add section
                    </Button>
                </div>
            </CardHeader>

            <CardContent className="min-h-0 flex-1 overflow-y-auto p-3">
                <div className="flex flex-col gap-4">
                    {sections.length === 0 ? (
                        <div className="rounded-merism-lg border border-dashed border-[color:var(--merism-hairline-strong)] bg-merism-bg-subtle p-4 text-sm text-merism-text-muted">
                            No sections yet. Add one to start shaping the guide structure.
                        </div>
                    ) : (
                        sections.map((section, index) => (
                            <SectionBlock
                                key={section.id}
                                section={section}
                                sectionIndex={index}
                                selectedQuestionId={selectedQuestionId}
                                selectedSectionId={selectedSectionId}
                                questionIndexById={questionIndexById}
                                onSelectQuestion={onSelectQuestion}
                                onUpdateSectionTitle={onUpdateSectionTitle}
                                onDuplicateSection={onDuplicateSection}
                                onRemoveSection={onRemoveSection}
                                onAddQuestion={onAddQuestion}
                                onDuplicateQuestion={onDuplicateQuestion}
                                onRemoveQuestion={onRemoveQuestion}
                                onMoveQuestion={onMoveQuestion}
                            />
                        ))
                    )}
                </div>
            </CardContent>
        </Card>
    )
}

function SectionBlock({
    section,
    sectionIndex,
    selectedQuestionId,
    selectedSectionId,
    questionIndexById,
    onSelectQuestion,
    onUpdateSectionTitle,
    onDuplicateSection,
    onRemoveSection,
    onAddQuestion,
    onDuplicateQuestion,
    onRemoveQuestion,
    onMoveQuestion,
}: {
    section: GuideSection
    sectionIndex: number
    selectedQuestionId: string | null
    selectedSectionId: string | null
    questionIndexById: Map<string, number>
    onSelectQuestion: (sectionId: string, questionId: string) => void
    onUpdateSectionTitle: (sectionId: string, title: string) => void
    onDuplicateSection: (sectionId: string) => void
    onRemoveSection: (sectionId: string) => void
    onAddQuestion: (sectionId: string, type: GuideQuestionType) => void
    onDuplicateQuestion: (sectionId: string, questionId: string) => void
    onRemoveQuestion: (sectionId: string, questionId: string) => void
    onMoveQuestion: (sectionId: string, fromIndex: number, toIndex: number) => void
}): JSX.Element {
    const sensors = useSensors(
        useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
        useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
    )

    const handleDragEnd = (event: DragEndEvent): void => {
        const { active, over } = event
        if (!over || active.id === over.id) return
        const fromIndex = section.questions.findIndex((question) => question.id === active.id)
        const toIndex = section.questions.findIndex((question) => question.id === over.id)
        if (fromIndex < 0 || toIndex < 0) return
        onMoveQuestion(section.id, fromIndex, toIndex)
    }

    return (
        <section
            className={cn(
                "rounded-merism-lg border border-[color:var(--merism-hairline)] bg-merism-surface p-3 shadow-merism-xs",
                selectedSectionId === section.id && "ring-1 ring-[color:var(--merism-accent-outline)]",
            )}
        >
            <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                        <span className="font-mono text-[11px] uppercase tracking-merism-caps text-merism-text-subtle">
                            Section {String(sectionIndex + 1).padStart(2, "0")}
                        </span>
                        <Tag variant="outline" size="sm" case="normal">
                            {section.questions.length} questions
                        </Tag>
                    </div>
                    <Input
                        value={section.title}
                        onChange={(e) => onUpdateSectionTitle(section.id, e.target.value)}
                        className="mt-2 h-9 border-none bg-transparent px-0 text-sm font-medium shadow-none focus-visible:ring-0"
                    />
                </div>

                <InlineMenu
                    ariaLabel="Section actions"
                    trigger={<MoreHorizontal className="h-4 w-4" />}
                    triggerClassName="inline-flex h-9 w-9 items-center justify-center rounded-merism-md text-merism-text-muted transition-colors hover:bg-merism-bg-subtle hover:text-merism-text"
                    items={[
                        {
                            label: "Duplicate section",
                            icon: <Copy className="h-4 w-4" />,
                            onClick: () => onDuplicateSection(section.id),
                        },
                        {
                            label: "Delete section",
                            icon: <Trash2 className="h-4 w-4" />,
                            danger: true,
                            onClick: () => onRemoveSection(section.id),
                        },
                    ]}
                />
            </div>

            <div className="mt-3">
                <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
                    <SortableContext
                        items={section.questions.map((question) => question.id)}
                        strategy={verticalListSortingStrategy}
                    >
                        <div className="flex flex-col gap-2">
                            {section.questions.map((question) => (
                                <SortableQuestionRow
                                    key={question.id}
                                    question={question}
                                    selected={selectedQuestionId === question.id}
                                    questionNumber={questionIndexById.get(question.id) ?? null}
                                    onSelect={() => onSelectQuestion(section.id, question.id)}
                                    onDuplicate={() => onDuplicateQuestion(section.id, question.id)}
                                    onRemove={() => onRemoveQuestion(section.id, question.id)}
                                />
                            ))}
                        </div>
                    </SortableContext>
                </DndContext>
            </div>

            <div className="mt-3">
                <InlineMenu
                    ariaLabel="Add question"
                    trigger={
                        <span className="inline-flex items-center gap-2">
                            <Plus className="h-4 w-4" />
                            Add question
                        </span>
                    }
                    triggerClassName="inline-flex w-full items-center justify-start rounded-merism-md px-2 py-2 text-sm text-merism-text-muted transition-colors hover:bg-merism-bg-subtle hover:text-merism-text"
                    items={QUESTION_TYPE_OPTIONS.map((option) => ({
                        label: QUESTION_TYPE_META[option.value].label,
                        icon: QUESTION_TYPE_META[option.value].icon,
                        onClick: () => onAddQuestion(section.id, option.value),
                    }))}
                    align="left"
                    menuClassName="w-60"
                />
            </div>
        </section>
    )
}

function SortableQuestionRow({
    question,
    selected,
    questionNumber,
    onSelect,
    onDuplicate,
    onRemove,
}: {
    question: GuideQuestion
    selected: boolean
    questionNumber: number | null
    onSelect: () => void
    onDuplicate: () => void
    onRemove: () => void
}): JSX.Element {
    const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
        id: question.id,
    })

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.7 : 1,
    }

    return (
        <div ref={setNodeRef} style={style}>
            <div
                role="button"
                tabIndex={0}
                onClick={onSelect}
                onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault()
                        onSelect()
                    }
                }}
                className={cn(
                    "group flex items-start gap-3 rounded-merism-md border px-3 py-2 text-left transition-colors",
                    selected
                        ? "border-[color:var(--merism-status-success)] bg-[color:var(--merism-status-success-bg)]"
                        : "border-transparent bg-transparent hover:border-[color:var(--merism-hairline)] hover:bg-merism-bg-subtle",
                )}
            >
                <button
                    {...attributes}
                    {...listeners}
                    type="button"
                    aria-label="Drag to reorder question"
                    className="mt-0.5 cursor-grab text-merism-text-subtle opacity-0 transition-opacity group-hover:opacity-100 hover:text-merism-text"
                >
                    <GripVertical className="h-4 w-4" />
                </button>

                <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                        <span className="font-mono text-[11px] uppercase tracking-merism-caps text-merism-text-subtle">
                            {questionNumber ? `Q${questionNumber}` : "Q"}
                        </span>
                        <span className="inline-flex items-center gap-1 text-[11px] uppercase tracking-merism-caps text-merism-text-subtle">
                            {QUESTION_TYPE_META[question.type].icon}
                            {QUESTION_TYPE_META[question.type].label}
                        </span>
                    </div>
                    <p className="mt-1 truncate text-sm text-merism-text">
                        {question.text || (
                            <span className="italic text-merism-text-subtle">
                                Untitled question
                            </span>
                        )}
                    </p>
                </div>

                <div className="flex items-center gap-1">
                    <button
                        type="button"
                        aria-label="Duplicate question"
                        onClick={onDuplicate}
                        className="inline-flex h-8 w-8 items-center justify-center rounded-merism-md text-merism-text-subtle opacity-0 transition-opacity group-hover:opacity-100 hover:bg-merism-bg-subtle hover:text-merism-text"
                    >
                        <Copy className="h-3.5 w-3.5" />
                    </button>
                    <button
                        type="button"
                        aria-label="Delete question"
                        onClick={onRemove}
                        className="inline-flex h-8 w-8 items-center justify-center rounded-merism-md text-merism-text-subtle opacity-0 transition-opacity group-hover:opacity-100 hover:bg-merism-bg-subtle hover:text-merism-danger"
                    >
                        <Trash2 className="h-3.5 w-3.5" />
                    </button>
                </div>
            </div>
        </div>
    )
}

function DynamicQuestionEditor({
    section,
    question,
    questionNumber,
    onUpdateQuestion,
    onSetQuestionType,
    onAddStimulus,
    onRemoveStimulus,
    onAddQuestionOption,
    onUpdateQuestionOption,
    onRemoveQuestionOption,
    onMoveQuestionOption,
    onDuplicateQuestion,
    onDeleteQuestion,
}: {
    section: GuideSection | null
    question: GuideQuestion | null
    questionNumber: number | null
    onUpdateQuestion: (sectionId: string, questionId: string, patch: Partial<GuideQuestion>) => void
    onSetQuestionType: (sectionId: string, questionId: string, questionType: GuideQuestionType) => void
    onAddStimulus: (sectionId: string, questionId: string, stimulusId: string) => void
    onRemoveStimulus: (sectionId: string, questionId: string, stimulusId: string) => void
    onAddQuestionOption: (
        sectionId: string,
        questionId: string,
        optionId: string,
        text: string,
    ) => void
    onUpdateQuestionOption: (
        sectionId: string,
        questionId: string,
        optionId: string,
        text: string,
    ) => void
    onRemoveQuestionOption: (
        sectionId: string,
        questionId: string,
        optionId: string,
    ) => void
    onMoveQuestionOption: (
        sectionId: string,
        questionId: string,
        fromIndex: number,
        toIndex: number,
    ) => void
    onDuplicateQuestion: (sectionId: string, questionId: string) => void
    onDeleteQuestion: (sectionId: string, questionId: string) => void
}): JSX.Element {
    if (!section || !question) {
        return (
            <Card className="h-full min-h-[28rem]">
                <CardContent className="flex h-full items-center justify-center p-8 text-center">
                    <div className="max-w-sm">
                        <div className="mx-auto mb-4 inline-flex h-12 w-12 items-center justify-center rounded-merism-full bg-merism-bg-subtle text-merism-text-subtle">
                            <WandSparkles className="h-5 w-5" />
                        </div>
                        <h2 className="text-base font-medium text-merism-text">
                            Select a question to edit
                        </h2>
                        <p className="mt-2 text-sm leading-relaxed text-merism-text-muted">
                            The center panel changes by question type. This is where you edit probing,
                            stimulus behavior, options, and other interview-specific controls.
                        </p>
                    </div>
                </CardContent>
            </Card>
        )
    }

    const meta = QUESTION_TYPE_META[question.type]

    return (
        <Card className="h-full min-h-0">
            <CardHeader className="gap-4 border-b border-[color:var(--merism-hairline)]">
                <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                        <CardTitle className="text-base font-medium">
                            {questionNumber ? `Question ${questionNumber}` : "Question"}
                        </CardTitle>
                        <CardDescription className="mt-1">
                            {section.title} · {meta.label}
                        </CardDescription>
                    </div>

                    <div className="flex items-center gap-1">
                        <Button
                            variant="ghost"
                            size="icon"
                            aria-label="Duplicate question"
                            iconLeft={<CopyPlus className="h-4 w-4" />}
                            onClick={() => onDuplicateQuestion(section.id, question.id)}
                        />
                        <Button
                            variant="ghost"
                            size="icon"
                            aria-label="Delete question"
                            iconLeft={<Trash2 className="h-4 w-4" />}
                            onClick={() => onDeleteQuestion(section.id, question.id)}
                        />
                    </div>
                </div>
            </CardHeader>

            <CardContent className="min-h-0 overflow-y-auto p-5">
                <div className="flex flex-col gap-6">
                    <EditorField label={question.type === "task" ? "Task text" : "Question text"} helper="Main text shown to participants.">
                        <Textarea
                            value={question.text}
                            onChange={(e) => onUpdateQuestion(section.id, question.id, { text: e.target.value })}
                            rows={4}
                            className="min-h-[120px]"
                            placeholder="Write the prompt that the participant will see or hear."
                        />
                    </EditorField>

                    <EditorField label="Question type" helper="Switching type swaps the configuration block below.">
                        <Select
                            value={question.type}
                            onValueChange={(value) => onSetQuestionType(section.id, question.id, value as GuideQuestionType)}
                            options={QUESTION_TYPE_OPTIONS}
                        />
                    </EditorField>

                    <div className="rounded-merism-lg border border-[color:var(--merism-hairline)] bg-merism-bg-subtle/35 p-4">
                        <div className="flex items-center justify-between gap-3">
                            <div>
                                <p className="font-mono text-[11px] uppercase tracking-merism-caps text-merism-text-subtle">
                                    Template
                                </p>
                                <h3 className="mt-1 text-sm font-medium text-merism-text">
                                    {meta.label} settings
                                </h3>
                            </div>
                            <Tag variant="outline" case="normal">
                                {meta.label}
                            </Tag>
                        </div>

                        <div className="mt-4">
                            {question.type === "conversational" && (
                                <ConversationalFields
                                    sectionId={section.id}
                                    question={question}
                                    onUpdateQuestion={onUpdateQuestion}
                                />
                            )}
                            {question.type === "task" && (
                                <TaskFields
                                    sectionId={section.id}
                                    question={question}
                                    onUpdateQuestion={onUpdateQuestion}
                                />
                            )}
                            {question.type === "multiple_choice" && (
                                <MultipleChoiceFields
                                    sectionId={section.id}
                                    question={question}
                                    onUpdateQuestion={onUpdateQuestion}
                                    onAddQuestionOption={onAddQuestionOption}
                                    onUpdateQuestionOption={onUpdateQuestionOption}
                                    onRemoveQuestionOption={onRemoveQuestionOption}
                                    onMoveQuestionOption={onMoveQuestionOption}
                                />
                            )}
                            {question.type === "rating" && (
                                <RatingFields
                                    sectionId={section.id}
                                    question={question}
                                    onUpdateQuestion={onUpdateQuestion}
                                />
                            )}
                            {question.type === "number_input" && (
                                <NumberInputFields
                                    sectionId={section.id}
                                    question={question}
                                    onUpdateQuestion={onUpdateQuestion}
                                />
                            )}
                        </div>
                    </div>

                    <div className="rounded-merism-lg border border-[color:var(--merism-hairline)] bg-merism-surface p-4">
                        <div className="flex items-center justify-between gap-3">
                            <div>
                                <p className="font-mono text-[11px] uppercase tracking-merism-caps text-merism-text-subtle">
                                    Stimulus
                                </p>
                                <h3 className="mt-1 text-sm font-medium text-merism-text">
                                    Attached references
                                </h3>
                            </div>
                            <Button
                                variant="secondary"
                                size="sm"
                                iconLeft={<Plus className="h-4 w-4" />}
                                onClick={() =>
                                    onAddStimulus(section.id, question.id, makeId("stimulus"))
                                }
                            >
                                Add stimulus
                            </Button>
                        </div>

                        {question.stimulusIds.length > 0 ? (
                            <div className="mt-3 flex flex-wrap gap-2">
                                {question.stimulusIds.map((stimulusId) => (
                                    <Tag
                                        key={stimulusId}
                                        variant="outline"
                                        removable
                                        onRemove={() =>
                                            onRemoveStimulus(section.id, question.id, stimulusId)
                                        }
                                        case="normal"
                                    >
                                        {stimulusId}
                                    </Tag>
                                ))}
                            </div>
                        ) : (
                            <p className="mt-3 text-sm text-merism-text-muted">
                                No stimulus linked yet.
                            </p>
                        )}
                    </div>
                </div>
            </CardContent>
        </Card>
    )
}

function ConversationalFields({
    sectionId,
    question,
    onUpdateQuestion,
}: {
    sectionId: string
    question: GuideQuestion
    onUpdateQuestion: (sectionId: string, questionId: string, patch: Partial<GuideQuestion>) => void
}): JSX.Element {
    return (
        <div className="flex flex-col gap-4">
            <EditorField label="Amount of probing">
                <Select
                    value={question.probingAmount}
                    onValueChange={(value) =>
                        onUpdateQuestion(sectionId, question.id, { probingAmount: value as ProbeAmount })
                    }
                    options={PROBE_AMOUNT_OPTIONS}
                />
            </EditorField>

            <EditorField label="Probing instructions">
                <Textarea
                    value={question.probingInstructions}
                    onChange={(e) =>
                        onUpdateQuestion(sectionId, question.id, {
                            probingInstructions: e.target.value,
                        })
                    }
                    rows={3}
                    placeholder="What should the interviewer probe for?"
                />
            </EditorField>

            <CheckboxRow
                label="Allow interviewer to skip question"
                helper="Useful when the participant already answered the signal elsewhere."
                checked={question.allowSkip}
                onChange={(checked) =>
                    onUpdateQuestion(sectionId, question.id, { allowSkip: checked })
                }
            />
        </div>
    )
}

function TaskFields({
    sectionId,
    question,
    onUpdateQuestion,
}: {
    sectionId: string
    question: GuideQuestion
    onUpdateQuestion: (sectionId: string, questionId: string, patch: Partial<GuideQuestion>) => void
}): JSX.Element {
    return (
        <div className="flex flex-col gap-4">
            <p className="rounded-merism-md border border-[color:var(--merism-hairline)] bg-merism-bg-subtle px-3 py-2 text-sm text-merism-text-muted">
                Task questions append a system prompt and are meant for goal-directed actions,
                not free-form discussion.
            </p>

            <CheckboxRow
                label="Allow interviewer to dynamically probe once they finish the task"
                helper="Lets the moderator ask follow-up questions after completion."
                checked={question.allowDynamicProbe}
                onChange={(checked) =>
                    onUpdateQuestion(sectionId, question.id, { allowDynamicProbe: checked })
                }
            />

            <CheckboxRow
                label="Allow interviewer to skip question"
                helper="Participants can move on if the task is not appropriate."
                checked={question.allowSkip}
                onChange={(checked) =>
                    onUpdateQuestion(sectionId, question.id, { allowSkip: checked })
                }
            />
        </div>
    )
}

function MultipleChoiceFields({
    sectionId,
    question,
    onUpdateQuestion,
    onAddQuestionOption,
    onUpdateQuestionOption,
    onRemoveQuestionOption,
    onMoveQuestionOption,
}: {
    sectionId: string
    question: GuideQuestion
    onUpdateQuestion: (sectionId: string, questionId: string, patch: Partial<GuideQuestion>) => void
    onAddQuestionOption: (
        sectionId: string,
        questionId: string,
        optionId: string,
        text: string,
    ) => void
    onUpdateQuestionOption: (
        sectionId: string,
        questionId: string,
        optionId: string,
        text: string,
    ) => void
    onRemoveQuestionOption: (
        sectionId: string,
        questionId: string,
        optionId: string,
    ) => void
    onMoveQuestionOption: (
        sectionId: string,
        questionId: string,
        fromIndex: number,
        toIndex: number,
    ) => void
}): JSX.Element {
    const sensors = useSensors(
        useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
        useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
    )

    const handleDragEnd = (event: DragEndEvent): void => {
        const { active, over } = event
        if (!over || active.id === over.id) return
        const fromIndex = question.options.findIndex((option) => option.id === active.id)
        const toIndex = question.options.findIndex((option) => option.id === over.id)
        if (fromIndex < 0 || toIndex < 0) return
        onMoveQuestionOption(sectionId, question.id, fromIndex, toIndex)
    }

    return (
        <div className="flex flex-col gap-4">
            <EditorField label="Selection type">
                <Select
                    value={question.selectionType}
                    onValueChange={(value) =>
                        onUpdateQuestion(sectionId, question.id, {
                            selectionType: value as SelectionType,
                        })
                    }
                    options={SELECTION_TYPE_OPTIONS}
                />
            </EditorField>

            <div className="rounded-merism-md border border-[color:var(--merism-hairline)] bg-merism-surface p-3">
                <div className="flex items-center justify-between gap-3">
                    <p className="font-mono text-[11px] uppercase tracking-merism-caps text-merism-text-subtle">
                        Options
                    </p>
                    <Button
                        size="sm"
                        variant="secondary"
                        iconLeft={<Plus className="h-4 w-4" />}
                        onClick={() =>
                            onAddQuestionOption(
                                sectionId,
                                question.id,
                                makeId("option"),
                                `Option ${question.options.length + 1}`,
                            )
                        }
                    >
                        Add option
                    </Button>
                </div>

                <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
                    <SortableContext
                        items={question.options.map((option) => option.id)}
                        strategy={verticalListSortingStrategy}
                    >
                        <div className="mt-3 flex flex-col gap-2">
                            {question.options.map((option, index) => (
                                <SortableOptionRow
                                    key={option.id}
                                    option={option}
                                    index={index}
                                    onUpdate={(text) =>
                                        onUpdateQuestionOption(sectionId, question.id, option.id, text)
                                    }
                                    onRemove={() =>
                                        onRemoveQuestionOption(sectionId, question.id, option.id)
                                    }
                                />
                            ))}
                        </div>
                    </SortableContext>
                </DndContext>
            </div>

            <CheckboxRow
                label="Randomize option order"
                helper="Keeps the response list fresh during repeated sessions."
                checked={question.randomizeOptionOrder}
                onChange={(checked) =>
                    onUpdateQuestion(sectionId, question.id, {
                        randomizeOptionOrder: checked,
                    })
                }
            />

            <CheckboxRow
                label='Allow "Other" option'
                helper="Adds a custom response path when the listed choices do not fit."
                checked={question.allowOtherOption}
                onChange={(checked) =>
                    onUpdateQuestion(sectionId, question.id, {
                        allowOtherOption: checked,
                    })
                }
            />

            <CheckboxRow
                label="Allow interviewer to skip question"
                helper="Use when the question should be optional in live interviews."
                checked={question.allowSkip}
                onChange={(checked) =>
                    onUpdateQuestion(sectionId, question.id, { allowSkip: checked })
                }
            />
        </div>
    )
}

function RatingFields({
    sectionId,
    question,
    onUpdateQuestion,
}: {
    sectionId: string
    question: GuideQuestion
    onUpdateQuestion: (sectionId: string, questionId: string, patch: Partial<GuideQuestion>) => void
}): JSX.Element {
    return (
        <div className="flex flex-col gap-4">
            <EditorField label="Scale range">
                <Select
                    value={question.scaleRange}
                    onValueChange={(value) =>
                        onUpdateQuestion(sectionId, question.id, {
                            scaleRange: value as GuideQuestion["scaleRange"],
                        })
                    }
                    options={RATING_SCALE_OPTIONS}
                />
            </EditorField>

            <div className="grid gap-4 md:grid-cols-3">
                <EditorField label="Low label">
                    <Input
                        value={question.lowLabel}
                        onChange={(e) =>
                            onUpdateQuestion(sectionId, question.id, { lowLabel: e.target.value })
                        }
                    />
                </EditorField>
                <EditorField label="Middle label">
                    <Input
                        value={question.middleLabel}
                        onChange={(e) =>
                            onUpdateQuestion(sectionId, question.id, {
                                middleLabel: e.target.value,
                            })
                        }
                    />
                </EditorField>
                <EditorField label="High label">
                    <Input
                        value={question.highLabel}
                        onChange={(e) =>
                            onUpdateQuestion(sectionId, question.id, { highLabel: e.target.value })
                        }
                    />
                </EditorField>
            </div>

            <div className="rounded-merism-md border border-[color:var(--merism-hairline)] bg-merism-bg-subtle px-3 py-2">
                <p className="font-mono text-[11px] uppercase tracking-merism-caps text-merism-text-subtle">
                    Rating preview
                </p>
                <div className="mt-2 flex items-center gap-2">
                    {buildScalePreview(question.scaleRange)}
                </div>
            </div>

            <CheckboxRow
                label="Ask for explanation after rating"
                helper="The moderator will ask why the participant chose that score."
                checked={question.askExplanationAfterRating}
                onChange={(checked) =>
                    onUpdateQuestion(sectionId, question.id, {
                        askExplanationAfterRating: checked,
                    })
                }
            />

            <EditorField label="Probing instructions">
                <Textarea
                    value={question.probingInstructions}
                    onChange={(e) =>
                        onUpdateQuestion(sectionId, question.id, {
                            probingInstructions: e.target.value,
                        })
                    }
                    rows={3}
                />
            </EditorField>

            <CheckboxRow
                label="Allow interviewer to skip question"
                helper="Makes the rating optional in live moderation."
                checked={question.allowSkip}
                onChange={(checked) =>
                    onUpdateQuestion(sectionId, question.id, { allowSkip: checked })
                }
            />
        </div>
    )
}

function NumberInputFields({
    sectionId,
    question,
    onUpdateQuestion,
}: {
    sectionId: string
    question: GuideQuestion
    onUpdateQuestion: (sectionId: string, questionId: string, patch: Partial<GuideQuestion>) => void
}): JSX.Element {
    return (
        <div className="flex flex-col gap-4">
            <div className="grid gap-4 md:grid-cols-2">
                <EditorField label="Placeholder">
                    <Input
                        value={question.placeholder}
                        onChange={(e) =>
                            onUpdateQuestion(sectionId, question.id, { placeholder: e.target.value })
                        }
                    />
                </EditorField>
                <EditorField label="Unit / suffix">
                    <Input
                        value={question.unitSuffix}
                        onChange={(e) =>
                            onUpdateQuestion(sectionId, question.id, { unitSuffix: e.target.value })
                        }
                    />
                </EditorField>
                <EditorField label="Minimum value">
                    <Input
                        value={question.minValue}
                        onChange={(e) =>
                            onUpdateQuestion(sectionId, question.id, { minValue: e.target.value })
                        }
                    />
                </EditorField>
                <EditorField label="Maximum value">
                    <Input
                        value={question.maxValue}
                        onChange={(e) =>
                            onUpdateQuestion(sectionId, question.id, { maxValue: e.target.value })
                        }
                    />
                </EditorField>
            </div>

            <div className="rounded-merism-md border border-[color:var(--merism-hairline)] bg-merism-bg-subtle px-3 py-2">
                <p className="font-mono text-[11px] uppercase tracking-merism-caps text-merism-text-subtle">
                    Number input preview
                </p>
                <div className="mt-2 flex items-center gap-2 text-sm text-merism-text-muted">
                    <span className="rounded-merism-md border border-[color:var(--merism-hairline)] bg-merism-surface px-3 py-2">
                        {question.placeholder || "0"}
                    </span>
                    {question.unitSuffix && <span>{question.unitSuffix}</span>}
                </div>
            </div>

            <CheckboxRow
                label="Allow decimal numbers"
                helper="Use when the answer may contain fractions or percentages."
                checked={question.allowDecimal}
                onChange={(checked) =>
                    onUpdateQuestion(sectionId, question.id, { allowDecimal: checked })
                }
            />

            <CheckboxRow
                label="Allow interviewer to skip question"
                helper="Makes the number question optional in the live interview."
                checked={question.allowSkip}
                onChange={(checked) =>
                    onUpdateQuestion(sectionId, question.id, { allowSkip: checked })
                }
            />
        </div>
    )
}

function SettingsAndSummaryPanel({
    sections,
    summary,
    randomizationEnabled,
    randomizationMode,
    onToggleRandomization,
    onChangeRandomizationMode,
}: {
    sections: GuideSection[]
    summary: ReturnType<typeof buildSummary>
    randomizationEnabled: boolean
    randomizationMode: SectionRandomizationMode
    onToggleRandomization: (enabled: boolean) => void
    onChangeRandomizationMode: (mode: SectionRandomizationMode) => void
}): JSX.Element {
    return (
        <div className="flex h-full min-h-0 flex-col gap-4">
            <Card className="shrink-0">
                <CardHeader className="gap-2 pb-3">
                    <CardTitle className="text-sm font-medium">General settings</CardTitle>
                    <CardDescription>Lightweight context controls for the guide.</CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-4 pt-0">
                    <CheckboxRow
                        label="Add section randomization"
                        helper="Turns on section-level ordering controls."
                        checked={randomizationEnabled}
                        onChange={onToggleRandomization}
                    />

                    <EditorField label="Randomization mode">
                        <Select
                            value={randomizationMode}
                            onValueChange={(value) =>
                                onChangeRandomizationMode(value as SectionRandomizationMode)
                            }
                            options={RANDOMIZATION_OPTIONS}
                            disabled={!randomizationEnabled}
                        />
                    </EditorField>
                </CardContent>
            </Card>

            <Card
                className="shrink-0 overflow-hidden"
                style={{ backgroundColor: `${functional.quote[500]}12` }}
            >
                <CardHeader className="gap-2 pb-3">
                    <CardTitle className="text-sm font-medium">Interview Summary</CardTitle>
                    <CardDescription>
                        A quiet snapshot of the structure while you edit.
                    </CardDescription>
                </CardHeader>
                <CardContent className="pt-0">
                    <dl className="grid grid-cols-2 gap-3">
                        {summary.stats.map((stat) => (
                            <SummaryStat key={stat.label} label={stat.label} value={stat.value} />
                        ))}
                    </dl>
                </CardContent>
            </Card>

            <Card className="min-h-0 flex-1">
                <CardHeader className="gap-2 pb-3">
                    <CardTitle className="text-sm font-medium">Context notes</CardTitle>
                    <CardDescription>
                        Keep this area quiet. It should support the editor, not compete with it.
                    </CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-2 pt-0 text-sm text-merism-text-muted">
                    <p>Total sections: {sections.length}</p>
                    <p>Total questions: {summary.totalQuestions}</p>
                    <p>Selected type: {summary.selectedType}</p>
                    <p>Stimulus-linked questions: {summary.questionsWithStimulus}</p>
                </CardContent>
            </Card>
        </div>
    )
}

function SummaryStat({ label, value }: { label: string; value: string | number }): JSX.Element {
    return (
        <div className="rounded-merism-md border border-[color:var(--merism-hairline)] bg-merism-surface/80 px-3 py-2">
            <dt className="font-mono text-[11px] uppercase tracking-merism-caps text-merism-text-subtle">
                {label}
            </dt>
            <dd className="mt-1 text-sm font-medium text-merism-text">{value}</dd>
        </div>
    )
}

function EditorField({
    label,
    helper,
    children,
}: {
    label: string
    helper?: string
    children: ReactNode
}): JSX.Element {
    return (
        <div className="flex flex-col gap-1.5">
            <InputLabel className="text-[11px] uppercase tracking-merism-caps text-merism-text-subtle">
                {label}
            </InputLabel>
            {children}
            {helper && <InputHelperText>{helper}</InputHelperText>}
        </div>
    )
}

function CheckboxRow({
    label,
    helper,
    checked,
    onChange,
}: {
    label: string
    helper?: string
    checked: boolean
    onChange: (checked: boolean) => void
}): JSX.Element {
    return (
        <label className="flex items-start gap-3 rounded-merism-md border border-[color:var(--merism-hairline)] bg-merism-surface px-3 py-2">
            <input
                type="checkbox"
                checked={checked}
                onChange={(e) => onChange(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded-merism-sm border-[color:var(--merism-hairline-strong)] text-merism-accent focus:ring-merism-accent/30"
            />
            <span className="min-w-0 flex-1">
                <span className="flex items-center gap-1.5 text-sm font-medium text-merism-text">
                    {label}
                    <Tooltip label={helper ?? label}>
                        <button
                            type="button"
                            aria-label={`${label} help`}
                            onClick={(event) => {
                                event.preventDefault()
                                event.stopPropagation()
                            }}
                            className="inline-flex h-4 w-4 items-center justify-center text-merism-text-subtle"
                        >
                            <Info className="h-3.5 w-3.5" />
                        </button>
                    </Tooltip>
                </span>
                {helper && <span className="mt-1 block text-xs leading-relaxed text-merism-text-muted">{helper}</span>}
            </span>
        </label>
    )
}

function SortableOptionRow({
    option,
    index,
    onUpdate,
    onRemove,
}: {
    option: GuideOption
    index: number
    onUpdate: (text: string) => void
    onRemove: () => void
}): JSX.Element {
    const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
        id: option.id,
    })

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.75 : 1,
    }

    return (
        <div ref={setNodeRef} style={style}>
            <div className="flex items-center gap-2 rounded-merism-md border border-[color:var(--merism-hairline)] bg-merism-bg-subtle px-2 py-1">
                <button
                    {...attributes}
                    {...listeners}
                    type="button"
                    aria-label="Drag option"
                    className="cursor-grab text-merism-text-subtle"
                >
                    <GripVertical className="h-4 w-4" />
                </button>
                <Input
                    value={option.text}
                    onChange={(e) => onUpdate(e.target.value)}
                    className="h-8 border-none bg-transparent px-0 shadow-none focus-visible:ring-0"
                    placeholder={`Option ${index + 1}`}
                />
                <button
                    type="button"
                    aria-label="Delete option"
                    onClick={onRemove}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-merism-md text-merism-text-subtle hover:bg-merism-surface hover:text-merism-danger"
                >
                    <Trash2 className="h-3.5 w-3.5" />
                </button>
            </div>
        </div>
    )
}

function InlineMenu({
    trigger,
    items,
    align = "right",
    menuClassName,
    triggerClassName,
    ariaLabel,
}: {
    trigger: ReactNode
    items: Array<{
        label: ReactNode
        icon?: ReactNode
        onClick: () => void
        danger?: boolean
    }>
    align?: "left" | "right"
    menuClassName?: string
    triggerClassName?: string
    ariaLabel?: string
}): JSX.Element {
    const [open, setOpen] = useState(false)
    const rootRef = useRef<HTMLDivElement | null>(null)

    useEffect(() => {
        if (!open) return

        const handlePointerDown = (event: PointerEvent): void => {
            if (
                rootRef.current &&
                event.target instanceof Node &&
                !rootRef.current.contains(event.target)
            ) {
                setOpen(false)
            }
        }

        const handleKeyDown = (event: KeyboardEvent): void => {
            if (event.key === "Escape") {
                setOpen(false)
            }
        }

        document.addEventListener("pointerdown", handlePointerDown)
        document.addEventListener("keydown", handleKeyDown)
        return () => {
            document.removeEventListener("pointerdown", handlePointerDown)
            document.removeEventListener("keydown", handleKeyDown)
        }
    }, [open])

    return (
        <div ref={rootRef} className="relative inline-flex">
            <button
                type="button"
                aria-label={ariaLabel}
                onClick={() => setOpen((next) => !next)}
                className={triggerClassName}
            >
                {trigger}
            </button>

            {open && (
                <div
                    role="menu"
                    className={cn(
                        "absolute z-30 mt-2 overflow-hidden rounded-merism-lg border border-[color:var(--merism-hairline)] bg-merism-surface p-1 shadow-merism-pop",
                        align === "right" ? "right-0" : "left-0",
                        menuClassName,
                    )}
                >
                    {items.map((item, index) => (
                        <button
                            key={index}
                            type="button"
                            role="menuitem"
                            onClick={() => {
                                setOpen(false)
                                item.onClick()
                            }}
                            className={cn(
                                "flex w-full items-center gap-2 rounded-merism-md px-3 py-2 text-left text-sm transition-colors hover:bg-merism-bg-subtle",
                                item.danger && "text-merism-danger",
                            )}
                        >
                            <span className="text-merism-text-subtle">{item.icon}</span>
                            <span>{item.label}</span>
                        </button>
                    ))}
                </div>
            )}
        </div>
    )
}

function buildScalePreview(scaleRange: GuideQuestion["scaleRange"]): JSX.Element[] {
    const values =
        scaleRange === "0-10"
            ? [0, 2, 4, 6, 8, 10]
            : scaleRange === "1-7"
                ? [1, 2, 3, 4, 5, 6, 7]
                : [1, 2, 3, 4, 5]
    return values.map((value) => (
        <span
            key={value}
            className="inline-flex h-8 w-8 items-center justify-center rounded-merism-full border border-[color:var(--merism-hairline)] bg-merism-surface text-sm text-merism-text"
        >
            {value}
        </span>
    ))
}

function buildSummary(
    sections: GuideSection[],
    selectedQuestion: GuideQuestion | null,
): {
    totalQuestions: number
    questionsWithStimulus: number
    selectedType: string
    stats: Array<{ label: string; value: string | number }>
} {
    const totalQuestions = sections.reduce((sum, section) => sum + section.questions.length, 0)
    const questionsWithStimulus = sections.reduce(
        (sum, section) =>
            sum + section.questions.filter((question) => question.stimulusIds.length > 0).length,
        0,
    )
    const estimatedMinutes = Math.max(5, Math.round((totalQuestions * 2.25) / 5) * 5)
    return {
        totalQuestions,
        questionsWithStimulus,
        selectedType: selectedQuestion ? QUESTION_TYPE_META[selectedQuestion.type].label : "None",
        stats: [
            { label: "Sections", value: sections.length },
            { label: "Questions", value: totalQuestions },
            { label: "Est. time", value: `${estimatedMinutes} min` },
            { label: "Stimuli", value: questionsWithStimulus },
        ],
    }
}

function makeId(prefix: string): string {
    const randomId =
        typeof crypto !== "undefined" && "randomUUID" in crypto
            ? crypto.randomUUID()
            : Math.random().toString(36).slice(2)
    return `${prefix}-${randomId.slice(0, 8)}`
}
