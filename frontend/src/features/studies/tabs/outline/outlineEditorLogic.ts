import { arrayMove } from "@dnd-kit/sortable";
import {
  actions,
  afterMount,
  connect,
  kea,
  listeners,
  path,
  reducers,
} from "kea";
import { api, ApiRequestError } from "~/lib/api";
import { studyLogic } from "~/features/studies/studyLogic";
import type { V3Outline, V3Question } from "./types";
import type { outlineEditorLogicType } from "./outlineEditorLogicType";

export type GuideQuestionType =
  | "conversational"
  | "multiple_choice"
  | "rating"
  | "number_input"
  | "task";

export type SelectionType = "single_select" | "multi_select";
export type ProbeAmount = "off" | "standard" | "deep";
export type SectionRandomizationMode =
  | "ordered"
  | "shuffle_sections"
  | "shuffle_questions";

export interface GuideOption {
  id: string;
  text: string;
}

export interface GuideQuestion {
  id: string;
  type: GuideQuestionType;
  text: string;
  probingAmount: ProbeAmount;
  probingInstructions: string;
  allowSkip: boolean;
  allowDynamicProbe: boolean;
  stimulusIds: string[];
  selectionType: SelectionType;
  options: GuideOption[];
  randomizeOptionOrder: boolean;
  allowOtherOption: boolean;
  scaleRange: "1-5" | "1-7" | "0-10";
  lowLabel: string;
  middleLabel: string;
  highLabel: string;
  askExplanationAfterRating: boolean;
  placeholder: string;
  unitSuffix: string;
  minValue: string;
  maxValue: string;
  allowDecimal: boolean;
}

export interface GuideSection {
  id: string;
  title: string;
  questions: GuideQuestion[];
}

export type ProbePolicy = ProbeAmount;
export type OutlineSectionScope = "global" | "per_concept" | "comparative";
export type OutlineSection = GuideSection;

interface InterviewGuideRecord {
  id: string;
  study: string;
  version: string;
  is_current: boolean;
  language: string;
  sections: GuideSection[];
  updated_at: string;
}

interface StudyOutlineResponse {
  outline: V3Outline | null;
  legacy_sections?: unknown;
}

interface SavedInterviewGuideResponse {
  id: string;
  study: string;
  version: string;
  is_current: boolean;
  language: string;
  sections: unknown;
  updated_at: string;
}

export const DEFAULT_SECTION_RANDOMIZATION_MODE: SectionRandomizationMode =
  "ordered";

const QUESTION_TYPE_DEFAULTS: Record<
  GuideQuestionType,
  Omit<GuideQuestion, "id" | "text">
> = {
  conversational: {
    type: "conversational",
    probingAmount: "standard",
    probingInstructions:
      "Probe for context, examples, and moments of friction when needed.",
    allowSkip: true,
    allowDynamicProbe: false,
    stimulusIds: [],
    selectionType: "single_select",
    options: [],
    randomizeOptionOrder: false,
    allowOtherOption: false,
    scaleRange: "1-5",
    lowLabel: "",
    middleLabel: "",
    highLabel: "",
    askExplanationAfterRating: false,
    placeholder: "",
    unitSuffix: "",
    minValue: "",
    maxValue: "",
    allowDecimal: false,
  },
  task: {
    type: "task",
    probingAmount: "standard",
    probingInstructions:
      "Use probing only after the participant finishes the task.",
    allowSkip: true,
    allowDynamicProbe: true,
    stimulusIds: [],
    selectionType: "single_select",
    options: [],
    randomizeOptionOrder: false,
    allowOtherOption: false,
    scaleRange: "1-5",
    lowLabel: "",
    middleLabel: "",
    highLabel: "",
    askExplanationAfterRating: false,
    placeholder: "",
    unitSuffix: "",
    minValue: "",
    maxValue: "",
    allowDecimal: false,
  },
  multiple_choice: {
    type: "multiple_choice",
    probingAmount: "standard",
    probingInstructions: "Probe only when the answer needs clarification.",
    allowSkip: true,
    allowDynamicProbe: false,
    stimulusIds: [],
    selectionType: "single_select",
    options: [
      { id: "opt-1", text: "Option 1" },
      { id: "opt-2", text: "Option 2" },
      { id: "opt-3", text: "Option 3" },
    ],
    randomizeOptionOrder: false,
    allowOtherOption: false,
    scaleRange: "1-5",
    lowLabel: "",
    middleLabel: "",
    highLabel: "",
    askExplanationAfterRating: false,
    placeholder: "",
    unitSuffix: "",
    minValue: "",
    maxValue: "",
    allowDecimal: false,
  },
  rating: {
    type: "rating",
    probingAmount: "standard",
    probingInstructions:
      "Ask for rationale after the score when the rating is ambiguous.",
    allowSkip: true,
    allowDynamicProbe: false,
    stimulusIds: [],
    selectionType: "single_select",
    options: [],
    randomizeOptionOrder: false,
    allowOtherOption: false,
    scaleRange: "1-5",
    lowLabel: "Low",
    middleLabel: "Neutral",
    highLabel: "High",
    askExplanationAfterRating: true,
    placeholder: "",
    unitSuffix: "",
    minValue: "",
    maxValue: "",
    allowDecimal: false,
  },
  number_input: {
    type: "number_input",
    probingAmount: "standard",
    probingInstructions:
      "Keep probes short; the answer is mainly quantitative.",
    allowSkip: true,
    allowDynamicProbe: false,
    stimulusIds: [],
    selectionType: "single_select",
    options: [],
    randomizeOptionOrder: false,
    allowOtherOption: false,
    scaleRange: "1-5",
    lowLabel: "",
    middleLabel: "",
    highLabel: "",
    askExplanationAfterRating: false,
    placeholder: "Enter a number",
    unitSuffix: "",
    minValue: "",
    maxValue: "",
    allowDecimal: false,
  },
};

