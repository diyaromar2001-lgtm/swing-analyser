"use client";

import { useEffect, useMemo, useState } from "react";
import { ensureApiResponse, getAdminApiKey, getAdminHeaders, isAdminProtectedError } from "../lib/api";

const ADMIN_API_KEY_STORAGE = "admin_api_key";

type CacheStatus = {
  scope?: string;
  actions?: Record<string, unknown>;
  crypto?: Record<string, unknown>;
};

type WarmupResult = {
  status?: string;
  scope?: string;
  duration_ms?: number;
  actions_count?: number;
  crypto_count?: number;
  warnings?: string[];
  errors?: string[];
  updated?: {
    actions?: Record<string, unknown> | null;
    crypto?: Record<string, unknown> | null;
  };
  warmup_progress?: Record<string, unknown> | null;
};

function formatValue(value: unknown): string {
  if (typeof value === "number") return value.toString();
  if (typeof value === "boolean") return value ? "true" : "false";
  if (value == null) return "—";
  return String(value);
}

export function AdminPanel({
  apiUrl,
  onClose,
  onKeyChange,
}: {
  apiUrl: string;
  onClose: () => void;
  onKeyChange?: (hasKey: boolean) => void;
}) {
  const [keyInput, setKeyInput] = useState("");
  const [savedKeyState, setSavedKeyState] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [testStatus, setTestStatus] = useState<"idle" | "ok" | "fail">("idle");
  const [cacheStatus, setCacheStatus] = useState<CacheStatus | null>(null);
  const [warmupLog, setWarmupLog] = useState<string[]>([]);
  const [batchState, setBatchState] = useState<{ current: number | null; elapsedMs: number }>({ current: null, elapsedMs: 0 });

  const hasKey = useMemo(() => !!getAdminApiKey(), [savedKeyState, message]);

  useEffect(() => {
    setSavedKeyState(getAdminApiKey());
  }, []);

  useEffect(() => {
    if (!busy) return;
    const started = Date.now();
    const timer = setInterval(() => {
      setBatchState(prev => ({ ...prev, elapsedMs: Date.now() - started }));
    }, 250);
    return () => clearInterval(timer);
  }, [busy]);

  async function saveKey() {
    const value = keyInput.trim();
    if (!value) {
      setMessage("Aucune clé à sauvegarder.");
      return;
    }
    try {
      window.localStorage.setItem(ADMIN_API_KEY_STORAGE, value);
      setSavedKeyState(value);
      onKeyChange?.(true);
      setKeyInput("");
      setMessage("Clé enregistrée.");
      setTestStatus("idle");
    } catch {
      setMessage("Impossible d'enregistrer la clé.");
    }
  }

  function clearKey() {
    try {
      window.localStorage.removeItem(ADMIN_API_KEY_STORAGE);
      setSavedKeyState(null);
      onKeyChange?.(false);
      setKeyInput("");
      setMessage("Clé supprimée.");
      setTestStatus("idle");
    } catch {
      setMessage("Impossible d'effacer la clé.");
    }
  }

  async function testKey() {
    setBusy("test");
    setMessage(null);
    try {
      const res = await fetch(`${apiUrl}/api/admin/ping`, {
        headers: getAdminHeaders(),
        cache: "no-store",
      });
      await ensureApiResponse(res);
      const json = await res.json();
      if (json?.admin) {
        setTestStatus("ok");
        setMessage("Clé validée.");
      } else {
        setTestStatus("fail");
        setMessage("Clé invalide.");
      }
    } catch (error) {
      setTestStatus("fail");
      if (isAdminProtectedError(error)) {
        setMessage("Action admin protégée — clé absente ou invalide.");
      } else {
        setMessage("Test de clé impossible.");
      }
    } finally {
      setBusy(null);
    }
  }

  async function fetchCacheStatus() {
    setBusy("cache");
    setMessage(null);
    try {
      const res = await fetch(`${apiUrl}/api/cache-status?scope=all`, { cache: "no-store" });
      await ensureApiResponse(res);
      const json = await res.json();
      setCacheStatus(json);
      setMessage("Cache vérifié.");
    } catch (error) {
      if (isAdminProtectedError(error)) {
        setMessage("Action admin protégée — clé absente ou invalide.");
      } else {
        setMessage("Vérification cache impossible.");
      }
    } finally {
      setBusy(null);
    }
  }

  async function runWarmup(url: string, label: string, withHeader = true) {
    setBusy(label);
    setMessage(null);
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: withHeader ? getAdminHeaders() : {},
      });
      await ensureApiResponse(res);
      const json = await res.json() as WarmupResult;
      setWarmupLog(prev => [
        `[${label}] actions=${formatValue(json.actions_count)} crypto=${formatValue(json.crypto_count)} duration=${formatValue(json.duration_ms)}ms`,
        ...(json.warnings?.length ? json.warnings.map(w => `[warn] ${w}`) : []),
        ...(json.errors?.length ? json.errors.map(e => `[error] ${e}`) : []),
        ...prev,
      ]);
      setMessage("Warmup terminé.");
    } catch (error) {
      if (isAdminProtectedError(error)) {
        setMessage("Action admin protégée — clé absente ou invalide.");
      } else {
        setMessage("Warmup trop long ou interrompu. Vérifiez le cache-status.");
      }
    } finally {
      setBusy(null);
      setBatchState({ current: null, elapsedMs: 0 });
    }
  }

  async function runActionsBatch(batch: number) {
    const label = `actions-batch-${batch}`;
    setBatchState({ current: batch, elapsedMs: 0 });
    await runWarmup(
      `${apiUrl}/api/warmup?scope=actions&batch=${batch}&batch_size=50&include_edge=false`,
      label,
    );
  }

  async function runActionsComplete() {
    for (const batch of [1, 2, 3, 4, 5]) {
      setBatchState({ current: batch, elapsedMs: 0 });
      await runWarmup(
        `${apiUrl}/api/warmup?scope=actions&batch=${batch}&batch_size=50&include_edge=false`,
        `actions-batch-${batch}`,
      );
    }
  }

  async function runCryptoWarmup() {
    await runWarmup(
      `${apiUrl}/api/warmup?scope=crypto&include_edge=false`,
      "crypto-warmup",
    );
  }

  async function runDangerClearCache() {
    if (!window.confirm("Cette action vide les caches et peut rendre l'app lente. Continuer ?")) {
      return;
    }
    setBusy("danger-clear-cache");
    setMessage(null);
    try {
      const res = await fetch(`${apiUrl}/api/clear-cache?scope=all`, {
        method: "POST",
        headers: getAdminHeaders(),
      });
      await ensureApiResponse(res);
      setMessage("Caches vidés. Lancez un warmup complet ensuite.");
    } catch (error) {
      if (isAdminProtectedError(error)) {
        setMessage("Action admin protégée — clé absente ou invalide.");
      } else {
        setMessage("Vidage des caches impossible.");
      }
    } finally {
      setBusy(null);
    }
  }

  const adminActive = !!savedKeyState;

  const actionsOk = !!cacheStatus?.actions
    && Number(cacheStatus.actions.ohlcv_cache_count ?? 0) > 150
    && Number(cacheStatus.actions.price_cache_count ?? 0) > 150
    && Number(cacheStatus.actions.screener_results_count ?? 0) > 0;
  const cryptoOk = !!cacheStatus?.crypto
    && Number(cacheStatus.crypto.crypto_price_cache_count ?? 0) > 0
    && Number(cacheStatus.crypto.crypto_screener_cache_count ?? 0) > 0
    && cacheStatus.crypto.crypto_regime_cache_status === "warm";

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex justify-end">
      <div className="w-full max-w-4xl h-full overflow-y-auto" style={{ background: "#0b0b14", borderLeft: "1px solid #1e1e2a" }}>
        <div className="p-5 border-b border-slate-800 flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-black text-white">Admin</h2>
              <span className={`text-[10px] font-bold px-2 py-1 rounded-full ${adminActive ? "bg-emerald-950 text-emerald-300" : "bg-slate-900 text-slate-400"}`}>
                {adminActive ? "Admin ON" : "Admin OFF"}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-2">Cette clé permet de lancer des actions lourdes. Ne la partagez pas.</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-sm px-3 py-1 rounded-lg border border-slate-700">Fermer</button>
        </div>

        <div className="p-5 grid gap-5">
          <section className="p-4 rounded-xl border border-slate-800 bg-slate-950">
            <div className="flex items-center justify-between gap-3 mb-3">
              <h3 className="font-bold text-white">Clé Admin</h3>
              <span className={`text-xs ${adminActive ? "text-emerald-300" : "text-slate-500"}`}>
                {adminActive ? "clé enregistrée" : "aucune clé enregistrée"}
              </span>
            </div>
            <input
              type="password"
              value={keyInput}
              onChange={(e) => setKeyInput(e.target.value)}
              placeholder="Admin API Key"
              className="w-full px-4 py-3 rounded-lg bg-black border border-slate-700 text-white outline-none"
            />
            <div className="flex flex-wrap gap-2 mt-3">
              <button onClick={saveKey} className="px-3 py-2 rounded-lg bg-emerald-600 text-white text-sm font-semibold">Sauvegarder la clé</button>
              <button onClick={clearKey} className="px-3 py-2 rounded-lg bg-slate-800 text-slate-200 text-sm font-semibold">Effacer la clé</button>
              <button onClick={testKey} disabled={busy === "test"} className="px-3 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold disabled:opacity-50">Tester la clé</button>
            </div>
            <div className="mt-3 text-sm text-slate-400">
              {message ? <span>{message}</span> : <span>Statut admin: {adminActive ? "Activé localement" : "Désactivé"}</span>}
              {testStatus === "ok" && <span className="ml-2 text-emerald-300">OK</span>}
              {testStatus === "fail" && <span className="ml-2 text-red-400">Échec</span>}
            </div>
          </section>

          <section className="p-4 rounded-xl border border-slate-800 bg-slate-950">
            <div className="flex items-center justify-between gap-3 mb-3">
              <h3 className="font-bold text-white">Warmup production</h3>
              <button onClick={fetchCacheStatus} disabled={busy === "cache"} className="px-3 py-2 rounded-lg bg-slate-800 text-slate-200 text-sm font-semibold disabled:opacity-50">Vérifier cache</button>
            </div>
            {!adminActive && <p className="text-xs text-amber-300 mb-3">Activez le mode Admin pour lancer les warmups.</p>}
            <div className="grid md:grid-cols-2 gap-4">
              <div className="p-3 rounded-lg border border-slate-800 bg-black/40">
                <h4 className="text-sm font-semibold text-white mb-2">Actions</h4>
                <div className="flex flex-wrap gap-2">
                  {[1, 2, 3, 4, 5].map((batch) => (
                    <button
                      key={batch}
                      onClick={() => runActionsBatch(batch)}
                      disabled={!adminActive || !!busy}
                      className="px-3 py-2 rounded-lg bg-indigo-600 text-white text-xs font-semibold disabled:opacity-40"
                    >
                      Warmup Actions batch {batch}
                    </button>
                  ))}
                  <button
                    onClick={runActionsComplete}
                    disabled={!adminActive || !!busy}
                    className="px-3 py-2 rounded-lg bg-emerald-700 text-white text-xs font-semibold disabled:opacity-40"
                  >
                    Warmup Actions complet 5 batchs
                  </button>
                </div>
              </div>
              <div className="p-3 rounded-lg border border-slate-800 bg-black/40">
                <h4 className="text-sm font-semibold text-white mb-2">Crypto</h4>
                <button
                  onClick={runCryptoWarmup}
                  disabled={!adminActive || !!busy}
                  className="px-3 py-2 rounded-lg bg-sky-600 text-white text-xs font-semibold disabled:opacity-40"
                >
                  Warmup Crypto
                </button>
              </div>
            </div>
            <div className="mt-4 text-xs text-slate-400 space-y-2">
              <div>Batch en cours: <span className="text-white">{batchState.current ?? "—"}</span></div>
              <div>Temps écoulé: <span className="text-white">{Math.floor(batchState.elapsedMs / 1000)}s</span></div>
              {busy && <div className="text-amber-300">Action en cours: {busy}</div>}
            </div>
          </section>

          <section className="p-4 rounded-xl border border-amber-900 bg-amber-950/20">
            <div className="flex items-center justify-between gap-3 mb-3">
              <h3 className="font-bold text-amber-200">Danger zone</h3>
              <span className="text-[10px] uppercase tracking-widest text-amber-300">Admin only</span>
            </div>
            <p className="text-xs text-amber-200/80 mb-3">
              Cette action vide les caches et peut rendre l'app lente. Utilisez-la seulement si nécessaire.
            </p>
            <button
              onClick={runDangerClearCache}
              disabled={!adminActive || !!busy}
              className="px-3 py-2 rounded-lg bg-amber-700 text-white text-xs font-semibold disabled:opacity-40"
            >
              Recalculer l&apos;analyse complète
            </button>
          </section>

          <section className="p-4 rounded-xl border border-slate-800 bg-slate-950">
            <div className="flex items-center justify-between gap-3 mb-3">
              <h3 className="font-bold text-white">Cache status</h3>
              {cacheStatus && (
                <div className="text-xs text-slate-400">
                  Actions {actionsOk ? <span className="text-emerald-300">OK</span> : <span className="text-amber-300">à vérifier</span>} · Crypto {cryptoOk ? <span className="text-emerald-300">OK</span> : <span className="text-amber-300">à vérifier</span>}
                </div>
              )}
            </div>
            <pre className="text-[11px] leading-5 whitespace-pre-wrap break-words text-slate-300 bg-black/40 border border-slate-800 rounded-lg p-3 overflow-x-auto">
              {cacheStatus ? JSON.stringify(cacheStatus, null, 2) : "Cliquez sur 'Vérifier cache'."}
            </pre>
          </section>

          <section className="p-4 rounded-xl border border-slate-800 bg-slate-950">
            <h3 className="font-bold text-white mb-3">Historique warmup</h3>
            <div className="space-y-1 text-[11px] text-slate-300">
              {warmupLog.length === 0 ? (
                <div className="text-slate-500">Aucun warmup exécuté.</div>
              ) : warmupLog.map((line, idx) => <div key={`${line}-${idx}`} className="font-mono">{line}</div>)}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
