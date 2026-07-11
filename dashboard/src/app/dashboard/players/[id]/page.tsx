"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import {
  getArtifactDownload,
  getPlayerHighlights,
  getPlayerReport
} from "@/lib/api";
import type { Artifact, PlayerHighlight, PlayerReport } from "@/types";

export default function PlayerReportPage() {
  const params = useParams<{ id: string }>();
  const playerId = Array.isArray(params.id) ? params.id[0] : params.id;
  const [report, setReport] = useState<PlayerReport | null>(null);
  const [highlights, setHighlights] = useState<PlayerHighlight | null>(null);
  const [artifact, setArtifact] = useState<Artifact | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!playerId) {
      return;
    }

    const load = async () => {
      try {
        const [reportResponse, highlightsResponse] = await Promise.all([
          getPlayerReport(playerId),
          getPlayerHighlights(playerId)
        ]);
        setReport(reportResponse);
        setHighlights(highlightsResponse);

        if (!highlightsResponse.download_url && highlightsResponse.artifact_id) {
          try {
            const artifactResponse = await getArtifactDownload(
              highlightsResponse.artifact_id
            );
            setArtifact(artifactResponse);
          } catch {
            setArtifact(null);
          }
        }
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Unable to load player report.");
      }
    };

    void load();
  }, [playerId]);

  const heatmapEntries = useMemo(
    () => Object.entries(report?.stats.heatmap_zones ?? {}),
    [report]
  );

  if (error) {
    return (
      <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-6 text-rose-200">
        {error}
      </div>
    );
  }

  if (!report || !highlights) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Spinner className="h-10 w-10 text-primary-500" />
      </div>
    );
  }

  const highlightUrl = highlights.download_url || artifact?.download_url || "#";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Player Report</h1>
        <p className="mt-2 text-sm text-slate-400">
          Player {report.player_id} • Match {report.match_id} • Generated{" "}
          {new Date(report.generated_at).toLocaleString()}
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Distance Covered" value={`${report.stats.distance_covered_m} m`} />
        <StatCard label="Top Speed" value={`${report.stats.top_speed_kmh} km/h`} />
        <StatCard label="Possessions" value={String(report.stats.possessions)} />
        <StatCard label="Time on Ball" value={`${report.stats.time_on_ball_seconds}s`} />
        <StatCard label="Passes" value={String(report.stats.passes)} />
        <StatCard label="Shots" value={String(report.stats.shots)} />
        <StatCard label="Goals" value={String(report.stats.goals)} />
        <StatCard label="Highlights" value={`${highlights.clip_count} clips`} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
        <Card className="border-slate-800 bg-slate-900/80">
          <CardHeader>
            <CardTitle>Heatmap Zones</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {heatmapEntries.map(([zone, value]) => (
              <div key={zone} className="space-y-2 rounded-xl border border-slate-800 bg-slate-950/60 p-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium capitalize text-slate-200">
                    {zone.replaceAll("_", " ")}
                  </span>
                  <span className="text-slate-400">{value}</span>
                </div>
                <div className="h-2 rounded-full bg-slate-800">
                  <div
                    className="h-2 rounded-full bg-secondary-500"
                    style={{ width: `${Math.min(100, Number(value) * 10)}%` }}
                  />
                </div>
              </div>
            ))}
            {heatmapEntries.length === 0 ? (
              <p className="text-sm text-slate-400">No heatmap data available.</p>
            ) : null}
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-slate-900/80">
          <CardHeader>
            <CardTitle>Highlights Package</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-sm text-slate-300">
              <p>Artifact ID: {highlights.artifact_id}</p>
              <p className="mt-2">Clips detected: {highlights.clip_count}</p>
            </div>
            {highlightUrl === "#" ? (
              <Button className="w-full" disabled>
                Download Highlights
              </Button>
            ) : (
              <Button
                className="w-full"
                onClick={() => window.open(highlightUrl, "_blank", "noopener,noreferrer")}
              >
                Download Highlights
              </Button>
            )}
            {report.extra ? (
              <pre className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-xs text-slate-400">
                {JSON.stringify(report.extra, null, 2)}
              </pre>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <Card className="border-slate-800 bg-slate-900/80">
      <CardContent className="pt-6">
        <p className="text-sm text-slate-400">{label}</p>
        <p className="mt-3 text-2xl font-semibold text-slate-100">{value}</p>
      </CardContent>
    </Card>
  );
}
