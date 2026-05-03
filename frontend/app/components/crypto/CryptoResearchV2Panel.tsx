"use client";

import { CryptoRegimeEngine } from "../../types";
import { getCryptoResearchV2Summary } from "../../lib/cryptoResearchV2";
import { formatCryptoPrice } from "../../lib/cryptoFormat";

export function CryptoResearchV2Panel({ regime }: { regime: CryptoRegimeEngine | null }) {
  const summary = getCryptoResearchV2Summary();
  const btcUp = (regime?.btc_price ?? 0) > (regime?.btc_sma200 ?? 0);
  const ethUp = (regime?.eth_price ?? 0) > (regime?.eth_sma200 ?? 0);
  const researchAllowed = ["CRYPTO_BULL", "CRYPTO_PULLBACK"].includes(regime?.crypto_regime ?? "");

  const cards = [
    {
      label: "Core Watchlist",
      value: summary.coreCount,
      tone: "#4ade80",
      note: "BTC, ETH, SOL, BNB, LINK",
    },
    {
      label: "Promising Research",
      value: summary.promisingCount,
      tone: "#7dd3fc",
      note: "AVAX, ARB, DOGE, INJ",
    },
    {
      label: "Speculative Watchlist",
      value: summary.speculativeCount,
      tone: "#fde047",
      note: "Daily / 4H timing only",
    },
    {
      label: "Avoid / Blocked",
      value: summary.avoidCount,
      tone: "#f87171",
      note: "OP, SEI, POL",
    },
  ];

  return (
    <div
      className="rounded-2xl p-5 mb-4 space-y-5 shadow-[0_0_0_1px_rgba(34,211,238,0.08)]"
      style={{ background: "linear-gradient(180deg, #081018 0%, #070b14 100%)", border: "1px solid #1f3b5a" }}
    >
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.3em] text-cyan-300">
            Crypto Research V2 - Research Only
          </p>
          <h3 className="text-lg font-black text-white mt-1">
            Ce modèle n&apos;autorise aucun trade
          </h3>
          <p className="text-xs text-cyan-100/70 mt-1 max-w-2xl">
            Crypto Research V2 est un modèle de recherche. Il n&apos;autorise pas les trades.
            Les décisions restent basées sur le moteur officiel.
          </p>
        </div>
        <div
          className="rounded-full px-3 py-1 text-[10px] font-black uppercase tracking-widest"
          style={{ background: researchAllowed ? "#052e16" : "#2a0d0d", color: researchAllowed ? "#4ade80" : "#fca5a5" }}
        >
          {researchAllowed ? "Recherche autorisée" : "Observation seulement"}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {cards.map((card) => (
          <div key={card.label} className="rounded-xl p-3" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
            <p className="text-[9px] text-gray-600 uppercase tracking-widest">{card.label}</p>
            <p className="text-lg font-black text-white mt-1" style={{ color: card.tone }}>
              {card.value}
            </p>
            <p className="text-[10px] text-gray-500 mt-1">{card.note}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="rounded-xl p-3" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
          <p className="text-[9px] text-gray-600 uppercase tracking-widest">Régime crypto actuel</p>
          <p className="text-sm font-black text-white mt-1">{regime?.regime_label ?? "—"}</p>
          <p className="text-[10px] text-gray-500 mt-1">{regime?.crypto_regime ?? "—"}</p>
          <p className="text-[10px] text-gray-500 mt-1">{researchAllowed ? "Recherche autorisée" : "Observation uniquement"}</p>
        </div>
        <div className="rounded-xl p-3" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
          <p className="text-[9px] text-gray-600 uppercase tracking-widest">BTC / ETH prices</p>
          <p className="text-sm font-black text-white mt-1">BTC {regime?.btc_price ? `$${formatCryptoPrice("BTC", regime.btc_price)}` : "—"}</p>
          <p className="text-[10px] text-gray-500 mt-1">ETH {regime?.eth_price ? `$${formatCryptoPrice("ETH", regime.eth_price)}` : "—"}</p>
        </div>
        <div className="rounded-xl p-3" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
          <p className="text-[9px] text-gray-600 uppercase tracking-widest">BTC / ETH trend</p>
          <p className="text-sm font-black mt-1" style={{ color: btcUp ? "#4ade80" : "#f87171" }}>
            BTC {btcUp ? "above" : "below"} SMA200
          </p>
          <p className="text-[10px] mt-1" style={{ color: ethUp ? "#4ade80" : "#f87171" }}>
            ETH {ethUp ? "above" : "below"} SMA200
          </p>
        </div>
      </div>

      <div className="rounded-xl p-3 text-xs" style={{ background: "#0c1220", border: "1px solid #1d4ed844" }}>
        <p className="font-black uppercase tracking-widest text-sky-300 mb-2">Discipline</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sky-100/80">
          <span>• CRYPTO_BEAR = observation uniquement</span>
          <span>• Daily = signal principal</span>
          <span>• 4H = timing seulement</span>
          <span>• Week-end = taille réduite / prudence</span>
        </div>
      </div>
    </div>
  );
}
