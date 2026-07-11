"use client";

import { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { healthCheck, listMatches } from "@/lib/api";
import type { Match } from "@/types";

interface DashboardSummary {
  matches: Match[];
  backendHealthy: boolean;
}

export default function DashboardOverviewPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [matches, health] = await Promise.all([
          listMatches(),
          healthCheck().catch(() => ({ status: "down" }))
        ]);
        setSummary({ matches, backendHealthy: health.status === "ok" });
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Unable to load dashboard.");
      }
    };

    void load();
  }, []);

  const metrics = useMemo(() => {
    const matches = summary?.matches ?? [];
    return {
      totalMatches: matches.length,
      processingJobs: matches.filter((match) =>
        ["queued", "pending", "processing", "running"].includes(match.status)
      ).length,
      completedReports: matches.filter((match) =>
        ["completed", "published"].includes(match.status)
      ).length,
      upcomingMatches: matches.filter(
        (match) => new Date(match.match_date).getTime() > Date.now()
      ).length
    };
  }, [summary]);

  if (error) {
    return (
      <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-6 text-rose-200">
        {error}
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Spinner className="h-10 w-10 text-primary-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Operations Dashboard</h1>
        <p className="mt-2 text-sm text-slate-400">
          Monitor ingestion throughput, analytics readiness, and publishing
          health across your sports video pipeline.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {[
          { label: "Total Matches", value: metrics.totalMatches },
          { label: "Processing Jobs", value: metrics.processingJobs },
          { label: "Completed Reports", value: metrics.completedReports },
          { label: "Upcoming Matches", value: metrics.upcomingMatches }
        ].map((metric) => (
          <Card key={metric.label} className="border-slate-800 bg-slate-900/80">
            <CardContent className="pt-6">
              <p className="text-sm text-slate-400">{metric.label}</p>
              <p className="mt-3 text-3xl font-semibold">{metric.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <Card className="border-slate-800 bg-slate-900/80">
          <CardHeader>
            <CardTitle>Recent Matches</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {summary.matches.slice(0, 5).map((match) => (
              <div
                key={match.id}
                className="flex flex-col gap-3 rounded-xl border border-slate-800 bg-slate-950/60 p-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <p className="font-medium">{match.title}</p>
                  <p className="text-sm text-slate-400">
                    {match.home_team} vs {match.away_team}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <Badge variant={getStatusVariant(match.status)}>{match.status}</Badge>
                  <span className="text-sm text-slate-400">
                    {new Date(match.match_date).toLocaleDateString()}
                  </span>
                </div>
              </div>
            ))}
            {summary.matches.length === 0 ? (
              <p className="text-sm text-slate-400">
                No matches available yet. Upload the first match from the Matches
                tab.
              </p>
            ) : null}
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-slate-900/80">
          <CardHeader>
            <CardTitle>Platform Health</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 p-4">
              <span className="text-sm text-slate-300">API Availability</span>
              <Badge variant={summary.backendHealthy ? "success" : "error"}>
                {summary.backendHealthy ? "Healthy" : "Unavailable"}
              </Badge>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-sm text-slate-400">
              Use this dashboard to keep ingestion workflows moving, inspect
              analytics coverage, and publish highlights once artifacts are ready.
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function getStatusVariant(status: string) {
  const normalized = status.toLowerCase();
  if (["completed", "published", "success"].includes(normalized)) {
    return "success" as const;
  }
  if (["processing", "queued", "pending", "running"].includes(normalized)) {
    return "warning" as const;
  }
  if (["failed", "error"].includes(normalized)) {
    return "error" as const;
  }
  return "neutral" as const;
}
