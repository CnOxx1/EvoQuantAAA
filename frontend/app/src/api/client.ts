export type ApiEnvelope<T = unknown> = {
  ok?: boolean;
  data?: T;
  error?: { status?: number; message?: string; [k: string]: unknown };
  detail?: unknown;
  [k: string]: unknown;
};

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, body: unknown, message?: string) {
    super(message || `HTTP ${status}`);
    this.status = status;
    this.body = body;
  }
}

export type ClientConfig = {
  apiBase: string;
  apiToken: string;
};

function headers(cfg: ClientConfig, json: boolean): HeadersInit {
  const h: Record<string, string> = { Accept: "application/json" };
  if (json) h["Content-Type"] = "application/json";
  const token = cfg.apiToken.trim();
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

export async function apiRequest<T = unknown>(
  cfg: ClientConfig,
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const base = cfg.apiBase.replace(/\/$/, "");
  const res = await fetch(`${base}${path}`, {
    method,
    headers: headers(cfg, body !== undefined),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { raw: text };
  }
  if (!res.ok) {
    const detail =
      data && typeof data === "object" && "detail" in data
        ? (data as { detail: unknown }).detail
        : data;
    throw new ApiError(res.status, detail);
  }
  return data as T;
}

export function unwrapData<T>(envelope: ApiEnvelope<T> | T): T {
  if (envelope && typeof envelope === "object" && "data" in envelope) {
    return (envelope as ApiEnvelope<T>).data as T;
  }
  return envelope as T;
}
