import { Dashboard } from "./components/Dashboard";
import { TickerResult } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function getScreenerData(): Promise<TickerResult[]> {
  try {
    const res = await fetch(`${API_URL}/api/screener`, { next: { revalidate: 0 } });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export default async function Home() {
  const data = await getScreenerData();

  if (data.length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "#070710" }}>
        <div className="text-center p-8 rounded-2xl" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
          <div className="text-4xl mb-4">📡</div>
          <p className="text-red-400 text-lg font-bold mb-2">Backend non connecté</p>
          <p className="text-gray-500 text-sm mb-4">Lancez le serveur FastAPI sur le port 8000</p>
          <code className="text-xs text-indigo-400 bg-black/40 px-4 py-2 rounded block">
            cd backend && venv\Scripts\uvicorn main:app --reload
          </code>
        </div>
      </div>
    );
  }

  return <Dashboard initialData={data} />;
}
