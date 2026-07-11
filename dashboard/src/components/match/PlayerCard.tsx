import Link from "next/link";
import { Card, CardContent } from "@/components/ui/Card";
import type { Player } from "@/types";

export function PlayerCard({ player }: { player: Player }) {
  return (
    <Link href={`/dashboard/players/${player.id}`}>
      <Card className="border-slate-800 bg-slate-950/60 transition hover:border-secondary-500/60 hover:bg-slate-950">
        <CardContent className="flex items-center justify-between gap-4 pt-6">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-secondary-500/15 text-lg font-semibold text-secondary-100">
              #{player.jersey_number}
            </div>
            <div>
              <p className="font-medium text-slate-100">{player.name}</p>
              <p className="text-sm text-slate-400">{player.position || "Player"}</p>
            </div>
          </div>
          <span className="text-sm text-primary-300">View report →</span>
        </CardContent>
      </Card>
    </Link>
  );
}
