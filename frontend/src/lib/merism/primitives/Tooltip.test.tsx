import { describe, expect, it } from "vitest";

import { Tooltip, TooltipProvider } from "~/lib/merism";
import { render, screen, waitFor } from "~/test/render";

describe("Tooltip", () => {
  it("opens on focus of the trigger", async () => {
    render(
      <TooltipProvider delayDuration={0}>
        <Tooltip label="Coverage: 30%">
          <button type="button">goal</button>
        </Tooltip>
      </TooltipProvider>,
    );
    const trigger = screen.getByRole("button", { name: "goal" });
    trigger.focus();
    // Radix sometimes lags one microtask behind focus.
    await waitFor(() => {
      expect(screen.getByRole("tooltip")).toHaveTextContent("Coverage: 30%");
    });
  });
});
