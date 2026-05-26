import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { forwardRef } from "react";

import { cn } from "../utils/cn";

/**
 * Button — Cohere-aligned editorial button.
 *
 * Visual contract:
 *   - Primary: Coral accent fill with warm-ink text (not white!).
 *   - Secondary: bg-surface + border; tactile, uses border on hover.
 *   - Ghost: text-only, no border; Coral text on hover.
 *   - Radius 10 px; never the default Tailwind ``rounded-md`` (6 px).
 *   - Tight tracking (-0.005em) and slight weight bump on primary.
 */

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap " +
    "rounded-merism-md font-medium tracking-merism-tight transition-colors duration-[var(--merism-duration-fast)] " +
    "ease-[var(--merism-ease)] disabled:cursor-not-allowed disabled:opacity-50 " +
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-merism-accent-outline " +
    "focus-visible:ring-offset-2 focus-visible:ring-offset-merism-bg select-none",
  {
    variants: {
      variant: {
        primary:
          "bg-merism-accent text-merism-accent-ink hover:bg-merism-accent-hover " +
          "active:bg-merism-accent-active shadow-merism-xs",
        secondary:
          "bg-merism-surface text-merism-text border border-[color:var(--merism-hairline-strong)] " +
          "hover:border-merism-border-strong hover:bg-merism-bg-subtle",
        ghost:
          "text-merism-text hover:bg-merism-bg-subtle hover:text-merism-accent",
        danger:
          "bg-merism-danger text-white hover:opacity-90 active:opacity-85 shadow-merism-xs",
        link: "text-merism-accent underline-offset-4 hover:underline p-0 h-auto",
      },
      // 8pt grid heights + paddings (~1/2 height each side):
      //   sm  h-8  px-4  → 32 / 16  · text 13px
      //   md  h-10 px-5  → 40 / 20  · text 14px
      //   lg  h-12 px-6  → 48 / 24  · text 16px
      //   icon h-10 w-10 → 40 square
      size: {
        sm: "h-8 px-4 text-[var(--text-merism-label)]",
        md: "h-10 px-5 text-[var(--text-merism-body-sm)]",
        lg: "h-12 px-6 text-[var(--text-merism-body)]",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  },
);

export interface ButtonProps
  extends
    ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  iconLeft?: ReactNode;
  iconRight?: ReactNode;
  /** Preferred name. */
  isLoading?: boolean;
  /** Deprecated alias for ``isLoading`` — kept for back-compat. */
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant,
      size,
      asChild = false,
      iconLeft,
      iconRight,
      isLoading,
      loading,
      disabled,
      children,
      ...props
    },
    ref,
  ) => {
    const Component = asChild ? Slot : "button";
    const busy = Boolean(isLoading || loading);

    // When asChild, Radix Slot requires exactly one child — so skip the
    // icon / spinner wrappers and let the caller handle layout. Variants
    // + className are still applied to the forwarded child.
    if (asChild) {
      return (
        <Component
          ref={ref}
          className={cn(buttonVariants({ variant, size }), className)}
          aria-busy={busy || undefined}
          aria-disabled={disabled ? true : undefined}
          {...props}
        >
          {children}
        </Component>
      );
    }

    return (
      <Component
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        disabled={disabled || busy}
        aria-busy={busy || undefined}
        aria-disabled={disabled ? true : undefined}
        data-loading={busy ? "" : undefined}
        {...props}
      >
        {busy ? (
          <span
            aria-hidden="true"
            className="inline-block h-3 w-3 animate-pulse rounded-merism-full bg-current opacity-70"
          />
        ) : (
          iconLeft
        )}
        {children}
        {iconRight}
      </Component>
    );
  },
);

Button.displayName = "Button";

export { buttonVariants };
