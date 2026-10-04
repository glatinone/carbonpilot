"use client";

import { AskPilot } from "@/components/AskPilot";
import { InsightCard } from "@/components/InsightCard";
import { EmptyState, ErrorBanner, Footnote, SectionHead, Skeleton } from "@/components/ui";
import { useDashboard } from "@/lib/hooks";
import { useLocale, useStreamLabel } from "@/lib/i18n";
import { formatPct } from "@/lib/format";

export default function InsightsPage() {
  const { data, loading, error, reload } = useDashboard();
  const { t } = useLocale();
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
          kicker={t("ins.bSignals")}
          title={t("ins.ready")}
          note={t("ins.rankedNote", {
            shown: data.insights.length,
            total: anomalies.length,
          })}
        />
        {data.insights.length === 0 ? (
          <EmptyState title={t("ins.emptyTitle")} hint={t("ins.emptyHint")} />
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
        <SectionHead
          kicker={t("ins.bRecord")}
          title={t("ins.allAnomalies")}
          note={t("ins.perStream")}
        />
        <table className="ledger">
          <thead>
            <tr>
              <th>{t("ins.thMonth")}</th>
              <th>{t("ins.thStream")}</th>
              <th>{t("ins.thChange")}</th>
              <th>{t("ins.thZ")}</th>
              <th>{t("ins.thDelta")}</th>
              <th>{t("ins.thSeverity")}</th>
            </tr>
          </thead>
          <tbody>
            {anomalies.map((anomaly) => (
              <tr key={`${anomaly.month}-${anomaly.activity_type}`}>
                <td>{anomaly.month}</td>
                <td>{streamLabel(anomaly.activity_type)}</td>
                <td className={anomaly.change_pct > 0 ? "text-alert" : "text-save"}>
                  {formatPct(anomaly.change_pct)}
                </td>
                <td>{anomaly.z_score.toFixed(2)}</td>
                <td>{anomaly.delta_tco2e.toFixed(1)}</td>
                <td className={anomaly.severity === "high" ? "text-stop" : "text-alert"}>
                  {t(`sev.${anomaly.severity}`)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="mt-5">
          <Footnote>{t("ins.method")}</Footnote>
        </div>
      </section>
    </div>
  );
}

function Header({ count }: { count?: number }) {
  const { t } = useLocale();
  return (
    <header className="flex flex-wrap items-end justify-between gap-x-8 gap-y-3 border-b-2 border-ink pb-4">
      <div>
        <p className="kicker">{t("ins.band")}</p>
        <h1 className="mt-1.5 font-serif text-[26px] font-semibold leading-none tracking-tight text-ink">
          {t("ins.title")}
        </h1>
      </div>
      {count !== undefined && (
        <p className="max-w-[46ch] font-serif text-[15px] leading-snug text-ink-soft">
          {t("ins.count", { n: count })}
        </p>
      )}
    </header>
  );
}
