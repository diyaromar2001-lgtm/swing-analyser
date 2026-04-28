import { NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Route appelée par le cron Vercel toutes les 5 minutes
// pour garder Railway éveillé (éviter le cold start de 30s)
export async function GET() {
  try {
    const res = await fetch(`${BACKEND}/health`, {
      next: { revalidate: 0 },
    });
    const data = await res.json();
    return NextResponse.json({ pong: true, backend: data, ts: new Date().toISOString() });
  } catch (e) {
    return NextResponse.json({ pong: false, error: String(e) }, { status: 503 });
  }
}
