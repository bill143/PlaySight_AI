import Heatmap from "@/components/Heatmap";
import ProgressBar from "@/components/ProgressBar";
import type { PlayerStat } from "@/lib/types";
import { shortId } from "@/lib/format";

interface PlayerCardProps {
  stat: PlayerStat;
  /** Jersey number resolved by the caller (identity/track/summary join), if known. */
  jerseyNumber?: number | null;
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-baseline justify-between gap-2 border-b border-slate-800/60 py-1">
      <dt className="text-xs text-slate-400">{label}</dt>
      <dd className="text-sm font-medium text-slate-100">{value}</dd>
    </div>
  );
}

/** Per-player stat card: jersey/identity, minutes, touches, confidence bar, heatmap. */
export default function PlayerCard({ stat, jerseyNumber }: PlayerCardProps) {
  const jersey = jerseyNumber ?? stat.jersey_number ?? null;
  const name =
    stat.player_name ??
    (jersey !== null ? `Jersey #${jersey}` : `Identity ${shortId(stat.player_identity_id)}`);
  const confidence = Math.max(0, Math.min(1, stat.avg_confidence ?? 0));

  return (
    <article className="card space-y-3">
      <header className="flex items-center gap-3">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-slate-700 bg-slate-800 text-lg font-bold text-sky-300">
          {jersey ?? "?"}
        </div>
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-white">{name}</h3>
          <p className="text-xs text-slate-500">
            Identity {shortId(stat.player_identity_id)} · estimated, confidence-scored
          </p>
        </div>
      </header>

      <dl className="grid grid-cols-2 gap-x-4">
        <Metric label="Minutes tracked" value={(stat.minutes_tracked ?? 0).toFixed(1)} />
        <Metric label="Touches" value={stat.touches ?? 0} />
        <Metric label="Distance (proxy)" value={`${Math.round(stat.distance_proxy_m ?? 0)} m`} />
        <Metric label="Passes" value={stat.passes ?? 0} />
        <Metric label="Tackles" value={stat.tackles ?? 0} />
        <Metric label="Shots" value={stat.shots ?? 0} />
        <Metric label="Turnovers" value={stat.turnovers ?? 0} />
        <Metric label="Scoring events" value={stat.scoring_events ?? 0} />
      </dl>

      <div>
        <div className="mb-1 flex items-center justify-between">
          <span className="text-xs text-slate-400">Identity confidence</span>
          <span className="text-xs font-medium text-slate-300">{Math.round(confidence * 100)}%</span>
        </div>
        <ProgressBar value={confidence} barClassName="bg-emerald-500" />
      </div>

      <Heatmap grid={stat.heatmap_json} caption="Movement heat (proxy grid)" />
    </article>
  );
}
