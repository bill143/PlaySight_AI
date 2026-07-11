"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import EventTimeline from "@/components/EventTimeline";
import Loading from "@/components/Loading";
import { getMatchEvents, getMatchSummary } from "@/lib/api";
import {
  EVENT_TYPE_ORDER,
  eventColorClass,
  eventTypeLabel,
  getPeriodConfig,
  periodBounds,
} from "@/lib/events";
import type { EventItem, Match, MatchSummary } from "@/lib/types";
import { errorMessage, fmtSeconds, shortId } from "@/lib/format";

interface TimelineTabProps {
  matchId: string;
  match: Match | null;
}

function playerKeyOf(event: EventItem): string {
  if (event.player_identity_id) return `id:${event.player_identity_id}`;
  if (event.track_id !== null && event.track_id !== undefined) return `track:${event.track_id}`;
  return "unknown";
}

/** Timeline tab: horizontal event axis + filterable list view. */
export default function TimelineTab({ matchId, match }: TimelineTabProps) {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [summary, setSummary] = useState<MatchSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [typeFilter, setTypeFilter] = useState("all");
  const [playerFilter, setPlayerFilter] = useState("all");
  const [periodFilter, setPeriodFilter] = useState("all");
  const [t0, setT0] = useState("");
  const [t1, setT1] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    const [ev, sum] = await Promise.allSettled([getMatchEvents(matchId), getMatchSummary(matchId)]);
    if (ev.status === "fulfilled") {
      setEvents(ev.value);
      setError(null);
    } else {
      setEvents([]);
      setError(errorMessage(ev.reason));
    }
    setSummary(sum.status === "fulfilled" ? sum.value : null);
    setLoading(false);
  }, [matchId]);

  useEffect(() => {
    void load();
  }, [load]);

  const periodConfig = useMemo(() => getPeriodConfig(match), [match]);

  const jerseyByTrack = useMemo(() => {
    const map = new Map<number, number>();
    for (const player of summary?.players ?? []) {
      if (player.track_id !== null && player.jersey_number !== null) {
        map.set(player.track_id, player.jersey_number);
      }
    }
    return map;
  }, [summary]);

  const labelFor = useCallback(
    (event: EventItem): string => {
      if (event.track_id !== null && event.track_id !== undefined) {
        const jersey = jerseyByTrack.get(event.track_id);
        return jersey !== undefined ? `#${jersey} (track ${event.track_id})` : `Track ${event.track_id}`;
      }
      if (event.player_identity_id) return `Identity ${shortId(event.player_identity_id)}`;
      return "Unassigned";
    },
    [jerseyByTrack],
  );

  const playerOptions = useMemo(() => {
    const map = new Map<string, string>();
    for (const event of events) {
      const key = playerKeyOf(event);
      if (!map.has(key)) map.set(key, labelFor(event));
    }
    return Array.from(map.entries());
  }, [events, labelFor]);

  const filtered = useMemo(() => {
    let pStart: number | null = null;
    let pEnd: number | null = null;
    if (periodFilter !== "all") {
      const bounds = periodBounds(periodConfig, Number(periodFilter));
      pStart = bounds[0];
      pEnd = bounds[1];
    }
    const startBound = t0.trim() === "" ? null : Number(t0);
    const endBound = t1.trim() === "" ? null : Number(t1);
    return events
      .filter((e) => typeFilter === "all" || e.event_type === typeFilter)
      .filter((e) => playerFilter === "all" || playerKeyOf(e) === playerFilter)
      .filter((e) => pStart === null || pEnd === null || (e.t_start_s < pEnd && e.t_end_s >= pStart))
      .filter((e) => startBound === null || Number.isNaN(startBound) || e.t_end_s >= startBound)
      .filter((e) => endBound === null || Number.isNaN(endBound) || e.t_start_s <= endBound)
      .sort((a, b) => a.t_start_s - b.t_start_s);
  }, [events, typeFilter, playerFilter, periodFilter, t0, t1, periodConfig]);

  const duration =
    summary && summary.video.duration_s > 0
      ? summary.video.duration_s
      : events.reduce((acc, e) => Math.max(acc, e.t_end_s), 60);

  const usedTypes = useMemo(() => {
    const present = new Set(events.map((e) => e.event_type));
    return EVENT_TYPE_ORDER.filter((t) => present.has(t)).concat(
      Array.from(present).filter((t) => !EVENT_TYPE_ORDER.includes(t)).sort(),
    );
  }, [events]);

  if (loading) return <Loading label="Loading events…" />;

  return (
    <div className="space-y-4">
      {error ? <p className="error-box">{error}</p> : null}

      {events.length === 0 && !error ? (
        <div className="card text-sm text-slate-400">
          No events yet. Upload a video and run processing to populate the timeline.
        </div>
      ) : (
        <>
          <div className="card space-y-3">
            <div className="flex flex-wrap items-end gap-3">
              <div>
                <label className="label" htmlFor="flt-type">
                  Event type
                </label>
                <select
                  id="flt-type"
                  className="input w-44"
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                >
                  <option value="all">All types</option>
                  {usedTypes.map((t) => (
                    <option key={t} value={t}>
                      {eventTypeLabel(t)}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label" htmlFor="flt-player">
                  Player
                </label>
                <select
                  id="flt-player"
                  className="input w-48"
                  value={playerFilter}
                  onChange={(e) => setPlayerFilter(e.target.value)}
                >
                  <option value="all">All players</option>
                  {playerOptions.map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label" htmlFor="flt-period">
                  Period
                </label>
                <select
                  id="flt-period"
                  className="input w-32"
                  value={periodFilter}
                  onChange={(e) => setPeriodFilter(e.target.value)}
                >
                  <option value="all">All</option>
                  {Array.from({ length: periodConfig.periods }, (_, i) => i + 1).map((p) => (
                    <option key={p} value={String(p)}>
                      Period {p}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label" htmlFor="flt-t0">
                  From (s)
                </label>
                <input
                  id="flt-t0"
                  type="number"
                  min={0}
                  className="input w-28"
                  value={t0}
                  onChange={(e) => setT0(e.target.value)}
                  placeholder="0"
                />
              </div>
              <div>
                <label className="label" htmlFor="flt-t1">
                  To (s)
                </label>
                <input
                  id="flt-t1"
                  type="number"
                  min={0}
                  className="input w-28"
                  value={t1}
                  onChange={(e) => setT1(e.target.value)}
                  placeholder="∞"
                />
              </div>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => {
                  setTypeFilter("all");
                  setPlayerFilter("all");
                  setPeriodFilter("all");
                  setT0("");
                  setT1("");
                }}
              >
                Reset
              </button>
            </div>
            <p className="text-xs text-slate-500">
              Showing {filtered.length} of {events.length} events
            </p>
          </div>

          <div className="card">
            <EventTimeline events={filtered} durationS={duration} labelFor={labelFor} />
            {summary?.engine ? (
              <p className="mt-3 text-xs text-slate-500">
                Engines:{" "}
                {Object.entries(summary.engine)
                  .map(([k, v]) => `${k}=${v}`)
                  .join(" · ")}
                {Object.values(summary.engine).some((v) => v === "stub" || v === "simple")
                  ? " — heuristic/stub output, not ground truth"
                  : ""}
              </p>
            ) : null}
          </div>

          <div className="card p-0">
            <div className="max-h-96 overflow-auto">
              <table className="w-full min-w-[640px] border-collapse">
                <thead className="sticky top-0 bg-slate-900">
                  <tr>
                    <th className="table-th">Start</th>
                    <th className="table-th">End</th>
                    <th className="table-th">Type</th>
                    <th className="table-th">Player</th>
                    <th className="table-th">Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((event) => (
                    <tr key={event.id} className="border-t border-slate-800/60">
                      <td className="table-td tabular-nums">{fmtSeconds(event.t_start_s)}</td>
                      <td className="table-td tabular-nums">{fmtSeconds(event.t_end_s)}</td>
                      <td className="table-td">
                        <span className="inline-flex items-center gap-1.5 capitalize">
                          <span
                            aria-hidden
                            className={`h-2 w-2 rounded-full ${eventColorClass(event.event_type)}`}
                          />
                          {eventTypeLabel(event.event_type)}
                        </span>
                      </td>
                      <td className="table-td text-slate-300">{labelFor(event)}</td>
                      <td className="table-td text-slate-400">
                        {Math.round((event.confidence ?? 0) * 100)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
