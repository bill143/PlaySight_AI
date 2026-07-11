"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import JobBadge from "@/components/JobBadge";
import Loading from "@/components/Loading";
import RequireAuth from "@/components/RequireAuth";
import ExportPublishTab from "@/components/tabs/ExportPublishTab";
import HighlightsTab from "@/components/tabs/HighlightsTab";
import PlayersTab from "@/components/tabs/PlayersTab";
import ReportsTab from "@/components/tabs/ReportsTab";
import TimelineTab from "@/components/tabs/TimelineTab";
import { getMatch } from "@/lib/api";
import type { Match } from "@/lib/types";
import { errorMessage, fmtDate } from "@/lib/format";

const TABS = [
  { key: "timeline", label: "Timeline" },
  { key: "players", label: "Players" },
  { key: "reports", label: "Reports" },
  { key: "highlights", label: "Highlights" },
  { key: "export", label: "Export & Publish" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

/** Match detail page with Timeline / Players / Reports / Highlights / Export tabs. */
export default function MatchDetailPage() {
  const params = useParams<{ id: string }>();
  const matchId = params?.id ?? "";

  return (
    <RequireAuth>
      <MatchDetail matchId={matchId} />
    </RequireAuth>
  );
}

function MatchDetail({ matchId }: { matchId: string }) {
  const [match, setMatch] = useState<Match | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabKey>("timeline");

  const load = useCallback(async () => {
    if (!matchId) return;
    setLoading(true);
    try {
      setMatch(await getMatch(matchId));
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [matchId]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-5">
      <div>
        <Link href="/" className="text-xs text-slate-400 hover:text-slate-200">
          ← Back to matches
        </Link>
        {loading ? (
          <Loading label="Loading match…" />
        ) : match ? (
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold text-white">vs {match.opponent}</h1>
            <JobBadge status={match.status} />
            <span className="rounded-full border border-slate-700 px-2 py-0.5 text-xs capitalize text-slate-300">
              {match.sport}
            </span>
            {match.kickoff_at ? (
              <span className="text-sm text-slate-400">{fmtDate(match.kickoff_at)}</span>
            ) : null}
            {match.venue ? <span className="text-sm text-slate-500">{match.venue}</span> : null}
          </div>
        ) : (
          <p className="error-box mt-3">{error ?? "Match not found."}</p>
        )}
      </div>

      <nav className="flex flex-wrap gap-1 border-b border-slate-800">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
              tab === t.key
                ? "border-sky-500 text-white"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {tab === "timeline" ? <TimelineTab matchId={matchId} match={match} /> : null}
      {tab === "players" ? <PlayersTab matchId={matchId} /> : null}
      {tab === "reports" ? <ReportsTab matchId={matchId} /> : null}
      {tab === "highlights" ? <HighlightsTab matchId={matchId} /> : null}
      {tab === "export" ? <ExportPublishTab matchId={matchId} /> : null}
    </div>
  );
}
