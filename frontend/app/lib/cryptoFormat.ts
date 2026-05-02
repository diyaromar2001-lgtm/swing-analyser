export function formatCryptoPrice(symbol: string, price?: number | null) {
  if (typeof price !== "number" || !Number.isFinite(price)) {
    return "—";
  }

  const s = symbol.toUpperCase();

  if (s === "BTC") {
    return price >= 100 ? price.toFixed(0) : price.toFixed(1);
  }

  if (["ETH", "BNB", "SOL"].includes(s)) {
    return price.toFixed(2);
  }

  if (price >= 100) return price.toFixed(2);
  if (price >= 10) return price.toFixed(3);
  if (price >= 1) return price.toFixed(4);
  if (price >= 0.1) return price.toFixed(5);
  return price.toFixed(6);
}

export function isCryptoDefensiveRegime(regime?: string | null) {
  return ["CRYPTO_BEAR", "CRYPTO_NO_TRADE", "CRYPTO_HIGH_VOLATILITY"].includes(regime ?? "");
}
