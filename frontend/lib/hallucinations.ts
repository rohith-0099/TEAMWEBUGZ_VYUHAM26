// The one definition of "Hallucinations blocked" (team/05 §4). The stat card, the filter chart
// and the technique list all use this, so their numbers always match.
import type { RejectReason, TechniqueMatch } from "@/lib/types";

export const HALLUCINATION_REASONS: readonly RejectReason[] = ["id_not_in_v20", "quote_not_in_source"];

export function isHallucination(t: TechniqueMatch): boolean {
  return t.status === "rejected" && !!t.reject_reason && HALLUCINATION_REASONS.includes(t.reject_reason);
}

export function countHallucinations(techniques: TechniqueMatch[] | undefined): number {
  return (techniques ?? []).filter(isHallucination).length;
}
