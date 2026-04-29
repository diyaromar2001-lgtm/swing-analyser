"use client";

import { useState, useCallback, useEffect } from "react";
import { getApiUrl } from "../lib/api";

const API_URL = getApiUrl();

interface ApiStatusData {
  reddit: { configured: boolean; missing_vars: string[] };
  twitter: { configured: boolean; missing_vars: string[] };
  all_configured: boolean;
  sentiment_cache: {
    entries: number;
    ttl_minutes: number;
    tickers: { ticker: string; age_minutes: number; expires_in: number }[];
  };
}

// ── Indicateur status inline (header) ────────────────────────────────────────

export function ApiStatusDot({ onClick }: { onClick: () => void }) {
  const [status, setStatus] = useState<"unknown" | "partial" | "ok" | "none">("unknown");

  useEffect(() => {
    fetch(`${API_URL}/api/status`)
      .then(r => r.json())
      .then((d: ApiStatusData) => {
        if (d.all_configured)                           setStatus("ok");
        else if (d.reddit.configured || d.twitter.configured) setStatus("partial");
        else                                            setStatus("none");
      })
      .catch(() => setStatus("unknown"));
  }, []);

  const dotColor =
    status === "ok"      ? "#4ade80" :
    status === "partial" ? "#f59e0b" :
    status === "none"    ? "#f87171" :
                           "#4b5563";

  const label =
    status === "ok"      ? "APIs connectées" :
    status === "partial" ? "APIs partiellement configurées" :
    status === "none"    ? "APIs non configurées" :
                           "Vérification…";

  return (
    <button
      onClick={onClick}
      title={label}
      className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs transition-all hover:opacity-80"
      style={{ background: "#0d0d18", border: `1px solid ${dotColor}44`, color: dotColor }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: dotColor }} />
      API
    </button>
  );
}

// ── Panel complet ─────────────────────────────────────────────────────────────

function StatusRow({
  label,
  ok,
  missing,
}: {
  label: string;
  ok: boolean;
  missing: string[];
}) {
  return (
    <div className="py-3" style={{ borderBottom: "1px solid #1a1a28" }}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-bold text-white">{label}</span>
        <span
          className="text-xs font-bold px-2 py-0.5 rounded-full"
          style={{
            background: ok ? "#052e16" : "#1f0909",
            color:      ok ? "#4ade80" : "#f87171",
            border:     `1px solid ${ok ? "#166534" : "#7f1d1d"}`,
          }}
        >
          {ok ? "✓ Connecté" : "✗ Non configuré"}
        </span>
      </div>
      {!ok && missing.length > 0 && (
        <div className="mt-2 space-y-1">
          <p className="text-[10px] text-gray-600 uppercase tracking-wider mb-1">Variables manquantes :</p>
          {missing.map(v => (
            <div key={v} className="flex items-center gap-2">
              <span className="text-red-500 text-xs">✗</span>
              <code className="text-xs px-2 py-0.5 rounded font-mono"
                style={{ background: "#0d0d18", color: "#f59e0b", border: "1px solid #2a1a00" }}>
                {v}
              </code>
            </div>
          ))}
          <p className="text-[10px] text-gray-700 mt-2 leading-relaxed">
            Ajoutez ces variables dans{" "}
            <code className="text-indigo-400">backend/.env</code>
            {" "}(voir <code className="text-indigo-400">.env.example</code>)
          </p>
        </div>
      )}
    </div>
  );
}

export function ApiStatusPanel({ onClose }: { onClose: () => void }) {
  const [data, setData]       = useState<ApiStatusData | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res  = await fetch(`${API_URL}/api/status`, { cache: "no-store" });
      const json = await res.json();
      setData(json);
    } catch {
      /* silencieux */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.75)" }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl overflow-hidden"
        style={{ background: "#0a0a14", border: "1px solid #1e1e2e" }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4"
          style={{ borderBottom: "1px solid #1e1e2e", background: "#0d0d18" }}>
          <div>
            <p className="font-black text-white text-sm">⚙️ API Status</p>
            <p className="text-[10px] text-gray-600 mt-0.5">État des connexions aux APIs externes</p>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={load} disabled={loading}
              className="text-xs text-gray-500 hover:text-gray-300 transition-colors px-2 py-1 rounded"
              style={{ border: "1px solid #1e1e2a" }}>
              {loading ? "…" : "🔄"}
            </button>
            <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors text-lg leading-none">✕</button>
          </div>
        </div>

        <div className="px-5 pb-5">
          {loading && !data && (
            <div className="py-8 text-center text-gray-600 text-sm">Vérification en cours…</div>
          )}

          {data && (
            <>
              {/* Statut APIs */}
              <StatusRow
                label="𝕏  Twitter / X"
                ok={data.twitter.configured}
                missing={data.twitter.missing_vars}
              />
              <StatusRow
                label="🔴  Reddit"
                ok={data.reddit.configured}
                missing={data.reddit.missing_vars}
              />

              {/* Cache sentiment */}
              <div className="pt-3">
                <p className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-2">Cache Sentiment</p>
                {data.sentiment_cache.entries === 0 ? (
                  <p className="text-xs text-gray-600">Aucune donnée en cache</p>
                ) : (
                  <>
                    <p className="text-xs text-gray-500 mb-2">
                      {data.sentiment_cache.entries} ticker{data.sentiment_cache.entries > 1 ? "s" : ""} en cache
                      · TTL {data.sentiment_cache.ttl_minutes} min
                    </p>
                    <div className="rounded-xl overflow-hidden" style={{ border: "1px solid #1e1e2a" }}>
                      <table className="w-full">
                        <thead style={{ background: "#0d0d18" }}>
                          <tr>
                            {["Ticker", "Âge", "Expire dans"].map(h => (
                              <th key={h} className="px-3 py-2 text-left text-[10px] font-semibold text-gray-600 uppercase tracking-wider">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {data.sentiment_cache.tickers.map(t => (
                            <tr key={t.ticker} style={{ borderTop: "1px solid #1a1a28" }}>
                              <td className="px-3 py-2 font-bold text-white text-xs">{t.ticker}</td>
                              <td className="px-3 py-2 text-xs text-gray-500">{t.age_minutes.toFixed(1)} min</td>
                              <td className="px-3 py-2 text-xs"
                                style={{ color: t.expires_in > 10 ? "#4ade80" : "#f59e0b" }}>
                                {t.expires_in > 0 ? `${t.expires_in.toFixed(0)} min` : "Expiré"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </div>

              {/* Guide rapide si non configuré */}
              {!data.all_configured && (
                <div className="mt-4 rounded-xl p-4 space-y-2"
                  style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
                  <p className="text-xs font-bold text-gray-400">📋 Guide de configuration</p>
                  <ol className="text-[11px] text-gray-600 space-y-1 list-decimal list-inside">
                    <li>Copiez <code className="text-indigo-400">backend/.env.example</code> → <code className="text-indigo-400">backend/.env</code></li>
                    {!data.reddit.configured && (
                      <li>Reddit : créez une app sur <code className="text-indigo-400">reddit.com/prefs/apps</code> (type : script)</li>
                    )}
                    {!data.twitter.configured && (
                      <li>Twitter : créez un projet sur <code className="text-indigo-400">developer.twitter.com</code> (plan Basic minimum)</li>
                    )}
                    <li>Redémarrez le backend après avoir rempli le <code className="text-indigo-400">.env</code></li>
                  </ol>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
