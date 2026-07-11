"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { EventTimeline } from "@/components/match/EventTimeline";
import { PlayerCard } from "@/components/match/PlayerCard";
import { Badge } from "@/components/ui/Badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { getJobStatus, getMatch } from "@/lib/api";
import type { Match, MatchEvent, Player, ProcessingJob } from "@/types";

export default function MatchDetailPage() {
  const params = useParams<{ id: string }>();
  const matchId = Array.isArray(params.id) ? params.id[0] : params.id;
  const [match, setMatch] = useState<Match | null>(null);
  const [job, setJob] = useState<ProcessingJob | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) {
      return;
    }

    const loadMatch = async () => {
      try {
        const fetchedMatch = await getMatch(matchId);
        setMatch(fetchedMatch);

        if (!fetchedMatch.job_id) {
          setJob(buildSyntheticJob(fetchedMatch));
          return;
        }

        const poll = async () => {
          try {
            const nextJob = await getJobStatus(fetchedMatch.job_id as string);
            setJob(nextJob);
          } catch {
            setJob(buildSyntheticJob(fetchedMatch));
          }
        };

        await poll();
        const intervalId = window.setInterval(() => {
          void poll();
        }, 5000);

        return () => window.clearInterval(intervalId);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Unable to load match.");
      }
    };

    let cleanup: (() => void) | undefined;
    void loadMatch().then((dispose) => {
      cleanup = dispose;
    });

    return () => {
      cleanup?.();
    };
  }, [matchId]);

  const events = useMemo<MatchEvent[]>(() => buildMockEvents(matchId), [matchId]);
  const players = useMemo<Player[]>(() => buildMockPlayers(matchId), [matchId]);

  if (error) {
    return (
      <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-6 text-rose-200">
        {error}
      </div>
    );
  }

  if (!match) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Spinner className="h-10 w-10 text-primary-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-3xl font-semibold">{match.title}</h1>
          <p className="mt-2 text-sm text-slate-400">
            {match.home_team} vs {match.away_team} •{" "}
            {new Date(match.match_date).toLocaleString()}
          </p>
        </div>
        <Badge variant={getStatusVariant(match.status)}>{match.status}</Badge>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        <Card className="border-slate-800 bg-slate-900/80">
          <CardHeader>
            <CardTitle>Match Overview</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <InfoRow label="Sport" value={match.sport} />
            <InfoRow label="Home Team" value={match.home_team} />
            <InfoRow label="Away Team" value={match.away_team} />
            <InfoRow label="Match ID" value={match.id} />
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-slate-900/80">
          <CardHeader>
            <CardTitle>Processing Job</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {job ? (
              <>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-400">Status</span>
                  <Badge variant={getStatusVariant(job.status)}>{job.status}</Badge>
                </div>
                <div>
                  <div className="mb-2 flex items-center justify-between text-sm text-slate-400">
                    <span>Progress</span>
                    <span>{job.progress}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-slate-800">
                    <div
                      className="h-2 rounded-full bg-primary-500"
                      style={{ width: `${Math.max(4, job.progress)}%` }}
                    />
                  </div>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-sm text-slate-300">
                  Current stage: {job.current_stage || "Awaiting updates"}
                  {job.error_message ? (
                    <div className="mt-2 text-rose-300">{job.error_message}</div>
                  ) : null}
                </div>
              </>
            ) : (
              <p className="text-sm text-slate-400">No job information available.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        <Card className="border-slate-800 bg-slate-900/80">
          <CardHeader>
            <CardTitle>Detected Match Events</CardTitle>
          </CardHeader>
          <CardContent>
            <EventTimeline events={events} />
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-slate-900/80">
          <CardHeader>
            <CardTitle>Featured Players</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {players.map((player) => (
              <PlayerCard key={player.id} player={player} />
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-2 font-medium text-slate-100">{value}</p>
    </div>
  );
}

function buildSyntheticJob(match: Match): ProcessingJob {
  const normalized = match.status.toLowerCase();
  const progress =
    normalized === "completed" || normalized === "published"
      ? 100
      : normalized === "processing"
        ? 64
        : normalized === "failed"
          ? 100
          : 12;

  return {
    id: match.job_id ?? `${match.id}-job`,
    match_id: match.id,
    status: normalized,
    progress,
    current_stage:
      normalized === "completed"
        ? "Analytics ready"
        : normalized === "processing"
          ? "Tracking player movement"
          : normalized === "failed"
            ? "Pipeline failed"
            : "Queued for ingestion",
    error_message: normalized === "failed" ? "Job needs retry from ingestion." : null
  };
}

function buildMockEvents(matchId: string): MatchEvent[] {
  return [
    {
      id: `${matchId}-e1`,
      type: "Kickoff",
      timestamp: "00:00",
      confidence: 0.99,
      description: "Match started and tracking initialized."
    },
    {
      id: `${matchId}-e2`,
      type: "Shot",
      timestamp: "12:14",
      confidence: 0.93,
      description: "Attacking sequence ended with a shot on target."
    },
    {
      id: `${matchId}-e3`,
      type: "Possession Swing",
      timestamp: "36:40",
      confidence: 0.9,
      description: "Midfield transition detected by the possession model."
    },
    {
      id: `${matchId}-e4`,
      type: "Goal",
      timestamp: "67:22",
      confidence: 0.97,
      description: "Scoring moment marked for highlight extraction."
    }
  ];
}

function buildMockPlayers(matchId: string): Player[] {
  return [
    { id: `${matchId}-p7`, jersey_number: 7, name: "Ava Carter", position: "Forward" },
    { id: `${matchId}-p10`, jersey_number: 10, name: "Luca Mendes", position: "Midfielder" },
    { id: `${matchId}-p3`, jersey_number: 3, name: "Mia Thompson", position: "Defender" },
    { id: `${matchId}-p1`, jersey_number: 1, name: "Noah Rivera", position: "Goalkeeper" }
  ];
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
