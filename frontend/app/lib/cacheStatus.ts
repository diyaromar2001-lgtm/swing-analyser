type AnyRecord = Record<string, unknown>;

function num(value: unknown): number {
  const n = typeof value === "number" ? value : Number(value ?? 0);
  return Number.isFinite(n) ? n : 0;
}

function str(value: unknown): string {
  return typeof value === "string" ? value : "";
}

export type CacheStatusResult = {
  ok: boolean;
  reasons: string[];
  status: "OK" | "À VÉRIFIER";
};

export function getActionsCacheStatus(actions?: AnyRecord | null): CacheStatusResult {
  const reasons: string[] = [];
  const ohlcv = num(actions?.ohlcv_cache_count);
  const price = num(actions?.price_cache_count);
  const screener = num(actions?.screener_results_count);
  const regime = str(actions?.regime_cache_status).toLowerCase();

  if (ohlcv <= 150) reasons.push("OHLCV insuffisant");
  if (price <= 150) reasons.push("Prix insuffisants");
  if (screener <= 0) reasons.push("Screener vide");
  if (regime !== "warm") reasons.push("Régime pas warm");

  return {
    ok: reasons.length === 0,
    reasons,
    status: reasons.length === 0 ? "OK" : "À VÉRIFIER",
  };
}

export function getCryptoCacheStatus(crypto?: AnyRecord | null): CacheStatusResult {
  const reasons: string[] = [];
  const price = num(crypto?.crypto_price_cache_count);
  const screener = num(crypto?.crypto_screener_cache_count);
  const regime = str(crypto?.crypto_regime_cache_status).toLowerCase();

  if (price <= 0) reasons.push("Prix crypto absents");
  if (screener <= 0) reasons.push("Screener crypto vide");
  if (regime !== "warm") reasons.push("Régime crypto pas warm");

  return {
    ok: reasons.length === 0,
    reasons,
    status: reasons.length === 0 ? "OK" : "À VÉRIFIER",
  };
}

