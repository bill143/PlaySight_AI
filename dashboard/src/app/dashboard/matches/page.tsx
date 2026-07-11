"use client";

import { useEffect, useState } from "react";
import { MatchCard } from "@/components/match/MatchCard";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { ingestMatch, listMatches } from "@/lib/api";
import type { Match } from "@/types";

interface UploadState {
  title: string;
  sport: string;
  home_team: string;
  away_team: string;
  match_date: string;
  video: File | null;
}

const initialUploadState: UploadState = {
  title: "",
  sport: "soccer",
  home_team: "",
  away_team: "",
  match_date: "",
  video: null
};

export default function MatchesPage() {
  const [matches, setMatches] = useState<Match[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [formState, setFormState] = useState<UploadState>(initialUploadState);

  const fetchMatches = async () => {
    setIsLoading(true);
    setError(null);
    try {
      setMatches(await listMatches());
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load matches.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void fetchMatches();
  }, []);

  const handleUpload = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!formState.video) {
      setUploadMessage("Please choose a match video before uploading.");
      return;
    }

    setIsUploading(true);
    setUploadMessage(null);

    try {
      const response = await ingestMatch(formState.video, {
        title: formState.title,
        sport: formState.sport,
        home_team: formState.home_team,
        away_team: formState.away_team,
        match_date: formState.match_date
      });
      setUploadMessage(
        `Upload started. Match ${response.match_id} is linked to job ${response.job_id}.`
      );
      setFormState(initialUploadState);
      await fetchMatches();
    } catch (uploadError) {
      setUploadMessage(
        uploadError instanceof Error ? uploadError.message : "Upload failed."
      );
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-3xl font-semibold">Matches</h1>
          <p className="mt-2 text-sm text-slate-400">
            Browse completed analytics runs or ingest a new match for AI
            processing.
          </p>
        </div>
        <Button type="button" onClick={() => document.getElementById("upload-form")?.scrollIntoView()}>
          Upload Match
        </Button>
      </div>

      <Card
        className="border-slate-800 bg-slate-900/80"
        id="upload-form"
      >
        <CardHeader>
          <CardTitle>Upload New Match</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4 md:grid-cols-2" onSubmit={handleUpload}>
            <Field
              label="Match Title"
              value={formState.title}
              onChange={(value) => setFormState((current) => ({ ...current, title: value }))}
            />
            <Field
              label="Sport"
              value={formState.sport}
              onChange={(value) => setFormState((current) => ({ ...current, sport: value }))}
            />
            <Field
              label="Home Team"
              value={formState.home_team}
              onChange={(value) =>
                setFormState((current) => ({ ...current, home_team: value }))
              }
            />
            <Field
              label="Away Team"
              value={formState.away_team}
              onChange={(value) =>
                setFormState((current) => ({ ...current, away_team: value }))
              }
            />
            <Field
              label="Match Date"
              type="date"
              value={formState.match_date}
              onChange={(value) =>
                setFormState((current) => ({ ...current, match_date: value }))
              }
            />
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-200">Video File</label>
              <input
                type="file"
                accept="video/*"
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    video: event.target.files?.[0] ?? null
                  }))
                }
                className="w-full rounded-lg border border-dashed border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-300 file:mr-4 file:rounded-md file:border-0 file:bg-primary-600 file:px-3 file:py-2 file:text-white"
              />
            </div>
            <div className="md:col-span-2 flex flex-col gap-3">
              {uploadMessage ? (
                <div className="rounded-lg border border-slate-700 bg-slate-950/60 px-4 py-3 text-sm text-slate-300">
                  {uploadMessage}
                </div>
              ) : null}
              <div className="flex justify-end">
                <Button disabled={isUploading} type="submit">
                  {isUploading ? "Uploading..." : "Start Ingestion"}
                </Button>
              </div>
            </div>
          </form>
        </CardContent>
      </Card>

      {error ? (
        <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-4 text-rose-200">
          {error}
        </div>
      ) : null}

      {isLoading ? (
        <div className="flex min-h-[30vh] items-center justify-center">
          <Spinner className="h-10 w-10 text-primary-500" />
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {matches.map((match) => (
            <MatchCard key={match.id} match={match} />
          ))}
          {matches.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-700 p-8 text-center text-sm text-slate-400">
              No matches found yet.
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text"
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
}) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-slate-200">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-100 outline-none transition focus:border-primary-500"
        required
      />
    </div>
  );
}
