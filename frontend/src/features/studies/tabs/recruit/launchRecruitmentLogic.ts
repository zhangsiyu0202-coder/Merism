import { connect, kea, listeners, path, reducers, actions } from "kea";

import { studyLogic } from "~/features/studies/studyLogic";
import { api, ApiRequestError } from "~/lib/api";

import { broadcastsLogic } from "./broadcastsLogic";

export interface LaunchRecruitmentResult {
  queued_broadcast_ids: string[];
  created_count: number;
  skipped_channels: Array<{
    channel_id: string;
    channel_name: string;
    reason: string;
  }>;
  errors: string[];
}

export const launchRecruitmentLogic = kea([
  path(["features", "studies", "tabs", "recruit", "launchRecruitmentLogic"]),

  connect(() => ({
    values: [studyLogic, ["studyId"]],
    actions: [
      studyLogic,
      ["loadStudy"],
      broadcastsLogic,
      ["loadBroadcasts", "loadStudyLinks"],
    ],
  })),

  actions({
    launchRecruitment: true,
    launchRecruitmentSuccess: (result: unknown) => ({
      result: result as LaunchRecruitmentResult,
    }),
    launchRecruitmentFailure: (error: unknown) => ({ error: String(error) }),
    clearLaunchFeedback: true,
    setLaunching: (launching: unknown) => ({ launching: Boolean(launching) }),
  }),

  reducers({
    isLaunching: [
      false,
      {
        setLaunching: (_, { launching }) => launching,
      },
    ],
    lastLaunchResult: [
      null as LaunchRecruitmentResult | null,
      {
        launchRecruitmentSuccess: (_, { result }) => result,
        clearLaunchFeedback: () => null,
      },
    ],
    launchError: [
      null as string | null,
      {
        launchRecruitment: () => null,
        launchRecruitmentFailure: (_, { error }) => error,
        launchRecruitmentSuccess: () => null,
        clearLaunchFeedback: () => null,
      },
    ],
  }),

  listeners(({ values, actions }) => ({
    launchRecruitment: async () => {
      if (!values.studyId) return;
      actions.setLaunching(true);
      try {
        const result = await api.action<LaunchRecruitmentResult>(
          `/api/studies/${values.studyId}/launch-recruitment/`,
        );
        actions.launchRecruitmentSuccess(result);
        actions.loadBroadcasts();
        actions.loadStudyLinks();
        actions.loadStudy();
      } catch (error) {
        if (error instanceof ApiRequestError) {
          actions.launchRecruitmentFailure(
            error.detail?.detail ?? error.message,
          );
        } else {
          actions.launchRecruitmentFailure("Failed to launch recruitment.");
        }
      } finally {
        actions.setLaunching(false);
      }
    },
  })),
]);
