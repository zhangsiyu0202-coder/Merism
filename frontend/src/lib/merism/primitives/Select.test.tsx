import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Select } from "~/lib/merism";
import { render, screen, waitForElementToBeRemoved } from "~/test/render";

const OPTIONS = [
  { value: "alpha", label: "Alpha" },
  { value: "beta", label: "Beta" },
  { value: "gamma", label: "Gamma" },
];

function SelectHarness({
  initialValue = "alpha",
  onValueChange,
}: {
  initialValue?: string;
  onValueChange?: (value: string) => void;
}): JSX.Element {
  const [value, setValue] = useState(initialValue);

  return (
    <Select
      aria-label="Example select"
      value={value}
      options={OPTIONS}
      onValueChange={(nextValue) => {
        setValue(nextValue);
        onValueChange?.(nextValue);
      }}
    />
  );
}

describe("Select", () => {
  it("renders the selected option label", () => {
    render(<SelectHarness initialValue="beta" />);
    expect(
      screen.getByRole("button", { name: "Example select" }),
    ).toHaveTextContent("Beta");
  });

  it("opens the listbox and commits a clicked option", async () => {
    const handleChange = vi.fn();
    const { user } = render(<SelectHarness onValueChange={handleChange} />);

    await user.click(screen.getByRole("button", { name: "Example select" }));
    await user.click(screen.getByRole("option", { name: "Gamma" }));

    expect(handleChange).toHaveBeenCalledWith("gamma");
    await waitForElementToBeRemoved(() => screen.queryByRole("listbox"));
    expect(
      screen.getByRole("button", { name: "Example select" }),
    ).toHaveTextContent("Gamma");
  });

  it("supports keyboard navigation", async () => {
    const handleChange = vi.fn();
    const { user } = render(<SelectHarness onValueChange={handleChange} />);

    const trigger = screen.getByRole("button", { name: "Example select" });
    trigger.focus();

    await user.keyboard("{ArrowDown}{ArrowDown}{Enter}");

    expect(handleChange).toHaveBeenCalledWith("beta");
    expect(trigger).toHaveTextContent("Beta");
  });
});
