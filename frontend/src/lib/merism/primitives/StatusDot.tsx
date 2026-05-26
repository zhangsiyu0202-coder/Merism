import { forwardRef, type HTMLAttributes } from "react";

import { cn } from "../utils/cn";

export interface StatusDotProps extends HTMLAttributes<HTMLSpanElement> {
  status: "ok" | "warn" | "error" | "neutral";
  /** Screen reader label. Required for accessibility. */
  label: string;
}

export const StatusDot = forwardRef<HTMLSpanElement, StatusDotProps>(
  ({ className, status, label, ...props }, ref) => {
    const palette = {
      ok: "bg-merism-success",
      warn: "bg-merism-warning",
      error: "bg-merism-danger",
      neutral: "bg-merism-text-muted",
    }[status];
    return (
      <span
        ref={ref}
        role="img"
        aria-label={label}
        className={cn("inline-block h-2 w-2 rounded-full", palette, className)}
        {...props}
      />
    );
  },
);
StatusDot.displayName = "StatusDot";
