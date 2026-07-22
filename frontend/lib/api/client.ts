const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken() {
  return accessToken;
}

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function parseError(response: Response): Promise<ApiError> {
  try {
    const body = await response.json();
    const err = body?.error ?? {};
    return new ApiError(response.status, err.code ?? "unknown_error", err.message ?? response.statusText);
  } catch {
    return new ApiError(response.status, "unknown_error", response.statusText);
  }
}

async function tryRefresh(): Promise<boolean> {
  const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: "POST",
    credentials: "include",
  });
  if (!response.ok) return false;
  const data = await response.json();
  setAccessToken(data.access_token);
  return true;
}

export async function apiFetch<T>(path: string, options: RequestInit = {}, _retry = true): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  if (response.status === 401 && _retry) {
    const refreshed = await tryRefresh();
    if (refreshed) return apiFetch<T>(path, options, false);
  }

  if (!response.ok) {
    throw await parseError(response);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export { API_BASE_URL };
