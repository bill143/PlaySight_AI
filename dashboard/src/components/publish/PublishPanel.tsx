"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { listMatches, publishToYoutube } from "@/lib/api";
import type { Match, PublishPrivacy, PublishRecord } from "@/types";

export function PublishPanel() {
  const [matches, setMatches] = useState<Match[]>([]);
  const [selectedMatch, setSelectedMatch] = useState("");
  const [artifactId, setArtifactId] = useState("");
  const [privacy, setPrivacy] = useState<PublishPrivacy>("unlisted");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<PublishRecord | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    const loadMatches = async () => {
      try {
        const response = await listMatches();
        setMatches(response);
        if (response[0]) {
          setSelectedMatch(response[0].id);
        }
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Unable to load matches.");
      } finally {
        setIsLoading(false);
      }
    };

    void loadMatches();
  }, []);

  const handlePublish = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);
    setMessage(null);

    try {
      const publishRecord = await publishToYoutube({
        match_id: selectedMatch,
        artifact_id: artifactId,
        privacy
      });
      setResult(publishRecord);
      setMessage("YouTube publish request submitted successfully.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Publish failed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Card className="border-slate-800 bg-slate-900/80">
      <CardHeader>
        <CardTitle>YouTube Publishing</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Spinner className="h-8 w-8 text-primary-500" />
          </div>
        ) : (
          <form className="space-y-4" onSubmit={handlePublish}>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-200">Match</label>
              <select
                value={selectedMatch}
                onChange={(event) => setSelectedMatch(event.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-100 outline-none transition focus:border-primary-500"
                required
              >
                <option value="" disabled>
                  Select a completed match
                </option>
                {matches.map((match) => (
                  <option key={match.id} value={match.id}>
                    {match.title} — {match.home_team} vs {match.away_team}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-200">Artifact ID</label>
              <input
                value={artifactId}
                onChange={(event) => setArtifactId(event.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-100 outline-none transition focus:border-primary-500"
                placeholder="highlight-artifact-123"
                required
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-200">Privacy</label>
              <select
                value={privacy}
                onChange={(event) => setPrivacy(event.target.value as PublishPrivacy)}
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-100 outline-none transition focus:border-primary-500"
              >
                <option value="private">Private</option>
                <option value="unlisted">Unlisted</option>
                <option value="public">Public</option>
              </select>
            </div>

            {message ? (
              <div className="rounded-lg border border-slate-700 bg-slate-950/60 px-4 py-3 text-sm text-slate-300">
                {message}
              </div>
            ) : null}

            <div className="flex justify-end">
              <Button disabled={isSubmitting || matches.length === 0} type="submit">
                {isSubmitting ? "Publishing..." : "Publish to YouTube"}
              </Button>
            </div>
          </form>
        )}

        {result ? (
          <div className="rounded-xl border border-secondary-500/30 bg-secondary-500/10 p-4 text-sm text-secondary-100">
            <p>Match ID: {result.match_id}</p>
            <p>Artifact ID: {result.artifact_id}</p>
            <p>Privacy: {result.privacy}</p>
            {result.status ? <p>Status: {result.status}</p> : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
