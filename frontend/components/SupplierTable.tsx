"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SupplierBreakdown } from "@/lib/types";
import { ErrorBanner, SectionHead, Skeleton } from "@/components/ui";
import { useLocale } from "@/lib/i18n";
import { formatUsd } from "@/lib/format";

/**
 * Where procurement carbon sits. The engine splits the single procurement spend
 * line across fixed, documented segments — this is demo attribution, never
 * measured counterparty data — so the UI says so under the table.
 */
export function SupplierTable() {
  const { t, locale } = useLocale();
  const [data, setData] = useState<SupplierBreakdown | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .suppliers()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load supplier data"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <section className="mt-8 border-t border-rule pt-4">
      <SectionHead
        kicker={t("sup.band")}
        title={t("sup.title")}
        note={t("sup.note")}
      />
      {error ? (
        <div className="mt-3">
          <ErrorBanner message={error} onRetry={() => window.location.reload()} />
        </div>
      ) : loading ? (
        <div className="mt-3">
          <Skeleton className="h-48" />
        </div>
      ) : data && data.segments.length > 0 ? (
        <>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[520px] table-fixed border-collapse text-[12px]">
              <thead>
                <tr className="border-b border-rule">
                  <th className="py-2 pr-3 text-left text-[10px] font-normal uppercase tracking-wide text-ink-faint">
                    {t("sup.thSegment")}
                  </th>
                  <th className="w-16 py-2 pr-3 text-right text-[10px] font-normal uppercase tracking-wide text-ink-faint">
                    {t("sup.thShare")}
                  </th>
                  <th className="w-28 py-2 pr-3 text-right text-[10px] font-normal uppercase tracking-wide text-ink-faint">
                    {t("sup.thSpend")}
                  </th>
                  <th className="w-32 py-2 text-right text-[10px] font-normal uppercase tracking-wide text-ink-faint">
                    {t("sup.thTco2e")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.segments.map((segment) => (
                  <tr key={segment.name} className="border-b border-rule/[.6] align-top">
                    <td className="py-2 pr-3 text-[13px] text-ink">{segment.name}</td>
                    <td className="fig py-2 pr-3 text-right text-ink-muted">
                      {segment.share_pct.toLocaleString(locale === "id" ? "id-ID" : "en-US", {
                        maximumFractionDigits: 0,
                      })}
                      %
                    </td>
                    <td className="fig py-2 pr-3 text-right text-ink">
                      {formatUsd(segment.spend_usd)}
                    </td>
                    <td className="fig py-2 text-right text-ink">
                      {segment.embedded_tco2e.toLocaleString(locale === "id" ? "id-ID" : "en-US", {
                        maximumFractionDigits: 1,
                      })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 max-w-[72ch] text-[11.5px] leading-relaxed text-ink-faint">
            {t("sup.footnote", { note: data.attribution_note })}
          </p>
        </>
      ) : (
        <p className="py-4 text-[12px] text-ink-muted">{t("sup.empty")}</p>
      )}
    </section>
  );
}
