import { getAccessToken } from "@/lib/auth";
import type {
  Artifact,
  HealthCheckResponse,
  LoginRequest,
  Match,
  PlayerHighlight,
  PlayerReport,
  ProcessingJob,
  PublishPayload,
  PublishRecord,
  TokenPair
} from "@/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

async function readResponseBody(response: Response) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }

  const text = await response.text();
  return text ? { message: text } : null;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  requiresAuth = true
): Promise<T> {
  const headers = new Headers(init.headers);

  if (!(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (requiresAuth) {
    const token = getAccessToken();
    if (token) {
      headers.set("Authorization", "Bearer " + token);
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store"
  });

  if (!response.ok) {
    const errorBody = await readResponseBody(response);
    const message =
      typeof errorBody === "string"
        ? errorBody
        : (errorBody as { detail?: string; message?: string } | null)?.detail ||
          (errorBody as { detail?: string; message?: string } | null)?.message ||
          `Request failed with status ${response.status}`;
    throw new Error(message);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return (await readResponseBody(response)) as T;
}

export function login(payload: LoginRequest) {
  return request<TokenPair>(
    "/auth/login",
    {
      method: "POST",
      body: JSON.stringify(payload)
    },
    false
  );
}

export function refreshToken(refresh_token: string) {
  return request<TokenPair>(
    "/auth/refresh",
    {
      method: "POST",
      body: JSON.stringify({ refresh_token })
    },
    false
  );
}

export function listMatches() {
  return request<Match[]>("/matches");
}

export function getMatch(id: string) {
  return request<Match>(`/matches/${id}`);
}

export function ingestMatch(file: File, metadata: Record<string, unknown>) {
  const formData = new FormData();
  formData.append("video", file);
  formData.append("metadata", JSON.stringify(metadata));

  return request<{ match_id: string; job_id: string; status: string }>(
    "/matches/ingest",
    {
      method: "POST",
      body: formData
    }
  );
}

export function getJobStatus(id: string) {
  return request<ProcessingJob>(`/jobs/${id}/status`);
}

export function getPlayerReport(id: string) {
  return request<PlayerReport>(`/players/${id}/report`);
}

export function getPlayerHighlights(id: string) {
  return request<PlayerHighlight>(`/players/${id}/highlights`);
}

export function getArtifactDownload(id: string) {
  return request<Artifact>(`/artifacts/${id}/download`);
}

export function publishToYoutube(payload: PublishPayload) {
  return request<PublishRecord>("/publish/youtube", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function healthCheck() {
  return request<HealthCheckResponse>("/health", {}, false);
}
