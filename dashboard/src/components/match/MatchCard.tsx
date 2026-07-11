import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Card, CardContent } from "@/components/ui/Card";
import type { Match } from "@/types";

export function MatchCard({ match }: { match: Match }) {
  return (
    <Link href={`/dashboard/matches/${match.id}`}>
      <Card className="h-full border-slate-800 bg-slate-900/80 transition hover:border-primary-500/60 hover:bg-slate-900">
        <CardContent className="flex h-full flex-col justify-between pt-6">
          <div>
            <div className="mb-4 flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-primary-300">
                  {match.sport}
                </p>
                <h3 className="mt-2 text-xl font-semibold text-slate-100">
                  {match.title}
                </h3>
              </div>
              <Badge variant={getStatusVariant(match.status)}>{match.status}</Badge>
            </div>
            <p className="text-sm text-slate-300">
              {match.home_team} vs {match.away_team}
            </p>
          </div>
          <div className="mt-6 text-sm text-slate-400">
            {new Date(match.match_date).toLocaleDateString()}
          </div>
        </CardContent>
      </Card>
    </Link>
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
  return "info" as const;
}
