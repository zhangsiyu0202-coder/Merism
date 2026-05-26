import { useMountedLogic, useValues } from "kea";
import { Suspense, lazy, useMemo, type ComponentType } from "react";
import { router } from "kea-router";

import { AppLayout } from "~/layout/AppLayout";
import { ErrorBoundary } from "~/layout/ErrorBoundary";
import { ParticipantLayout } from "~/layout/ParticipantLayout";
import { PlainLayout } from "~/layout/PlainLayout";
import { userLogic } from "~/models/userLogic";

import { Providers } from "./providers";
import { Scene, urls } from "./routes";
import { sceneImports } from "./routeRegistry";
import { sceneLogic } from "./sceneLogic";

/**
 * App — top-level component.
 *
 * - Mounts :data:`sceneLogic`, which subscribes to kea-router.
 * - Reads the active scene + its config, picks the layout wrapper.
 * - Lazily renders the scene's default export (code-split per scene).
 *
 * A bad route (no match in :data:`routes`) falls through to ``Error404``.
 */
export function App(): JSX.Element {
  useMountedLogic(sceneLogic);
  useMountedLogic(userLogic);
  const { activeScene, activeSceneConfig } = useValues(sceneLogic);
  const { user, userLoading } = useValues(userLogic);

  const SceneComponent = useMemo(
    () => lazyForScene(activeScene),
    [activeScene],
  );

  const Layout = pickLayout(activeSceneConfig.layout);

  // Auth guard
  const needsAuth = !activeSceneConfig.allowUnauthenticated;
  if (needsAuth && userLoading && user === null) {
    return (
      <Providers>
        <div className="flex h-screen items-center justify-center bg-merism-bg">
          <span className="text-merism-text-muted">Loading…</span>
        </div>
      </Providers>
    );
  }
  if (needsAuth && !userLoading && user === null) {
    router.actions.push(urls.login());
    return (
      <Providers>
        <PlainLayout>
          <Suspense fallback={<SceneFallback />}>
            {(() => {
              const L = lazyForScene(Scene.Login);
              return <L />;
            })()}
          </Suspense>
        </PlainLayout>
      </Providers>
    );
  }

  return (
    <Providers>
      <ErrorBoundary>
        <Layout>
          <Suspense fallback={<SceneFallback />}>
            <SceneComponent />
          </Suspense>
        </Layout>
      </ErrorBoundary>
    </Providers>
  );
}

const sceneCache = new Map<Scene, ComponentType>();

function lazyForScene(scene: Scene): ComponentType {
  const cached = sceneCache.get(scene);
  if (cached) return cached;
  const component = lazy(sceneImports[scene] ?? sceneImports[Scene.Error404]);
  sceneCache.set(scene, component);
  return component;
}

function pickLayout(
  kind: "app" | "plain" | "participant" | undefined,
): ComponentType<{ children: React.ReactNode }> {
  if (kind === "plain") return PlainLayout;
  if (kind === "participant") return ParticipantLayout;
  return AppLayout;
}

function SceneFallback(): JSX.Element {
  return (
    <div className="flex min-h-64 items-center justify-center text-sm text-merism-text-muted">
      <span
        aria-hidden="true"
        className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-merism-accent"
      />
      Loading…
    </div>
  );
}
