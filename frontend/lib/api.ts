import type { AppState, Health } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<Health>("/api/health"),
  sessions: () => request<{ id: string; title: string; mode: string; gap: number | null }[]>("/api/sessions"),
  create: (mode: "quick" | "guided") => request<AppState>("/api/sessions", { method: "POST", body: JSON.stringify({ mode }) }),
  get: (id: string) => request<AppState>(`/api/sessions/${id}`),
  mode: (id: string, mode: "quick" | "guided") =>
    request<AppState>(`/api/sessions/${id}`, { method: "PATCH", body: JSON.stringify({ mode }) }),
  message: (id: string, content: string) =>
    request<AppState>(`/api/sessions/${id}/messages`, { method: "POST", body: JSON.stringify({ content }) }),
  profile: (id: string, patch: Record<string, unknown>) =>
    request<AppState>(`/api/sessions/${id}/profile`, { method: "PATCH", body: JSON.stringify(patch) }),
  event: (id: string, event: string) =>
    request<AppState>(`/api/sessions/${id}/events`, { method: "POST", body: JSON.stringify({ event }) }),
  apply: (id: string, scenarioId: string) => request<AppState>(`/api/sessions/${id}/scenarios/${scenarioId}/apply`, { method: "POST" }),
  discard: (id: string, scenarioId: string) =>
    request<AppState>(`/api/sessions/${id}/scenarios/${scenarioId}/discard`, { method: "POST" }),
  stress: (id: string, coverage: number) =>
    request<{ sample: { coverage: number; items: { label: string; status: string; detail: string }[] } }>(
      `/api/sessions/${id}/stress`,
      { method: "POST", body: JSON.stringify({ coverage }) },
    ),
};
