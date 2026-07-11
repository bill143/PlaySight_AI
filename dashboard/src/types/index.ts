export type JobStatus =
  | "pending"
  | "queued"
  | "processing"
  | "running"
  | "completed"
  | "failed"
  | "published";

export type PublishPrivacy = "private" | "unlisted" | "public";

export interface User {
  id: string;
  name: string;
  email: string;
  role?: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface Video {
  id?: string;
  title?: string;
  url?: string;
  duration_seconds?: number;
}

export interface Player {
  id: string;
  name: string;
  jersey_number: number | string;
  position?: string;
  team?: string;
}

export interface MatchEvent {
  id: string;
  type: string;
  timestamp: string;
  confidence: number;
  description?: string;
}

export interface Match {
  id: string;
  title: string;
  sport: string;
  home_team: string;
  away_team: string;
  match_date: string;
  status: JobStatus | string;
  job_id?: string;
  video?: Video;
  players?: Player[];
  events?: MatchEvent[];
}

export interface ProcessingJob {
  id: string;
  match_id: string;
  status: JobStatus | string;
  progress: number;
  current_stage?: string | null;
  error_message?: string | null;
}

export interface PlayerStats {
  distance_covered_m: number;
  top_speed_kmh: number;
  possessions: number;
  passes: number;
  shots: number;
  goals: number;
  time_on_ball_seconds: number;
  heatmap_zones: Record<string, number>;
}

export interface PlayerReport {
  player_id: string;
  match_id: string;
  generated_at: string;
  stats: PlayerStats;
  extra?: Record<string, unknown> | null;
}

export interface PlayerHighlight {
  player_id: string;
  match_id: string;
  artifact_id: string;
  download_url?: string;
  clip_count: number;
}

export interface Artifact {
  artifact_id: string;
  download_url: string;
  expires_in: number;
}

export interface PublishPayload {
  match_id: string;
  artifact_id: string;
  privacy: PublishPrivacy;
}

export interface PublishRecord extends PublishPayload {
  id?: string;
  status?: string;
  published_at?: string;
}

export interface HealthCheckResponse {
  status: "ok" | string;
}
