"use client";

export function StatusBadge({ status, tooRisky }: { status: string; tooRisky: boolean }) {
  if (status === "Hors tendance") {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-700/50 text-gray-400 border border-gray-600/40">
        Hors tendance
      </span>
    );
  }
  if (tooRisky) {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/30">
        Trop risqué
      </span>
    );
  }
  if (status === "En zone d'achat") {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
        Zone d&apos;achat
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/30">
      {status}
    </span>
  );
}
