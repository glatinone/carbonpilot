import type { BreakdownRow } from "@/lib/types";
import { formatUsd, titleize } from "@/lib/format";

const COLORS = ["#34d399", "#38bdf8", "#a3e635", "#fbbf24", "#fb7185", "#a78bfa", "#64748b"];

export function BreakdownBars({
  rows,
  showCost = false,
}: {
  rows: BreakdownRow[];
  showCost?: boolean;
}) {
  const max = Math.max(...rows.map((row) => row.tco2e), 1);

  return (
    <ul className="space-y-3">
      {rows.map((row, index) => (
        <li key={row.key}>
          <div className="mb-1.5 flex items-baseline justify-between gap-3 text-xs">
            <span className="font-medium text-slate-300">{titleize(row.key)}</span>
            <span className="flex items-baseline gap-3">
              {showCost && (
                <span className="metric text-[11px] text-slate-500">
                  {formatUsd(row.cost_usd)}
                </span>
              )}
              <span className="metric text-slate-400">
                {row.tco2e.toLocaleString("en-US", { maximumFractionDigits: 0 })} t
              </span>
              <span className="metric w-11 text-right font-semibold text-white">
                {row.pct.toFixed(0)}%
              </span>
            </span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink-800">
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${Math.max((row.tco2e / max) * 100, 2)}%`,
                backgroundColor: COLORS[index % COLORS.length],
              }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
