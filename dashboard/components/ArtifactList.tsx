"use client";

import { useState } from "react";

import { saveArtifact } from "@/lib/api";
import type { ArtifactRef } from "@/lib/types";
import { errorMessage, fmtBytes, fmtDate } from "@/lib/format";

interface ArtifactListProps {
  artifacts: ArtifactRef[];
  emptyLabel?: string;
}

/** Table of artifacts with authenticated download buttons. */
export default function ArtifactList({ artifacts, emptyLabel = "No artifacts yet." }: ArtifactListProps) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onDownload(artifact: ArtifactRef): Promise<void> {
    setBusyId(artifact.id);
    setError(null);
    try {
      await saveArtifact(artifact);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  }

  if (artifacts.length === 0) {
    return <p className="text-sm text-slate-500">{emptyLabel}</p>;
  }

  return (
    <div className="space-y-2">
      {error ? <p className="error-box">{error}</p> : null}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] border-collapse">
          <thead>
            <tr className="border-b border-slate-800">
              <th className="table-th">Kind</th>
              <th className="table-th">Filename</th>
              <th className="table-th">Size</th>
              <th className="table-th">Created</th>
              <th className="table-th" />
            </tr>
          </thead>
          <tbody>
            {artifacts.map((artifact) => (
              <tr key={artifact.id} className="border-b border-slate-800/60">
                <td className="table-td">
                  <span className="rounded bg-slate-800 px-1.5 py-0.5 text-xs text-slate-300">
                    {artifact.kind}
                  </span>
                </td>
                <td className="table-td break-all">{artifact.filename}</td>
                <td className="table-td text-slate-400">{fmtBytes(artifact.size_bytes)}</td>
                <td className="table-td text-slate-400">{fmtDate(artifact.created_at)}</td>
                <td className="table-td">
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => void onDownload(artifact)}
                    disabled={busyId !== null}
                  >
                    {busyId === artifact.id ? "Downloading…" : "Download"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
