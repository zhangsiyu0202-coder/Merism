import { actions, kea, path, reducers, selectors } from "kea";
import { urlToAction } from "kea-router";

import { Scene, routes } from "./routes";
import { sceneConfigs } from "./routeRegistry";
import type { SceneConfig, SceneParams } from "./sceneTypes";

import type { sceneLogicType } from "./sceneLogicType";

/**
 * sceneLogic — owns the active scene + URL params for the whole app.
 *
 * ``AppLayout`` and ``NavigationSidebar`` subscribe to ``activeScene``;
 * individual features read ``sceneParams`` to pick up URL segments.
 */
export const sceneLogic = kea<sceneLogicType>([
  path(["app", "sceneLogic"]),

  actions({
    setScene: (scene: Scene, params: SceneParams) => ({ scene, params }),
  }),

  reducers({
    activeScene: [
      Scene.Home as Scene,
      {
        setScene: (_, { scene }) => scene,
      },
    ],
    sceneParams: [
      {
        params: {},
        searchParams: {},
        hashParams: {},
      } as SceneParams,
      {
        setScene: (_, { params }) => params,
      },
    ],
  }),

  selectors({
    activeSceneConfig: [
      (s) => [s.activeScene],
      (scene): SceneConfig => sceneConfigs[scene],
    ],
  }),

  urlToAction(({ actions }) => {
    const handlers: Record<
      string,
      (
        params: Record<string, string | undefined>,
        searchParams: Record<string, string>,
        hashParams: Record<string, string>,
      ) => void
    > = {};
    for (const [pattern, scene] of Object.entries(routes)) {
      handlers[pattern] = (params, searchParams, hashParams) => {
        // Drop undefined values so downstream consumers see a clean map.
        const cleanParams: Record<string, string> = {};
        for (const [key, value] of Object.entries(params)) {
          if (value !== undefined) cleanParams[key] = value;
        }
        actions.setScene(scene, {
          params: cleanParams,
          searchParams,
          hashParams,
        });
      };
    }
    return handlers;
  }),
]);
