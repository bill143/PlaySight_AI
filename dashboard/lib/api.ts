/**
 * Typed fetch wrapper for the PlaySight REST API (docs/CONTRACTS.md section 12).
 *
 * - Base URL from `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`), prefix `/api/v1`.
 * - Bearer token from localStorage key `ps_access` (refresh token under `ps_refresh`).
 * - On 401 the wrapper transparently calls `POST /api/v1/auth/refresh` once and retries;
 *   if the refresh fails, tokens are cleared and the browser is sent to `/login`.
 */

import type {
  ArtifactRef,
  EventItem,
  Job,
  JobCreatedResponse,
  JsonObject,
  Match,
  MatchSummary,
  Me,
  PeriodConfig,
  Player,
  PlayerStat,
  Privacy,
  PublishResponse,
  Team,
  TokenPair,
  UploadRecord,
  VideoAssetRef,
} from "@/lib/types";
import { errorMessage } from "@/lib/format";

const ACCESS_KEY = "ps_access";
const REFRESH_KEY = "ps_refresh";
const API_PREFIX = "/api/v1";

/** API origin, e.g. `http://localhost:8000` (no trailing slash). */
export function apiBaseUrl(): string {
  const base =
    process.env.NEXT_PUBLIC_API_URL ??
    (process.env.NODE_ENV === "production"
      ? "https://playsight-api.fly.dev"
      : "http://localhost:8000");
  return base.replace(/\/+$/, "");
}

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

/** Current access token, or null outside the browser / when signed out. */
export function getAccessToken(): string | null {
  return isBrowser() ? window.localStorage.getItem(ACCESS_KEY) : null;
}

/** Current refresh token, or null. */
export function getRefreshToken(): string | null {
  return isBrowser() ? window.localStorage.getItem(REFRESH_KEY) : null;
}

/** Persist a token pair to localStorage. */
export function setTokens(accessToken: string, refreshToken: string): void {
  if (!isBrowser()) return;
  window.localStorage.setItem(ACCESS_KEY, accessToken);
  window.localStorage.setItem(REFRESH_KEY, refreshToken);
}

