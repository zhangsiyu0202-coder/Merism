import { afterMount, connect, kea, path, selectors } from "kea";
import { loaders } from "kea-loaders";

import { studyLogic } from "~/features/studies/studyLogic";
import { api } from "~/lib/api";

import type { conceptReportLogicType } from "./conceptReportLogicType";

export interface ConceptReportRow {
  concept_id: string;
  label: string;
  rank: number;
  stimulus_id: string;
  sessions_seen: number;
  dimensions: Array<{ name: string; value: number }>;
}

export interface ConceptReport {
  block_id: string;
  block_title: string;
  rotation: string;
  concepts: ConceptReportRow[];
  winner_concept_id: string | null;
  total_sessions: number;
}

interface ConceptBlockBrief {
  id: string;
  title: string;
}

/**
 * conceptReportLogic — aggregated per-concept comparison data.
 *
 * Loads every ConceptBlock attached to the current study, then calls
 * ``/api/concept-blocks/:id/report/`` for each in parallel. Re-fetches
 * when the study id changes.
 */
export const conceptReportLogic = kea<conceptReportLogicType>([
  path(["features", "studies", "tabs", "analysis", "conceptReportLogic"]),

  connect({ values: [studyLogic, ["study"]] }),

  loaders(({ values }) => ({
    reports: [
      [] as ConceptReport[],
      {
        loadReports: async () => {
          const studyId = values.study?.id;
          if (!studyId) return [];
          const list = await api.list<ConceptBlockBrief>(
            "/api/concept-blocks/",
            {
              study: studyId,
            },
          );
          const blocks = list.results ?? [];
          if (blocks.length === 0) return [];
          const reports = await Promise.all(
            blocks.map((b) =>
              api.get<ConceptReport>(`/api/concept-blocks/${b.id}/report/`),
            ),
          );
          return reports;
        },
      },
    ],
  })),

  selectors({
    hasReports: [(s) => [s.reports], (r) => r.length > 0],
  }),

  afterMount(({ actions, values }) => {
    if (values.study?.id) actions.loadReports();
  }),
]);
