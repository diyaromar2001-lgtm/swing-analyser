export type CryptoResearchBucket = "CORE_WATCHLIST" | "PROMISING_RESEARCH" | "SPECULATIVE_WATCHLIST" | "AVOID_BLOCKED";
export type CryptoResearchStatus = "RESEARCH_ONLY" | "WATCHLIST_ONLY" | "BLOCKED_REGIME" | "INSUFFICIENT_SAMPLE" | "OVERFIT_RISK" | "AVOID";
export type CryptoResearchWeekendRisk = "REDUCED" | "BLOCKED";
export type CryptoResearchSampleStatus = "SAMPLED_OK" | "INSUFFICIENT_SAMPLE";

export interface CryptoResearchV2Row {
  symbol: string;
  bucket: CryptoResearchBucket;
  score: number;
  bestStrategy: string;
  bestRegime: string;
  timeframe: string;
  rsVsBtc: number | null;
  rsVsEth: number | null;
  liquidity: number | null;
  weekendRisk: CryptoResearchWeekendRisk;
  overfitRisk: boolean;
  sampleStatus: CryptoResearchSampleStatus;
  researchStatus: CryptoResearchStatus;
  notes: string;
}

export const CRYPTO_RESEARCH_V2_ROWS: CryptoResearchV2Row[] = [
  {
    "symbol": "BTC",
    "bucket": "CORE_WATCHLIST",
    "score": 75.2,
    "bestStrategy": "BTC/ETH Regime Pullback",
    "bestRegime": "CRYPTO_BULL / CRYPTO_PULLBACK",
    "timeframe": "daily + 4H timing",
    "rsVsBtc": 0.0,
    "rsVsEth": 0.0411,
    "liquidity": 100,
    "weekendRisk": "REDUCED",
    "overfitRisk": false,
    "sampleStatus": "SAMPLED_OK",
    "researchStatus": "RESEARCH_ONLY",
    "notes": "ancre de régime, ultra-liquide, cœur du système"
  },
  {
    "symbol": "ETH",
    "bucket": "CORE_WATCHLIST",
    "score": 52.4,
    "bestStrategy": "BTC/ETH Regime Pullback",
    "bestRegime": "CRYPTO_BULL / CRYPTO_PULLBACK",
    "timeframe": "daily + 4H timing",
    "rsVsBtc": -0.0411,
    "rsVsEth": 0.0,
    "liquidity": 100,
    "weekendRisk": "REDUCED",
    "overfitRisk": true,
    "sampleStatus": "SAMPLED_OK",
    "researchStatus": "OVERFIT_RISK",
    "notes": "ancre de régime, edge faible dans ce pass"
  },
  {
    "symbol": "SOL",
    "bucket": "CORE_WATCHLIST",
    "score": 52.5,
    "bestStrategy": "Alt RS Rotation",
    "bestRegime": "CRYPTO_BULL / CRYPTO_PULLBACK",
    "timeframe": "daily + 4H timing",
    "rsVsBtc": -0.1279,
    "rsVsEth": -0.0868,
    "liquidity": 100,
    "weekendRisk": "REDUCED",
    "overfitRisk": false,
    "sampleStatus": "SAMPLED_OK",
    "researchStatus": "RESEARCH_ONLY",
    "notes": "bon candidat swing mais dépendant du régime"
  },
  {
    "symbol": "BNB",
    "bucket": "CORE_WATCHLIST",
    "score": 60.2,
    "bestStrategy": "Alt RS Rotation",
    "bestRegime": "CRYPTO_BULL / CRYPTO_PULLBACK",
    "timeframe": "daily",
    "rsVsBtc": -0.1219,
    "rsVsEth": -0.0808,
    "liquidity": 100,
    "weekendRisk": "REDUCED",
    "overfitRisk": false,
    "sampleStatus": "SAMPLED_OK",
    "researchStatus": "RESEARCH_ONLY",
    "notes": "liquide mais setup fragile"
  },
  {
    "symbol": "LINK",
    "bucket": "CORE_WATCHLIST",
    "score": 52.9,
    "bestStrategy": "Alt RS Rotation",
    "bestRegime": "CRYPTO_BULL / CRYPTO_PULLBACK",
    "timeframe": "daily + 4H timing",
    "rsVsBtc": -0.1177,
    "rsVsEth": -0.0766,
    "liquidity": 100,
    "weekendRisk": "REDUCED",
    "overfitRisk": false,
    "sampleStatus": "SAMPLED_OK",
    "researchStatus": "RESEARCH_ONLY",
    "notes": "bon symbole swing, dépendance BTC/ETH élevée"
  },
  {
    "symbol": "AVAX",
    "bucket": "PROMISING_RESEARCH",
    "score": 62.8,
    "bestStrategy": "Alt RS Rotation",
    "bestRegime": "CRYPTO_BULL / CRYPTO_PULLBACK",
    "timeframe": "daily + 4H timing",
    "rsVsBtc": -0.1562,
    "rsVsEth": -0.1152,
    "liquidity": 100,
    "weekendRisk": "REDUCED",
    "overfitRisk": true,
    "sampleStatus": "SAMPLED_OK",
    "researchStatus": "RESEARCH_ONLY",
    "notes": "intéressant mais sample mince"
  },
  {
    "symbol": "ARB",
    "bucket": "PROMISING_RESEARCH",
    "score": 68.5,
    "bestStrategy": "Alt RS Rotation",
    "bestRegime": "CRYPTO_BULL / CRYPTO_PULLBACK",
    "timeframe": "daily + 4H timing",
    "rsVsBtc": 0.1031,
    "rsVsEth": 0.1442,
    "liquidity": 51.6,
    "weekendRisk": "REDUCED",
    "overfitRisk": true,
    "sampleStatus": "SAMPLED_OK",
    "researchStatus": "RESEARCH_ONLY",
    "notes": "très intéressant mais micro-échantillon"
  },
  {
    "symbol": "DOGE",
    "bucket": "PROMISING_RESEARCH",
    "score": 72.9,
    "bestStrategy": "Alt RS Rotation",
    "bestRegime": "CRYPTO_BULL / CRYPTO_PULLBACK",
    "timeframe": "daily only",
    "rsVsBtc": 0.0084,
    "rsVsEth": 0.0494,
    "liquidity": 80.1,
    "weekendRisk": "REDUCED",
    "overfitRisk": true,
    "sampleStatus": "SAMPLED_OK",
    "researchStatus": "RESEARCH_ONLY",
    "notes": "potentiel mais pump/chase risk"
  },
  {
    "symbol": "INJ",
    "bucket": "PROMISING_RESEARCH",
    "score": 62.0,
    "bestStrategy": "Alt RS Rotation",
    "bestRegime": "CRYPTO_BULL / CRYPTO_PULLBACK",
    "timeframe": "daily + 4H timing",
    "rsVsBtc": 0.1739,
    "rsVsEth": 0.215,
    "liquidity": 83.1,
    "weekendRisk": "REDUCED",
    "overfitRisk": true,
    "sampleStatus": "SAMPLED_OK",
    "researchStatus": "RESEARCH_ONLY",
    "notes": "bon profil swing mais instable"
  },
  {
    "symbol": "TON",
    "bucket": "SPECULATIVE_WATCHLIST",
    "score": 58.3,
    "bestStrategy": "Alt RS Rotation / Range probe",
    "bestRegime": "CRYPTO_RANGE",
    "timeframe": "daily only",
    "rsVsBtc": -0.0889,
    "rsVsEth": -0.0478,
    "liquidity": 84.1,
    "weekendRisk": "REDUCED",
    "overfitRisk": false,
    "sampleStatus": "INSUFFICIENT_SAMPLE",
    "researchStatus": "WATCHLIST_ONLY",
    "notes": "comportement idiosyncratique, data plus courte"
  },
  {
    "symbol": "UNI",
    "bucket": "SPECULATIVE_WATCHLIST",
    "score": 58.2,
    "bestStrategy": "Alt RS Rotation",
    "bestRegime": "CRYPTO_BULL / CRYPTO_PULLBACK",
    "timeframe": "daily + 4H timing",
    "rsVsBtc": -0.1518,
    "rsVsEth": -0.1108,
    "liquidity": 93.4,
    "weekendRisk": "REDUCED",
    "overfitRisk": false,
    "sampleStatus": "INSUFFICIENT_SAMPLE",
    "researchStatus": "WATCHLIST_ONLY",
    "notes": "petit échantillon mais comportement propre"
  },
  {
    "symbol": "ICP",
    "bucket": "SPECULATIVE_WATCHLIST",
    "score": 57.0,
    "bestStrategy": "Alt RS Rotation",
    "bestRegime": "CRYPTO_BULL / CRYPTO_PULLBACK",
    "timeframe": "daily + 4H timing",
    "rsVsBtc": -0.1482,
    "rsVsEth": -0.1071,
    "liquidity": 77.5,
    "weekendRisk": "REDUCED",
    "overfitRisk": false,
    "sampleStatus": "INSUFFICIENT_SAMPLE",
    "researchStatus": "WATCHLIST_ONLY",
    "notes": "liquidité correcte, edge pas encore solide"
  },
  {
    "symbol": "DOT",
    "bucket": "SPECULATIVE_WATCHLIST",
    "score": 51.5,
    "bestStrategy": "Alt RS Rotation",
    "bestRegime": "CRYPTO_BULL / CRYPTO_PULLBACK",
    "timeframe": "daily only",
    "rsVsBtc": -0.1967,
    "rsVsEth": -0.1557,
    "liquidity": 82.9,
    "weekendRisk": "REDUCED",
    "overfitRisk": false,
    "sampleStatus": "INSUFFICIENT_SAMPLE",
    "researchStatus": "WATCHLIST_ONLY",
    "notes": "parfois intéressant mais peu robuste"
  },
  {
    "symbol": "ADA",
    "bucket": "SPECULATIVE_WATCHLIST",
    "score": 46.8,
    "bestStrategy": "Alt RS Rotation",
    "bestRegime": "CRYPTO_BULL / CRYPTO_PULLBACK",
    "timeframe": "daily only",
    "rsVsBtc": -0.1558,
    "rsVsEth": -0.1147,
    "liquidity": 76.0,
    "weekendRisk": "REDUCED",
    "overfitRisk": false,
    "sampleStatus": "INSUFFICIENT_SAMPLE",
    "researchStatus": "WATCHLIST_ONLY",
    "notes": "correct mais pas assez fort"
  },
  {
    "symbol": "NEAR",
    "bucket": "SPECULATIVE_WATCHLIST",
    "score": 48.6,
    "bestStrategy": "Alt RS Rotation",
    "bestRegime": "CRYPTO_BULL / CRYPTO_PULLBACK",
    "timeframe": "daily + 4H timing",
    "rsVsBtc": -0.1228,
    "rsVsEth": -0.0817,
    "liquidity": 84.3,
    "weekendRisk": "REDUCED",
    "overfitRisk": false,
    "sampleStatus": "SAMPLED_OK",
    "researchStatus": "WATCHLIST_ONLY",
    "notes": "intéressant mais pas validé"
  },
  {
    "symbol": "XRP",
    "bucket": "SPECULATIVE_WATCHLIST",
    "score": 54.2,
    "bestStrategy": "Alt RS Rotation",
    "bestRegime": "CRYPTO_BULL / CRYPTO_PULLBACK",
    "timeframe": "daily only",
    "rsVsBtc": -0.1175,
    "rsVsEth": -0.0764,
    "liquidity": 100,
    "weekendRisk": "REDUCED",
    "overfitRisk": false,
    "sampleStatus": "SAMPLED_OK",
    "researchStatus": "WATCHLIST_ONLY",
    "notes": "très corrélé au marché, edge faible"
  },
  {
    "symbol": "LTC",
    "bucket": "SPECULATIVE_WATCHLIST",
    "score": 53.3,
    "bestStrategy": "Alt RS Rotation",
    "bestRegime": "CRYPTO_BULL / CRYPTO_PULLBACK",
    "timeframe": "daily only",
    "rsVsBtc": -0.1358,
    "rsVsEth": -0.0947,
    "liquidity": 100,
    "weekendRisk": "REDUCED",
    "overfitRisk": false,
    "sampleStatus": "SAMPLED_OK",
    "researchStatus": "WATCHLIST_ONLY",
    "notes": "liquidité OK, signal faible"
  },
  {
    "symbol": "BCH",
    "bucket": "SPECULATIVE_WATCHLIST",
    "score": 49.5,
    "bestStrategy": "BTC/ETH pullback probe",
    "bestRegime": "CRYPTO_BULL / CRYPTO_PULLBACK",
    "timeframe": "daily only",
    "rsVsBtc": -0.173,
    "rsVsEth": -0.1319,
    "liquidity": 100,
    "weekendRisk": "REDUCED",
    "overfitRisk": false,
    "sampleStatus": "SAMPLED_OK",
    "researchStatus": "WATCHLIST_ONLY",
    "notes": "pas assez convaincant"
  },
  {
    "symbol": "SUI",
    "bucket": "SPECULATIVE_WATCHLIST",
    "score": 43.9,
    "bestStrategy": "Alt RS Rotation",
    "bestRegime": "CRYPTO_BULL / CRYPTO_PULLBACK",
    "timeframe": "daily + 4H timing",
    "rsVsBtc": -0.1186,
    "rsVsEth": -0.0775,
    "liquidity": 87.2,
    "weekendRisk": "REDUCED",
    "overfitRisk": false,
    "sampleStatus": "SAMPLED_OK",
    "researchStatus": "WATCHLIST_ONLY",
    "notes": "fragile / dépendant du régime"
  },
  {
    "symbol": "ATOM",
    "bucket": "SPECULATIVE_WATCHLIST",
    "score": 42.8,
    "bestStrategy": "Range probe",
    "bestRegime": "CRYPTO_RANGE",
    "timeframe": "daily only",
    "rsVsBtc": -0.0597,
    "rsVsEth": -0.0186,
    "liquidity": 75.5,
    "weekendRisk": "REDUCED",
    "overfitRisk": false,
    "sampleStatus": "SAMPLED_OK",
    "researchStatus": "WATCHLIST_ONLY",
    "notes": "faible edge"
  },
  {
    "symbol": "FIL",
    "bucket": "SPECULATIVE_WATCHLIST",
    "score": 40.3,
    "bestStrategy": "Range probe",
    "bestRegime": "CRYPTO_RANGE",
    "timeframe": "daily only",
    "rsVsBtc": -0.0669,
    "rsVsEth": -0.0259,
    "liquidity": 74.0,
    "weekendRisk": "REDUCED",
    "overfitRisk": false,
    "sampleStatus": "SAMPLED_OK",
    "researchStatus": "WATCHLIST_ONLY",
    "notes": "fragile"
  },
  {
    "symbol": "APT",
    "bucket": "SPECULATIVE_WATCHLIST",
    "score": 38.6,
    "bestStrategy": "Alt RS Rotation",
    "bestRegime": "CRYPTO_BULL / CRYPTO_PULLBACK",
    "timeframe": "daily + 4H timing",
    "rsVsBtc": -0.0022,
    "rsVsEth": 0.0389,
    "liquidity": 69.8,
    "weekendRisk": "REDUCED",
    "overfitRisk": false,
    "sampleStatus": "INSUFFICIENT_SAMPLE",
    "researchStatus": "WATCHLIST_ONLY",
    "notes": "pas encore propre"
  },
  {
    "symbol": "OP",
    "bucket": "AVOID_BLOCKED",
    "score": 31.8,
    "bestStrategy": "Alt RS Rotation",
    "bestRegime": "CRYPTO_BULL / CRYPTO_PULLBACK",
    "timeframe": "daily + 4H timing",
    "rsVsBtc": -0.0675,
    "rsVsEth": -0.0265,
    "liquidity": 47.2,
    "weekendRisk": "BLOCKED",
    "overfitRisk": true,
    "sampleStatus": "INSUFFICIENT_SAMPLE",
    "researchStatus": "AVOID",
    "notes": "trop faible"
  },
  {
    "symbol": "SEI",
    "bucket": "AVOID_BLOCKED",
    "score": 30.2,
    "bestStrategy": "Alt RS Rotation",
    "bestRegime": "CRYPTO_BULL / CRYPTO_PULLBACK",
    "timeframe": "daily + 4H timing",
    "rsVsBtc": -0.101,
    "rsVsEth": -0.06,
    "liquidity": 32.2,
    "weekendRisk": "BLOCKED",
    "overfitRisk": true,
    "sampleStatus": "INSUFFICIENT_SAMPLE",
    "researchStatus": "AVOID",
    "notes": "trop faible / trop bruité"
  },
  {
    "symbol": "POL",
    "bucket": "AVOID_BLOCKED",
    "score": 18.0,
    "bestStrategy": "Avoid",
    "bestRegime": "CRYPTO_BULL / CRYPTO_PULLBACK",
    "timeframe": "daily only",
    "rsVsBtc": -0.1539,
    "rsVsEth": -0.1128,
    "liquidity": 0,
    "weekendRisk": "BLOCKED",
    "overfitRisk": true,
    "sampleStatus": "INSUFFICIENT_SAMPLE",
    "researchStatus": "AVOID",
    "notes": "données / volume / 4H faibles"
  }
];

