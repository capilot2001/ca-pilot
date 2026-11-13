/**
 * Error handling policy: the client never sees raw backend text or stack traces.
 *
 * - For a few known 4xx (409 conflict, 404 not found) the backend's `detail` is a
 *   curated, user-safe message, so we surface it.
 * - Everything else maps to a friendly message by status. The real error is
 *   logged to the console for developers only.
 */

export class ApiError extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** status 0 is reserved for "network unreachable". */
export function friendlyMessage(status: number, detail?: string): string {
  if (detail && (status === 409 || status === 404)) return detail;

  if (status === 0)
    return "Can't reach the server. Check your connection and that the backend is running.";
  if (status === 400 || status === 422)
    return "Please check the highlighted details and try again.";
  if (status === 401) return "Your session has expired. Please sign in again.";
  if (status === 403) return "You don't have access to do that.";
  if (status === 404) return "We couldn't find what you were looking for.";
  if (status === 409) return "That conflicts with something that already exists.";
  if (status === 413) return "That file is too large to upload.";
  if (status === 429)
    return "Too many requests — please wait a moment and try again.";
  if (status >= 500)
    return "Something went wrong on our side. Please try again.";
  return "Something went wrong. Please try again.";
}
