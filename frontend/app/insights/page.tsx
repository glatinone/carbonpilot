"use client";

import { AskPilot } from "@/components/AskPilot";
import { InsightCard } from "@/components/InsightCard";
import { EmptyState, ErrorBanner, Footnote, SectionHead, Skeleton } from "@/components/ui";
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
    <div>
      <Header count={anomalies.length} />

      <div className="mt-8">
        <AskPilot />
      </div>

      <section className="mt-8 border-t border-rule pt-4">
        <SectionHead
          kicker="Signals"
          title="Decision-ready"
          note={`${data.insights.length} of ${anomalies.length} anomalies ranked for action`}
        />
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

      <section className="mt-8 border-t border-rule pt-4">
        <SectionHead kicker="Record" title="All detected anomalies" note="per activity stream" />
        <table className="ledger">
          <thead>
            <tr>
              <th>Month</th>
              <th>Activity stream</th>
              <th>Change</th>
              <th>Z-score</th>
              <th>Delta tCO₂e</th>
              <th>Severity</th>
            </tr>
          </thead>
          <tbody>
            {anomalies.map((anomaly) => (
              <tr key={`${anomaly.month}-${anomaly.activity_type}`}>
                <td>{anomaly.month}</td>
                <td>{titleize(anomaly.activity_type)}</td>
                <td className={anomaly.change_pct > 0 ? "text-alert" : "text-save"}>
                  {formatPct(anomaly.change_pct)}
                </td>
                <td>{anomaly.z_score.toFixed(2)}</td>
                <td>{anomaly.delta_tco2e.toFixed(1)}</td>
                <td className={anomaly.severity === "high" ? "text-stop" : "text-alert"}>
                  {anomaly.severity}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="mt-5">
          <Footnote>
            <b>Method.</b> Robust z-score using median and median absolute deviation (MAD), computed
            per activity stream so a spike cannot inflate its own baseline — a company-level event is
            only reported when the total moved by at least 10%. Signals are ranked by carbon × cost ×
            effort weighted by confidence. <b>Uncertainty.</b> Detected, not forecast: every figure is
            a measured change against that stream&rsquo;s own history.
          </Footnote>
        </div>
      </section>
    </div>
  );
}

function Header({ count }: { count?: number }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-x-8 gap-y-3 border-b-2 border-ink pb-4">
      <div>
        <p className="kicker">Diagnose</p>
        <h1 className="mt-1.5 font-serif text-[26px] font-semibold leading-none tracking-tight text-ink">
          AI Insights
        </h1>
      </div>
      {count !== undefined && (
        <p className="max-w-[46ch] font-serif text-[15px] leading-snug text-ink-soft">
          <b className="font-semibold text-ink">{count}</b> anomal{count === 1 ? "y" : "ies"} in the
          recorded series
        </p>
      )}
    </header>
  );
}
