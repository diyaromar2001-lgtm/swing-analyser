"use client";

import { useState, useEffect, useCallback } from "react";
import { SentimentResult } from "../types";
import { getApiUrl } from "../lib/api";

const API_URL = getApiUrl();

// ── Score Ring (arc SVG simple) ───────────────────────────────────────────────

function ScoreRing({ score, size = 52 }: { score: number; size?: number }) {
  const r    = size * 0.38;
  const cx   = size / 2;
  const cy   = size / 2;
  const circ = 2 * Math.PI * r;
  const pct  = score / 10;
  const arc  = pct * circ * 0.75;

  const color =
    score >= 7.5 ? "#4ade80" :
    score >= 5.5 ? "#818cf8" :
    score >= 4.0 ? "#f59e0b" :
                   "#f87171";

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="#1e1e2a" strokeWidth={size * 0.1}
          strokeDasharray={`${circ * 0.75} ${circ}`}
          style={{ transform: `rotate(-225deg)`, transformOrigin: `${cx}px ${cy}px` }}
          strokeLinecap="round" />
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeWidth={size * 0.1}
          strokeDasharray={`${arc} ${circ}`}
          style={{ transform: `rotate(-225deg)`, transformOrigin: `${cx}px ${cy}px`, transition: "stroke-dasharray .5s ease" }}
          strokeLinecap="round" />
      </svg>
      <div className="absolute text-center leading-none">
        <p className="font-black" style={{ fontSize: size * 0.22, color }}>{score.toFixed(1)}</p>
        <p className="text-gray-600" style={{ fontSize: size * 0.13 }}>/10</p>
      </div>
    </div>
  );
}

// ── Barre score source ────────────────────────────────────────────────────────

function SourceBar({
  label,
  score,
  error,
  emoji,
}: {
  label: string;
  score: number;
  error?: string | null;
  emoji: string;
}) {
  const color =
    error ? "#374151" :
    score >= 7 ? "#4ade80" :
    score >= 5 ? "#818cf8" :
    score >= 3.5 ? "#f59e0b" :
                   "#f87171";

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-gray-500 flex items-center gap-1.5">
          <span>{emoji}</span>{label}
          {error && (
            <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: "#1a0a00", color: "#f59e0b" }}>
              {error.length > 40 ? error.slice(0, 40) + "…" : error}
            </span>
          )}
        </span>
        <span className="text-xs font-bold tabular-nums" style={{ color: error ? "#4b5563" : color }}>
          {error ? "N/A" : `${score.toFixed(1)}/10`}
        </span>
      </div>
      <div className="h-1.5 rounded-full" style={{ background: "#1a1a28" }}>
        {!error && (
          <div
            className="h-full rounded-full transition-all duration-700"
            style={{ width: `${score * 10}%`, background: color }}
          />
        )}
      </div>
    </div>
  );
}

// ── Badge hype / label ────────────────────────────────────────────────────────

function HypeBadge({ risk }: { risk: "Low" | "Medium" | "High" }) {
  const cfg = {
    Low:    { bg: "#052e16", text: "#4ade80", label: "🟢 Hype Low"    },
    Medium: { bg: "#1c1500", text: "#fde047", label: "🟡 Hype Medium" },
    High:   { bg: "#1f0909", text: "#f87171", label: "🔴 Hype High"   },
  }[risk];
  return (
    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full"
      style={{ background: cfg.bg, color: cfg.text, border: `1px solid ${cfg.text}33` }}>
      {cfg.label}
    </span>
  );
}

function LabelBadge({ label }: { label: SentimentResult["sentiment_label"] }) {
  const cfg = {
    "Very Bullish": { bg: "#052e16", text: "#4ade80"  },
    "Bullish":      { bg: "#0a1a0a", text: "#86efac"  },
    "Neutral":      { bg: "#0f0f20", text: "#818cf8"  },
    "Bearish":      { bg: "#1a0e00", text: "#f59e0b"  },
    "Very Bearish": { bg: "#1f0909", text: "#f87171"  },
  }[label] ?? { bg: "#0f0f20", text: "#818cf8" };
  return (
    <span className="text-xs font-bold px-2 py-0.5 rounded"
      style={{ background: cfg.bg, color: cfg.text, border: `1px solid ${cfg.text}33` }}>
      {label}
    </span>
  );
}

// ── Panel principal ───────────────────────────────────────────────────────────

interface SentimentPanelProps {
  ticker: string;
  /** Mode compact pour la colonne du tableau */
  compact?: boolean;
}

