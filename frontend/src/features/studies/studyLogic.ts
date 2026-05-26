import { afterMount, connect, kea, listeners, path, selectors } from "kea";
import { loaders } from "kea-loaders";

import { sceneLogic } from "~/app/sceneLogic";
import { api } from "~/lib/api";
import type { Study } from "~/types";

import type { studyLogicType } from "./studyLogicType";

/**
 * studyLogic — the currently open study (``/studies/:id/:tab``).
 *
 * Reads ``:id`` out of :data:`sceneLogic.sceneParams.params.id` and
 * loads the full study record. Tab logics ``connect`` to read
 * ``study`` without re-fetching.
 */
export const studyLogic = kea<studyLogicType>([
  path(["features", "studies", "studyLogic"]),

  connect(() => ({
    values: [sceneLogic, ["sceneParams"]],
  })),

  selectors({
    studyId: [(s) => [s.sceneParams], (p) => p.params["id"] ?? null],
    activeTab: [(s) => [s.sceneParams], (p) => p.params["tab"] ?? "outline"],
  }),

  loaders(({ values }) => ({
    study: [
      null as Study | null,
      {
        loadStudy: async () => {
          const id = values.studyId;
          if (!id) return null;
          return await api.get<Study>(`/api/studies/${id}/`);
        },
      },
    ],
  })),

  listeners(({ actions, values }) => ({
    // reload whenever :id changes in the URL
    [sceneLogic.actionTypes.setScene]: () => {
      if (values.studyId && values.studyId !== values.study?.id) {
        actions.loadStudy();
      }
    },
  })),

  afterMount(({ actions, values }) => {
    if (values.studyId) {
      actions.loadStudy();
    }
  }),
]);