function makeId(prefix: string): string {
  const randomId =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2);
  // v3 Outline schema enforces ``^[a-zA-Z0-9_]+$`` on section/question
  // ids — strip dashes from the random part and use ``_`` not ``-`` as
  // the separator. Otherwise PUT /api/studies/<id>/outline/ returns 422
  // and the UI shows "Failed to save guide.".
  const cleanId = randomId.replace(/[^a-zA-Z0-9]/g, "").slice(0, 8) || "x";
  return `${prefix}_${cleanId}`;
}

function normalizeOutlineId(raw: string): string {
  // Mirror the backend's ``migrate_guide_to_v3._normalize_id`` so any
  // legacy ids (e.g. loaded from a v1-list-shape guide that had dashes
  // or other punctuation) are coerced into ``[a-zA-Z0-9_]+`` before
  // we PUT them back to v3.
  const cleaned = raw.replace(/[^a-zA-Z0-9_]/g, "_");
  return cleaned.length > 0 ? cleaned : "x";
}

function buildQuestion(type: GuideQuestionType, text: string): GuideQuestion {
  return {
    id: makeId(type),
    text,
    ...QUESTION_TYPE_DEFAULTS[type],
  };
}

function buildStarterSections(): GuideSection[] {
  return [
    {
      id: "section_context",
      title: "Context",
      questions: [
        buildQuestion(
          "conversational",
          "Tell me about the last time you tried to complete this task.",
        ),
        buildQuestion(
          "task",
          "Open the page and try to finish the core flow without help.",
        ),
      ],
    },
    {
      id: "section_core",
      title: "Core exploration",
      questions: [
        buildQuestion(
          "multiple_choice",
          "Which part of the experience felt most difficult?",
        ),
        buildQuestion("rating", "How confident did you feel while doing that?"),
      ],
    },
    {
      id: "section_close",
      title: "Wrap-up",
      questions: [
        buildQuestion("number_input", "How many minutes did this take?"),
      ],
    },
  ];
}

const STARTER_SECTIONS = buildStarterSections();

function probePolicyToProbeAmount(value: unknown): ProbeAmount {
  if (value === "off" || value === "standard" || value === "deep") {
    return value;
  }
  if (value === "none") {
    return "off";
  }
  if (value === "light") {
    return "standard";
  }
  return "standard";
}

function probeAmountToFollowUpMode(
  value: ProbeAmount,
): V3Question["follow_up_mode"] {
  if (value === "off" || value === "standard" || value === "deep") {
    return value;
  }
  return "standard";
}

function makeGuideQuestionFromV3Question(question: V3Question): GuideQuestion {
  return {
    ...buildQuestion("conversational", question.ask),
    id: question.id,
    probingAmount: probePolicyToProbeAmount(question.follow_up_mode),
    probingInstructions: question.probe_instruction ?? "",
  };
}

function makeGuideSectionFromOutlineSection(
  section: V3Outline["sections"][number],
): GuideSection {
  return {
    id: section.id,
    title: section.title,
    questions: section.questions.map((question) =>
      makeGuideQuestionFromV3Question(question),
    ),
  };
}

function makeGuideSectionsFromOutline(
  outline: V3Outline | null | undefined,
): GuideSection[] {
  if (!outline) {
    return STARTER_SECTIONS;
  }
  return outline.sections.map((section) =>
    makeGuideSectionFromOutlineSection(section),
  );
}

