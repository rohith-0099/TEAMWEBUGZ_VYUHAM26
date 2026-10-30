// Safety helper: never render IOC value in the DOM. Owner: Frontend A.
import type { IOC } from "@/lib/types";

/**
 * Returns the defanged display representation of an IOC.
 * Rule: The raw `value` must never be rendered in UI elements or rendered as clickable links.
 */
export function safeDisplay(ioc: IOC | { display: string }): string {
  return ioc.display;
}
