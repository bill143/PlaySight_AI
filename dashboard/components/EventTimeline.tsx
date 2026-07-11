"use client";

import { EVENT_TYPE_ORDER, eventColorClass, eventTypeLabel } from "@/lib/events";
import type { EventItem } from "@/lib/types";
import { fmtSeconds } from "@/lib/format";

interface EventTimelineProps {
  events: EventItem[];
  /** Total timeline length in seconds (video duration). */
  durationS: number;
  /** Optional player label used in block tooltips. */
  labelFor?: (event: EventItem) => string;
}

function tickStep(duration: number): number {
  const steps = [5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600];
  for (const step of steps) {
    if (duration / step <= 10) return step;
  }
  return 3600;
}

/**
 * Horizontal time axis with one lane per event type; events render as
 * positioned blocks colored by type.
 */
export default function EventTimeline({ events, durationS, labelFor }: EventTimelineProps) {
  if (events.length === 0) {
    return <p className="text-sm text-slate-500">No events to display.</p>;
  }

  const maxEnd = events.reduce((acc, e) => Math.max(acc, e.t_end_s), 0);
  const duration = Math.max(durationS, maxEnd, 1);
  const step = tickStep(duration);
  const ticks: number[] = [];
  for (let t = 0; t <= duration; t += step) ticks.push(t);

  const knownLanes = EVENT_TYPE_ORDER.filter((type) => events.some((e) => e.event_type === type));
  const extraLanes = Array.from(new Set(events.map((e) => e.event_type)))
    .filter((type) => !EVENT_TYPE_ORDER.includes(type))
    .sort();
  const lanes = [...knownLanes, ...extraLanes];

  return (
    <div className="overflow-x-auto pb-1">
      <div className="min-w-[640px] pr-8">
        <div className="relative ml-[7.5rem] h-5 border-b border-slate-800 text-[10px] text-slate-500">
          {ticks.map((t) => (
            <span
              key={t}
              className="absolute -translate-x-1/2"
              style={{ left: `${(t / duration) * 100}%` }}
            >
              {fmtSeconds(t)}
            </span>
          ))}
        </div>

        {lanes.map((type) => (
          <div key={type} className="flex items-center gap-2 py-1.5">
            <div className="flex w-28 shrink-0 items-center gap-1.5">
              <span aria-hidden className={`h-2 w-2 rounded-full ${eventColorClass(type)}`} />
              <span className="truncate text-xs capitalize text-slate-300">{eventTypeLabel(type)}</span>
            </div>
            <div className="relative h-6 flex-1 rounded border border-slate-800/70 bg-slate-900/70">
              {events
                .filter((e) => e.event_type === type)
                .map((e) => {
                  const left = Math.max(0, Math.min(100, (e.t_start_s / duration) * 100));
                  const rawWidth = ((Math.max(e.t_end_s, e.t_start_s) - e.t_start_s) / duration) * 100;
                  const width = Math.min(Math.max(rawWidth, 0.6), 100 - left);
                  const tooltip = [
                    `${eventTypeLabel(e.event_type)} ${fmtSeconds(e.t_start_s)}–${fmtSeconds(e.t_end_s)}`,
                    labelFor ? labelFor(e) : null,
                    `confidence ${Math.round((e.confidence ?? 0) * 100)}%`,
                  ]
                    .filter(Boolean)
                    .join(" · ");
                  return (
                    <div
                      key={e.id}
                      title={tooltip}
                      className={`absolute bottom-0.5 top-0.5 rounded-sm ${eventColorClass(e.event_type)} opacity-80 transition-opacity hover:opacity-100`}
                      style={{ left: `${left}%`, width: `${width}%` }}
                    />
                  );
                })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