function makeGuideQuestionFromLegacyQuestion(
  rawQuestion: unknown,
  fallbackIndex: number,
): GuideQuestion {
  if (rawQuestion === null || typeof rawQuestion !== "object") {
    return buildQuestion("conversational", "New question");
  }

  const question = rawQuestion as Record<string, unknown>;
  const text =
    (typeof question.text === "string" && question.text.trim()) ||
    (typeof question.ask === "string" && question.ask.trim()) ||
    "New question";
  const followUpMode = probePolicyToProbeAmount(question.probe_policy);
  const probingInstructions =
    (typeof question.intent === "string" && question.intent) ||
    (typeof question.probingInstructions === "string" &&
      question.probingInstructions) ||
    (typeof question.probe_instruction === "string" &&
      question.probe_instruction) ||
    "";

  return {
    ...buildQuestion("conversational", text),
    id:
      typeof question.id === "string" && question.id
        ? question.id
        : makeId(`question_${fallbackIndex}`),
    probingAmount: followUpMode,
    probingInstructions,
    stimulusIds: Array.isArray(question.linked_stimulus_ids)
      ? question.linked_stimulus_ids.filter(
          (value): value is string => typeof value === "string",
        )
      : [],
  };
}

function makeGuideSectionsFromLegacySections(
  legacySections: unknown,
): GuideSection[] {
  if (!Array.isArray(legacySections)) {
    return STARTER_SECTIONS;
  }

  const sections: GuideSection[] = legacySections.flatMap(
    (rawSection, index) => {
      if (rawSection === null || typeof rawSection !== "object") {
        return [];
      }
      const section = rawSection as Record<string, unknown>;
      const questions = Array.isArray(section.questions)
        ? section.questions.map((question, questionIndex) =>
            makeGuideQuestionFromLegacyQuestion(question, questionIndex),
          )
        : [];
      return [
        {
          id:
            typeof section.id === "string" && section.id
              ? section.id
              : makeId(`section_${index}`),
          title:
            typeof section.title === "string" && section.title
              ? section.title
              : `Section ${index + 1}`,
          questions:
            questions.length > 0
              ? questions
              : [buildQuestion("conversational", "New question")],
        },
      ];
    },
  );

  return sections.length > 0 ? sections : STARTER_SECTIONS;
}

function makeOutlineFromGuideSections(sections: GuideSection[]): V3Outline {
  return {
    version: "v3",
    sections: sections.map((section) => ({
      id: normalizeOutlineId(section.id),
      title: section.title,
      questions: section.questions.map((question) => ({
        id: normalizeOutlineId(question.id),
        ask: question.text,
        follow_up_mode: probeAmountToFollowUpMode(question.probingAmount),
        probe_instruction: question.probingInstructions.trim() || null,
      })),
    })),
  };
}

function makeGuideRecordFromSections(
  sections: GuideSection[],
  metadata: {
    id: string;
    study: string;
    version: string;
    language: string;
    isCurrent: boolean;
    updatedAt: string;
  },
): InterviewGuideRecord {
  return {
    id: metadata.id,
    study: metadata.study,
    version: metadata.version,
    is_current: metadata.isCurrent,
    language: metadata.language,
    sections,
    updated_at: metadata.updatedAt,
  };
}

function makeGuideRecordFromOutlineResponse(
  response: StudyOutlineResponse,
  studyId: string,
): InterviewGuideRecord {
  const sections = response.outline
    ? makeGuideSectionsFromOutline(response.outline)
    : makeGuideSectionsFromLegacySections(response.legacy_sections);
  return makeGuideRecordFromSections(sections, {
    id: `${studyId}-outline`,
    study: studyId,
    version: "v3",
    language: "en",
    isCurrent: true,
    updatedAt: new Date().toISOString(),
  });
}

function isV3Outline(value: unknown): value is V3Outline {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const outline = value as Record<string, unknown>;
  return outline.version === "v3" && Array.isArray(outline.sections);
}

function makeGuideRecordFromSavedGuide(
  response: SavedInterviewGuideResponse,
): InterviewGuideRecord {
  const sections = isV3Outline(response.sections)
    ? makeGuideSectionsFromOutline(response.sections)
    : makeGuideSectionsFromLegacySections(response.sections);
  return makeGuideRecordFromSections(sections, {
    id: response.id,
    study: response.study,
    version: response.version || "v3",
    language: response.language || "en",
    isCurrent: response.is_current,
    updatedAt: response.updated_at,
  });
}

function cloneQuestion(question: GuideQuestion): GuideQuestion {
  return {
    ...question,
    id: makeId(question.type),
    options: question.options.map((option) => ({
      ...option,
      id: makeId("option"),
    })),
    stimulusIds: [...question.stimulusIds],
  };
}

function updateQuestion(
  sections: GuideSection[],
  sectionId: string,
  questionId: string,
  patch: Partial<GuideQuestion>,
): GuideSection[] {
  return sections.map((section) => {
    if (section.id !== sectionId) return section;
    return {
      ...section,
      questions: section.questions.map((question) => {
        if (question.id !== questionId) return question;
        return {
          ...question,
          ...patch,
        };
      }),
    };
  });
}

