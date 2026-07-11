"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import Loading from "@/components/Loading";
import PlayerCard from "@/components/PlayerCard";
import { getMatchEvents, getMatchStats, getMatchSummary } from "@/lib/api";
import type { EventItem, MatchSummary, PlayerStat } from "@/lib/types";
import { errorMessage } from "@/lib/format";

interface PlayersTabProps {
  matchId: string;
}

/** Players tab: per-player stat cards with confidence bars and heatmaps. */
export default function PlayersTab({ matchId }: PlayersTabProps) {
  const [stats, setStats] = useState<PlayerStat[]>([]);
  const [summary, setSummary] = useState<MatchSummary | null>(null);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const [st, sum, ev] = await Promise.allSettled([
      getMatchStats(matchId),
      getMatchSummary(matchId),
      getMatchEvents(matchId),
    ]);
    if (st.status === "fulfilled") {
      setStats(st.value);
      setError(null);
    } else {
      setStats([]);
      setError(errorMessage(st.reason));
    }
    setSummary(sum.status === "fulfilled" ? sum.value : null);
    setEvents(ev.status === "fulfilled" ? ev.value : []);
    setLoading(false);
  }, [matchId]);

  useEffect(() => {
    void load();
  }, [load]);

  // Events carry both identity and track ids, which lets us bridge stats
  // (keyed by identity) to summary players (keyed by track) for jersey display.
  const identityToTrack = useMemo(() => {
    const map = new Map<string, number>();
    for (const event of events) {
      if (event.player_identity_id && event.track_id !== null && event.track_id !== undefined) {
        if (!map.has(event.player_identity_id)) map.set(event.player_identity_id, event.track_id);
      }
    }
    return map;
  }, [events]);

  const trackToJersey = useMemo(() => {
    const map = new Map<number, number>();
    for (const player of summary?.players ?? []) {
      if (player.track_id !== null && player.jersey_number !== null) {
        map.set(player.track_id, player.jersey_number);
      }
    }
    return map;
  }, [summary]);

  const jerseyFor = useCallback(
    (stat: PlayerStat): number | null => {
      if (stat.jersey_number !== undefined && stat.jersey_number !== null) return stat.jersey_number;
      const track = stat.track_id ?? identityToTrack.get(stat.player_identity_id);
      if (track === undefined || track === null) return null;
      return trackToJersey.get(track) ?? null;
    },
    [identityToTrack, trackToJersey],
  );

  if (loading) return <Loading label="Loading player stats…" />;

  return (
    <div className="space-y-4">
      {error ? <p className="error-box">{error}</p> : null}

      {stats.length === 0 ? (
        <div className="card text-sm text-slate-400">
          No player stats yet. Process the match to generate tracking-based statistics.
        </div>
      ) : (
        <>
          <p className="text-xs text-slate-500">
            {stats.length} tracked players · identities are estimated from jersey OCR and appearance
            embeddings (no face recognition), confidence-scored.
          </p>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {stats.map((stat) => (
              <PlayerCard key={stat.id} stat={stat} jerseyNumber={jerseyFor(stat)} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
