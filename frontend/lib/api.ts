const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

export class ApiClientError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiClientError";
    this.status = status;
    this.detail = detail;
  }
}

type RequestOptions = {
  method?: "GET" | "POST" | "DELETE";
  body?: unknown;
  token?: string | null;
  headers?: Record<string, string>;
};

export async function api<T>(
  path: string,
  { method = "GET", body, token, headers }: RequestOptions = {},
): Promise<T> {
  const requestHeaders: Record<string, string> = {
    Accept: "application/json",
    ...headers,
  };

  if (body !== undefined) {
    requestHeaders["Content-Type"] = "application/json";
  }

  if (token) {
    requestHeaders["Authorization"] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers: requestHeaders,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiClientError(
      0,
      `Unable to reach the API at ${API_URL}. Is the backend running?`,
    );
  }

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}.`;
    try {
      const payload = await response.json();
      if (payload?.detail) detail = String(payload.detail);
    } catch {
      // response body was not JSON — keep the fallback message
    }
    throw new ApiClientError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function apiForm<T>(
  path: string,
  form: FormData,
  token?: string | null,
): Promise<T> {
  const requestHeaders: Record<string, string> = { Accept: "application/json" };
  if (token) {
    requestHeaders["Authorization"] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: requestHeaders,
      body: form,
    });
  } catch {
    throw new ApiClientError(
      0,
      `Unable to reach the API at ${API_URL}. Is the backend running?`,
    );
  }

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}.`;
    try {
      const payload = await response.json();
      if (payload?.detail) detail = String(payload.detail);
    } catch {
      // response body was not JSON — keep the fallback message
    }
    throw new ApiClientError(response.status, detail);
  }

  return (await response.json()) as T;
}

export function apiUrl(path: string): string {
  return `${API_URL}${path}`;
}