function resetQuestionType(
  question: GuideQuestion,
  type: GuideQuestionType,
): GuideQuestion {
  const defaults = QUESTION_TYPE_DEFAULTS[type];
  return {
    ...question,
    type,
    probingAmount: defaults.probingAmount,
    probingInstructions: defaults.probingInstructions,
    allowSkip: defaults.allowSkip,
    allowDynamicProbe: defaults.allowDynamicProbe,
    selectionType: defaults.selectionType,
    options: defaults.options.map((option) => ({
      ...option,
      id: makeId("option"),
    })),
    randomizeOptionOrder: defaults.randomizeOptionOrder,
    allowOtherOption: defaults.allowOtherOption,
    scaleRange: defaults.scaleRange,
    lowLabel: defaults.lowLabel,
    middleLabel: defaults.middleLabel,
    highLabel: defaults.highLabel,
    askExplanationAfterRating: defaults.askExplanationAfterRating,
    placeholder: defaults.placeholder,
    unitSuffix: defaults.unitSuffix,
    minValue: defaults.minValue,
    maxValue: defaults.maxValue,
    allowDecimal: defaults.allowDecimal,
  };
}

function firstQuestionLocation(
  sections: GuideSection[],
): { sectionId: string; questionId: string } | null {
  for (const section of sections) {
    const question = section.questions[0];
    if (question) {
      return { sectionId: section.id, questionId: question.id };
    }
  }
  return null;
}

function findQuestion(
  sections: GuideSection[],
  sectionId: string,
  questionId: string,
): GuideQuestion | null {
  const section = sections.find((item) => item.id === sectionId);
  if (!section) return null;
  return (
    section.questions.find((question) => question.id === questionId) ?? null
  );
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) {
    return error.detail?.detail ?? fallback;
  }
  if (error instanceof Error) {
    return error.message || fallback;
  }
  return fallback;
}

function defineActionCreator<T extends (...args: any[]) => unknown>(
  creator: T,
): (...args: unknown[]) => unknown {
  return creator as unknown as (...args: unknown[]) => unknown;
}

let autosaveTimer: number | null = null;

// Manual-save mode (2026-05-24): autosave was killing edits when users
// switched tabs before the 900ms debounce fired. The list below is kept
// for the ``autosaveQueued`` reducer (the "unsaved changes" indicator)
// but is no longer wired to a setTimeout — saves only fire on explicit
// ``saveGuide`` action from the Save button.

// ── Stale localStorage cleanup ────────────────────────────────
//
// An earlier (2026-05-24 morning) iteration shipped a localStorage
// draft layer that ended up restoring stale "starter" sections over
// the server's real outline. The layer has been removed. This helper
// runs once on logic mount to evict any leftover keys so users who
// hit that bug auto-recover on next page load.

const _STALE_DRAFT_PREFIX = "merism:outline-draft";

function evictStaleDraftKeys(): void {
  if (typeof window === "undefined") return;
  try {
    const toDelete: string[] = [];
    for (let i = 0; i < window.localStorage.length; i++) {
      const key = window.localStorage.key(i);
      if (key && key.startsWith(_STALE_DRAFT_PREFIX)) {
        toDelete.push(key);
      }
    }
    for (const key of toDelete) {
      window.localStorage.removeItem(key);
    }
  } catch {
    // ignore — quota / privacy / etc.
  }
}
const AUTOSAVE_ACTIONS = [
  "addSection",
  "updateSectionTitle",
  "duplicateSection",
  "removeSection",
  "moveSection",
  "addQuestion",
  "duplicateQuestion",
  "removeQuestion",
  "moveQuestion",
  "updateQuestion",
  "setQuestionType",
  "addStimulusToQuestion",
  "removeStimulusFromQuestion",
  "addQuestionOption",
  "updateQuestionOption",
  "removeQuestionOption",
  "moveQuestionOption",
  "setSectionRandomizationEnabled",
  "setSectionRandomizationMode",
] as const;

function scheduleAutosave(_triggerSave: () => void): void {
  // No-op: kept for source-compat with the reducer scaffolding above.
  // Autosave was removed 2026-05-24 in favor of an explicit Save button.
  if (autosaveTimer !== null) {
    window.clearTimeout(autosaveTimer);
    autosaveTimer = null;
  }
}

