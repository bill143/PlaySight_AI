"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import ArtifactList from "@/components/ArtifactList";
import JobBadge from "@/components/JobBadge";
import Loading from "@/components/Loading";
import ProgressBar from "@/components/ProgressBar";
import {
  getUploadRecord,
  listArtifacts,
  listJobs,
  processMatch,
  publishYouTube,
  requestAnnotate,
  requestAudioExport,
  requestHighlights,
} from "@/lib/api";
import type { ArtifactRef, Job, Privacy, UploadRecord } from "@/lib/types";
import { errorMessage, fmtBytes, fmtDate } from "@/lib/format";

interface ExportPublishTabProps {
  matchId: string;
}

const PUBLISHABLE_KINDS = new Set(["annotated_video", "player_highlights", "match_audio"]);
const ACTIVE_JOB_STATUSES = new Set(["queued", "running"]);
const ACTIVE_UPLOAD_STATUSES = new Set(["pending", "uploading"]);

/**
 * Export & Publish tab: job table with 2s live polling, retry, annotated video +
 * audio export triggers, and the YouTube publish form (rights confirmation required).
 */
export default function ExportPublishTab({ matchId }: ExportPublishTabProps) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [artifacts, setArtifacts] = useState<ArtifactRef[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);

  // publish form
  const [artifactId, setArtifactId] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("");
  const [privacy, setPrivacy] = useState<Privacy>("private");
  const [confirmRights, setConfirmRights] = useState(false);
  const [publishing, setPublishing] = useState(false);

  // upload records created in this session
  const [uploadIds, setUploadIds] = useState<string[]>([]);
  const [uploads, setUploads] = useState<Record<string, UploadRecord>>({});

  const refreshJobs = useCallback(async () => {
    const all = await listJobs();
    setJobs(
      all
        .filter((job) => !job.match_id || job.match_id === matchId)
        .sort((a, b) => (a.created_at < b.created_at ? 1 : -1)),
    );
  }, [matchId]);

  const refreshArtifacts = useCallback(async () => {
    setArtifacts(await listArtifacts({ match_id: matchId }));
  }, [matchId]);

  const refreshAll = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true);
      try {
        await Promise.all([refreshJobs(), refreshArtifacts()]);
        setError(null);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    },
    [refreshJobs, refreshArtifacts],
  );

  useEffect(() => {
    void refreshAll();
  }, [refreshAll]);

  // Poll every 2 seconds while any job is queued/running.
  const anyJobActive = jobs.some((job) => ACTIVE_JOB_STATUSES.has(job.status));
  useEffect(() => {
    if (!anyJobActive) return;
    const timer = setInterval(() => {
      void refreshAll(true);
    }, 2000);
    return () => clearInterval(timer);
  }, [anyJobActive, refreshAll]);

  const refreshUploads = useCallback(async () => {
    const entries = await Promise.all(
      uploadIds.map(async (id) => [id, await getUploadRecord(id)] as const),
    );
    setUploads(Object.fromEntries(entries));
  }, [uploadIds]);

  useEffect(() => {
    if (uploadIds.length === 0) return;
    refreshUploads().catch((err: unknown) => setError(errorMessage(err)));
  }, [uploadIds, refreshUploads]);

  const anyUploadActive = Object.values(uploads).some((u) => ACTIVE_UPLOAD_STATUSES.has(u.status));
  useEffect(() => {
    if (!anyUploadActive) return;
    const timer = setInterval(() => {
      refreshUploads().catch(() => undefined);
    }, 3000);
    return () => clearInterval(timer);
  }, [anyUploadActive, refreshUploads]);

  const publishOptions = useMemo(
    () =>
      artifacts.filter(
        (a) =>
          PUBLISHABLE_KINDS.has(a.kind) ||
          a.content_type.startsWith("video/") ||
          a.content_type.startsWith("audio/"),
      ),
    [artifacts],
  );

  async function triggerExport(kind: "annotate" | "export_audio"): Promise<void> {
    setBusyAction(kind);
    setError(null);
    try {
      const res =
        kind === "annotate" ? await requestAnnotate(matchId) : await requestAudioExport(matchId);
      setNotice(`Job ${res.job_id} queued.`);
      await refreshAll(true);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyAction(null);
    }
  }

  async function retryJob(job: Job): Promise<void> {
    setBusyAction(`retry:${job.id}`);
    setError(null);
    try {
      if (job.kind === "analyze") {
        await processMatch(matchId);
      } else if (job.kind === "annotate") {
        await requestAnnotate(matchId);
      } else if (job.kind === "export_audio") {
        await requestAudioExport(matchId);
      } else if (job.kind === "highlights") {
        const params = job.params_json ?? {};
        const identity =
          typeof params.player_identity_id === "string" ? params.player_identity_id : null;
        const track = typeof params.track_id === "number" ? params.track_id : null;
        if (identity) {
          await requestHighlights(matchId, { player_identity_id: identity });
        } else if (track !== null) {
          await requestHighlights(matchId, { track_id: track });
        } else {
          setNotice("Original highlights parameters unavailable — regenerate from the Highlights tab.");
          return;
        }
      } else {
        setNotice("Publish retries go through the publish form below (idempotent per key).");
        return;
      }
      setNotice(`Retried ${job.kind} job.`);
      await refreshAll(true);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyAction(null);
    }
  }

  async function onPublish(e: React.FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    if (!confirmRights) {
      setError("You must confirm you hold the rights to publish this content.");
      return;
    }
    setPublishing(true);
    setError(null);
    try {
      const res = await publishYouTube({
        artifact_id: artifactId,
        title: title.trim(),
        description: description.trim() || undefined,
        tags: tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
        privacy,
        confirm_rights: true,
      });
      setUploadIds((prev) => (prev.includes(res.upload_id) ? prev : [...prev, res.upload_id]));
      setNotice(`Publish requested — upload ${res.upload_id}, job ${res.job_id}.`);
      setConfirmRights(false);
      await refreshAll(true);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPublishing(false);
    }
  }

  return (
    <div className="space-y-4">
      {error ? <p className="error-box">{error}</p> : null}
      {notice ? <p className="notice-box">{notice}</p> : null}

      <section className="card">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-white">Jobs</h2>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="btn btn-secondary"
              disabled={busyAction !== null}
              onClick={() => void triggerExport("annotate")}
            >
              {busyAction === "annotate" ? "Queueing…" : "Render annotated video"}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={busyAction !== null}
              onClick={() => void triggerExport("export_audio")}
            >
              {busyAction === "export_audio" ? "Queueing…" : "Export audio summary"}
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => void refreshAll(true)}>
              Refresh
            </button>
          </div>
        </div>

        {loading ? (
          <Loading label="Loading jobs…" />
        ) : jobs.length === 0 ? (
          <p className="text-sm text-slate-500">No jobs yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] border-collapse">
              <thead>
                <tr className="border-b border-slate-800">
                  <th className="table-th">Kind</th>
                  <th className="table-th">Status</th>
                  <th className="table-th">Progress</th>
                  <th className="table-th">Created</th>
                  <th className="table-th">Finished</th>
                  <th className="table-th" />
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id} className="border-b border-slate-800/60 align-top">
                    <td className="table-td font-medium">{job.kind}</td>
                    <td className="table-td">
                      <JobBadge status={job.status} />
                      {job.error ? (
                        <details className="mt-1">
                          <summary className="cursor-pointer text-xs text-rose-300">
                            Error log
                          </summary>
                          <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-slate-950 p-2 text-xs text-rose-200">
                            {job.error}
                          </pre>
                        </details>
                      ) : null}
                    </td>
                    <td className="table-td">
                      <div className="flex items-center gap-2">
                        <ProgressBar value={job.progress ?? 0} className="w-32" />
                        <span className="text-xs text-slate-400">
                          {Math.round((job.progress ?? 0) * 100)}%
                        </span>
                      </div>
                    </td>
                    <td className="table-td text-slate-400">{fmtDate(job.created_at)}</td>
                    <td className="table-td text-slate-400">{fmtDate(job.finished_at)}</td>
                    <td className="table-td">
                      {job.status === "failed" ? (
                        <button
                          type="button"
                          className="btn btn-secondary"
                          disabled={busyAction !== null}
                          onClick={() => void retryJob(job)}
                        >
                          {busyAction === `retry:${job.id}` ? "Retrying…" : "Retry"}
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card space-y-3">
        <h2 className="text-sm font-semibold text-white">Publish to YouTube</h2>
        <form className="grid gap-3 md:grid-cols-2" onSubmit={(e) => void onPublish(e)}>
          <div className="md:col-span-2">
            <label className="label" htmlFor="pub-artifact">
              Artifact
            </label>
            <select
              id="pub-artifact"
              className="input"
              value={artifactId}
              onChange={(e) => setArtifactId(e.target.value)}
              required
            >
              <option value="">Select an artifact…</option>
              {publishOptions.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.kind} — {a.filename} ({fmtBytes(a.size_bytes)})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="pub-title">
              Title
            </label>
            <input
              id="pub-title"
              type="text"
              className="input"
              maxLength={100}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="label" htmlFor="pub-privacy">
              Privacy
            </label>
            <select
              id="pub-privacy"
              className="input"
              value={privacy}
              onChange={(e) => setPrivacy(e.target.value as Privacy)}
            >
              <option value="private">private</option>
              <option value="unlisted">unlisted</option>
              <option value="public">public</option>
            </select>
          </div>
          <div className="md:col-span-2">
            <label className="label" htmlFor="pub-description">
              Description
            </label>
            <textarea
              id="pub-description"
              className="input"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="md:col-span-2">
            <label className="label" htmlFor="pub-tags">
              Tags
            </label>
            <input
              id="pub-tags"
              type="text"
              className="input"
              placeholder="comma,separated,tags"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
            />
          </div>
          <label className="flex items-start gap-2 text-sm text-slate-300 md:col-span-2">
            <input
              type="checkbox"
              className="mt-1 h-4 w-4 rounded border-slate-600 bg-slate-900"
              checked={confirmRights}
              onChange={(e) => setConfirmRights(e.target.checked)}
              required
            />
            <span>
              I confirm that I own or hold the rights to publish this content and that publishing
              complies with league and club policies.{" "}
              <span className="text-slate-500">(required — sent as confirm_rights)</span>
            </span>
          </label>
          <div className="md:col-span-2">
            <button
              type="submit"
              className="btn btn-primary"
              disabled={publishing || !artifactId || !title.trim() || !confirmRights}
            >
              {publishing ? "Publishing…" : "Publish"}
            </button>
          </div>
        </form>
      </section>

      {uploadIds.length > 0 ? (
        <section className="card space-y-3">
          <h2 className="text-sm font-semibold text-white">Upload records</h2>
          {uploadIds.map((id) => {
            const record = uploads[id];
            if (!record) {
              return (
                <p key={id} className="text-sm text-slate-500">
                  Loading upload {id}…
                </p>
              );
            }
            return (
              <div key={id} className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                <div className="flex flex-wrap items-center gap-3">
                  <JobBadge status={record.status} />
                  <span className="text-sm font-medium text-white">{record.title}</span>
                  <span className="text-xs text-slate-500">
                    {record.platform} · {record.privacy} · attempts {record.attempts}
                  </span>
                </div>
                {record.url ? (
                  <a
                    className="mt-1 inline-block break-all text-sm text-sky-400 hover:underline"
                    href={record.url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {record.url}
                  </a>
                ) : null}
                {record.error_log_json && record.error_log_json.length > 0 ? (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-xs text-rose-300">
                      Error log ({record.error_log_json.length})
                    </summary>
                    <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-slate-950 p-2 text-xs text-rose-200">
                      {JSON.stringify(record.error_log_json, null, 2)}
                    </pre>
                  </details>
                ) : null}
              </div>
            );
          })}
        </section>
      ) : null}

      <section className="card space-y-3">
        <h2 className="text-sm font-semibold text-white">All artifacts</h2>
        <ArtifactList artifacts={artifacts} emptyLabel="No artifacts yet — run processing first." />
      </section>
    </div>
  );
}