export const CRYPTO_RESEARCH_V2_BY_SYMBOL: Record<string, CryptoResearchV2Row> = Object.fromEntries(
  CRYPTO_RESEARCH_V2_ROWS.map((row) => [row.symbol, row])
) as Record<string, CryptoResearchV2Row>;

export function getCryptoResearchV2Row(symbol: string | null | undefined) {
  if (!symbol) return null;
  return CRYPTO_RESEARCH_V2_BY_SYMBOL[symbol.toUpperCase()] ?? null;
}

export function getCryptoResearchV2Counts() {
  return CRYPTO_RESEARCH_V2_ROWS.reduce((acc, row) => {
    acc[row.bucket] += 1;
    return acc;
  }, {
    CORE_WATCHLIST: 0,
    PROMISING_RESEARCH: 0,
    SPECULATIVE_WATCHLIST: 0,
    AVOID_BLOCKED: 0,
  });
}

export function getCryptoResearchV2Summary() {
  const counts = getCryptoResearchV2Counts();
  return {
    total: CRYPTO_RESEARCH_V2_ROWS.length,
    coreCount: counts.CORE_WATCHLIST,
    promisingCount: counts.PROMISING_RESEARCH,
    speculativeCount: counts.SPECULATIVE_WATCHLIST,
    avoidCount: counts.AVOID_BLOCKED,
  };
}

export function applyCryptoResearchV2Overlay<T extends { ticker: string }>(row: T) {
  const research = getCryptoResearchV2Row(row.ticker);
  if (!research) return row;
  return {
    ...row,
    crypto_research_v2_score: research.score,
    crypto_research_v2_bucket: research.bucket,
    crypto_research_v2_best_strategy: research.bestStrategy,
    crypto_research_v2_best_regime: research.bestRegime,
    crypto_research_v2_timeframe: research.timeframe,
    crypto_research_v2_rs_vs_btc: research.rsVsBtc,
    crypto_research_v2_rs_vs_eth: research.rsVsEth,
    crypto_research_v2_liquidity: research.liquidity,
    crypto_research_v2_weekend_risk: research.weekendRisk,
    crypto_research_v2_overfit_risk: research.overfitRisk,
    crypto_research_v2_sample_status: research.sampleStatus,
    crypto_research_v2_status: research.researchStatus,
    crypto_research_v2_notes: research.notes,
  };
}
