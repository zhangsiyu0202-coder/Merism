import { useActions, useMountedLogic, useValues } from "kea";
import { router } from "kea-router";
import { lazy, Suspense, type ComponentType } from "react";
import { useTranslation } from "react-i18next";

import { urls, type StudyTab } from "~/app/routes";
import { PageHeading, TabRail, Tag, type TabRailItem } from "~/lib/merism";

import SharePanel from "./SharePanel";
import { studyLogic } from "./studyLogic";

/**
 * StudyPage — the tabbed shell for a single study.
 *
 * URL: ``/studies/:id/:tab``. Tabs are lazy-loaded so we don't ship all
 * eight in the Study bundle. Each tab is its own folder under ``tabs/``
 * with a single ``<TabName>Tab.tsx`` default export.
 */

const tabComponents: Record<
  StudyTab,
  () => Promise<{ default: ComponentType }>
> = {
  outline: () => import("./tabs/outline/OutlineTab"),
  screener: () => import("./tabs/screener/ScreenerTab"),
  stimuli: () => import("./tabs/stimuli/StimuliTab"),
  recruit: () => import("./tabs/recruit/RecruitTab"),
  report: () => import("./tabs/report/ReportTab"),
  sessions: () => import("./tabs/sessions/SessionsTab"),
  settings: () => import("./tabs/settings/SettingsTab"),
};

const tabCache = new Map<StudyTab, ComponentType>();
function tabFor(tab: StudyTab): ComponentType {
  const cached = tabCache.get(tab);
  if (cached) return cached;
  const component = lazy(tabComponents[tab] ?? tabComponents.outline);
  tabCache.set(tab, component);
  return component;
}

export default function StudyPage(): JSX.Element {
  const { t } = useTranslation();
  useMountedLogic(studyLogic);
  const { study, studyLoading, studyId, activeTab } = useValues(studyLogic);
  const { push } = useActions(router);

  if (!studyId) {
    return <div className="text-merism-text-muted">—</div>;
  }

  const TabComponent = tabFor((activeTab as StudyTab) || "outline");

  const TABS: TabRailItem[] = [
    { value: "outline", label: t("study.tabs.outline") },
    { value: "screener", label: t("study.tabs.screener") },
    { value: "stimuli", label: t("study.tabs.stimuli") },
    { value: "recruit", label: t("study.tabs.recruit") },
    { value: "report", label: t("study.tabs.report") },
    { value: "sessions", label: t("study.tabs.sessions") },
    { value: "settings", label: t("study.tabs.settings") },
  ];

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <PageHeading
        title={study?.name ?? (studyLoading ? t("common.loading") : "—")}
        lede={study?.research_goal || ""}
        status={
          study && (
            <>
              <Tag variant="accent">
                {t(`studies.status.${study.status}`, {
                  defaultValue: study.status,
                })}
              </Tag>
              <Tag variant="outline" case="normal">
                {t(`study.mode.${study.interview_mode}`, {
                  defaultValue: study.interview_mode,
                })}
              </Tag>
            </>
          )
        }
      />

      {study?.share_url && (
        <div className="mt-4">
          <SharePanel study={study} />
        </div>
      )}

      <div className="flex min-h-0 flex-1 flex-col gap-4 pt-4">
        <TabRail
          tabs={TABS}
          activeTab={activeTab}
          onTabChange={(value) => push(urls.study(studyId, value as StudyTab))}
        />

        <Suspense
          fallback={
            <div className="text-merism-text-muted">{t("common.loading")}</div>
          }
        >
          <div className="min-h-0 flex-1">
            <TabComponent />
          </div>
        </Suspense>
      </div>
    </div>
  );
}
