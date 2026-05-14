import { AnimatePresence, motion } from "motion/react";
import { Check, ChevronDown } from "lucide-react";
import {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type ReactNode,
} from "react";

import { cn } from "../utils/cn";

export interface SelectOption {
  value: string;
  label: ReactNode;
  description?: ReactNode;
  disabled?: boolean;
}

export interface SelectProps extends Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  "children" | "onChange" | "value"
> {
  value: string;
  onValueChange: (value: string) => void;
  options: ReadonlyArray<SelectOption>;
  placeholder?: string;
  invalid?: boolean;
  emptyText?: string;
  size?: "sm" | "md";
  className?: string;
  triggerClassName?: string;
  contentClassName?: string;
}

function firstEnabledOptionIndex(options: ReadonlyArray<SelectOption>): number {
  return options.findIndex((option) => !option.disabled);
}

function lastEnabledOptionIndex(options: ReadonlyArray<SelectOption>): number {
  for (let index = options.length - 1; index >= 0; index -= 1) {
    const option = options[index];
    if (option && !option.disabled) {
      return index;
    }
  }
  return -1;
}

function nextEnabledOptionIndex(
  options: ReadonlyArray<SelectOption>,
  startIndex: number,
  direction: 1 | -1,
): number {
  if (options.length === 0) {
    return -1;
  }

  for (let step = 1; step <= options.length; step += 1) {
    const index =
      (startIndex + step * direction + options.length) % options.length;
    const option = options[index];
    if (option && !option.disabled) {
      return index;
    }
  }

  return startIndex;
}

