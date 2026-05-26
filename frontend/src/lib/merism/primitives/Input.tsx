import {
  forwardRef,
  type InputHTMLAttributes,
  type LabelHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";

import { cn } from "../utils/cn";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, invalid, ...props }, ref) => (
    <input
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(
        "flex h-10 w-full rounded-merism-md border border-[color:var(--merism-hairline-strong)] bg-merism-surface " +
          "px-3 py-2 text-sm text-merism-text placeholder:text-merism-text-muted " +
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-merism-accent/60 " +
          "disabled:cursor-not-allowed disabled:opacity-50",
        invalid && "border-merism-danger focus-visible:ring-merism-danger/50",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, invalid, ...props }, ref) => (
    <textarea
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(
        "flex min-h-[80px] w-full rounded-merism-md border border-[color:var(--merism-hairline-strong)] " +
          "bg-merism-surface px-3 py-2 text-sm text-merism-text " +
          "placeholder:text-merism-text-muted " +
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-merism-accent/60 " +
          "disabled:cursor-not-allowed disabled:opacity-50",
        invalid && "border-merism-danger focus-visible:ring-merism-danger/50",
        className,
      )}
      {...props}
    />
  ),
);
Textarea.displayName = "Textarea";

export const InputLabel = forwardRef<
  HTMLLabelElement,
  LabelHTMLAttributes<HTMLLabelElement>
>(({ className, ...props }, ref) => (
  <label
    ref={ref}
    className={cn(
      "text-sm font-medium leading-none text-merism-text",
      className,
    )}
    {...props}
  />
));
InputLabel.displayName = "InputLabel";

export function InputHelperText({
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={cn("text-xs text-merism-text-muted", className)} {...props} />
  );
}

export function InputErrorText({
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p
      className={cn("text-xs text-merism-danger", className)}
      role="alert"
      {...props}
    />
  );
}
