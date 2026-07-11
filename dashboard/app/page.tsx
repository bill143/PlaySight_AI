"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import JobBadge from "@/components/JobBadge";
import Loading from "@/components/Loading";
import RequireAuth from "@/components/RequireAuth";
import {
  createMatch,
  createTeam,
  listMatches,
  listTeams,
  processMatch,
  uploadMatchVideo,
} from "@/lib/api";
import type { Match, Team } from "@/lib/types";
import { errorMessage, fmtDate } from "@/lib/format";

const SPORT_SUGGESTIONS = ["soccer", "basketball", "hockey", "handball", "futsal", "rugby", "volleyball"];

/** Matches dashboard: list with status chips, create form, upload + process actions. */
export default function HomePage() {
  return (
    <RequireAuth>
      <MatchesDashboard />
    </RequireAuth>
  );
}

function MatchesDashboard() {
  const [matches, setMatches] = useState<Match[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // create-match form
  const [teamId, setTeamId] = useState("");
  const [opponent, setOpponent] = useState("");
  const [sport, setSport] = useState("soccer");
  const [kickoff, setKickoff] = useState("");
  const [venue, setVenue] = useState("");
  const [creating, setCreating] = useState(false);

  // create-team form
  const [teamName, setTeamName] = useState("");
  const [teamSport, setTeamSport] = useState("soccer");
  const [creatingTeam, setCreatingTeam] = useState(false);

  // per-match actions
  const [uploadingId, setUploadingId] = useState<string | null>(null);
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [uploaded, setUploaded] = useState<Record<string, string>>({});

  const refresh = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [ms, ts] = await Promise.all([listMatches(), listTeams()]);
      setMatches(ms);
      setTeams(ts);
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const anyProcessing = matches.some((m) => m.status === "processing");
  useEffect(() => {
    if (!anyProcessing) return;
    const timer = setInterval(() => {
      void refresh(true);
    }, 4000);
    return () => clearInterval(timer);
  }, [anyProcessing, refresh]);

  async function onCreateMatch(e: React.FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    setCreating(true);
    setError(null);
    try {
      const match = await createMatch({
        team_id: teamId || null,
        opponent: opponent.trim(),
        sport: sport.trim(),
        kickoff_at: kickoff ? new Date(kickoff).toISOString() : null,
        venue: venue.trim() || null,
      });
      setNotice(`Match vs ${match.opponent} created.`);
      setOpponent("");
      setKickoff("");
      setVenue("");
      await refresh(true);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setCreating(false);
    }
  }

  async function onCreateTeam(e: React.FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    setCreatingTeam(true);
    setError(null);
    try {
      const team = await createTeam({ name: teamName.trim(), sport: teamSport.trim() });
      setTeams((prev) => [...prev, team]);
      setTeamId(team.id);
      setTeamName("");
      setNotice(`Team ${team.name} created.`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setCreatingTeam(false);
    }
  }

  async function handleUpload(matchId: string, e: React.ChangeEvent<HTMLInputElement>): Promise<void> {
    const input = e.currentTarget;
    const file = input.files?.[0];
    if (!file) return;
    setUploadingId(matchId);
    setError(null);
    try {
      await uploadMatchVideo(matchId, file);
      setUploaded((prev) => ({ ...prev, [matchId]: file.name }));
      setNotice(`Uploaded ${file.name}. Ready to process.`);
      await refresh(true);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setUploadingId(null);
      input.value = "";
    }
  }

  async function onProcess(matchId: string): Promise<void> {
    setProcessingId(matchId);
    setError(null);
    try {
      const res = await processMatch(matchId);
      setNotice(`Analysis job ${res.job_id} queued.`);
      await refresh(true);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setProcessingId(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-white">Matches</h1>
        <button type="button" className="btn btn-ghost" onClick={() => void refresh()}>
          Refresh
        </button>
      </div>

      {error ? <p className="error-box">{error}</p> : null}
      {notice ? <p className="notice-box">{notice}</p> : null}

      <div className="grid gap-6 lg:grid-cols-[320px,1fr]">
        <section className="space-y-4">
          <form className="card space-y-3" onSubmit={(e) => void onCreateMatch(e)}>
            <h2 className="text-sm font-semibold text-white">New match</h2>
            <div>
              <label className="label" htmlFor="match-team">
                Team
              </label>
              <select
                id="match-team"
                className="input"
                value={teamId}
                onChange={(e) => setTeamId(e.target.value)}
              >
                <option value="">No team</option>
                {teams.map((team) => (
                  <option key={team.id} value={team.id}>
                    {team.name} ({team.sport})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="match-opponent">
                Opponent
              </label>
              <input
                id="match-opponent"
                type="text"
                className="input"
                value={opponent}
                onChange={(e) => setOpponent(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="label" htmlFor="match-sport">
                Sport
              </label>
              <input
                id="match-sport"
                type="text"
                className="input"
                list="sport-suggestions"
                value={sport}
                onChange={(e) => setSport(e.target.value)}
                required
              />
              <datalist id="sport-suggestions">
                {SPORT_SUGGESTIONS.map((s) => (
                  <option key={s} value={s} />
                ))}
              </datalist>
            </div>
            <div>
              <label className="label" htmlFor="match-kickoff">
                Kickoff (optional)
              </label>
              <input
                id="match-kickoff"
                type="datetime-local"
                className="input"
                value={kickoff}
                onChange={(e) => setKickoff(e.target.value)}
              />
            </div>
            <div>
              <label className="label" htmlFor="match-venue">
                Venue (optional)
              </label>
              <input
                id="match-venue"
                type="text"
                className="input"
                value={venue}
                onChange={(e) => setVenue(e.target.value)}
              />
            </div>
            <button
              type="submit"
              className="btn btn-primary w-full"
              disabled={creating || !opponent.trim() || !sport.trim()}
            >
              {creating ? "Creating…" : "Create match"}
            </button>
          </form>

          <details className="card">
            <summary className="cursor-pointer text-sm font-semibold text-white">New team</summary>
            <form className="mt-3 space-y-3" onSubmit={(e) => void onCreateTeam(e)}>
              <div>
                <label className="label" htmlFor="team-name">
                  Team name
                </label>
                <input
                  id="team-name"
                  type="text"
                  className="input"
                  value={teamName}
                  onChange={(e) => setTeamName(e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="label" htmlFor="team-sport">
                  Sport
                </label>
                <input
                  id="team-sport"
                  type="text"
                  className="input"
                  list="sport-suggestions"
                  value={teamSport}
                  onChange={(e) => setTeamSport(e.target.value)}
                  required
                />
              </div>
              <button
                type="submit"
                className="btn btn-secondary w-full"
                disabled={creatingTeam || !teamName.trim() || !teamSport.trim()}
              >
                {creatingTeam ? "Creating…" : "Create team"}
              </button>
            </form>
          </details>
        </section>

        <section>
          {loading ? (
            <Loading label="Loading matches…" />
          ) : matches.length === 0 ? (
            <div className="card text-sm text-slate-400">
              No matches yet. Create your first match, upload a video and process it.
            </div>
          ) : (
            <div className="card overflow-x-auto p-0">
              <table className="w-full min-w-[760px] border-collapse">
                <thead>
                  <tr>
                    <th className="table-th">Match</th>
                    <th className="table-th">Sport</th>
                    <th className="table-th">Kickoff</th>
                    <th className="table-th">Status</th>
                    <th className="table-th">Video</th>
                    <th className="table-th">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {matches.map((match) => (
                    <tr key={match.id} className="border-t border-slate-800/70 hover:bg-slate-900/40">
                      <td className="table-td">
                        <Link
                          href={`/matches/${match.id}`}
                          className="font-medium text-sky-400 hover:underline"
                        >
                          vs {match.opponent}
                        </Link>
                        <div className="text-xs text-slate-500">{fmtDate(match.created_at)}</div>
                      </td>
                      <td className="table-td capitalize">{match.sport}</td>
                      <td className="table-td text-slate-400">
                        {match.kickoff_at ? fmtDate(match.kickoff_at) : "—"}
                      </td>
                      <td className="table-td">
                        <JobBadge status={match.status} />
                      </td>
                      <td className="table-td text-xs text-slate-400">{uploaded[match.id] ?? "—"}</td>
                      <td className="table-td">
                        <div className="flex flex-wrap items-center gap-2">
                          <label
                            className={`btn btn-secondary cursor-pointer ${
                              uploadingId !== null ? "pointer-events-none opacity-50" : ""
                            }`}
                          >
                            {uploadingId === match.id ? "Uploading…" : "Upload video"}
                            <input
                              type="file"
                              accept="video/*"
                              className="hidden"
                              disabled={uploadingId !== null}
                              onChange={(e) => void handleUpload(match.id, e)}
                            />
                          </label>
                          <button
                            type="button"
                            className="btn btn-primary"
                            disabled={processingId !== null || match.status === "processing"}
                            onClick={() => void onProcess(match.id)}
                          >
                            {processingId === match.id ? "Starting…" : "Process"}
                          </button>
                          <Link href={`/matches/${match.id}`} className="btn btn-ghost">
                            Open
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
