import {
  actions,
  connect,
  kea,
  listeners,
  path,
  reducers,
  selectors,
} from "kea";

import { sceneLogic } from "~/app/sceneLogic";
import { Scene } from "~/app/routes";
import { studiesLogic } from "~/features/studies/studiesLogic";

import type { sidebarLogicType } from "./sidebarLogicType";

/**
 * sidebarLogic — drives the "pinned studies" zone in the left nav.
 *
 * We track the most-recently-opened study IDs in ``localStorage``
 * so the pinned list survives refresh without costing a backend
 * field. When ``sceneLogic`` enters a Study scene we push the
 * current ``studyId`` to the front; when the user never returns
 * to a study within 30 opens it falls off the bottom.
 *
 * The resolved pinned list (IDs → Study objects) is derived from
 * ``studiesLogic.studies``; if the store hasn't loaded yet we just
 * skip unknown IDs.
 */

const STORAGE_KEY = "merism.sidebar.recentStudyIds";
const COLLAPSED_STORAGE_KEY = "merism.sidebar.isCollapsed";
const SIDE_PANEL_STORAGE_KEY = "merism.sidePanel.state";
const MAX_PINNED = 3;

function readStored(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((v): v is string => typeof v === "string");
  } catch {
    return [];
  }
}

function writeStored(ids: string[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
  } catch {
    // ignore quota / private mode failures
  }
}

function readCollapsed(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(COLLAPSED_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function writeCollapsed(v: boolean): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(COLLAPSED_STORAGE_KEY, v ? "1" : "0");
  } catch {
    // ignore
  }
}

export type SidePanelTab = "ask" | null;

interface SidePanelState {
  tab: SidePanelTab;
  isOpen: boolean;
  width: number;
}

const DEFAULT_SIDE_PANEL_WIDTH = 480;
const MIN_SIDE_PANEL_WIDTH = 320;
const MAX_SIDE_PANEL_WIDTH = 900;

function readSidePanelState(): SidePanelState {
  const defaults: SidePanelState = {
    tab: null,
    isOpen: false,
    width: DEFAULT_SIDE_PANEL_WIDTH,
  };
  if (typeof window === "undefined") return defaults;
  try {
    const raw = window.localStorage.getItem(SIDE_PANEL_STORAGE_KEY);
    if (!raw) return defaults;
    const parsed = JSON.parse(raw);
    return {
      tab: parsed.tab ?? null,
      isOpen: Boolean(parsed.isOpen),
      width:
        typeof parsed.width === "number"
          ? Math.max(
              MIN_SIDE_PANEL_WIDTH,
              Math.min(MAX_SIDE_PANEL_WIDTH, parsed.width),
            )
          : DEFAULT_SIDE_PANEL_WIDTH,
    };
  } catch {
    return defaults;
  }
}

function writeSidePanelState(state: SidePanelState): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(SIDE_PANEL_STORAGE_KEY, JSON.stringify(state));
  } catch {
    // ignore
  }
}

export const sidebarLogic = kea<sidebarLogicType>([
  path(["layout", "sidebarLogic"]),

  connect(() => ({
    values: [
      studiesLogic,
      ["studies"],
      sceneLogic,
      ["sceneParams", "activeScene"],
    ],
  })),

  actions({
    touchStudy: (studyId: string) => ({ studyId }),
    toggleCollapsed: true,
    setCollapsed: (collapsed: boolean) => ({ collapsed }),
    openSidePanel: (tab: Exclude<SidePanelTab, null>) => ({ tab }),
    closeSidePanel: true,
    toggleSidePanel: (tab: Exclude<SidePanelTab, null>) => ({ tab }),
    setSidePanelWidth: (width: number) => ({ width }),
  }),

  reducers({
    recentStudyIds: [
      readStored() as string[],
      {
        touchStudy: (current, { studyId }) => {
          const next = [
            studyId,
            ...current.filter((id) => id !== studyId),
          ].slice(0, MAX_PINNED);
          writeStored(next);
          return next;
        },
      },
    ],
    isCollapsed: [
      readCollapsed() as boolean,
      {
        toggleCollapsed: (current) => {
          const next = !current;
          writeCollapsed(next);
          return next;
        },
        setCollapsed: (_, { collapsed }) => {
          writeCollapsed(collapsed);
          return collapsed;
        },
      },
    ],
    sidePanel: [
      readSidePanelState() as SidePanelState,
      {
        openSidePanel: (state, { tab }) => {
          const next = { ...state, tab, isOpen: true };
          writeSidePanelState(next);
          return next;
        },
        closeSidePanel: (state) => {
          const next = { ...state, isOpen: false };
          writeSidePanelState(next);
          return next;
        },
        toggleSidePanel: (state, { tab }) => {
          // If opening same tab that's already open → close
          if (state.isOpen && state.tab === tab) {
            const next = { ...state, isOpen: false };
            writeSidePanelState(next);
            return next;
          }
          const next = { ...state, tab, isOpen: true };
          writeSidePanelState(next);
          return next;
        },
        setSidePanelWidth: (state, { width }) => {
          const clamped = Math.max(
            MIN_SIDE_PANEL_WIDTH,
            Math.min(MAX_SIDE_PANEL_WIDTH, width),
          );
          const next = { ...state, width: clamped };
          writeSidePanelState(next);
          return next;
        },
      },
    ],
  }),

  selectors({
    pinnedStudies: [
      (s) => [s.recentStudyIds, s.studies],
      (ids, studies) => {
        const map = new Map(studies.map((st) => [st.id, st]));
        return ids
          .map((id) => map.get(id))
          .filter((s): s is NonNullable<typeof s> => !!s);
      },
    ],
  }),

  listeners(({ actions, values }) => ({
    // Whenever the URL leads us into a Study, bump that ID to front.
    [sceneLogic.actionTypes.setScene]: ({ scene, params }) => {
      if (scene === Scene.Study && params.params.id) {
        if (params.params.id !== values.recentStudyIds[0]) {
          actions.touchStudy(params.params.id);
        }
      }
    },
  })),
]);
