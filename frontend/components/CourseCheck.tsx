"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CourseCheck as CourseCheckData } from "@/lib/types";
import { ErrorBanner, SectionHead, Skeleton } from "@/components/ui";
import { useLocale } from "@/lib/i18n";
import { formatTonnes } from "@/lib/format";

/**
 * The approved plan against recorded reality. The engine delivers a verdict
 * key plus the numbers; this component turns it into rows and a sentence in the
 * current language. `onPlanChange` lets the actions page refresh this whenever
 * an action is approved/cancelled.
 */
export function CourseCheck({
  refreshKey,
}: {
  refreshKey?: number;
}) {
  const { t, locale } = useLocale();
  const [data, setData] = useState<CourseCheckData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api
      .course()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load course check"))
      .finally(() => setLoading(false));
  }, [refreshKey]);

  return (
    <section className="mt-8 border-t border-rule pt-4">
      <SectionHead
        kicker={t("course.band")}
        title={t("course.title")}
        note={t("course.lead")}
      />
      {error ? (
        <div className="mt-3">
          <ErrorBanner message={error} onRetry={() => window.location.reload()} />
        </div>
      ) : loading ? (
        <div className="mt-3">
          <Skeleton className="h-32" />
        </div>
      ) : data ? (
        <>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[420px] table-fixed border-collapse text-[12px]">
              <thead>
                <tr className="border-b border-rule">
                  <th className="py-2 pr-3 text-left text-[10px] font-normal uppercase tracking-wide text-ink-faint">
                    {t("course.thRequired")}
                  </th>
                  <th className="py-2 pr-3 text-left text-[10px] font-normal uppercase tracking-wide text-ink-faint">
                    {t("course.thActual")}
                  </th>
                  <th className="py-2 text-right text-[10px] font-normal uppercase tracking-wide text-ink-faint">
                    {t("course.thStatus")}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-rule/[.6]">
                  <td className="fig py-2 pr-3 text-ink">
                    {data.required_monthly_tco2e.toLocaleString(locale === "id" ? "id-ID" : "en-US", {
                      maximumFractionDigits: 2,
                    })}{" "}
                    <span className="text-ink-faint">tCO₂e/mo</span>
                  </td>
                  <td className="fig py-2 pr-3 text-ink">
                    {data.actual_monthly_tco2e.toLocaleString(locale === "id" ? "id-ID" : "en-US", {
                      maximumFractionDigits: 2,
                    })}{" "}
                    <span className="text-ink-faint">tCO₂e/mo</span>
                  </td>
                  <td
                    className={`fig py-2 text-right ${data.verdict_key === "course.onTrack" ? "text-save" : "text-alert"}`}
                  >
                    {data.verdict_key === "course.noPlan"
                      ? "—"
                      : data.verdict_key === "course.onTrack"
                        ? "▲"
                        : "▼"}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="mt-4 border-l-2 border-ink pl-3">
            <p className="text-[10px] uppercase tracking-wide text-ink-faint">
              {t("course.band")}
            </p>
            <p className="mt-1 text-[13px] leading-relaxed text-ink">
              {t(data.verdict_key, {
                actual: data.actual_monthly_tco2e.toFixed(2),
                required: data.required_monthly_tco2e.toFixed(2),
                baseline: data.baseline_monthly_tco2e.toFixed(2),
              })}
            </p>
            <p className="mt-2 max-w-[72ch] text-[11.5px] leading-relaxed text-ink-faint">
              {t("course.method")}
            </p>
          </div>
        </>
      ) : null}
    </section>
  );
}
