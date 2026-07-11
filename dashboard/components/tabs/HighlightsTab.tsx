"use client";

import { useCallback, useEffect, useState } from "react";

import JobBadge from "@/components/JobBadge";
import Loading from "@/components/Loading";
import ProgressBar from "@/components/ProgressBar";
import VideoPlayer from "@/components/VideoPlayer";
import { getJob, getMatchStats, listArtifacts, requestHighlights, saveArtifact } from "@/lib/api";
import type { ArtifactRef, Job, PlayerStat } from "@/lib/types";
import { errorMessage, fmtBytes, fmtDate, shortId } from "@/lib/format";

interface HighlightsTabProps {
  matchId: string;
}

const TERMINAL_STATUSES = new Set(["succeeded", "failed", "cancelled"]);

/** Highlights tab: generate per-player reels and preview/download the results. */
export default function HighlightsTab({ matchId }: HighlightsTabProps) {
  const [artifacts, setArtifacts] = useState<ArtifactRef[]>([]);
  const [stats, setStats] = useState<PlayerStat[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [identitySel, setIdentitySel] = useState("");
  const [trackInput, setTrackInput] = useState("");
  const [generating, setGenerating] = useState(false);
  const [activeJob, setActiveJob] = useState<Job | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const [arts, st] = await Promise.allSettled([
      listArtifacts({ match_id: matchId, kind: "player_highlights" }),
      getMatchStats(matchId),
    ]);
    if (arts.status === "fulfilled") {
      setArtifacts(arts.value);
      setError(null);
    } else {
      setArtifacts([]);
      setError(errorMessage(arts.reason));
    }
    setStats(st.status === "fulfilled" ? st.value : []);
    setLoading(false);
  }, [matchId]);

  useEffect(() => {
    void load();
  }, [load]);

  // Poll the active highlights job every 2s until it reaches a terminal state.
  useEffect(() => {
    if (!activeJob || TERMINAL_STATUSES.has(activeJob.status)) return;
    const timer = setInterval(() => {
      getJob(activeJob.id)
        .then((job) => {
          setActiveJob(job);
          if (job.status === "succeeded") {
            setNotice("Highlights ready.");
            void load();
          } else if (job.status === "failed") {
            setError(job.error ?? "Highlights job failed.");
          }
        })
        .catch((err: unknown) => setError(errorMessage(err)));
    }, 2000);
    return () => clearInterval(timer);
  }, [activeJob, load]);

  async function onGenerate(e: React.FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    const body: { player_identity_id?: string; track_id?: number } = {};
    if (identitySel) {
      body.player_identity_id = identitySel;
    } else if (trackInput.trim() !== "") {
      const track = Number(trackInput);
      if (!Number.isInteger(track) || track < 0) {
        setError("Track id must be a non-negative integer.");
        return;
      }
      body.track_id = track;
    } else {
      setError("Choose a player identity or enter a track id.");
      return;
    }
    setGenerating(true);
    setError(null);
    setNotice(null);
    try {
      const res = await requestHighlights(matchId, body);
      const job = await getJob(res.job_id).catch(() => null);
      setActiveJob(
        job ?? {
          id: res.job_id,
          kind: "highlights",
          status: "queued",
          progress: 0,
          error: null,
          created_at: new Date().toISOString(),
          started_at: null,
          finished_at: null,
        },
      );
      setNotice(`Highlights job ${res.job_id} queued.`);
      await load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setGenerating(false);
    }
  }

  if (loading) return <Loading label="Loading highlights…" />;

  return (
    <div className="space-y-4">
      {error ? <p className="error-box">{error}</p> : null}
      {notice ? <p className="notice-box">{notice}</p> : null}

      <section className="card space-y-3">
        <h2 className="text-sm font-semibold text-white">Generate player highlights</h2>
        <form className="flex flex-wrap items-end gap-3" onSubmit={(e) => void onGenerate(e)}>
          <div>
            <label className="label" htmlFor="hl-identity">
              Player identity
            </label>
            <select
              id="hl-identity"
              className="input w-56"
              value={identitySel}
              onChange={(e) => setIdentitySel(e.target.value)}
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
          <div>
            <label className="label" htmlFor="hl-track">
              or track id
            </label>
            <input
              id="hl-track"
              type="number"
              min={0}
              className="input w-28"
              value={trackInput}
              onChange={(e) => setTrackInput(e.target.value)}
              disabled={identitySel !== ""}
              placeholder="e.g. 3"
            />
          </div>
          <button type="submit" className="btn btn-primary" disabled={generating}>
            {generating ? "Queueing…" : "Generate highlights"}
          </button>
        </form>

        {activeJob ? (
          <div className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-800 bg-slate-950/60 p-3">
            <JobBadge status={activeJob.status} />
            <span className="text-xs text-slate-400">Job {shortId(activeJob.id)}</span>
            <ProgressBar value={activeJob.progress ?? 0} className="w-40" />
            <span className="text-xs text-slate-400">
              {Math.round((activeJob.progress ?? 0) * 100)}%
            </span>
          </div>
        ) : null}
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">Highlight reels</h2>
          <button type="button" className="btn btn-ghost" onClick={() => void load()}>
            Refresh
          </button>
        </div>
        {artifacts.length === 0 ? (
          <div className="card text-sm text-slate-400">No highlight reels yet.</div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {artifacts.map((artifact) => (
              <article key={artifact.id} className="card space-y-3">
                <header className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <h3 className="break-all text-sm font-medium text-white">{artifact.filename}</h3>
                    <p className="text-xs text-slate-500">
                      {fmtDate(artifact.created_at)} · {fmtBytes(artifact.size_bytes)}
                    </p>
                  </div>
                  <button
                    type="button"
                    className="btn btn-secondary shrink-0"
                    onClick={() =>
                      void saveArtifact(artifact).catch((err: unknown) => setError(errorMessage(err)))
                    }
                  >
                    Download
                  </button>
                </header>
                <VideoPlayer artifactId={artifact.id} />
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
