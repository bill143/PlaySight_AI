"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import ArtifactList from "@/components/ArtifactList";
import Loading from "@/components/Loading";
import { getMatchStats, getPlayerReport, listArtifacts } from "@/lib/api";
import type { ArtifactRef, JsonObject, PlayerStat } from "@/lib/types";
import { errorMessage, shortId } from "@/lib/format";

interface ReportsTabProps {
  matchId: string;
}

const REPORT_KINDS = new Set(["player_report_json", "player_report_pdf"]);

/** Reports tab: per-player report JSON view + downloadable report artifacts. */
export default function ReportsTab({ matchId }: ReportsTabProps) {
  const [stats, setStats] = useState<PlayerStat[]>([]);
  const [artifacts, setArtifacts] = useState<ArtifactRef[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [identityId, setIdentityId] = useState("");
  const [report, setReport] = useState<JsonObject | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const [st, arts] = await Promise.allSettled([
      getMatchStats(matchId),
      listArtifacts({ match_id: matchId }),
    ]);
    if (st.status === "fulfilled") {
      setStats(st.value);
      setError(null);
    } else {
      setStats([]);
      setError(errorMessage(st.reason));
    }
    setArtifacts(arts.status === "fulfilled" ? arts.value : []);
    setLoading(false);
  }, [matchId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!identityId) {
      setReport(null);
      setReportError(null);
      return;
    }
    let cancelled = false;
    setReportLoading(true);
    getPlayerReport(matchId, identityId)
      .then((data) => {
        if (!cancelled) {
          setReport(data);
          setReportError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setReport(null);
          setReportError(errorMessage(err));
        }
      })
      .finally(() => {
        if (!cancelled) setReportLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [identityId, matchId]);

  const reportArtifacts = useMemo(
    () => artifacts.filter((a) => REPORT_KINDS.has(a.kind)),
    [artifacts],
  );

  if (loading) return <Loading label="Loading reports…" />;

  return (
    <div className="space-y-4">
      {error ? <p className="error-box">{error}</p> : null}

      <section className="card space-y-3">
        <h2 className="text-sm font-semibold text-white">Per-player report</h2>
        {stats.length === 0 ? (
          <p className="text-sm text-slate-400">
            No player identities yet — process the match first.
          </p>
        ) : (
          <>
            <div className="max-w-sm">
              <label className="label" htmlFor="report-identity">
                Player identity
              </label>
              <select
                id="report-identity"
                className="input"
                value={identityId}
                onChange={(e) => setIdentityId(e.target.value)}
              >
                <option value="">Select an identity…</option>
                {stats.map((stat) => (
                  <option key={stat.player_identity_id} value={stat.player_identity_id}>
                    {stat.jersey_number !== null && stat.jersey_number !== undefined
                      ? `#${stat.jersey_number} · `
                      : ""}
                    Identity {shortId(stat.player_identity_id)} ({stat.touches} touches)
                  </option>
                ))}
              </select>
            </div>
            {reportLoading ? <Loading label="Loading report…" /> : null}
            {reportError ? <p className="error-box">{reportError}</p> : null}
            {report ? (
              <pre className="max-h-96 overflow-auto rounded-lg border border-slate-800 bg-slate-950 p-4 text-xs text-slate-300">
                {JSON.stringify(report, null, 2)}
              </pre>
            ) : null}
          </>
        )}
      </section>

      <section className="card space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">Report artifacts (PDF / JSON)</h2>
          <button type="button" className="btn btn-ghost" onClick={() => void load()}>
            Refresh
          </button>
        </div>
        <ArtifactList
          artifacts={reportArtifacts}
          emptyLabel="No report artifacts yet — they are generated during match processing."
        />
      </section>
    </div>
  );
}
