"use client";

import { useEffect, useMemo, useState } from "react";
import { ensureApiResponse, getAdminApiKey, getAdminHeaders, isAdminProtectedError } from "../lib/api";
import { getActionsCacheStatus, getCryptoCacheStatus } from "../lib/cacheStatus";

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
  const [successNotice, setSuccessNotice] = useState<string | null>(null);
  const [repairNotice, setRepairNotice] = useState<string | null>(null);
  const [infoNotice, setInfoNotice] = useState<string | null>(null);
  const [adminErrorNotice, setAdminErrorNotice] = useState<string | null>(null);
  const [dataErrorNotice, setDataErrorNotice] = useState<string | null>(null);
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
    setSuccessNotice(null);
    setRepairNotice(null);
    setInfoNotice(null);
    setAdminErrorNotice(null);
    setDataErrorNotice(null);
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
    setSuccessNotice(null);
    setRepairNotice(null);
    setInfoNotice(null);
    setAdminErrorNotice(null);
    setDataErrorNotice(null);
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
    setSuccessNotice(null);
    setRepairNotice(null);
    setInfoNotice(null);
    setAdminErrorNotice(null);
    setDataErrorNotice(null);
    try {
      const res = await fetch(`${apiUrl}/api/admin/ping`, {
        headers: getAdminHeaders(),
        cache: "no-store",
      });
      await ensureApiResponse(res);
      const json = await res.json();
      if (json?.admin) {
        setTestStatus("ok");
        setSuccessNotice("Clé validée.");
      } else {
        setTestStatus("fail");
        setAdminErrorNotice("Clé invalide.");
      }
    } catch (error) {
      setTestStatus("fail");
      if (isAdminProtectedError(error)) {
        setAdminErrorNotice("Action admin protégée — clé absente ou invalide.");
      } else {
        setDataErrorNotice("Test de clé impossible.");
      }
    } finally {
      setBusy(null);
    }
  }

  async function fetchCacheStatus() {
    setBusy("cache");
    setMessage(null);
    setSuccessNotice(null);
    setRepairNotice(null);
    setInfoNotice(null);
    setAdminErrorNotice(null);
    setDataErrorNotice(null);
    try {
      const res = await fetch(`${apiUrl}/api/cache-status?scope=all`, { cache: "no-store" });
      await ensureApiResponse(res);
      const json = await res.json();
      setCacheStatus(json);
      const actionsStatus = getActionsCacheStatus(json?.actions);
      const cryptoStatus = getCryptoCacheStatus(json?.crypto);
      const actionsOk = actionsStatus.ok;
      const cryptoOk = cryptoStatus.ok;
      if (actionsOk && cryptoOk) {
        setSuccessNotice("Caches prêts : Actions OK · Crypto OK");
        setRepairNotice(null);
        setInfoNotice(null);
        setAdminErrorNotice(null);
        setDataErrorNotice(null);
      } else {
        setRepairNotice("Cache vérifié.");
        setInfoNotice(`Actions ${actionsStatus.status} : ${actionsStatus.reasons.join(", ") || "OK"} ? Crypto ${cryptoStatus.status} : ${cryptoStatus.reasons.join(", ") || "OK"}`);
      }
    } catch (error) {
      if (isAdminProtectedError(error)) {
        setAdminErrorNotice("Action admin protégée — clé absente ou invalide.");
      } else {
        setDataErrorNotice("Vérification cache impossible.");
      }
    } finally {
      setBusy(null);
    }
  }

  async function runWarmup(url: string, label: string, withHeader = true) {
    setBusy(label);
    setMessage(null);
    setSuccessNotice(null);
    setRepairNotice(null);
    setInfoNotice(null);
    setAdminErrorNotice(null);
    setDataErrorNotice(null);
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
      setSuccessNotice("Warmup terminé.");
    } catch (error) {
      if (isAdminProtectedError(error)) {
        setAdminErrorNotice("Action admin protégée — clé absente ou invalide.");
      } else {
        setDataErrorNotice("Warmup trop long ou interrompu. Vérifiez le cache-status.");
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

  async function runEdgeActionsCompute() {
    setBusy("edge-actions");
    setMessage(null);
    setSuccessNotice(null);
    setRepairNotice(null);
    setInfoNotice(null);
    setAdminErrorNotice(null);
    setDataErrorNotice(null);
    try {
      const res = await fetch(
        `${apiUrl}/api/warmup/edge-actions?grades=A%2B,A,B`,
        {
          method: "POST",
          headers: getAdminHeaders(),
        }
      );
      await ensureApiResponse(res);
      const json = await res.json() as any;
      setWarmupLog(prev => [
        `[edge-actions] computed=${json.edge_actions_computed}/${json.edge_actions_count} duration=${json.duration_ms}ms`,
        ...(json.warnings?.length ? json.warnings.map((w: string) => `[warn] ${w}`) : []),
        ...(json.errors?.length ? json.errors.map((e: string) => `[error] ${e}`) : []),
        ...prev,
      ]);
      if (json.edge_actions_count === 0) {
        setRepairNotice("Aucun ticker éligible trouvé dans le cache actuel.");
        setInfoNotice("Utilisez le calcul par ticker dans le Trade Plan (bouton 'Calculer Edge [TICKER]').");
      } else {
        setSuccessNotice(`Edge calculé pour ${json.edge_actions_computed} / ${json.edge_actions_count} tickers.`);
      }
    } catch (error) {
      if (isAdminProtectedError(error)) {
        setAdminErrorNotice("Action admin protégée — clé absente ou invalide.");
      } else {
        setDataErrorNotice("Calcul edge impossible.");
      }
    } finally {
      setBusy(null);
    }
  }

  async function runDangerClearCache() {
    if (!window.confirm("Cette action vide les caches et peut rendre l'app lente. Continuer ?")) {
      return;
    }
    setBusy("danger-clear-cache");
    setMessage(null);
    setSuccessNotice(null);
    setRepairNotice(null);
    setInfoNotice(null);
    setAdminErrorNotice(null);
    setDataErrorNotice(null);
    try {
      const res = await fetch(`${apiUrl}/api/clear-cache?scope=all`, {
        method: "POST",
        headers: getAdminHeaders(),
      });
      await ensureApiResponse(res);
      setRepairNotice("Caches vidés. Lancez un warmup complet ensuite.");
    } catch (error) {
      if (isAdminProtectedError(error)) {
        setAdminErrorNotice("Action admin protégée — clé absente ou invalide.");
      } else {
        setDataErrorNotice("Vidage des caches impossible.");
      }
    } finally {
      setBusy(null);
    }
  }

  const adminActive = !!savedKeyState;

  const actionsStatus = getActionsCacheStatus(cacheStatus?.actions);
  const cryptoStatus = getCryptoCacheStatus(cacheStatus?.crypto);
  const actionsOk = actionsStatus.ok;
  const cryptoOk = cryptoStatus.ok;

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
            <div className="mt-3 space-y-2">
              {successNotice && (
                <div className="rounded-lg border border-emerald-800 bg-emerald-950/40 px-3 py-2 text-sm text-emerald-200">
                  {successNotice}
                </div>
              )}
              {repairNotice && !successNotice && (
                <div className="rounded-lg border border-slate-700 bg-slate-900/60 px-3 py-2 text-sm text-slate-200">
                  {repairNotice}
                  {infoNotice ? <div className="mt-1 text-xs text-slate-400">{infoNotice}</div> : null}
                </div>
              )}
              {adminErrorNotice && (
                <div className="rounded-lg border border-red-800 bg-red-950/40 px-3 py-2 text-sm text-red-200">
                  {adminErrorNotice}
                </div>
              )}
              {dataErrorNotice && (
                <div className="rounded-lg border border-amber-800 bg-amber-950/40 px-3 py-2 text-sm text-amber-200">
                  {dataErrorNotice}
                </div>
              )}
              {!successNotice && !repairNotice && !adminErrorNotice && !dataErrorNotice && (
                <div className="text-sm text-slate-400">
                  {message ? <span>{message}</span> : <span>Statut admin: {adminActive ? "Activé localement" : "Désactivé"}</span>}
                  {testStatus === "ok" && <span className="ml-2 text-emerald-300">OK</span>}
                  {testStatus === "fail" && <span className="ml-2 text-red-400">Échec</span>}
                </div>
              )}
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
              <div className="p-3 rounded-lg border border-slate-800 bg-black/40">
                <h4 className="text-sm font-semibold text-white mb-2">Edge v1 Analysis</h4>
                <button
                  onClick={runEdgeActionsCompute}
                  disabled={!adminActive || !!busy}
                  className="px-3 py-2 rounded-lg bg-blue-600 text-white text-xs font-semibold disabled:opacity-40"
                >
                  Calculer Edge Actions (A+/A/B)
                </button>
                <p className="text-[10px] text-slate-400 mt-2">Compute strategy edge for A+/A/B grade setups only. Does not modify existing data.</p>
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
                  Actions {actionsOk ? <span className="text-emerald-300">OK</span> : <span className="text-amber-300">a verifier</span>} ? Crypto {cryptoOk ? <span className="text-emerald-300">OK</span> : <span className="text-amber-300">a verifier</span>}
                </div>
              )}
            </div>
            <pre className="text-[11px] leading-5 whitespace-pre-wrap break-words text-slate-300 bg-black/40 border border-slate-800 rounded-lg p-3 overflow-x-auto">
              {cacheStatus ? JSON.stringify(cacheStatus, null, 2) : "Cliquez sur 'Verifier cache'."}
            </pre>
            {cacheStatus && (!actionsOk || !cryptoOk) && (
              <div className="mt-3 grid md:grid-cols-2 gap-3 text-xs">
                <div className="rounded-lg border border-slate-800 bg-black/30 p-3">
                  <div className="font-semibold text-white mb-1">Actions a verifier parce que :</div>
                  <ul className="list-disc pl-4 space-y-1 text-slate-300">
                    {actionsStatus.reasons.length ? actionsStatus.reasons.map((reason) => <li key={reason}>{reason}</li>) : <li>OK</li>}
                  </ul>
                </div>
                <div className="rounded-lg border border-slate-800 bg-black/30 p-3">
                  <div className="font-semibold text-white mb-1">Crypto a verifier parce que :</div>
                  <ul className="list-disc pl-4 space-y-1 text-slate-300">
                    {cryptoStatus.reasons.length ? cryptoStatus.reasons.map((reason) => <li key={reason}>{reason}</li>) : <li>OK</li>}
                  </ul>
                </div>
              </div>
            )}
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
