"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { PricingScenario } from "@/lib/types";
import { ErrorBanner, SectionHead } from "@/components/ui";
import { useLocale } from "@/lib/i18n";
import { formatUsd, formatTonnes, formatUsdFull } from "@/lib/format";

const PRESETS = [0, 25, 50, 100, 150];

/**
 * Carbon pricing scenario.
 *
 * One human number ($/tCO₂e) revalues the entire action catalog. The engine
 * does the arithmetic; this panel only collects the number, calls the engine,
 * and renders its structured verdict. The verdict sentence is keyed, so each
 * language can phrase it — but every figure in it came from the engine.
 */
export function PricingPanel() {
  const { t, locale } = useLocale();
  const [price, setPrice] = useState(50);
  const [scenario, setScenario] = useState<PricingScenario | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Track the price that produced the displayed result, so the header number
  // never drifts away from what was actually computed.
  const [appliedPrice, setAppliedPrice] = useState(50);
  const firstRun = useRef(true);

  const run = async (priceValue: number) => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.pricingScenario(priceValue);
      setScenario(result);
      setAppliedPrice(priceValue);
      setPrice(priceValue);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not run the pricing engine");
    } finally {
      setLoading(false);
    }
  };

  // Initial run shows the baseline being revalued at \$50/t, the default
  // mid-market assumption — no user interaction needed to see the feature.
  useEffect(() => {
    if (firstRun.current) {
      firstRun.current = false;
      void run(50);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error) {
    return <ErrorBanner message={error} onRetry={() => void run(appliedPrice)} />;
  }

  const annual =
    scenario && scenario.annual_carbon_cost_usd > 0
      ? t("pricing.annualCost", { price: appliedPrice, amount: formatUsdFull(scenario.annual_carbon_cost_usd) })
      : null;

  return (
    <section className="mt-8 border-t border-rule pt-4">
      <SectionHead
        kicker={t("pricing.band")}
        title={t("pricing.title", { price: `$${appliedPrice}` })}
        note={t("pricing.lead")}
      />

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-[12px] text-ink-muted">
          {t("pricing.priceLabel")}
          <input
            type="number"
            min={0}
            step={5}
            value={price}
            onChange={(event) => setPrice(Number(event.target.value))}
            onKeyDown={(event) => {
              if (event.key === "Enter") void run(price);
            }}
            className="fig w-28 border border-rule-strong bg-transparent px-2 py-1.5 text-[13px] text-ink outline-none focus:border-ink"
          />
        </label>
        <button type="button" className="btn" disabled={loading} onClick={() => void run(price)}>
          {loading ? t("pricing.applying") : t("pricing.apply")}
        </button>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="text-[11px] uppercase tracking-wide text-ink-faint">{t("pricing.presets")}:</span>
        {PRESETS.map((preset) => (
          <button
            key={preset}
            type="button"
            className={`chip ${appliedPrice === preset && !loading ? "border-ink text-ink" : ""}`}
            onClick={() => void run(preset)}
          >
            ${preset}
          </button>
        ))}
      </div>

      {annual && <p className="fig mt-4 text-[12px] text-ink-muted">{annual}</p>}

      {scenario && !loading && scenario.action_count > 0 && (
        <>
          <div className="mt-5 border-l-2 border-ink pl-3">
            <p className="text-[10px] uppercase tracking-wide text-ink-faint">
              {t("pricing.verdictTitle")}
            </p>
            <p className="mt-1 text-[13px] leading-relaxed text-ink">
              {t(scenario.verdict_key, {
                price: formatUsd(scenario.price_usd_per_t),
                leader_title:
                  scenario.verdict_vars.leader_title ?? "",
                leader_net_usd: formatUsd(Number(scenario.verdict_vars.leader_net_usd ?? 0)),
                leader_carbon_value_usd: formatUsd(
                  Number(scenario.verdict_vars.leader_carbon_value_usd ?? 0),
                ),
              })}
            </p>
          </div>

          <SectionHead
            kicker={t("pricing.bRanked")}
            title={t("pricing.bRanked")}
            note={`${scenario.action_count} ${t("act.ranked").toLowerCase()}`}
          />

          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[640px] table-fixed border-collapse text-[12px]">
              <thead>
                <tr className="border-b border-rule">
                  <th className="w-10 py-2 pr-2 text-left align-bottom text-[10px] font-normal uppercase tracking-wide text-ink-faint">
                    {t("pricing.thRank")}
                  </th>
                  <th className="py-2 pr-3 text-left align-bottom text-[10px] font-normal uppercase tracking-wide text-ink-faint">
                    {t("pricing.thAction")}
                  </th>
                  <th className="w-20 py-2 pr-3 text-right align-bottom text-[10px] font-normal uppercase tracking-wide text-ink-faint">
                    {t("pricing.thT")}
                  </th>
                  <th className="w-24 py-2 pr-3 text-right align-bottom text-[10px] font-normal uppercase tracking-wide text-ink-faint">
                    {t("pricing.thCarbonValue")}
                  </th>
                  <th className="w-24 py-2 pr-3 text-right align-bottom text-[10px] font-normal uppercase tracking-wide text-ink-faint">
                    {t("pricing.thNet")}
                  </th>
                  <th className="w-28 py-2 text-right align-bottom text-[10px] font-normal uppercase tracking-wide text-ink-faint">
                    {t("pricing.thDelta")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {scenario.actions.map((action) => {
                  const delta = action.rank_financial - action.rank_priced;
                  const deltaLabel =
                    delta > 0 ? t("pricing.up", { n: delta }) : delta < 0 ? t("pricing.down", { n: -delta }) : t("pricing.same");
                  return (
                    <tr
                      key={action.id}
                      className="border-b border-rule/[.6] align-top hover:bg-canvas/60"
                    >
                      <td className="fig py-2 pr-2 text-ink">{action.rank_priced}</td>
                      <td className="py-2 pr-3 text-ink">
                        <span className="block text-[13px] leading-snug">{action.title}</span>
                      </td>
                      <td className="fig py-2 pr-3 text-right text-ink-muted">
                        {formatTonnes(action.carbon_impact_t, 1)}
                      </td>
                      <td className="fig py-2 pr-3 text-right text-save">
                        {formatUsd(action.carbon_value_usd)}
                      </td>
                      <td className={`fig py-2 pr-3 text-right ${action.net_usd < 0 ? "text-save" : "text-stop"}`}>
                        {formatUsd(action.net_usd)}
                      </td>
                      <td className="py-2 text-right text-ink-muted">{deltaLabel}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
