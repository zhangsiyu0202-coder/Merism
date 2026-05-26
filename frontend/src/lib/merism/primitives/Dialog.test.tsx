import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "~/lib/merism";
import { render, screen } from "~/test/render";

function DialogFixture({
  dismissible,
  onOpenChange,
}: {
  dismissible?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        onOpenChange?.(o);
      }}
    >
      <DialogTrigger asChild>
        <button type="button">open</button>
      </DialogTrigger>
      <DialogContent dismissible={dismissible}>
        <DialogTitle>Title</DialogTitle>
        <DialogDescription>Body</DialogDescription>
        <DialogClose asChild>
          <button type="button">close</button>
        </DialogClose>
      </DialogContent>
    </Dialog>
  );
}

describe("Dialog", () => {
  it("is hidden by default and visible when triggered", async () => {
    const { user } = render(<DialogFixture />);
    expect(screen.queryByRole("dialog")).toBeNull();

    await user.click(screen.getByRole("button", { name: "open" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("close button calls onOpenChange(false)", async () => {
    const onOpenChange = vi.fn();
    const { user } = render(<DialogFixture onOpenChange={onOpenChange} />);

    await user.click(screen.getByRole("button", { name: "open" }));
    onOpenChange.mockClear();

    await user.click(screen.getByRole("button", { name: "close" }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("Escape closes a dismissible dialog", async () => {
    const onOpenChange = vi.fn();
    const { user } = render(<DialogFixture onOpenChange={onOpenChange} />);
    await user.click(screen.getByRole("button", { name: "open" }));
    onOpenChange.mockClear();

    await user.keyboard("{Escape}");
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("Escape does NOT close when dismissible=false", async () => {
    const onOpenChange = vi.fn();
    const { user } = render(
      <DialogFixture dismissible={false} onOpenChange={onOpenChange} />,
    );
    await user.click(screen.getByRole("button", { name: "open" }));
    onOpenChange.mockClear();

    await user.keyboard("{Escape}");
    expect(onOpenChange).not.toHaveBeenCalled();
  });
});