export const outlineEditorLogic = kea<outlineEditorLogicType>([
  path(["features", "studies", "tabs", "outline", "outlineEditorLogic"]),

  connect(() => ({
    values: [studyLogic, ["studyId"]],
    actions: [studyLogic, ["loadStudySuccess"]],
  })),

  actions({
    addSection: defineActionCreator(
      (sectionId: string, title: string, questionId: string | null) => ({
        sectionId,
        title,
        questionId,
      }),
    ),
    updateSectionTitle: defineActionCreator(
      (sectionId: string, title: string) => ({
        sectionId,
        title,
      }),
    ),
    duplicateSection: defineActionCreator(
      (sectionId: string, newSectionId: string, questionId: string) => ({
        sectionId,
        newSectionId,
        questionId,
      }),
    ),
    removeSection: defineActionCreator((sectionId: string) => ({ sectionId })),
    moveSection: defineActionCreator((fromIndex: number, toIndex: number) => ({
      fromIndex,
      toIndex,
    })),
    selectQuestion: defineActionCreator(
      (sectionId: string, questionId: string) => ({
        sectionId,
        questionId,
      }),
    ),
    clearSelection: true,
    addQuestion: defineActionCreator(
      (
        sectionId: string,
        questionType: GuideQuestionType,
        questionId: string,
      ) => ({
        sectionId,
        questionType,
        questionId,
      }),
    ),
    duplicateQuestion: defineActionCreator(
      (sectionId: string, questionId: string, newQuestionId: string) => ({
        sectionId,
        questionId,
        newQuestionId,
      }),
    ),
    removeQuestion: defineActionCreator(
      (sectionId: string, questionId: string) => ({
        sectionId,
        questionId,
      }),
    ),
    moveQuestion: defineActionCreator(
      (sectionId: string, fromIndex: number, toIndex: number) => ({
        sectionId,
        fromIndex,
        toIndex,
      }),
    ),
    updateQuestion: defineActionCreator(
      (
        sectionId: string,
        questionId: string,
        patch: Partial<GuideQuestion>,
      ) => ({
        sectionId,
        questionId,
        patch,
      }),
    ),
    setQuestionType: defineActionCreator(
      (
        sectionId: string,
        questionId: string,
        questionType: GuideQuestionType,
      ) => ({
        sectionId,
        questionId,
        questionType,
      }),
    ),
    addStimulusToQuestion: defineActionCreator(
      (sectionId: string, questionId: string, stimulusId: string) => ({
        sectionId,
        questionId,
        stimulusId,
      }),
    ),
    removeStimulusFromQuestion: defineActionCreator(
      (sectionId: string, questionId: string, stimulusId: string) => ({
        sectionId,
        questionId,
        stimulusId,
      }),
    ),
    addQuestionOption: defineActionCreator(
      (
        sectionId: string,
        questionId: string,
        optionId: string,
        text: string,
      ) => ({
        sectionId,
        questionId,
        optionId,
        text,
      }),
    ),
    updateQuestionOption: defineActionCreator(
      (
        sectionId: string,
        questionId: string,
        optionId: string,
        text: string,
      ) => ({
        sectionId,
        questionId,
        optionId,
        text,
      }),
    ),
    removeQuestionOption: defineActionCreator(
      (sectionId: string, questionId: string, optionId: string) => ({
        sectionId,
        questionId,
        optionId,
      }),
    ),
    moveQuestionOption: defineActionCreator(
      (
        sectionId: string,
        questionId: string,
        fromIndex: number,
        toIndex: number,
      ) => ({
        sectionId,
        questionId,
        fromIndex,
        toIndex,
      }),
    ),
    setSectionRandomizationEnabled: defineActionCreator((enabled: boolean) => ({
      enabled,
    })),
    setSectionRandomizationMode: defineActionCreator(
      (mode: SectionRandomizationMode) => ({
        mode,
      }),
    ),
    loadGuide: true,
    loadGuideSuccess: defineActionCreator(
      (guide: InterviewGuideRecord | null) => ({
        guide,
      }),
    ),
    loadGuideFailure: defineActionCreator((error: string) => ({ error })),
    saveGuide: defineActionCreator((revision: number) => ({ revision })),
    saveGuideSuccess: defineActionCreator(
      (guide: InterviewGuideRecord, revision: number) => ({ guide, revision }),
    ),
    saveGuideFailure: defineActionCreator((error: string) => ({ error })),
    markSaved: true,
  }),

  reducers({
    sections: [
      STARTER_SECTIONS,
      {
        loadGuideSuccess: (state, { guide }) =>
          guide ? guide.sections : state,
        saveGuideSuccess: (_state, { guide }) =>
          guide.sections ?? STARTER_SECTIONS,
        addSection: (state, { sectionId, title, questionId }) => [
          ...state,
          {
            id: sectionId,
            title,
            questions: [
              {
                ...buildQuestion("conversational", "New question"),
                id: questionId ?? makeId("question"),
              },
            ],
          },
        ],
        updateSectionTitle: (state, { sectionId, title }) =>
          state.map((section) =>
            section.id === sectionId ? { ...section, title } : section,
          ),
        duplicateSection: (state, { sectionId, newSectionId, questionId }) =>
          state.flatMap((section) => {
            if (section.id !== sectionId) return [section];
            const clonedQuestions = section.questions.map((question, index) => {
              const cloned = cloneQuestion(question);
              if (index === 0) {
                cloned.id = questionId;
              }
              return cloned;
            });
            const cloned = {
              ...section,
              id: newSectionId,
              title: `${section.title} copy`,
              questions: clonedQuestions,
            };
            return [section, cloned];
          }),
        removeSection: (state, { sectionId }) =>
          state.filter((section) => section.id !== sectionId),
        moveSection: (state, { fromIndex, toIndex }) =>
          arrayMove(state, fromIndex, toIndex),
        addQuestion: (state, { sectionId, questionType, questionId }) =>
          state.map((section) => {
            if (section.id !== sectionId) return section;
            return {
              ...section,
              questions: [
                ...section.questions,
                {
                  ...buildQuestion(questionType, "New question"),
                  id: questionId,
                },
              ],
            };
          }),
        duplicateQuestion: (state, { sectionId, questionId, newQuestionId }) =>
          state.map((section) => {
            if (section.id !== sectionId) return section;
            const index = section.questions.findIndex(
              (question) => question.id === questionId,
            );
            if (index < 0) return section;
            const cloned = cloneQuestion(
              section.questions[index] as GuideQuestion,
            );
            cloned.id = newQuestionId;
            const nextQuestions = [...section.questions];
            nextQuestions.splice(index + 1, 0, cloned);
            return {
              ...section,
              questions: nextQuestions,
            };
          }),
        removeQuestion: (state, { sectionId, questionId }) =>
          state.map((section) => {
            if (section.id !== sectionId) return section;
            return {
              ...section,
              questions: section.questions.filter(
                (question) => question.id !== questionId,
              ),
            };
          }),
        moveQuestion: (state, { sectionId, fromIndex, toIndex }) =>
          state.map((section) =>
            section.id === sectionId
              ? {
                  ...section,
                  questions: arrayMove(section.questions, fromIndex, toIndex),
                }
              : section,
          ),
        updateQuestion: (state, { sectionId, questionId, patch }) =>
          updateQuestion(state, sectionId, questionId, patch),
        setQuestionType: (state, { sectionId, questionId, questionType }) =>
          state.map((section) => {
            if (section.id !== sectionId) return section;
            return {
              ...section,
              questions: section.questions.map((question) =>
                question.id === questionId
                  ? resetQuestionType(question, questionType)
                  : question,
              ),
            };
          }),
        addStimulusToQuestion: (state, { sectionId, questionId, stimulusId }) =>
          updateQuestion(state, sectionId, questionId, {
            stimulusIds: Array.from(
              new Set([
                ...(findQuestion(state, sectionId, questionId)?.stimulusIds ??
                  []),
                stimulusId,
              ]),
            ),
          }),
        removeStimulusFromQuestion: (
          state,
          { sectionId, questionId, stimulusId },
        ) =>
          updateQuestion(state, sectionId, questionId, {
            stimulusIds: (
              findQuestion(state, sectionId, questionId)?.stimulusIds ?? []
            ).filter((item) => item !== stimulusId),
          }),
        addQuestionOption: (state, { sectionId, questionId, optionId, text }) =>
          updateQuestion(state, sectionId, questionId, {
            options: [
              ...(findQuestion(state, sectionId, questionId)?.options ?? []),
              { id: optionId, text },
            ],
          }),
        updateQuestionOption: (
          state,
          { sectionId, questionId, optionId, text },
        ) =>
          updateQuestion(state, sectionId, questionId, {
            options: (
              findQuestion(state, sectionId, questionId)?.options ?? []
            ).map((option) =>
              option.id === optionId ? { ...option, text } : option,
            ),
          }),
        removeQuestionOption: (state, { sectionId, questionId, optionId }) =>
          updateQuestion(state, sectionId, questionId, {
            options: (
              findQuestion(state, sectionId, questionId)?.options ?? []
            ).filter((option) => option.id !== optionId),
          }),
        moveQuestionOption: (
          state,
          { sectionId, questionId, fromIndex, toIndex },
        ) =>
          updateQuestion(state, sectionId, questionId, {
            options: arrayMove(
              findQuestion(state, sectionId, questionId)?.options ?? [],
              fromIndex,
              toIndex,
            ),
          }),
        setSectionRandomizationEnabled: (state) => state,
        setSectionRandomizationMode: (state) => state,
        markSaved: (state) => state,
      },
    ],
    selectedSectionId: [
      STARTER_SECTIONS[0]?.id ?? null,
      {
        loadGuideSuccess: (state, { guide }) =>
          guide
            ? guide.sections.length > 0
              ? (firstQuestionLocation(guide.sections)?.sectionId ?? null)
              : null
            : state,
        saveGuideSuccess: (_state, { guide }) =>
          guide.sections.length > 0
            ? (firstQuestionLocation(guide.sections)?.sectionId ?? null)
            : null,
        selectQuestion: (_, { sectionId }) => sectionId,
        clearSelection: () => null,
        addSection: (_, { sectionId }) => sectionId,
        addQuestion: (_, { sectionId }) => sectionId,
        duplicateQuestion: (_, { sectionId }) => sectionId,
        duplicateSection: (_, { newSectionId }) => newSectionId,
      },
    ],
    selectedQuestionId: [
      STARTER_SECTIONS[0]?.questions[0]?.id ?? null,
      {
        loadGuideSuccess: (state, { guide }) =>
          guide
            ? guide.sections.length > 0
              ? (firstQuestionLocation(guide.sections)?.questionId ?? null)
              : null
            : state,
        saveGuideSuccess: (_state, { guide }) =>
          guide.sections.length > 0
            ? (firstQuestionLocation(guide.sections)?.questionId ?? null)
            : null,
        selectQuestion: (_, { questionId }) => questionId,
        clearSelection: () => null,
        addSection: (_, { questionId }) => questionId,
        addQuestion: (_, { questionId }) => questionId,
        duplicateQuestion: (_, { newQuestionId }) => newQuestionId,
        duplicateSection: (_, { questionId }) => questionId,
      },
    ],
    sectionRandomizationEnabled: [
      false,
      {
        setSectionRandomizationEnabled: (_, { enabled }) => enabled,
      },
    ],
    sectionRandomizationMode: [
      DEFAULT_SECTION_RANDOMIZATION_MODE,
      {
        setSectionRandomizationMode: (_, { mode }) => mode,
      },
    ],
    loadedGuideId: [
      null as string | null,
      {
        loadGuideSuccess: (_, { guide }) => guide?.id ?? null,
        saveGuideSuccess: (_, { guide }) => guide.id,
      },
    ],
    loadedGuideVersion: [
      "1.0.0",
      {
        loadGuideSuccess: (_, { guide }) => guide?.version ?? "1.0.0",
        saveGuideSuccess: (_, { guide }) => guide.version,
      },
    ],
    loadedGuideLanguage: [
      "en",
      {
        loadGuideSuccess: (_, { guide }) => guide?.language ?? "en",
        saveGuideSuccess: (_, { guide }) => guide.language,
      },
    ],
    isLoadingGuide: [
      false,
      {
        loadGuide: () => true,
        loadGuideSuccess: () => false,
        loadGuideFailure: () => false,
      },
    ],
    isSavingGuide: [
      false,
      {
        saveGuide: () => true,
        saveGuideSuccess: () => false,
        saveGuideFailure: () => false,
      },
    ],
    draftRevision: [
      0,
      {
        addSection: (state) => state + 1,
        updateSectionTitle: (state) => state + 1,
        duplicateSection: (state) => state + 1,
        removeSection: (state) => state + 1,
        moveSection: (state) => state + 1,
        addQuestion: (state) => state + 1,
        duplicateQuestion: (state) => state + 1,
        removeQuestion: (state) => state + 1,
        moveQuestion: (state) => state + 1,
        updateQuestion: (state) => state + 1,
        setQuestionType: (state) => state + 1,
        addStimulusToQuestion: (state) => state + 1,
        removeStimulusFromQuestion: (state) => state + 1,
        addQuestionOption: (state) => state + 1,
        updateQuestionOption: (state) => state + 1,
        removeQuestionOption: (state) => state + 1,
        moveQuestionOption: (state) => state + 1,
        setSectionRandomizationEnabled: (state) => state + 1,
        setSectionRandomizationMode: (state) => state + 1,
        loadGuideSuccess: () => 0,
        markSaved: (state) => state,
      },
    ],
    savedRevision: [
      0,
      {
        loadGuideSuccess: () => 0,
        saveGuideSuccess: (_, { revision }) => revision,
      },
    ],
    guideError: [
      null as string | null,
      {
        loadGuide: () => null,
        loadGuideSuccess: () => null,
        loadGuideFailure: (_, { error }) => error,
        saveGuide: () => null,
        saveGuideSuccess: () => null,
        saveGuideFailure: (_, { error }) => error,
      },
    ],
    autosaveQueued: [
      false,
      {
        addSection: () => true,
        updateSectionTitle: () => true,
        duplicateSection: () => true,
        removeSection: () => true,
        moveSection: () => true,
        addQuestion: () => true,
        duplicateQuestion: () => true,
        removeQuestion: () => true,
        moveQuestion: () => true,
        updateQuestion: () => true,
        setQuestionType: () => true,
        addStimulusToQuestion: () => true,
        removeStimulusFromQuestion: () => true,
        addQuestionOption: () => true,
        updateQuestionOption: () => true,
        removeQuestionOption: () => true,
        moveQuestionOption: () => true,
        setSectionRandomizationEnabled: () => true,
        setSectionRandomizationMode: () => true,
        loadGuideSuccess: () => false,
        saveGuide: () => false,
        saveGuideSuccess: () => false,
        saveGuideFailure: () => false,
        markSaved: () => false,
      },
    ],
  }),

  afterMount(({ actions: a }) => {
    // Clean up any leftover localStorage keys from the abandoned
    // draft-persistence layer (see Stale localStorage cleanup above).
    evictStaleDraftKeys();
    // Fire loadGuide unconditionally on mount. The listener itself
    // guards on studyId so a null at mount time doesn't crash; the
    // loadStudySuccess listener below catches the case where studyId
    // arrives later.
    a.loadGuide();
  }),

  listeners(({ actions: a, values }) => ({
    [studyLogic.actionTypes.loadStudySuccess]: () => {
      if (values.studyId) {
        a.loadGuide();
      }
    },
    loadGuide: async () => {
      // No re-entry guard. Earlier code had ``if (values.isLoadingGuide)
      // return;`` — but Kea fires reducers BEFORE listeners, so by the
      // time this listener runs, the reducer already set
      // ``isLoadingGuide=true`` and the guard returned every time,
      // killing the API call. Same bug as saveGuide had earlier.
      const studyId = values.studyId;
      if (!studyId) {
        return;
      }
      try {
        const response = await api.get<StudyOutlineResponse>(
          `/api/studies/${studyId}/outline/`,
        );
        const guide = makeGuideRecordFromOutlineResponse(response, studyId);
        a.loadGuideSuccess(guide);
      } catch (error) {
        a.loadGuideFailure(errorMessage(error, "Failed to load guide."));
      }
    },
    saveGuide: async ({ revision }) => {
      if (!values.studyId) {
        a.saveGuideFailure("No study loaded.");
        return;
      }
      // No re-entry guard here. Earlier code checked
      // ``values.isSavingGuide`` to short-circuit, but Kea fires
      // reducers BEFORE listeners — so by the time this listener
      // body runs, the reducer has already set ``isSavingGuide=true``,
      // the guard returns early, and ``saveGuideSuccess`` never fires.
      // Result: the UI shows "保存中…" forever. The fix is to drop
      // the guard. The PUT endpoint is idempotent; if the user
      // somehow double-clicks, last write wins which is fine.
      const payload = {
        outline: makeOutlineFromGuideSections(values.sections),
      };
      try {
        const guide = await api.replace<SavedInterviewGuideResponse>(
          `/api/studies/${values.studyId}/outline/`,
          payload,
        );
        a.saveGuideSuccess(makeGuideRecordFromSavedGuide(guide), revision);
      } catch (error) {
        a.saveGuideFailure(errorMessage(error, "Failed to save guide."));
      }
    },
    ...AUTOSAVE_ACTIONS.reduce<Record<string, () => void>>(
      (acc, actionName) => {
        // Mutation actions are tracked by the ``autosaveQueued`` /
        // ``draftRevision`` reducers (those drive the dirty indicator).
        // No side-effect listener needed.
        acc[actionName] = () => {};
        return acc;
      },
      {},
    ),
    addSection: ({ sectionId, questionId }) => {
      if (questionId) {
        const section = values.sections.find((item) => item.id === sectionId);
        if (section) {
          a.selectQuestion(sectionId, questionId);
        }
      }
      if (values.studyId && !values.isLoadingGuide) {
        scheduleAutosave(() => a.saveGuide(values.draftRevision));
      }
    },
    addQuestion: ({ sectionId, questionId }) => {
      a.selectQuestion(sectionId, questionId);
      if (values.studyId && !values.isLoadingGuide) {
        scheduleAutosave(() => a.saveGuide(values.draftRevision));
      }
    },
    duplicateQuestion: ({ sectionId, newQuestionId }) => {
      a.selectQuestion(sectionId, newQuestionId);
      if (values.studyId && !values.isLoadingGuide) {
        scheduleAutosave(() => a.saveGuide(values.draftRevision));
      }
    },
    duplicateSection: ({ newSectionId, questionId }) => {
      a.selectQuestion(newSectionId, questionId);
      if (values.studyId && !values.isLoadingGuide) {
        scheduleAutosave(() => a.saveGuide(values.draftRevision));
      }
    },
    removeQuestion: ({ sectionId, questionId }) => {
      if (
        values.selectedQuestionId !== questionId ||
        values.selectedSectionId !== sectionId
      ) {
        return;
      }
      const section = values.sections.find((item) => item.id === sectionId);
      if (!section) return;
      const question = section.questions.find((item) => item.id === questionId);
      if (!question) return;
      const remaining = section.questions.filter(
        (item) => item.id !== questionId,
      );
      if (remaining[0]) {
        a.selectQuestion(sectionId, remaining[0].id);
        return;
      }
      const fallback = firstQuestionLocation(
        values.sections.filter((item) => item.id !== sectionId),
      );
      if (fallback) {
        a.selectQuestion(fallback.sectionId, fallback.questionId);
      } else {
        a.clearSelection();
      }
    },
    removeSection: ({ sectionId }) => {
      if (values.selectedSectionId !== sectionId) {
        return;
      }
      const remaining = values.sections.filter(
        (section) => section.id !== sectionId,
      );
      const fallback = firstQuestionLocation(remaining);
      if (fallback) {
        a.selectQuestion(fallback.sectionId, fallback.questionId);
      } else {
        a.clearSelection();
      }
    },
  })),
]);
