import { describe, expect, it } from "vitest";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "~/lib/merism";
import { render, screen } from "~/test/render";

function TabsFixture() {
  return (
    <Tabs defaultValue="one">
      <TabsList>
        <TabsTrigger value="one">One</TabsTrigger>
        <TabsTrigger value="two">Two</TabsTrigger>
      </TabsList>
      <TabsContent value="one">First panel</TabsContent>
      <TabsContent value="two">Second panel</TabsContent>
    </Tabs>
  );
}

describe("Tabs", () => {
  it("pointer click switches the visible panel", async () => {
    const { user } = render(<TabsFixture />);
    expect(screen.getByText("First panel")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Two" }));
    expect(screen.getByText("Second panel")).toBeInTheDocument();
  });

  it("ArrowRight moves focus to the next tab", async () => {
    const { user } = render(<TabsFixture />);
    const tabOne = screen.getByRole("tab", { name: "One" });
    tabOne.focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Two" })).toHaveFocus();
  });
});
