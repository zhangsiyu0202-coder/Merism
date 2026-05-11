import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

/** Merge Tailwind classes safely (deduplicates conflicting utilities). */
export function cn(...inputs: ClassValue[]): string {
    return twMerge(clsx(inputs))
}
