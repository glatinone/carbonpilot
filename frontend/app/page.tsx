"use client";

import Link from "next/link";
import { AskPilot } from "@/components/AskPilot";
import { TrendChart } from "@/components/TrendChart";
import { Emphasised, ErrorBanner, Footnote, SectionHead, Skeleton, Stat } from "@/components/ui";
import { useDashboard } from "@/lib/hooks";
import { useLocale, useStreamLabel } from "@/lib/i18n";
import { formatPct, formatTonnes, formatUsd, monthLabel, titleize } from "@/lib/format";

export default function DashboardPage() {
  const { data, loading, error, reload } = useDashboard();
  const { t, locale } = useLocale();
  const streamLabel = useStreamLabel();

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
  const cloudShare = (cloudCost / totalCost) * 100;
  const largestLine = breakdown[0];
  const insightCount = insights.length;

  return (
    <div>
      <Header company={data.company.name} region={data.company.region} period={baseline.period} />

      {/* Statement band. The finding is written as a sentence and the figure sits
          inside it in tabular mono — the composition the Monitor surface was missing. */}
      <section className="mt-7">
        <div className="grid gap-x-12 gap-y-8 lg:grid-cols-[1.45fr_1fr]">
          <div>
            <p className="kicker">{t("dash.footprint")}</p>
            <div className="mt-2.5 flex flex-wrap items-baseline gap-x-4 gap-y-2">
              <span className="fig text-[46px] font-medium leading-none tracking-[-0.02em] text-ink">
                {baseline.total_tco2e.toLocaleString(locale === "id" ? "id-ID" : "en-US", {
                  maximumFractionDigits: 0,
                })}
              </span>
              <span className="text-[13px] text-ink-muted">{t("dash.perYear")}</span>
              {data.trend_pct !== null && (
                <span
                  className={`fig border border-rule-strong px-2 py-0.5 text-[11.5px] ${
                    data.trend_pct > 0 ? "text-alert" : "text-save"
                  }`}
                >
                  {t("dash.vsPrev", { pct: formatPct(data.trend_pct) })}
                </span>
              )}
            </div>

            <p className="mt-5 max-w-[56ch] font-serif text-[19px] leading-[1.55] text-ink-soft">
              {largestLine && (
                <Emphasised
                  template={t("dash.largestLine")}
                  values={{
                    stream: streamLabel(largestLine.key),
                    pct: largestLine.pct.toFixed(1),
                  }}
                />
              )}
              {topAnomaly && (
                <Emphasised
                  template={t("dash.largestLine2")}
                  values={{
                    stream: streamLabel(topAnomaly.activity_type),
                    pct: formatPct(topAnomaly.change_pct),
                    month: monthLabel(topAnomaly.month, locale),
                  }}
                  tone="alert"
                />
              )}
            </p>

            <div className="mt-6">
              <p className="kicker mb-2.5">{t("dash.scopeSplit")}</p>
              <div className="flex gap-0.5">
                <span className="h-3 bg-ink" style={{ flex: 11.6 }} />
                <span className="h-3 bg-ink-muted" style={{ flex: 27.3 }} />
                <span className="h-3 bg-bar" style={{ flex: 61.1 }} />
              </div>
              <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-[11.5px] text-ink-muted">
                {scopeRows.map((row) => (
                  <span key={row.key}>
                    {row.key} <span className="fig text-ink">{row.pct.toFixed(1)}%</span>
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-x-6 gap-y-6 self-start">
            <Stat
              label={t("dash.operatingCost")}
              value={formatUsd(baseline.total_cost_usd).replace("+", "")}
              sub={t("dash.trackedLines")}
            />
            <Stat
              label={t("dash.cloudShare")}
              value={`${cloudShare.toFixed(0)}%`}
              sub={t("dash.inScope2", {
                amount: formatTonnes(baseline.scope_split.scope_2?.tco2e ?? 0),
              })}
            />
            <Stat
              label={t("dash.opportunities")}
              value={String(data.opportunity_count)}
              sub={t("dash.rankedActions")}
              tone="save"
            />
            <Stat
              label={t("dash.signals")}
              value={String(insightCount)}
              sub={t("dash.flagged")}
              tone="alert"
            />
          </div>
        </div>
      </section>

      {/* AI is the primary UI */}
      <div className="mt-8">
        <AskPilot />
      </div>

      {/* Charts, as ruled bands rather than two cards */}
      <div className="mt-8 grid gap-x-10 gap-y-8 lg:grid-cols-2">
        <section className="border-t border-rule pt-4">
          <SectionHead
            kicker={t("dash.bTrend")}
            title={t("dash.monthly")}
            note={`${baseline.period?.start ?? ""} → ${baseline.period?.end ?? ""}`}
          />
          <TrendChart series={series} highlightMonth={topAnomaly?.month} />
        </section>

        <section className="border-t border-rule pt-4">
          <SectionHead
            kicker={t("dash.bSources")}
            title={t("dash.whereFrom")}
            note={t("dash.nStreams", { n: breakdown.length })}
          />
          <table className="ledger">
            <thead>
              <tr>
                <th>{t("dash.thStream")}</th>
                <th>{t("dash.thTco2e")}</th>
                <th>{t("dash.thShare")}</th>
                <th>{t("dash.thCost")}</th>
              </tr>
            </thead>
            <tbody>
              {breakdown.map((row) => (
                <tr key={row.key}>
                  <td>{streamLabel(row.key)}</td>
                  <td>
                    {row.tco2e.toLocaleString(locale === "id" ? "id-ID" : "en-US", {
                      maximumFractionDigits: 1,
                    })}
                  </td>
                  <td>{row.pct.toFixed(1)}%</td>
                  <td>{row.cost_usd.toLocaleString(locale === "id" ? "id-ID" : "en-US", { maximumFractionDigits: 0 })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>

      {/* Signals + ranked actions */}
      <div className="mt-8 grid gap-x-10 gap-y-8 lg:grid-cols-2">
        <section className="border-t border-rule pt-4">
          <SectionHead
            kicker={t("dash.bDiagnose")}
            title={t("dash.signalsFound", { n: insights.length })}
            action={
              <Link href="/insights" className="btn-quiet">
                {t("dash.investigate")}
              </Link>
            }
          />
          <ul>
            {insights.slice(0, 3).map((insight, index) => (
              <li
                key={`${insight.activity_type}-${insight.month}`}
                className="flex items-baseline gap-3 border-b border-rule py-2.5 last:border-b-0"
              >
                <span className="fig w-4 shrink-0 text-[10.5px] text-alert">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="min-w-0">
                  <span className="block text-[12.5px] font-medium leading-snug text-ink">
                    {insight.headline}
                  </span>
                  <span className="mt-0.5 block text-[11.5px] leading-relaxed text-ink-muted">
                    {insight.detail}
                  </span>
                </span>
              </li>
            ))}
            {insights.length === 0 && (
              <li className="py-2.5 text-[12px] text-ink-muted">{t("dash.noAnomalies")}</li>
            )}
          </ul>
        </section>

        <section className="border-t border-rule pt-4">
          <SectionHead
            kicker={t("dash.bAct")}
            title={t("dash.topActions")}
            action={
              <Link href="/actions" className="btn-quiet">
                {t("dash.actionPlan")}
              </Link>
            }
          />
          <ul>
            {data.recommendations.slice(0, 4).map((recommendation, index) => (
              <li
                key={recommendation.id}
                className="flex items-baseline gap-3 border-b border-rule py-2.5 last:border-b-0"
              >
                <span className="fig w-4 shrink-0 text-[10.5px] text-ink-faint">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[12.5px] font-medium text-ink">
                    {recommendation.title}
                  </span>
                  <span className="fig mt-0.5 block text-[11.5px] text-ink-muted">
                    −{formatTonnes(recommendation.carbon_impact_t)} ·{" "}
                    {formatUsd(recommendation.cost_impact_usd)}/yr ·{" "}
                    {t(`effort.${recommendation.effort}`)} ·{" "}
                    {recommendation.confidence_pct.toFixed(0)}%
                  </span>
                </span>
                <span className="fig shrink-0 text-[12.5px] text-ink">
                  {recommendation.score.toFixed(0)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <div className="mt-8">
        <Footnote>
          {t("dash.method", {
            records: baseline.activity_count,
            months: baseline.month_count ?? 0,
            region: titleize(data.company.region),
          })}{" "}
          <b>{t("dash.sourcesLabel")}</b> UK Government GHG Conversion Factors 2026; Cloud Carbon
          Footprint methodology.
        </Footnote>
      </div>
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
  const { t } = useLocale();
  return (
    <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3 border-b-2 border-ink pb-4">
      <div>
        <p className="kicker">{t("dash.kicker")}</p>
        <h1 className="mt-1.5 font-serif text-[26px] font-semibold leading-none tracking-tight text-ink">
          {company}
        </h1>
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        {region && <span className="chip">{t("dash.gridRegion", { region })}</span>}
        {period && (
          <span className="chip">
            {period.start} → {period.end}
          </span>
        )}
      </div>
    </header>
  );
}
