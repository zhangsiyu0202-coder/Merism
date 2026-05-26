import type { ComponentType } from "react";

import type { Scene } from "./routes";

/** URL-captured params split by source. */
export interface SceneParams {
  params: Record<string, string>;
  searchParams: Record<string, string>;
  hashParams: Record<string, string>;
}

/** Per-scene static config used by ``AppLayout`` and ``sceneLogic``. */
export interface SceneConfig {
  /** Human-readable title. Shown in tab + topbar. */
  name: string;
  /** Layout wrapper. Default: ``app``. */
  layout?: "app" | "plain" | "participant";
  /** Skips the auth guard. Default: false. */
  allowUnauthenticated?: boolean;
  /** Hides from nav sidebar. Default: false. */
  hideFromNav?: boolean;
}

/** What a feature module exports via lazy import. */
export interface SceneExport {
  component: ComponentType;
}

export type LazyScene = () => Promise<{ default: ComponentType }>;

export type SceneConfigMap = Record<Scene, SceneConfig>;
export type SceneImportMap = Record<Scene, LazyScene>;
