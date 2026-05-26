import { createRef } from "react";
import { describe, expect, it, vi } from "vitest";

import { Button } from "~/lib/merism";
import { render, screen } from "~/test/render";

describe("Button", () => {
  it("renders its text", () => {
    render(<Button>Save</Button>);
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
  });

  it("applies the variant class", () => {
    render(<Button variant="danger">Delete</Button>);
    expect(screen.getByRole("button")).toHaveClass("bg-merism-danger");
  });

  it("applies the size class", () => {
    render(<Button size="sm">Small</Button>);
    expect(screen.getByRole("button")).toHaveClass("h-8");
  });

  it("forwards refs", () => {
    const ref = createRef<HTMLButtonElement>();
    render(<Button ref={ref}>Ref</Button>);
    expect(ref.current).toBeInstanceOf(HTMLButtonElement);
  });

  it("exposes aria-busy when loading and aria-disabled when disabled", () => {
    render(
      <Button loading disabled>
        Wait
      </Button>,
    );
    const btn = screen.getByRole("button");
    expect(btn).toHaveAttribute("aria-busy", "true");
    expect(btn).toHaveAttribute("aria-disabled", "true");
    expect(btn).toBeDisabled();
  });

  it("asChild renders the child element instead of a button", () => {
    render(
      <Button asChild>
        <a href="/x">link</a>
      </Button>,
    );
    const el = screen.getByRole("link", { name: "link" });
    expect(el.tagName).toBe("A");
    expect(el).toHaveAttribute("href", "/x");
  });

  it("calls onClick", async () => {
    const onClick = vi.fn();
    const { user } = render(<Button onClick={onClick}>Go</Button>);
    await user.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
