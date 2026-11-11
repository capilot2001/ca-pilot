import { ApiError, friendlyMessage } from "./errors";

const API_BASE = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

const JSON_HEADERS = { "Content-Type": "application/json" };

async function readDetail(res: Response): Promise<string | undefined> {
  try {
    const body = await res.clone().json();
    if (typeof body?.detail === "string") return body.detail;
  } catch {
    /* not JSON — nothing to surface */
  }
  return undefined;
}

async function raiseFor(res: Response, method: string, path: string): Promise<never> {
  const detail = await readDetail(res);
  // developers see the real status + detail; users never do
  console.error(`[api] ${method} ${path} → ${res.status}`, detail ?? "");
  throw new ApiError(friendlyMessage(res.status, detail), res.status);
}

/** Fetch JSON, mapping any failure to a sanitized ApiError. */
export async function apiFetch<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const method = init?.method ?? "GET";
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch (err) {
    console.error(`[api] ${method} ${path} → network error`, err);
    throw new ApiError(friendlyMessage(0), 0);
  }
  if (!res.ok) await raiseFor(res, method, path);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** POST a JSON body. */
export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  });
}

/** Download a file (export endpoints). Returns the blob + server filename. */
export async function apiDownload(
  path: string,
  body: unknown
): Promise<{ blob: Blob; filename: string }> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    });
  } catch (err) {
    console.error(`[api] POST ${path} → network error`, err);
    throw new ApiError(friendlyMessage(0), 0);
  }
  if (!res.ok) await raiseFor(res, "POST", path);
  const cd = res.headers.get("Content-Disposition") ?? "";
  const match = cd.match(/filename="(.+?)"/);
  const filename = match ? match[1] : "download";
  return { blob: await res.blob(), filename };
}

/** Multipart upload (extract / gstr2a import). */
export async function apiUpload<T>(path: string, files: File[]): Promise<T> {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { method: "POST", body: fd });
  } catch (err) {
    console.error(`[api] POST ${path} → network error`, err);
    throw new ApiError(friendlyMessage(0), 0);
  }
  if (!res.ok) await raiseFor(res, "POST", path);
  return (await res.json()) as T;
}

export { API_BASE };
