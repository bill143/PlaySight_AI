/**
 * Hand-written mirrors of the PlaySight API schemas (docs/CONTRACTS.md sections 5, 9, 12).
 *
 * Fields the contract leaves to the API implementation are typed optional so the UI
 * degrades gracefully whichever enrichment the server applies.
 */

/** Generic JSON object payload. */
export type JsonObject = Record<string, unknown>;

export type MatchStatus = "created" | "processing" | "processed" | "failed";

export type JobKind = "analyze" | "highlights" | "export_audio" | "annotate" | "publish" | "report";

export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export type UploadStatus = "pending" | "uploading" | "succeeded" | "failed";

export type Privacy = "private" | "unlisted" | "public";

export type IdentityMethod = "ocr" | "reid" | "manual" | "unresolved";

/** Event taxonomy (CONTRACTS.md section 8). Kept open to strings for forward compat. */
export type EventType = "touch" | "pass" | "tackle" | "shot_attempt" | "turnover" | "scoring_event";

export type ArtifactKind =
  | "player_tracks"
  | "player_identities"
  | "player_stats"
  | "match_summary"
  | "annotated_video"
  | "player_report_json"
  | "player_report_pdf"
  | "player_highlights"
  | "match_audio"
  | "upload_status";

/** `POST /auth/login` / `POST /auth/refresh` response. */
export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

/** `GET /auth/me` response. */
export interface Me {
  id: string;
  club_id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  roles?: string[];
}

export interface Team {
  id: string;
  club_id: string;
  name: string;
  sport: string;
  age_group: string | null;
}

export interface Player {
  id: string;
  club_id: string;
  team_id: string | null;
  full_name: string;
  jersey_number: number | null;
  position: string | null;
  external_ref: string | null;
}

/** `matches.period_config_json` shape. */
export interface PeriodConfig {
  periods: number;
  period_minutes: number;
}

export interface Match {
  id: string;
  club_id?: string;
  team_id: string | null;
  opponent: string;
  sport: string;
  kickoff_at: string | null;
  venue: string | null;
  /** Server may expose the JSON column under either name. */
  period_config_json?: PeriodConfig | null;
  period_config?: PeriodConfig | null;
  status: MatchStatus;
  created_at: string;
}

export interface VideoAssetRef {
  id: string;
  club_id?: string;
  match_id: string;
  storage_key?: string;
  filename: string;
  duration_s?: number | null;
  fps?: number | null;
  width?: number | null;
  height?: number | null;
  status: string;
  meta_json?: JsonObject | null;
}

/** `GET /jobs/{id}` response (CONTRACTS.md section 12). */
export interface Job {
  id: string;
  kind: JobKind | string;
  status: JobStatus | string;
  progress: number;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  result?: JsonObject | null;
  /** Present when the API mirrors the processing_jobs row. */
  match_id?: string | null;
  params_json?: JsonObject | null;
  correlation_id?: string | null;
  retries?: number;
}

export interface ArtifactRef {
  id: string;
  club_id?: string;
  match_id: string | null;
  kind: ArtifactKind | string;
  storage_key?: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
  meta_json?: JsonObject | null;
}

export interface EventItem {
  id: string;
  match_id?: string;
  event_type: EventType | string;
  t_start_s: number;
  t_end_s: number;
  player_identity_id: string | null;
  track_id: number | null;
  confidence: number;
  meta_json?: JsonObject | null;
}

export interface PlayerIdentity {
  id: string;
  club_id?: string;
  match_id: string;
  track_id: number;
  player_id: string | null;
  jersey_number: number | null;
  confidence: number;
  method: IdentityMethod | string;
}

/** One `player_match_stats` row; `heatmap_json` is a 12x8 grid of floats. */
export interface PlayerStat {
  id: string;
  match_id?: string;
  player_identity_id: string;
  minutes_tracked: number;
  distance_proxy_m: number;
  touches: number;
  passes: number;
  tackles: number;
  shots: number;
  turnovers: number;
  scoring_events: number;
  avg_confidence: number;
  heatmap_json: number[][] | null;
  /** Optional enrichments the API may add for display. */
  jersey_number?: number | null;
  track_id?: number | null;
  player_name?: string | null;
}

/** Entry of `match_summary.json.players` (CONTRACTS.md section 9). */
export interface SummaryPlayer {
  player_id: string | null;
  track_id: number | null;
  jersey_number: number | null;
  minutes_tracked: number;
  touches: number;
  confidence: number;
}

/** `match_summary.json` shape (CONTRACTS.md section 9). */
export interface MatchSummary {
  match_id: string;
  generated_at: string;
  video: { duration_s: number; fps: number };
  teams: { home: string; away: string };
  counts: { tracks: number; identified: number; events: number };
  events_by_type: Record<string, number>;
  players: SummaryPlayer[];
  engine: Record<string, string>;
  limitations: string[];
}

export interface UploadRecord {
  id: string;
  club_id?: string;
  artifact_id: string;
  platform: string;
  idempotency_key?: string;
  status: UploadStatus | string;
  platform_video_id: string | null;
  url: string | null;
  title: string;
  description: string | null;
  tags_json?: string[] | null;
  category_id?: string;
  privacy: Privacy | string;
  error_log_json?: unknown[] | null;
  attempts: number;
  created_at: string;
  updated_at?: string;
}

/** Response of the job-creating match endpoints (`{job_id}`). */
export interface JobCreatedResponse {
  job_id: string;
}

/** Response of `POST /publish/youtube`. */
export interface PublishResponse {
  upload_id: string;
  job_id: string;
}
