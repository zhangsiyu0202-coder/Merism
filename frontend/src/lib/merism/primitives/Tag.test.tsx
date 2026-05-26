import { describe, expect, it, vi } from "vitest";

import { Tag } from "~/lib/merism";
import { render, screen } from "~/test/render";

describe("Tag", () => {
  it("renders its content", () => {
    render(<Tag>P0</Tag>);
    expect(screen.getByText("P0")).toBeInTheDocument();
  });

  it("renders a remove button with an accessible name when removable", () => {
    render(
      <Tag removable onRemove={() => {}}>
        Label
      </Tag>,
    );
    expect(screen.getByRole("button", { name: "Remove" })).toBeInTheDocument();
  });

  it("invokes onRemove when the remove button is clicked", async () => {
    const onRemove = vi.fn();
    const { user } = render(
      <Tag removable onRemove={onRemove}>
        Label
      </Tag>,
    );
    await user.click(screen.getByRole("button", { name: "Remove" }));
    expect(onRemove).toHaveBeenCalledTimes(1);
  });

  it("does not render a remove button when non-removable", () => {
    render(<Tag>Static</Tag>);
    expect(screen.queryByRole("button", { name: "Remove" })).toBeNull();
  });
});
