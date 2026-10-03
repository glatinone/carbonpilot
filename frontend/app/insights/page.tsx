"use client";

import { AskPilot } from "@/components/AskPilot";
import { InsightCard } from "@/components/InsightCard";
import { ErrorBanner, EmptyState, Skeleton } from "@/components/ui";
import { useDashboard } from "@/lib/hooks";
import { formatPct, titleize } from "@/lib/format";

export default function InsightsPage() {
  const { data, loading, error, reload } = useDashboard();

  if (error) {
    return (
      <div className="space-y-6">
        <Header />
        <ErrorBanner message={error} onRetry={reload} />
      </div>
    );
  }

  if (loading || !data) {
    return (
      <div className="space-y-6">
        <Header />
        <Skeleton className="h-40" />
        <Skeleton className="h-40" />
        <Skeleton className="h-40" />
      </div>
    );
  }

  const anomalies = data.anomalies.filter((a) => a.activity_type !== "all");

  return (
    <div className="space-y-6">
      <Header count={anomalies.length} />

      <AskPilot />

      <section className="space-y-4">
        <h2 className="text-sm font-semibold text-white">Decision-ready signals</h2>
        {data.insights.length === 0 ? (
          <EmptyState
            title="No anomalies in the current series"
            hint="The monthly emission series is statistically stable."
          />
        ) : (
          data.insights.map((insight, index) => (
            <InsightCard
              key={`${insight.activity_type}-${insight.month}`}
              insight={insight}
              index={index}
            />
          ))
        )}
      </section>

      <section className="card card-pad">
        <h2 className="mb-4 text-sm font-semibold text-white">All detected anomalies</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-ink-700/60 text-[10px] uppercase tracking-wider text-slate-500">
                <th className="pb-2 pr-4 font-medium">Month</th>
                <th className="pb-2 pr-4 font-medium">Activity stream</th>
                <th className="pb-2 pr-4 text-right font-medium">Change</th>
                <th className="pb-2 pr-4 text-right font-medium">Z-score</th>
                <th className="pb-2 pr-4 text-right font-medium">Delta</th>
                <th className="pb-2 font-medium">Severity</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-800/80">
              {anomalies.map((anomaly) => (
                <tr key={`${anomaly.month}-${anomaly.activity_type}`}>
                  <td className="py-2.5 pr-4 font-mono text-slate-400">{anomaly.month}</td>
                  <td className="py-2.5 pr-4 text-slate-300">
                    {titleize(anomaly.activity_type)}
                  </td>
                  <td
                    className={`py-2.5 pr-4 text-right font-mono ${
                      anomaly.change_pct > 0 ? "text-signal-rose" : "text-signal-mint"
                    }`}
                  >
                    {formatPct(anomaly.change_pct)}
                  </td>
                  <td className="py-2.5 pr-4 text-right font-mono text-slate-400">
                    {anomaly.z_score.toFixed(2)}
                  </td>
                  <td className="py-2.5 pr-4 text-right font-mono text-slate-400">
                    {anomaly.delta_tco2e.toFixed(1)} t
                  </td>
                  <td className="py-2.5">
                    <span
                      className={`chip ${
                        anomaly.severity === "high"
                          ? "border-signal-rose/40 text-signal-rose"
                          : "border-signal-amber/40 text-signal-amber"
                      }`}
                    >
                      {anomaly.severity}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-[11px] leading-relaxed text-slate-500">
          Method: robust z-score using median and median absolute deviation (MAD), computed per
          activity stream so a spike cannot inflate its own baseline. A company-level event is only
          reported when the total moved by at least 10%.
        </p>
      </section>
    </div>
  );
}

function Header({ count }: { count?: number }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <p className="label">Diagnose</p>
        <h1 className="mt-1 text-xl font-semibold tracking-tight text-white">AI Insights</h1>
      </div>
      {count !== undefined && (
        <span className="chip">
          {count} anomal{count === 1 ? "y" : "ies"} in the recorded series
        </span>
      )}
    </header>
  );
}
