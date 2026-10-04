"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { JapacBenchmark, JapacGridRow } from "@/lib/types";
import { Emphasised, ErrorBanner, Footnote, SectionHead, Skeleton } from "@/components/ui";
import { useLocale } from "@/lib/i18n";

/**
 * A comparison surface, so it is a table and not a chart.
 *
 * The editorial idea: the same measured consumption, priced against every grid in
 * the region. That turns "how much do we emit" into "where would this have been
 * cheaper on the atmosphere", which is a decision a location-aware operator can
 * actually act on.
 *
 * The basis travels with the numbers. Ember publishes full-lifecycle intensity;
 * the company's own reported figures use a generation-boundary Scope 2 factor. The
 * page states both rather than quietly blending them, because a comparison that
 * hides its boundary is worse than no comparison.
 */
export default function JapacPage() {
  const { t, locale } = useLocale();
  const [data, setData] = useState<JapacBenchmark | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await api.japac());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load benchmarks");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const nf = (value: number, digits = 0) =>
    value.toLocaleString(locale === "id" ? "id-ID" : "en-US", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });

  if (error) {
    return (
      <div>
        <Masthead />
        <div className="mt-7">
          <ErrorBanner message={error} onRetry={load} />
        </div>
      </div>
    );
  }

  if (loading || !data) {
    return (
      <div>
        <Masthead />
        <Skeleton className="mt-7 h-28" />
        <Skeleton className="mt-6 h-64" />
      </div>
    );
  }

  const { home, measured, countries } = data;
  const cleanest = countries[0];
  const dirtiest = countries[countries.length - 1];

  return (
    <div>
      <Masthead />

      {/* Where we stand, and what the same consumption costs elsewhere. */}
      <section className="mt-7">
        <div className="grid gap-x-12 gap-y-8 lg:grid-cols-[1.45fr_1fr]">
          <div>
            <p className="kicker">{t("japac.home")}</p>
            <div className="mt-2.5 flex flex-wrap items-baseline gap-x-4 gap-y-2">
              <span className="fig text-[46px] font-medium leading-none tracking-[-0.02em] text-ink">
                {nf(home.intensity, 1)}
              </span>
              <span className="text-[13px] text-ink-muted">{t("japac.unit")}</span>
              <span className="fig border border-rule-strong px-2 py-0.5 text-[11.5px] text-alert">
                {t("japac.rank", { n: home.rank, of: home.of })}
              </span>
            </div>

            <p className="mt-5 max-w-[56ch] font-serif text-[19px] leading-[1.55] text-ink-soft">
              <Emphasised
                template={t("japac.lead")}
                values={{ country: home.country, rank: String(home.rank), of: String(home.of) }}
              />
            </p>

            <p className="mt-4 text-[12px] text-ink-muted">
              {t("japac.homeGrid")}: <span className="fig text-ink">{home.country}</span> ·{" "}
              {t("japac.thYear")} <span className="fig text-ink">{home.year}</span>
            </p>
          </div>

          <div className="grid grid-cols-2 gap-x-6 gap-y-6 self-start">
            <div>
              <p className="kicker">{t("japac.measuredKwh")}</p>
              <p className="fig mt-1.5 text-[22px] font-medium leading-none tracking-tight text-ink">
                {nf(measured.electricity_kwh)}
              </p>
              <p className="mt-1.5 text-[11px] leading-snug text-ink-muted">kWh</p>
            </div>
            <div>
              <p className="kicker">{t("japac.measuredTco2e")}</p>
              <p className="fig mt-1.5 text-[22px] font-medium leading-none tracking-tight text-ink">
                {nf(measured.tco2e, 1)}
              </p>
              <p className="mt-1.5 text-[11px] leading-snug text-ink-muted">tCO₂e</p>
            </div>
            <div>
              <p className="kicker">{cleanest.country}</p>
              <p className="fig mt-1.5 text-[22px] font-medium leading-none tracking-tight text-save">
                {nf(cleanest.counterfactual_tco2e, 0)}
              </p>
              <p className="mt-1.5 text-[11px] leading-snug text-ink-muted">
                {t("japac.cleaner", { pct: nf(Math.abs(cleanest.delta_pct_vs_home), 0) })}
              </p>
            </div>
            <div>
              <p className="kicker">{dirtiest.country}</p>
              <p className="fig mt-1.5 text-[22px] font-medium leading-none tracking-tight text-alert">
                {nf(dirtiest.counterfactual_tco2e, 0)}
              </p>
              <p className="mt-1.5 text-[11px] leading-snug text-ink-muted">
                {t("japac.dirtier", { pct: nf(Math.abs(dirtiest.delta_pct_vs_home), 0) })}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* The comparison itself. */}
      <section className="mt-8 border-t border-rule pt-4">
        <SectionHead
          kicker={t("japac.kicker")}
          title={t("japac.counterfactualTitle")}
          note={t("japac.counterfactualNote")}
        />

        <div className="overflow-x-auto">
          <table className="ledger">
            <thead>
              <tr>
                <th>{t("japac.thRank")}</th>
                <th>{t("japac.thCountry")}</th>
                <th>{t("japac.thIntensity")}</th>
                <th>{t("japac.thYear")}</th>
                <th>{t("japac.thDelta")}</th>
                <th>{t("japac.thMix")}</th>
                <th>{t("japac.thCounterfactual")}</th>
              </tr>
            </thead>
            <tbody>
              {countries.map((row) => (
                <tr key={row.iso3} className={row.iso3 === home.iso3 ? "bg-paper-band" : undefined}>
                  <td className="text-ink-faint">{row.rank}</td>
                  <td>
                    {row.country}
                    {row.iso3 === home.iso3 && (
                      <span className="ml-2 text-[10px] text-ink-faint">{t("japac.sameGrid")}</span>
                    )}
                  </td>
                  <td>{nf(row.intensity, 1)}</td>
                  <td className="text-ink-muted">{row.year}</td>
                  <td className={deltaTone(row)}>{deltaLabel(row, home, t, nf)}</td>
                  <td className="text-ink-muted">{topSources(row)}</td>
                  <td>{nf(row.counterfactual_tco2e, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="mt-8">
        <Footnote>
          <b>{t("japac.methodTitle")}.</b> {data.boundary_note} {t("japac.basisWarning")}{" "}
          <b>{t("japac.source")}:</b> {data.source} ({data.retrieved_via}) ·{" "}
          <b>{t("japac.licence")}:</b> {data.licence} · <b>{t("japac.boundary")}:</b> {data.basis}.
        </Footnote>
      </div>
    </div>
  );
}

function deltaTone(row: JapacGridRow): string {
  if (row.delta_pct_vs_home < 0) return "text-save";
  if (row.delta_pct_vs_home > 0) return "text-alert";
  return "text-ink-muted";
}

function deltaLabel(
  row: JapacGridRow,
  home: JapacBenchmark["home"],
  t: (key: string, vars?: Record<string, string | number>) => string,
  nf: (value: number, digits?: number) => string,
): string {
  if (row.iso3 === home.iso3) return "—";
  // Formatted through the locale-aware helper: the intensity column already uses
  // the locale's decimal separator, and a hardcoded toFixed() would print "86.9%"
  // next to "705,3" in Indonesian.
  const pct = nf(Math.abs(row.delta_pct_vs_home), 1);
  return row.delta_pct_vs_home < 0 ? t("japac.cleaner", { pct }) : t("japac.dirtier", { pct });
}

/** The two largest generation sources, so the intensity has an explanation. */
function topSources(row: JapacGridRow): string {
  return Object.entries(row.shares_pct)
    .filter((entry): entry is [string, number] => typeof entry[1] === "number" && entry[1] > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 2)
    .map(([fuel, pct]) => `${fuel.replace(/_/g, " ")} ${pct.toFixed(0)}%`)
    .join(" · ");
}

function Masthead() {
  const { t } = useLocale();
  return (
    <header className="flex flex-wrap items-end justify-between gap-x-8 gap-y-3 border-b-2 border-ink pb-4">
      <div>
        <p className="kicker">{t("japac.kicker")}</p>
        <h1 className="mt-1.5 font-serif text-[26px] font-semibold leading-none tracking-tight text-ink">
          {t("japac.title")}
        </h1>
      </div>
      <p className="max-w-[44ch] font-serif text-[15px] leading-snug text-ink-soft">
        {t("japac.band")} · {t("japac.unit")}
      </p>
    </header>
  );
}