export function SentimentPanel({ ticker, compact = false }: SentimentPanelProps) {
  const [data, setData]       = useState<SentimentResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const fetch_ = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res  = await fetch(`${API_URL}/api/social-sentiment?ticker=${ticker}`, { cache: "no-store" });
      const json = await res.json();
      if (json && typeof json.sentiment_score === "number") {
        setData(json as SentimentResult);
      } else {
        setError(json?.detail ?? "Réponse inattendue du backend");
      }
    } catch (e) {
      setError("Impossible de contacter le backend");
    } finally {
      setLoading(false);
    }
  }, [ticker]);

  useEffect(() => {
    fetch_();
  }, [fetch_]);

  // ── Compact (colonne tableau) ──
  if (compact) {
    if (loading) {
      return (
        <div className="flex items-center gap-1 px-2 py-1 rounded text-xs" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
          <svg className="animate-spin h-3 w-3 text-indigo-400" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span className="text-gray-600">…</span>
        </div>
      );
    }
    if (!data) return <span className="text-xs text-gray-700">—</span>;

    const score = data.sentiment_score;
    const color =
      score >= 7.5 ? "#4ade80" :
      score >= 5.5 ? "#818cf8" :
      score >= 4.0 ? "#f59e0b" :
                     "#f87171";
    return (
      <div className="flex flex-col items-center gap-0.5">
        <span className="text-sm font-black tabular-nums" style={{ color }}>{score.toFixed(1)}</span>
        <span className="text-[9px] text-gray-600">/10</span>
        {data.hype_risk === "High" && <span className="text-[9px]" title="Hype élevée">⚠️</span>}
      </div>
    );
  }

  // ── Full (dans TradePlan) ──

  if (loading) {
    return (
      <div className="rounded-xl p-4 space-y-3" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
        <div className="flex items-center gap-2">
          <svg className="animate-spin h-4 w-4 text-indigo-400" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <p className="text-xs text-gray-500">Analyse du sentiment social en cours…</p>
        </div>
        {[1, 2, 3].map(i => (
          <div key={i} className="h-3 rounded animate-pulse" style={{ background: "#1a1a28", width: `${60 + i * 12}%` }} />
        ))}
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-xl p-4 flex items-center gap-3" style={{ background: "#140808", border: "1px solid #7f1d1d33" }}>
        <span className="text-red-500">✗</span>
        <p className="text-xs text-gray-500">{error ?? "Données indisponibles"}</p>
        <button onClick={fetch_} className="ml-auto text-xs text-indigo-400 hover:text-indigo-300">Réessayer</button>
      </div>
    );
  }

  const twitterUnconfigured = !!(data.twitter_error?.includes("not configured"));
  const redditUnconfigured  = !!(data.reddit_error?.includes("not configured"));
  const bothUnavailable     = twitterUnconfigured && redditUnconfigured;

  if (bothUnavailable) {
    // Liste précise des clés manquantes
    const missing: string[] = [];
    if (twitterUnconfigured) missing.push("X_BEARER_TOKEN");
    if (redditUnconfigured)  missing.push("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT");

    return (
      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid #2a1a00" }}>
        <div className="px-4 py-3 flex items-center gap-2" style={{ background: "#1a0e00", borderBottom: "1px solid #2a1a00" }}>
          <span>💬</span>
          <p className="text-xs font-bold text-amber-500">Social Sentiment — APIs non configurées</p>
        </div>
        <div className="px-4 py-4 space-y-3" style={{ background: "#0a0a14" }}>
          <p className="text-xs text-gray-500 leading-relaxed">
            Ajoutez les variables suivantes dans <code className="text-indigo-400">backend/.env</code> pour activer cette fonctionnalité :
          </p>
          <div className="space-y-1.5">
            {missing.map(v => (
              <div key={v} className="flex items-center gap-2">
                <span className="text-red-500 text-xs">✗</span>
                <code className="text-xs px-2 py-0.5 rounded font-mono"
                  style={{ background: "#0d0d18", color: "#f59e0b", border: "1px solid #2a1a00" }}>
                  {v}
                </code>
              </div>
            ))}
          </div>
          <p className="text-[10px] text-gray-700">
            Voir <code className="text-indigo-400">.env.example</code> pour les instructions.
            Reddit est gratuit · Twitter nécessite le plan Basic ($100/mois).
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl overflow-hidden" style={{ border: "1px solid #1e1e2a" }}>

      {/* Header */}
      <div className="px-4 py-3 flex items-center gap-3" style={{ background: "#0d0d18", borderBottom: "1px solid #1e1e2a" }}>
        <span className="text-sm">💬</span>
        <p className="text-xs font-bold text-gray-300">Social Sentiment</p>
        {data.cached && (
          <span className="text-[10px] text-gray-600 ml-auto">🕐 Cache</span>
        )}
        <button onClick={fetch_} className="text-[10px] text-gray-600 hover:text-gray-300 transition-colors ml-auto">🔄</button>
      </div>

      <div className="px-4 py-4 space-y-4" style={{ background: "#0a0a14" }}>

        {/* Score global + label */}
        <div className="flex items-center gap-4">
          <ScoreRing score={data.sentiment_score} size={56} />
          <div>
            <p className="text-xs text-gray-500 mb-1">Score global pondéré</p>
            <div className="flex items-center gap-2 flex-wrap">
              <LabelBadge label={data.sentiment_label} />
              <HypeBadge risk={data.hype_risk} />
            </div>
            <p className="text-[10px] text-gray-600 mt-1.5">
              {data.mention_volume} mentions · Tendance : <span className="text-gray-400">{data.sentiment_trend}</span>
              {data.divergence && <span className="text-amber-500 ml-1">⚠️ Divergence</span>}
            </p>
          </div>
        </div>

        {/* Scores par source */}
        <div className="space-y-2.5">
          <SourceBar
            label="X / Twitter"
            score={data.twitter_score}
            error={data.twitter_error}
            emoji="𝕏"
          />
          <SourceBar
            label="Reddit"
            score={data.reddit_score}
            error={data.reddit_error}
            emoji="🔴"
          />
        </div>

        {/* Impact */}
        <div className="rounded-lg px-3 py-2.5 text-xs leading-relaxed"
          style={{ background: "#0f0f1e", border: "1px solid #1e1e2e" }}>
          <p className="font-bold text-gray-300 mb-1">Impact sur le signal</p>
          <p className="text-gray-400">{data.impact_on_trade_signal}</p>
        </div>

        {/* Résumé */}
        <p className="text-[11px] text-gray-500 leading-relaxed">{data.summary ?? ""}</p>

        {/* Disclaimer */}
        <p className="text-[10px] text-gray-700 italic">
          Le sentiment social est indicatif uniquement. Ne jamais acheter sur la seule base du sentiment.
        </p>

      </div>
    </div>
  );
}

