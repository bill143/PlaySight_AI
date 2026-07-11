import type { MatchEvent } from "@/types";

export function EventTimeline({ events }: { events: MatchEvent[] }) {
  return (
    <div className="space-y-5">
      {events.map((event, index) => (
        <div key={event.id} className="relative pl-8">
          {index < events.length - 1 ? (
            <span className="absolute left-[11px] top-6 h-[calc(100%+1rem)] w-px bg-slate-700" />
          ) : null}
          <span className="absolute left-0 top-1 flex h-6 w-6 items-center justify-center rounded-full bg-primary-600 text-[10px] font-bold text-white">
            {index + 1}
          </span>
          <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-medium text-slate-100">{event.type}</p>
                <p className="text-sm text-slate-400">
                  {event.description || "Model-detected match moment"}
                </p>
              </div>
              <div className="text-sm text-slate-400">
                {event.timestamp} • {(event.confidence * 100).toFixed(0)}% confidence
              </div>
            </div>
          </div>
        </div>
      ))}
      {events.length === 0 ? (
        <p className="text-sm text-slate-400">No detected events available.</p>
      ) : null}
    </div>
  );
}