export function Select({
  value,
  onValueChange,
  options,
  placeholder = "Select an option",
  invalid = false,
  emptyText = "No options available",
  size = "md",
  className,
  triggerClassName,
  contentClassName,
  disabled = false,
  onBlur,
  onFocus,
  onKeyDown,
  ...buttonProps
}: SelectProps): JSX.Element {
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const listboxRef = useRef<HTMLDivElement | null>(null);
  const listboxId = useId();
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  const selectedIndex = options.findIndex((option) => option.value === value);
  const selectedOption = selectedIndex >= 0 ? options[selectedIndex] : null;
  const activeOption = activeIndex >= 0 ? options[activeIndex] : undefined;
  const defaultActiveIndex =
    selectedIndex >= 0 && !options[selectedIndex]?.disabled
      ? selectedIndex
      : firstEnabledOptionIndex(options);

  const closeMenu = (restoreFocus: boolean): void => {
    setIsOpen(false);
    if (restoreFocus) {
      requestAnimationFrame(() => triggerRef.current?.focus());
    }
  };

  useLayoutEffect(() => {
    if (!isOpen) {
      return;
    }

    setActiveIndex(defaultActiveIndex);

    const animationFrame = requestAnimationFrame(() => {
      listboxRef.current?.focus();
    });

    return () => {
      cancelAnimationFrame(animationFrame);
    };
  }, [defaultActiveIndex, isOpen]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const handlePointerDown = (event: PointerEvent): void => {
      if (
        wrapperRef.current &&
        event.target instanceof Node &&
        !wrapperRef.current.contains(event.target)
      ) {
        closeMenu(false);
      }
    };

    document.addEventListener("pointerdown", handlePointerDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
    };
  }, [isOpen]);

  const commitSelection = (nextValue: string): void => {
    if (nextValue === value) {
      closeMenu(true);
      return;
    }
    onValueChange(nextValue);
    closeMenu(true);
  };

  const triggerSizeClassName =
    size === "sm"
      ? "min-h-10 px-3 py-2 text-[var(--text-merism-label)]"
      : "min-h-11 px-3.5 py-2.5 text-[var(--text-merism-body-sm)]";

  return (
    <div ref={wrapperRef} className={cn("relative", className)}>
      <button
        {...buttonProps}
        ref={triggerRef}
        type="button"
        disabled={disabled}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        aria-controls={listboxId}
        data-open={isOpen ? "true" : "false"}
        className={cn(
          "flex w-full items-center justify-between gap-3 rounded-merism-lg border " +
            "border-[color:var(--merism-hairline)] bg-merism-surface text-left text-merism-text shadow-merism-xs " +
            "transition-[border-color,background-color,box-shadow,transform] duration-[var(--merism-duration-fast)] " +
            "ease-[var(--merism-ease)] hover:border-merism-border-strong hover:bg-merism-surface hover:shadow-merism-sm " +
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-merism-accent-outline " +
            "focus-visible:ring-offset-2 focus-visible:ring-offset-merism-bg " +
            "data-[open=true]:border-merism-border-strong data-[open=true]:shadow-merism-float " +
            "disabled:cursor-not-allowed disabled:opacity-50",
          triggerSizeClassName,
          invalid &&
            "border-merism-danger/50 focus-visible:ring-merism-danger/35 data-[open=true]:border-merism-danger/60",
          triggerClassName,
        )}
        onClick={() => {
          if (!disabled) {
            setIsOpen((open) => !open);
          }
        }}
        onFocus={onFocus}
        onBlur={onBlur}
        onKeyDown={(event) => {
          onKeyDown?.(event);
          if (event.defaultPrevented || disabled) {
            return;
          }

          if (
            event.key === "ArrowDown" ||
            event.key === "ArrowUp" ||
            event.key === "Enter" ||
            event.key === " "
          ) {
            event.preventDefault();
            if (!isOpen) {
              setActiveIndex(
                event.key === "ArrowUp"
                  ? lastEnabledOptionIndex(options)
                  : defaultActiveIndex,
              );
              setIsOpen(true);
              return;
            }

            if (event.key === "ArrowDown") {
              setActiveIndex((currentIndex) =>
                nextEnabledOptionIndex(
                  options,
                  currentIndex < 0 ? defaultActiveIndex : currentIndex,
                  1,
                ),
              );
              return;
            }

            if (event.key === "ArrowUp") {
              setActiveIndex((currentIndex) =>
                nextEnabledOptionIndex(
                  options,
                  currentIndex < 0 ? defaultActiveIndex : currentIndex,
                  -1,
                ),
              );
              return;
            }

            const option = options[activeIndex];
            if (option && !option.disabled) {
              commitSelection(option.value);
            }
            return;
          }

          if (event.key === "Escape" && isOpen) {
            event.preventDefault();
            closeMenu(true);
          }
        }}
      >
        <span
          className={cn(
            "min-w-0 flex-1 truncate",
            selectedOption ? "text-merism-text" : "text-merism-text-muted",
          )}
        >
          {selectedOption?.label ?? placeholder}
        </span>
        <ChevronDown
          aria-hidden="true"
          className={cn(
            "h-4 w-4 shrink-0 text-merism-text-subtle transition-transform duration-[var(--merism-duration-fast)] ease-[var(--merism-ease)]",
            isOpen && "rotate-180 text-merism-text-muted",
          )}
        />
      </button>

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.99 }}
            transition={{
              duration: 0.18,
              ease: [0.22, 0.61, 0.36, 1],
            }}
            className={cn(
              "absolute left-0 top-[calc(100%+0.5rem)] z-30 min-w-full overflow-hidden rounded-merism-xl " +
                "border border-[color:var(--merism-glass-edge)] bg-[color:var(--merism-glass-surface)] p-1.5 shadow-merism-pop backdrop-blur-[14px]",
              contentClassName,
            )}
          >
            <div
              ref={listboxRef}
              id={listboxId}
              role="listbox"
              tabIndex={-1}
              aria-activedescendant={
                activeOption ? `${listboxId}-${activeOption.value}` : undefined
              }
              className="flex max-h-[min(20rem,calc(100vh-8rem))] flex-col gap-1 overflow-auto focus:outline-none"
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  event.preventDefault();
                  closeMenu(true);
                  return;
                }

                if (event.key === "Tab") {
                  closeMenu(false);
                  return;
                }

                if (event.key === "ArrowDown") {
                  event.preventDefault();
                  setActiveIndex((currentIndex) =>
                    nextEnabledOptionIndex(
                      options,
                      currentIndex < 0 ? defaultActiveIndex : currentIndex,
                      1,
                    ),
                  );
                  return;
                }

                if (event.key === "ArrowUp") {
                  event.preventDefault();
                  setActiveIndex((currentIndex) =>
                    nextEnabledOptionIndex(
                      options,
                      currentIndex < 0 ? defaultActiveIndex : currentIndex,
                      -1,
                    ),
                  );
                  return;
                }

                if (event.key === "Home") {
                  event.preventDefault();
                  setActiveIndex(firstEnabledOptionIndex(options));
                  return;
                }

                if (event.key === "End") {
                  event.preventDefault();
                  setActiveIndex(lastEnabledOptionIndex(options));
                  return;
                }

                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  const option = options[activeIndex];
                  if (option && !option.disabled) {
                    commitSelection(option.value);
                  }
                }
              }}
            >
              {options.length === 0 ? (
                <div className="px-3.5 py-3 text-[var(--text-merism-label)] text-merism-text-muted">
                  {emptyText}
                </div>
              ) : (
                options.map((option, index) => {
                  const isActive = index === activeIndex;
                  const isSelected = option.value === value;

                  return (
                    <div
                      key={option.value}
                      id={`${listboxId}-${option.value}`}
                      role="option"
                      aria-selected={isSelected}
                      data-active={isActive ? "true" : "false"}
                      data-selected={isSelected ? "true" : "false"}
                      data-disabled={option.disabled ? "true" : "false"}
                      className={cn(
                        "flex min-h-11 cursor-pointer items-start gap-3 rounded-merism-lg px-3.5 py-2.5 " +
                          "text-left transition-[background-color,box-shadow,color] duration-[var(--merism-duration-fast)] " +
                          "ease-[var(--merism-ease)]",
                        option.disabled
                          ? "cursor-not-allowed text-merism-text-subtle opacity-50"
                          : "text-merism-text",
                        !option.disabled &&
                          !isActive &&
                          !isSelected &&
                          "hover:bg-merism-bg-subtle/80",
                        isActive &&
                          !isSelected &&
                          "bg-merism-bg-subtle shadow-[inset_0_0_0_1px_var(--merism-hairline)]",
                        isSelected &&
                          "bg-merism-accent-soft shadow-[inset_0_0_0_1px_var(--merism-accent-outline)]",
                      )}
                      onMouseEnter={() => {
                        if (!option.disabled) {
                          setActiveIndex(index);
                        }
                      }}
                      onMouseDown={(event) => {
                        event.preventDefault();
                      }}
                      onClick={() => {
                        if (!option.disabled) {
                          commitSelection(option.value);
                        }
                      }}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-[var(--text-merism-body-sm)] font-medium">
                          {option.label}
                        </div>
                        {option.description ? (
                          <div className="mt-0.5 text-[var(--text-merism-caption)] text-merism-text-muted">
                            {option.description}
                          </div>
                        ) : null}
                      </div>
                      <Check
                        aria-hidden="true"
                        className={cn(
                          "mt-0.5 h-4 w-4 shrink-0 transition-opacity duration-[var(--merism-duration-fast)] ease-[var(--merism-ease)]",
                          isSelected
                            ? "opacity-100 text-merism-accent"
                            : "opacity-0 text-merism-text-subtle",
                        )}
                      />
                    </div>
                  );
                })
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
