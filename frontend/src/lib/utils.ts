import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

const TIMEZONE_REGEX = /([+-]\d{2}:?\d{2}|Z)$/

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function parseApiDate(value?: string | null): Date | null {
  if (!value) return null
  const normalized = TIMEZONE_REGEX.test(value) ? value : `${value}Z`
  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}

export function formatMessageTime(value?: string | Date | null): string {
  const date = value instanceof Date ? value : parseApiDate(value ?? undefined)
  if (!date) return ""
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}
