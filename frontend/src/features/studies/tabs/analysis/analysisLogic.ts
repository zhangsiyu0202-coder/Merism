import { actions, afterMount, connect, kea, path, selectors } from "kea";
import { loaders } from "kea-loaders";

import { api } from "~/lib/api";
import { studyLogic } from "~/features/studies/studyLogic";

import type { analysisLogicType } from "./analysisLogicType";

export interface ThemeEntry {
  code_id: string;
  name: string;
  count: number;
  description: string;
}

export interface SentimentTrendPoint {
  date: string;
  positive: number;
  negative: number;
  neutral: number;
  mixed: number;
}

export interface AnalysisKpi {
  session_count: number;
  session_completed: number;
  quote_count: number;
  insight_count: number;
  theme_count: number;
  talk_time_hours: number;
}

export interface TopTask {
  title: string;
  category: string;
  priority: "P0" | "P1" | "P2";
  evidence_quote_id?: string;
  session_id: string;
}

export interface StudyAggregate {
  study_id: string;
  kpi: AnalysisKpi;
  top_themes: ThemeEntry[];
  sentiment_distribution: Record<string, number>;
  action_distribution: Record<string, number>;
  sentiment_over_time: SentimentTrendPoint[];
  top_tasks: TopTask[];
  codebook_size: number;
}

export interface StudyNarrative {
  summary: string;
  eyebrow: string;
  byline: string;
}

export const analysisLogic = kea<analysisLogicType>([
  path(["features", "studies", "tabs", "analysis", "analysisLogic"]),

  connect(() => ({
    values: [studyLogic, ["studyId"]],
  })),

  actions({
    refreshNarrative: true,
  }),

  loaders(({ values }) => ({
    aggregate: [
      null as StudyAggregate | null,
      {
        loadAggregate: async () => {
          const id = values.studyId;
          if (!id) return null;
          return await api.get<StudyAggregate>(`/api/studies/${id}/analysis/`);
        },
      },
    ],
    narrative: [
      null as StudyNarrative | null,
      {
        refreshNarrative: async () => {
          const id = values.studyId;
          if (!id) return null;
          try {
            return await api.create<StudyNarrative>(
              `/api/studies/${id}/narrative/`,
            );
          } catch {
            return null;
          }
        },
      },
    ],
  })),

  selectors({
    hasData: [(s) => [s.aggregate], (agg) => !!agg && agg.kpi.quote_count > 0],
    sentimentDistList: [
      (s) => [s.aggregate],
      (agg) =>
        agg
          ? Object.entries(agg.sentiment_distribution).map(([key, value]) => ({
              key,
              value,
            }))
          : [],
    ],
  }),

  afterMount(({ actions, values }) => {
    if (values.studyId) {
      actions.loadAggregate();
      actions.refreshNarrative();
    }
  }),
]);
