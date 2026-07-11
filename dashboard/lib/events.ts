/** Event taxonomy display constants + match period helpers (CONTRACTS.md section 8). */

import type { Match, PeriodConfig } from "@/lib/types";

/** Canonical taxonomy order used for timeline lanes and legends. */
export const EVENT_TYPE_ORDER: readonly string[] = [
  "touch",
  "pass",
  "tackle",
  "shot_attempt",
  "turnover",
  "scoring_event",
];

const EVENT_COLOR_CLASSES: Record<string, string> = {
  touch: "bg-sky-500",
  pass: "bg-emerald-500",
  tackle: "bg-amber-500",
  shot_attempt: "bg-rose-500",
  turnover: "bg-orange-500",
  scoring_event: "bg-yellow-400",
};

/** Tailwind background class for an event type block/dot. */
export function eventColorClass(eventType: string): string {
  return EVENT_COLOR_CLASSES[eventType] ?? "bg-slate-400";
}

/** Human label for an event type (`shot_attempt` -> `shot attempt`). */
export function eventTypeLabel(eventType: string): string {
  return eventType.replace(/_/g, " ");
}

export const DEFAULT_PERIOD_CONFIG: PeriodConfig = { periods: 2, period_minutes: 45 };

/** Period configuration of a match, falling back to the contract default. */
export function getPeriodConfig(match: Match | null | undefined): PeriodConfig {
  const raw = match?.period_config_json ?? match?.period_config;
  if (
    raw &&
    typeof raw.periods === "number" &&
    raw.periods > 0 &&
    typeof raw.period_minutes === "number" &&
    raw.period_minutes > 0
  ) {
    return raw;
  }
  return DEFAULT_PERIOD_CONFIG;
}

/** `[startSeconds, endSeconds]` covered by a 1-based period number. */
export function periodBounds(config: PeriodConfig, period: number): [number, number] {
  const lengthS = config.period_minutes * 60;
  return [(period - 1) * lengthS, period * lengthS];
}
