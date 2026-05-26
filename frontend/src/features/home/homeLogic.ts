import { actions, afterMount, kea, path, reducers, selectors } from "kea";
import { loaders } from "kea-loaders";

import { api } from "~/lib/api";
import type { Study } from "~/types";

import type { homeLogicType } from "./homeLogicType";

/**
 * homeLogic — powers the Home scene.
 *
 * Loads the compact ``/api/home/stats/`` object plus a list of
 * studies (up to 24, newest-first) for the horizontal strip.
 *
 * Tabs (Overview / Activity / Drafts) are URL-driven via the
 * ``?tab=`` query param; ``activeHomeTab`` mirrors that back.
 */

export type HomeTab = "overview" | "activity" | "drafts";

export interface HomeStats {
  sessions_week: number;
  studies_total: number;
  studies_active: number;
  talk_time_hours: number;
  participants_total: number;
  insights_total: number;
}

export const homeLogic = kea<homeLogicType>([
  path(["features", "home", "homeLogic"]),

  actions({
    setActiveTab: (tab: HomeTab) => ({ tab }),
  }),

  reducers({
    activeTab: [
      "overview" as HomeTab,
      {
        setActiveTab: (_, { tab }) => tab,
      },
    ],
  }),

  loaders({
    stats: [
      null as HomeStats | null,
      {
        loadStats: async () => {
          return await api.get<HomeStats>("/api/home/stats/");
        },
      },
    ],
    studies: [
      [] as Study[],
      {
        loadStudies: async () => {
          const response = await api.list<Study>("/api/studies/", {
            page_size: 24,
          });
          return response.results;
        },
      },
    ],
  }),

  selectors({
    draftStudies: [
      (s) => [s.studies],
      (v) => v.filter((s) => s.status === "draft"),
    ],
    activeStudies: [
      (s) => [s.studies],
      (v) => v.filter((st) => st.status === "live"),
    ],
  }),

  afterMount(({ actions }) => {
    actions.loadStats();
    actions.loadStudies();
  }),
]);
