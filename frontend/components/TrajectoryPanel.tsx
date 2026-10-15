"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Trajectory } from "@/lib/types";
import { ErrorBanner, SectionHead, Skeleton } from "@/components/ui";
import { useLocale } from "@/lib/i18n";
import { formatUsd } from "@/lib/format";

const CURRENT_YEAR = new Date().getFullYear();

/**
 * Cost of a stated target: the engine draws the linear glide from today's footprint
 * to a % reduction by a target year, and prices every year at a human-supplied
 * carbon price. All numbers come from the engine.
 */
export function TrajectoryPanel() {
  const { t, locale } = useLocale();
  const [targetPct, setTargetPct] = useState(42);
  const [targetYear, setTargetYear] = useState(2030);
  const [price, setPrice] = useState(50);
  const [result, setResult] = useState<Trajectory | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canRun =
    !loading &&
    targetPct >= 1 &&
    targetPct <= 99 &&
    targetYear > CURRENT_YEAR &&
    price >= 0;

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.trajectory({
        target_reduction_pct: targetPct,
        target_year: targetYear,
        price_usd_per_t: price,
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not project the trajectory");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="mt-8 border-t border-rule pt-4">
      <SectionHead
        kicker={t("tray.band")}
        title={t("tray.title")}
        note={t("tray.lead")}
      />

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-[12px] text-ink-muted">
          {t("tray.inputPct")}
          <input
            type="number"
            min={1}
            max={99}
            value={targetPct}
            onChange={(event) => setTargetPct(Number(event.target.value))}
            className="fig w-20 border border-rule-strong bg-transparent px-2 py-1.5 text-[13px] text-ink outline-none focus:border-ink"
          />
        </label>
        <label className="flex items-center gap-2 text-[12px] text-ink-muted">
          {t("tray.inputYear")}
          <input
            type="number"
            min={CURRENT_YEAR + 1}
            value={targetYear}
            onChange={(event) => setTargetYear(Number(event.target.value))}
            className="fig w-24 border border-rule-strong bg-transparent px-2 py-1.5 text-[13px] text-ink outline-none focus:border-ink"
          />
        </label>
        <label className="flex items-center gap-2 text-[12px] text-ink-muted">
          {t("tray.price")}
          <input
            type="number"
            min={0}
            step={5}
            value={price}
            onChange={(event) => setPrice(Number(event.target.value))}
            className="fig w-24 border border-rule-strong bg-transparent px-2 py-1.5 text-[13px] text-ink outline-none focus:border-ink"
          />
        </label>
        <button type="button" className="btn" disabled={!canRun} onClick={() => void run()}>
          {loading ? t("tray.running") : t("tray.run")}
        </button>
      </div>

      {error ? (
        <div className="mt-4">
          <ErrorBanner message={error} onRetry={() => void run()} />
        </div>
      ) : loading ? (
        <div className="mt-4">
          <Skeleton className="h-40" />
        </div>
      ) : result && result.years.length > 0 ? (
        <div className="mt-5">
          <p className="fig text-[12px] text-ink-muted">
            {result.years[0]?.year} → {result.years[result.years.length - 1]?.year} ·{" "}
            {result.baseline_total_tco2e.toLocaleString(locale === "id" ? "id-ID" : "en-US", {
              maximumFractionDigits: 0,
            })}{" "}
            → {result.target_total_tco2e.toLocaleString(locale === "id" ? "id-ID" : "en-US", {
              maximumFractionDigits: 0,
            })}{" "}
            · −{result.target_reduction_pct}% by {result.target_year}
          </p>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[480px] table-fixed border-collapse text-[12px]">
              <thead>
                <tr className="border-b border-rule">
                  <th className="py-2 pr-3 text-left text-[10px] font-normal uppercase tracking-wide text-ink-faint">
                    {t("tray.thYear")}
                  </th>
                  <th className="py-2 pr-3 text-right text-[10px] font-normal uppercase tracking-wide text-ink-faint">
                    {t("tray.thProjected")}
                  </th>
                  <th className="py-2 text-right text-[10px] font-normal uppercase tracking-wide text-ink-faint">
                    {t("tray.thCost")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {result.years.map((year) => (
                  <tr key={year.year} className="border-b border-rule/[.6]">
                    <td className="fig py-2 pr-3 text-ink">{year.year}</td>
                    <td className="fig py-2 pr-3 text-right text-ink">
                      {year.projected_tco2e.toLocaleString(locale === "id" ? "id-ID" : "en-US", {
                        maximumFractionDigits: 0,
                      })}{" "}
                      <span className="text-ink-faint">tCO₂e</span>
                    </td>
                    <td className="fig py-2 text-right text-ink-muted">
                      {formatUsd(year.carbon_cost_usd)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      <p className="mt-3 max-w-[72ch] text-[11.5px] leading-relaxed text-ink-faint">
        {t("tray.method")}
      </p>
    </section>
  );
}