// ── Version inline pour le tableau (chargement au clic) ──────────────────────

export function SentimentCell({ ticker, apisConfigured = true }: { ticker: string; apisConfigured?: boolean }) {
  const [data, setData]    = useState<SentimentResult | null>(null);
  const [loading, setLoad] = useState(false);
  const [tried, setTried]  = useState(false);

  const load = useCallback(async () => {
    if (data || loading || !apisConfigured) return;
    setLoad(true);
    setTried(true);
    try {
      const res  = await fetch(`${API_URL}/api/social-sentiment?ticker=${ticker}`);
      const json = await res.json();
      if (json && typeof json.sentiment_score === "number") {
        setData(json);
      }
    } catch {
      /* silencieux */
    } finally {
      setLoad(false);
    }
  }, [ticker, data, loading, apisConfigured]);

  // APIs non configurées → texte explicite
  if (!apisConfigured) {
    return (
      <span className="text-[10px] text-gray-700 whitespace-nowrap" title="Configurez les clés API dans le panneau ⚙️ API Status">
        ⚙️ Non conf.
      </span>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center">
        <svg className="animate-spin h-3.5 w-3.5 text-indigo-400" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      </div>
    );
  }

  if (data) {
    const score = data.sentiment_score;
    const color =
      score >= 7.5 ? "#4ade80" :
      score >= 5.5 ? "#818cf8" :
      score >= 4.0 ? "#f59e0b" :
                     "#f87171";
    return (
      <div
        className="flex flex-col items-center gap-0.5"
        title={`${data.sentiment_label ?? ""} — ${(data.summary ?? "").slice(0, 80)}…`}
      >
        <span className="text-sm font-black tabular-nums leading-none" style={{ color }}>{score.toFixed(1)}</span>
        <span className="text-[9px] text-gray-600">/10</span>
        {data.hype_risk === "High" && <span className="text-[9px]">⚠️</span>}
      </div>
    );
  }

  return (
    <button
      onClick={load}
      className="text-xs px-2 py-1 rounded font-medium transition-all hover:opacity-80"
      style={{ background: "#0d0d18", border: "1px solid #1e1e2a", color: "#4b5563" }}
      title="Charger le sentiment social"
    >
      💬
    </button>
  );
}
