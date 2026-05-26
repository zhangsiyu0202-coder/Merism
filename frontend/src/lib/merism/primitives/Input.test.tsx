import { describe, expect, it } from "vitest";

import {
  Input,
  InputErrorText,
  InputHelperText,
  InputLabel,
  Textarea,
} from "~/lib/merism";
import { render, screen } from "~/test/render";

describe("Input", () => {
  it("exposes a textbox role with the typed value", async () => {
    const { user } = render(<Input placeholder="email" />);
    const input = screen.getByRole("textbox");
    await user.type(input, "alice@merism.test");
    expect(input).toHaveValue("alice@merism.test");
  });

  it("associates a label via htmlFor/id", () => {
    render(
      <>
        <InputLabel htmlFor="email">Email</InputLabel>
        <Input id="email" />
      </>,
    );
    const input = screen.getByLabelText("Email");
    expect(input).toBeInTheDocument();
  });

  it("sets aria-invalid when invalid", () => {
    render(<Input invalid data-testid="x" />);
    expect(screen.getByTestId("x")).toHaveAttribute("aria-invalid", "true");
  });

  it("renders helper text", () => {
    render(<InputHelperText>Helper copy</InputHelperText>);
    expect(screen.getByText("Helper copy")).toBeInTheDocument();
  });

  it("renders error text with role=alert", () => {
    render(<InputErrorText>Broken</InputErrorText>);
    expect(screen.getByRole("alert")).toHaveTextContent("Broken");
  });
});

describe("Textarea", () => {
  it("exposes a textbox role and accepts typing", async () => {
    const { user } = render(<Textarea />);
    const textarea = screen.getByRole("textbox");
    await user.type(textarea, "a paragraph of text");
    expect(textarea).toHaveValue("a paragraph of text");
  });

  it("sets aria-invalid when invalid", () => {
    render(<Textarea invalid />);
    expect(screen.getByRole("textbox")).toHaveAttribute("aria-invalid", "true");
  });
});
