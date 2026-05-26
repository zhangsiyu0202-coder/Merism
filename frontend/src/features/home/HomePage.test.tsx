import { http, HttpResponse } from "msw";
import { useMountedLogic } from "kea";
import { describe, expect, it } from "vitest";

import { server } from "~/test/msw/server";
import { render, screen, waitFor } from "~/test/render";
import { studiesLogic } from "~/features/studies/studiesLogic";

import HomePage from "./HomePage";

const fixtureStudy = {
  id: "study-1",
  name: "Pricing interviews",
  research_goal: "Learn what users think about pricing.",
  research_objectives: [],
  interview_mode: "voice",
  status: "draft",
  estimated_minutes: 30,
  created_at: "2026-05-18T00:00:00Z",
  updated_at: "2026-05-18T00:00:00Z",
};

function HomePageHarness(): JSX.Element {
  useMountedLogic(studiesLogic);
  return <HomePage />;
}

describe("HomePage", () => {
  it("routes to the new study settings page when the button is clicked", async () => {
    server.use(
      http.get("/api/home/stats/", () =>
        HttpResponse.json({
          sessions_week: 4,
          studies_total: 1,
          studies_active: 1,
          talk_time_hours: 7.5,
          participants_total: 12,
          insights_total: 3,
        }),
      ),
      http.get("/api/studies/", () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [fixtureStudy],
        }),
      ),
      http.post("/api/studies/", async () =>
        HttpResponse.json(
          {
            ...fixtureStudy,
            id: "study-created",
            name: "Untitled study",
            research_goal: "(Draft — set a research goal)",
          },
          { status: 201 },
        ),
      ),
    );

    const { user } = render(<HomePageHarness />);

    await user.click(
      screen.getByRole("button", {
        name: /新建研究|New study/,
      }),
    );

    await waitFor(() => {
      expect(window.location.pathname).toBe("/studies/study-created/settings");
    });
  });
});
