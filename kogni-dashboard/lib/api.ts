import { AuthResponse, WeeklyReport } from "@/types/kogni";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Token management (localStorage) ─────────────────────────────────────────

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("kogni_token");
}

export function setToken(token: string) {
  localStorage.setItem("kogni_token", token);
}

export function clearToken() {
  localStorage.removeItem("kogni_token");
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export async function register(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? "Registration failed");
  return res.json();
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? "Login failed");
  return res.json();
}

// ── Dashboard data ───────────────────────────────────────────────────────────

export async function fetchWeeklyReport(): Promise<WeeklyReport> {
  const token = localStorage.getItem("kogni_token");
  if (!token) throw new Error("Unauthenticated");
  const res = await fetch(`${API}/api/v1/dashboard/weekly-report`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (res.status === 401) throw new Error("Unauthenticated");
  if (!res.ok) throw new Error("Failed to fetch weekly report");
  return res.json();
}

// ── WebSocket ─────────────────────────────────────────────────────────────────

export function createLiveSocket(
  token: string,
  onMessage: (data: unknown) => void,
  onClose?: () => void
): WebSocket {
  const wsBase = API.replace(/^http/, "ws");
  const ws = new WebSocket(`${wsBase}/api/v1/ws/live?token=${token}`);
  ws.onmessage = (e) => {
    try { onMessage(JSON.parse(e.data)); } catch {}
  };
  ws.onclose = () => onClose?.();
  return ws;
}

// ── Recovery ─────────────────────────────────────────────────────────────────

export async function fetchPassage(): Promise<{ passage_id: number; text: string }> {
  const token = getToken();
  const res   = await fetch(`${API}/api/v1/recovery/passage`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Failed to fetch passage");
  return res.json();
}

export async function measureRecovery(
  keystroke_timings: number[],
  pre_score?: number,
  passage_id?: number
): Promise<{
  recovered: boolean;
  post_iki_mean: number;
  baseline_iki: number | null;
  pct_of_baseline: number | null;
  message: string;
}> {
  const token = getToken();
  const res   = await fetch(`${API}/api/v1/recovery/measure`, {
    method:  "POST",
    headers: {
      "Content-Type":  "application/json",
      Authorization:   `Bearer ${token}`,
    },
    body: JSON.stringify({ keystroke_timings, pre_score, passage_id }),
  });
  if (!res.ok) throw new Error("Recovery measurement failed");
  return res.json();
}

export async function fetchRecoveryHistory(): Promise<{ history: unknown[] }> {
  const token = getToken();
  const res   = await fetch(`${API}/api/v1/recovery/history`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Failed to fetch recovery history");
  return res.json();
}