/** Remove both tokens (sign out). */
export function clearTokens(): void {
  if (!isBrowser()) return;
  window.localStorage.removeItem(ACCESS_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
}

/** Error thrown for any non-2xx API response (status 0 = network failure). */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function toApiError(res: Response): Promise<ApiError> {
  let code = `http_${res.status}`;
  let message = res.statusText || `Request failed with status ${res.status}`;
  try {
    const data: unknown = await res.json();
    if (data && typeof data === "object") {
      const obj = data as Record<string, unknown>;
      const err = obj.error;
      if (err && typeof err === "object") {
        const e = err as Record<string, unknown>;
        if (typeof e.code === "string") code = e.code;
        if (typeof e.message === "string") message = e.message;
      } else if (typeof obj.detail === "string") {
        message = obj.detail;
      } else if (Array.isArray(obj.detail)) {
        const msgs = obj.detail
          .map((d) => {
            if (d && typeof d === "object") {
              const msg = (d as Record<string, unknown>).msg;
              if (typeof msg === "string") return msg;
            }
            return null;
          })
          .filter((m): m is string => m !== null);
        if (msgs.length > 0) {
          message = msgs.join("; ");
          code = "validation_error";
        }
      }
    }
  } catch {
    /* response body was not JSON */
  }
  return new ApiError(res.status, code, message);
}

let refreshPromise: Promise<boolean> | null = null;

async function doRefresh(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;
  try {
    const res = await fetch(`${apiBaseUrl()}${API_PREFIX}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return false;
    const data = (await res.json()) as Partial<TokenPair>;
    if (typeof data.access_token !== "string") return false;
    setTokens(data.access_token, typeof data.refresh_token === "string" ? data.refresh_token : refreshToken);
    return true;
  } catch {
    /* network failure during refresh */
    return false;
  }
}

/** Single-flight refresh: concurrent 401s share one refresh round-trip. */
async function tryRefresh(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = doRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

function redirectToLogin(): void {
  if (!isBrowser()) return;
  const path = window.location.pathname;
  if (path !== "/login" && path !== "/register") window.location.assign("/login");
}

interface RequestOptions {
  method?: string;
  /** JSON-serializable request body (mutually exclusive with `form`). */
  body?: unknown;
  /** Multipart form body; Content-Type is left to the browser. */
  form?: FormData;
  query?: Record<string, string | number | boolean | null | undefined>;
  /** Attach the bearer token (default true). */
  auth?: boolean;
  headers?: Record<string, string>;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  let url = `${apiBaseUrl()}${API_PREFIX}${path}`;
  if (query) {
    const qs = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== "") qs.set(key, String(value));
    }
    const encoded = qs.toString();
    if (encoded) url += `?${encoded}`;
  }
  return url;
}

async function request<T>(path: string, opts: RequestOptions = {}, isRetry = false): Promise<T> {
  const { method = "GET", body, form, query, auth = true } = opts;
  const headers: Record<string, string> = { ...(opts.headers ?? {}) };
  const init: RequestInit = { method, headers };
  if (form) {
    init.body = form;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  if (auth) {
    const token = getAccessToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  let res: Response;
  try {
    res = await fetch(buildUrl(path, query), init);
  } catch (err) {
    throw new ApiError(
      0,
      "network_error",
      `Cannot reach the PlaySight API at ${apiBaseUrl()} (${errorMessage(err)})`,
    );
  }

  if (res.status === 401 && auth && !isRetry) {
    const refreshed = await tryRefresh();
    if (refreshed) return request<T>(path, opts, true);
    clearTokens();
    redirectToLogin();
    throw new ApiError(401, "auth_expired", "Session expired — please sign in again.");
  }

  if (!res.ok) throw await toApiError(res);
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

/** Accept either a bare JSON array or `{<key>: [...]}` / `{items: [...]}` wrappers. */
function asList<T>(data: unknown, ...keys: string[]): T[] {
  if (Array.isArray(data)) return data as T[];
  if (data && typeof data === "object") {
    for (const key of [...keys, "items", "results", "data"]) {
      const value = (data as Record<string, unknown>)[key];
      if (Array.isArray(value)) return value as T[];
    }
  }
  return [];
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

/** Log in with email/password; stores the returned token pair. */
export async function login(email: string, password: string): Promise<TokenPair> {
  const tokens = await request<TokenPair>("/auth/login", {
    method: "POST",
    body: { email, password },
    auth: false,
  });
  setTokens(tokens.access_token, tokens.refresh_token);
  return tokens;
}

export interface RegisterClubInput {
  club_name: string;
  email: string;
  password: string;
  full_name: string;
}

/**
 * Bootstrap a club + first admin user, then ensure the browser is signed in.
 * If the response does not include tokens, falls back to a normal login.
 */
export async function registerClub(input: RegisterClubInput): Promise<void> {
  const data = await request<Record<string, unknown>>("/auth/register-club", {
    method: "POST",
    // `name` is included alongside `club_name` for schema-naming tolerance;
    // pydantic ignores unknown fields by default.
    body: {
      club_name: input.club_name,
      name: input.club_name,
      email: input.email,
      password: input.password,
      full_name: input.full_name,
    },
    auth: false,
  });
  const access = typeof data.access_token === "string" ? data.access_token : null;
  const refresh = typeof data.refresh_token === "string" ? data.refresh_token : null;
  if (access && refresh) {
    setTokens(access, refresh);
    return;
  }
  await login(input.email, input.password);
}

/** `GET /auth/me`. */
export async function me(): Promise<Me> {
  return request<Me>("/auth/me");
}

// ---------------------------------------------------------------------------
// Teams / players
// ---------------------------------------------------------------------------

/** `GET /teams`. */
export async function listTeams(): Promise<Team[]> {
  return asList<Team>(await request<unknown>("/teams"), "teams");
}

export interface CreateTeamInput {
  name: string;
  sport: string;
  age_group?: string | null;
}

/** `POST /teams`. */
export async function createTeam(input: CreateTeamInput): Promise<Team> {
  return request<Team>("/teams", { method: "POST", body: input });
}

/** `GET /players`. */
export async function listPlayers(): Promise<Player[]> {
  return asList<Player>(await request<unknown>("/players"), "players");
}

// ---------------------------------------------------------------------------
// Matches
// ---------------------------------------------------------------------------

/** `GET /matches`. */
export async function listMatches(): Promise<Match[]> {
  return asList<Match>(await request<unknown>("/matches"), "matches");
}

export interface CreateMatchInput {
  team_id?: string | null;
  opponent: string;
  sport: string;
  kickoff_at?: string | null;
  venue?: string | null;
  period_config_json?: PeriodConfig;
}

/** `POST /matches`. */
export async function createMatch(input: CreateMatchInput): Promise<Match> {
  return request<Match>("/matches", { method: "POST", body: input });
}

/** `GET /matches/{id}`. */
export async function getMatch(matchId: string): Promise<Match> {
  return request<Match>(`/matches/${matchId}`);
}

/** `POST /matches/{id}/videos` — multipart video upload. */
export async function uploadMatchVideo(matchId: string, file: File): Promise<VideoAssetRef> {
  const form = new FormData();
  form.append("file", file, file.name);
  return request<VideoAssetRef>(`/matches/${matchId}/videos`, { method: "POST", form });
}

/** `POST /matches/{id}/process` — queue the analyze job. */
export async function processMatch(matchId: string): Promise<JobCreatedResponse> {
  return request<JobCreatedResponse>(`/matches/${matchId}/process`, { method: "POST" });
}

export interface HighlightsRequest {
  player_identity_id?: string;
  track_id?: number;
}

/** `POST /matches/{id}/highlights`. */
export async function requestHighlights(
  matchId: string,
  body: HighlightsRequest,
): Promise<JobCreatedResponse> {
  return request<JobCreatedResponse>(`/matches/${matchId}/highlights`, { method: "POST", body });
}

/** `POST /matches/{id}/annotate`. */
export async function requestAnnotate(matchId: string): Promise<JobCreatedResponse> {
  return request<JobCreatedResponse>(`/matches/${matchId}/annotate`, { method: "POST" });
}

/** `POST /matches/{id}/export/audio`. */
export async function requestAudioExport(matchId: string): Promise<JobCreatedResponse> {
  return request<JobCreatedResponse>(`/matches/${matchId}/export/audio`, { method: "POST" });
}

/** `GET /matches/{id}/summary`. */
export async function getMatchSummary(matchId: string): Promise<MatchSummary> {
  return request<MatchSummary>(`/matches/${matchId}/summary`);
}

export type EventFilters = {
  type?: string;
  player?: string;
  period?: number;
  t0?: number;
  t1?: number;
};

/** `GET /matches/{id}/events` (server-side filters optional; UI also filters locally). */
export async function getMatchEvents(matchId: string, filters?: EventFilters): Promise<EventItem[]> {
  const data = await request<unknown>(`/matches/${matchId}/events`, {
    query: filters ? { ...filters } : undefined,
  });
  return asList<EventItem>(data, "events");
}

/** `GET /matches/{id}/stats`. */
export async function getMatchStats(matchId: string): Promise<PlayerStat[]> {
  return asList<PlayerStat>(await request<unknown>(`/matches/${matchId}/stats`), "stats", "players");
}

/** `GET /matches/{id}/players/{identity_id}/report`. */
export async function getPlayerReport(matchId: string, identityId: string): Promise<JsonObject> {
  return request<JsonObject>(`/matches/${matchId}/players/${identityId}/report`);
}

// ---------------------------------------------------------------------------
// Jobs
// ---------------------------------------------------------------------------

export type JobFilters = {
  status?: string;
  kind?: string;
};

/** `GET /jobs`. */
export async function listJobs(filters?: JobFilters): Promise<Job[]> {
  const data = await request<unknown>("/jobs", { query: filters ? { ...filters } : undefined });
  return asList<Job>(data, "jobs");
}

/** `GET /jobs/{id}`. */
export async function getJob(jobId: string): Promise<Job> {
  return request<Job>(`/jobs/${jobId}`);
}

// ---------------------------------------------------------------------------
// Artifacts
// ---------------------------------------------------------------------------

export type ArtifactFilters = {
  match_id?: string;
  kind?: string;
};

/** `GET /artifacts`. */
export async function listArtifacts(filters?: ArtifactFilters): Promise<ArtifactRef[]> {
  const data = await request<unknown>("/artifacts", { query: filters ? { ...filters } : undefined });
  return asList<ArtifactRef>(data, "artifacts");
}

/** Fetch `GET /artifacts/{id}/download` with auth and return the raw blob. */
export async function downloadArtifactBlob(artifactId: string): Promise<Blob> {
  const url = `${apiBaseUrl()}${API_PREFIX}/artifacts/${artifactId}/download`;
  const doFetch = (): Promise<Response> => {
    const token = getAccessToken();
    return fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : undefined });
  };
  let res = await doFetch();
  if (res.status === 401 && (await tryRefresh())) res = await doFetch();
  if (!res.ok) throw await toApiError(res);
  return res.blob();
}

/** Download an artifact through the browser save dialog (object URL + anchor click). */
export async function saveArtifact(artifact: Pick<ArtifactRef, "id" | "filename">): Promise<void> {
  const blob = await downloadArtifactBlob(artifact.id);
  const url = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = artifact.filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
}

// ---------------------------------------------------------------------------
// Publishing
// ---------------------------------------------------------------------------

export interface PublishInput {
  artifact_id: string;
  title: string;
  description?: string;
  tags?: string[];
  category_id?: string;
  privacy?: Privacy;
  /** Must be true — the API rejects publishes without an explicit rights confirmation. */
  confirm_rights: boolean;
}

/** `POST /publish/youtube`. */
export async function publishYouTube(input: PublishInput): Promise<PublishResponse> {
  return request<PublishResponse>("/publish/youtube", { method: "POST", body: input });
}

/** `GET /publish/{upload_id}`. */
export async function getUploadRecord(uploadId: string): Promise<UploadRecord> {
  return request<UploadRecord>(`/publish/${uploadId}`);
}
