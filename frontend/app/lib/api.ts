const LOCAL_API_URL = "http://localhost:8000";
const PROD_API_URL = "/api";

export function getApiUrl() {
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    if (host === "localhost" || host === "127.0.0.1") {
      return process.env.NEXT_PUBLIC_API_URL || LOCAL_API_URL;
    }
    return process.env.NEXT_PUBLIC_API_URL || PROD_API_URL;
  }

  return process.env.NEXT_PUBLIC_API_URL || LOCAL_API_URL;
}
