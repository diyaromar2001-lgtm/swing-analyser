"use client";

export function ScoreBadge({ score, category }: { score: number | null; category: string }) {
  if (score === null) {
    return <span className="text-gray-500 text-sm">—</span>;
  }

  const color =
    category === "Opportunité forte"
      ? "text-emerald-400"
      : category === "Risque modéré"
      ? "text-amber-400"
      : "text-red-400";

  const bg =
    category === "Opportunité forte"
      ? "bg-emerald-400/10 border-emerald-400/30"
      : category === "Risque modéré"
      ? "bg-amber-400/10 border-amber-400/30"
      : "bg-red-400/10 border-red-400/30";

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs font-bold ${color} ${bg}`}>
      {score.toFixed(0)}
    </span>
  );
}
