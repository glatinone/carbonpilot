"use client";

import Link from "next/link";
import { AskPilot } from "@/components/AskPilot";
import { BreakdownBars } from "@/components/BreakdownBars";
import { TrendChart } from "@/components/TrendChart";
import { ErrorBanner, Skeleton, StatCard } from "@/components/ui";
import { useDashboard } from "@/lib/hooks";
import { formatPct, formatTonnes, formatUsd, titleize } from "@/lib/format";

export default function DashboardPage() {
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
        <Skeleton className="h-32" />
        <Skeleton className="h-24" />
        <div className="grid gap-5 lg:grid-cols-2">
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );
  }

  const { baseline, breakdown, breakdown_by_activity, series, anomalies, insights } = data;
  const topAnomaly = anomalies.find((a) => a.activity_type !== "all");
  const scopeRows = Object.entries(baseline.scope_split).map(([key, value]) => ({
    key: key.replace("scope_", "Scope "),
    tco2e: value.tco2e,
    cost_usd: 0,
    pct: value.pct,
  }));

  // Cloud is a small share of carbon but a large share of cost — worth surfacing.
  const cloudCost = breakdown_by_activity
    .filter((row) => row.key.startsWith("cloud"))
    .reduce((sum, row) => sum + row.cost_usd, 0);
  const totalCost = baseline.total_cost_usd || 1;

  return (
    <div className="space-y-6">
      <Header company={data.company.name} region={data.company.region} period={baseline.period} />

      {/* Hero */}
      <section className="card card-pad grid gap-6 lg:grid-cols-[1.15fr_1fr]">
        <div>
          <p className="label">Estimated footprint</p>
          <div className="mt-2 flex items-end gap-3">
            <span className="metric text-5xl font-semibold tracking-tight text-white">
              {baseline.total_tco2e.toLocaleString("en-US", { maximumFractionDigits: 0 })}
            </span>
            <span className="pb-1.5 text-sm text-slate-400">tCO₂e / year</span>
          </div>
          {data.trend_pct !== null && (
            <p
              className={`mt-2 text-sm ${
                data.trend_pct > 0 ? "text-signal-rose" : "text-signal-mint"
              }`}
            >
              {formatPct(data.trend_pct)} vs previous month
            </p>
          )}
          <p className="mt-4 max-w-md text-xs leading-relaxed text-slate-500">
            Measured from {baseline.activity_count} activity records across{" "}
            {baseline.month_count} months, using cited emission factors under the GHG Protocol.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4 self-start">
          <StatCard
            label="Operating cost"
            value={formatUsd(baseline.total_cost_usd).replace("+", "")}
            sub="tracked activity lines"
          />
          <StatCard
            label="Cloud cost share"
            value={`${((cloudCost / totalCost) * 100).toFixed(0)}%`}
            sub="of tracked spend"
            accent="text-signal-sky"
          />
          <StatCard
            label="Opportunities"
            value={String(data.opportunity_count)}
            sub="ranked actions found"
            accent="text-signal-mint"
          />
          <StatCard
            label="Anomalies"
            value={String(anomalies.filter((a) => a.activity_type !== "all").length)}
            sub="statistically flagged"
            accent="text-signal-amber"
          />
        </div>
      </section>

      {/* AI is the primary UI */}
      <AskPilot />

      {/* Charts */}
      <div className="grid gap-5 lg:grid-cols-2">
        <section className="card card-pad">
          <div className="mb-4 flex items-baseline justify-between">
            <h2 className="text-sm font-semibold text-white">Monthly emissions</h2>
            <span className="text-[11px] text-slate-500">{baseline.period?.start} → {baseline.period?.end}</span>
          </div>
          <TrendChart series={series} highlightMonth={topAnomaly?.month} />
        </section>

        <section className="card card-pad">
          <div className="mb-4 flex items-baseline justify-between">
            <h2 className="text-sm font-semibold text-white">Emission breakdown</h2>
            <span className="text-[11px] text-slate-500">by category</span>
          </div>
          <BreakdownBars rows={breakdown} showCost />
          <div className="mt-5 border-t border-ink-700/60 pt-4">
            <p className="label mb-3">Scope split</p>
            <BreakdownBars rows={scopeRows} />
          </div>
        </section>
      </div>

      {/* Insights + actions */}
      <div className="grid gap-5 lg:grid-cols-2">
        <section className="card card-pad">
          <div className="mb-4 flex items-baseline justify-between">
            <h2 className="text-sm font-semibold text-white">AI found {insights.length} signals</h2>
            <Link href="/insights" className="text-[11px] text-signal-mint hover:underline">
              Investigate →
            </Link>
          </div>
          <ul className="space-y-3">
            {insights.slice(0, 3).map((insight) => (
              <li key={`${insight.activity_type}-${insight.month}`} className="flex gap-3">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-signal-rose" />
                <div>
                  <p className="text-xs font-medium text-slate-200">{insight.headline}</p>
                  <p className="mt-0.5 text-[11px] leading-relaxed text-slate-500">
                    {insight.detail}
                  </p>
                </div>
              </li>
            ))}
            {insights.length === 0 && (
              <li className="text-xs text-slate-500">No anomalies detected in the current series.</li>
            )}
          </ul>
        </section>

        <section className="card card-pad">
          <div className="mb-4 flex items-baseline justify-between">
            <h2 className="text-sm font-semibold text-white">Top recommended actions</h2>
            <Link href="/actions" className="text-[11px] text-signal-mint hover:underline">
              Action plan →
            </Link>
          </div>
          <ul className="space-y-3">
            {data.recommendations.slice(0, 4).map((recommendation, index) => (
              <li key={recommendation.id} className="flex items-center gap-3">
                <span className="metric w-7 shrink-0 text-right text-xs font-semibold text-signal-mint">
                  {recommendation.score.toFixed(0)}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-medium text-slate-200">
                    {index + 1}. {recommendation.title}
                  </p>
                  <p className="text-[11px] text-slate-500">
                    −{formatTonnes(recommendation.carbon_impact_t)} ·{" "}
                    {formatUsd(recommendation.cost_impact_usd)}/yr · {recommendation.effort} effort
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <p className="pb-4 text-center text-[11px] text-slate-600">
        {titleize(data.company.region)} grid factors · GHG Protocol Corporate Standard · estimates
        carry methodological uncertainty and are labelled as such
      </p>
    </div>
  );
}

function Header({
  company = "—",
  region,
  period,
}: {
  company?: string;
  region?: string;
  period?: { start: string; end: string };
}) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <p className="label">Executive dashboard</p>
        <h1 className="mt-1 text-xl font-semibold tracking-tight text-white">{company}</h1>
      </div>
      <div className="flex items-center gap-2">
        {region && <span className="chip">Grid region · {region}</span>}
        {period && (
          <span className="chip">
            {period.start} → {period.end}
          </span>
        )}
      </div>
    </header>
  );
}
