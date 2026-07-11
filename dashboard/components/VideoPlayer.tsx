"use client";

import { useCallback, useEffect, useState } from "react";

import { downloadArtifactBlob } from "@/lib/api";
import { errorMessage } from "@/lib/format";

interface VideoPlayerProps {
  /** Artifact id served by `GET /artifacts/{id}/download`. */
  artifactId: string;
  /** Fetch the video immediately instead of waiting for the user. */
  autoLoad?: boolean;
}

/**
 * HTML5 video preview for an artifact. The file is fetched with the bearer
 * token into an object URL (plain `<video src>` cannot send auth headers).
 */
export default function VideoPlayer({ artifactId, autoLoad = false }: VideoPlayerProps) {
  const [src, setSrc] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const blob = await downloadArtifactBlob(artifactId);
      setSrc(URL.createObjectURL(blob));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [artifactId]);

  useEffect(() => {
    if (autoLoad) void load();
  }, [autoLoad, load]);

  // Revoke stale object URLs on change and on unmount.
  useEffect(() => {
    return () => {
      if (src) URL.revokeObjectURL(src);
    };
  }, [src]);

  if (src) {
    return (
      <video
        controls
        preload="metadata"
        className="aspect-video w-full rounded-lg border border-slate-800 bg-black"
        src={src}
      />
    );
  }

  return (
    <div className="flex aspect-video w-full flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-slate-700 bg-slate-950/60 p-4">
      {error ? <p className="text-center text-xs text-rose-300">{error}</p> : null}
      <button type="button" className="btn btn-secondary" onClick={() => void load()} disabled={loading}>
        {loading ? "Loading preview…" : "Load preview"}
      </button>
    </div>
  );
}
