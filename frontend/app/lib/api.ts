const LOCAL_API_URL = "http://localhost:8000";
const PROD_API_URL = "https://swing-analyser-production.up.railway.app";
const ADMIN_API_KEY_STORAGE = "admin_api_key";

export class AdminProtectedError extends Error {
  constructor(message = "Action admin protégée") {
    super(message);
    this.name = "AdminProtectedError";
  }
}

export function getApiUrl() {
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    if (host === "localhost" || host === "127.0.0.1") {
      return process.env.NEXT_PUBLIC_API_URL || LOCAL_API_URL;
    }
    return PROD_API_URL;
  }

  return PROD_API_URL;
}

export async function ensureApiResponse(response: Response) {
  if (response.status === 401) {
    throw new AdminProtectedError();
  }
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response;
}

export function isAdminProtectedError(error: unknown) {
  return error instanceof AdminProtectedError
    || (error instanceof Error && error.name === "AdminProtectedError");
}

export function getAdminApiKey(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const value = window.localStorage.getItem(ADMIN_API_KEY_STORAGE);
    return value && value.trim() ? value.trim() : null;
  } catch {
    return null;
  }
}

export function getAdminHeaders(): HeadersInit {
  const key = getAdminApiKey();
  return key ? { "X-Admin-Key": key } : {};
}
