"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Recommendation } from "@/lib/types";
import { useLocale, useStreamLabel } from "@/lib/i18n";
import { EFFORT_COLOR, formatTonnes, formatUsd, formatUsdMagnitude } from "@/lib/format";

const OWNERS = ["Engineering", "Facilities", "Procurement", "Travel & Ops", "Finance"];

/**
 * A ranked line in the action register. The rank and score lead because they are
 * the ranking the product computed; the impact figures are aligned right so the
 * eye can compare rows without reading prose.
 */
export function RecommendationCard({
  recommendation,
  rank,
  onCreated,
}: {
  recommendation: Recommendation;
  rank: number;
  onCreated?: () => void;
}) {
  const { t } = useLocale();
  const streamLabel = useStreamLabel();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [owner, setOwner] = useState(OWNERS[0]);
  const [created, setCreated] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const evidence = recommendation.evidence;
  const calculation = evidence.calculation;
  const tradeoff = evidence.tradeoff;

  async function createAction() {
    setBusy(true);
    setError(null);
    try {
      await api.createAction(recommendation.id, owner);
      setCreated(true);
      onCreated?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create action");
    } finally {
      setBusy(false);
    }
  }

  return (
    <article id={`rec-${recommendation.id}`} className="scroll-mt-6 border-b border-rule">
      <div className="flex flex-col gap-3 py-4 md:flex-row md:items-start md:gap-6">
        <div className="flex shrink-0 items-baseline gap-3 md:w-20 md:flex-col md:gap-0.5">
          <p className="fig text-[10px] text-ink-faint">
            {t("rec.rank", { n: String(rank).padStart(2, "0") })}
          </p>
          <p className="fig text-[19px] font-medium leading-none text-ink">
            {recommendation.score.toFixed(0)}
          </p>
          <p className="text-[10px] text-ink-faint md:mt-0.5">{t("rec.score")}</p>
        </div>

        <div className="min-w-0 flex-1">
          <h3 className="text-[13.5px] font-medium leading-snug text-ink">{recommendation.title}</h3>
          <p className="mt-1 text-[12px] leading-relaxed text-ink-muted">
            {recommendation.description}
          </p>

          <div className="mt-2.5 flex flex-wrap items-baseline gap-x-5 gap-y-1.5">
            <span className="fig text-[13px] text-save">
              −{formatTonnes(recommendation.carbon_impact_t)}
              <span className="ml-1 text-[10px] text-ink-faint">{t("rec.perYear")}</span>
            </span>
            <span className="fig text-[13px] text-ink">
              {formatUsd(recommendation.cost_impact_usd)}
              <span className="ml-1 text-[10px] text-ink-faint">{t("rec.perYear")}</span>
            </span>
            <span className={`text-[11px] ${EFFORT_COLOR[recommendation.effort]}`}>
              {t(`effort.${recommendation.effort}`)}
            </span>
            <span className="fig text-[11px] text-ink-muted">
              {t("rec.confidence", { pct: recommendation.confidence_pct.toFixed(0) })}
            </span>
          </div>

          {tradeoff && (
            <p className="mt-2.5 border-l-2 border-l-rule-strong pl-2.5 text-[11.5px] leading-relaxed text-ink-muted">
              <span className="fig text-ink-faint">
                {t("rec.tradeoffVs", { rank: String(tradeoff.vs_rank).padStart(2, "0") })}
              </span>{" "}
              {tradeoffSentence(t, tradeoff)}
            </p>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2.5 border-t border-rule py-2.5">
        <select value={owner} onChange={(event) => setOwner(event.target.value)} className="select">
          {OWNERS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>

        <button
          type="button"
          className="btn-primary px-3 py-1.5 text-[12px]"
          onClick={() => void createAction()}
          disabled={busy || created}
        >
          {created ? t("rec.created") : busy ? t("rec.creating") : t("rec.create")}
        </button>

        <button type="button" className="btn-quiet ml-auto" onClick={() => setOpen((value) => !value)}>
          {open ? t("rec.hideEvidence") : t("rec.why")}
        </button>
      </div>

      {error && (
        <p className="border-t border-rule py-2 text-[11.5px] text-stop">{error}</p>
      )}

      {open && (
        <div className="border-t border-rule bg-paper-band/60 px-4 py-4">
          {calculation && (
            <div className="mb-4 border-b border-rule pb-3">
              <p className="kicker mb-2">{t("rec.calculation")}</p>
              <p className="fig text-[12px] leading-relaxed text-ink">
                {calculation.activity_value.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                <span className="ml-1 text-ink-muted">{calculation.activity_unit}</span>
                <span className="mx-2 text-ink-faint">×</span>
                {calculation.factor_value ?? "—"}
                <span className="ml-1 text-ink-muted">
                  kgCO₂e/{calculation.activity_unit}
                </span>
                <span className="mx-2 text-ink-faint">=</span>
                {formatTonnes(calculation.result_tco2e, 2)}
              </p>
              <p className="mt-2 text-[11px] leading-relaxed text-ink-muted">
                {t("rec.calcSource", {
                  source: calculation.factor_source ?? "—",
                  year: String(calculation.factor_year ?? "—"),
                })}
                {calculation.factor_uncertainty_pct !== null && (
                  <>
                    {" · "}
                    {t("rec.calcUncertainty", { pct: String(calculation.factor_uncertainty_pct) })}
                  </>
                )}
              </p>
            </div>
          )}
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-[11.5px] sm:grid-cols-3">
            <Evidence label={t("rec.stream")} value={streamLabel(recommendation.activity_type)} />
            <Evidence
              label={t("rec.share")}
              value={`${evidence.share_of_footprint_pct ?? "—"}%`}
            />
            <Evidence label={t("rec.baseline")} value={`${evidence.baseline_tco2e ?? "—"} tCO₂e`} />
            <Evidence label={t("rec.method")} value={String(evidence.method ?? "—")} />
            <Evidence label={t("rec.unit")} value={String(evidence.unit ?? "—")} />
            <Evidence label={t("rec.basis")} value="GHG Protocol" />
          </dl>

          {Array.isArray(evidence.assumptions) && (
            <div className="mt-4 border-t border-rule pt-3">
              <p className="kicker mb-2">{t("rec.assumptions")}</p>
              <ul className="space-y-1">
                {(evidence.assumptions as string[]).map((assumption) => (
                  <li key={assumption} className="text-[11.5px] leading-relaxed text-ink-muted">
                    {assumption}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {Array.isArray(evidence.driver) && evidence.driver.length > 0 && (
            <div className="mt-4 border-t border-rule pt-3">
              <p className="kicker mb-2">{t("rec.driver")}</p>
              {(evidence.driver as Array<{ description: string }>).map((driver) => (
                <p key={driver.description} className="text-[11.5px] text-ink-muted">
                  {driver.description}
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </article>
  );
}

function Evidence({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 border-b border-rule pb-1.5">
      <dt className="shrink-0 text-ink-muted">{label}</dt>
      <dd className="fig truncate text-right text-ink">{value}</dd>
    </div>
  );
}

type Translate = (key: string, vars?: Record<string, string | number>) => string;

/**
 * The comparison that makes the ranking a decision rather than a sort.
 *
 * Built from whole translated clauses rather than glued-together fragments: each
 * clause is a complete phrase in its own right, so neither language is forced into
 * the other's word order. The figures go through the shared formatters, so the
 * units match the numbers printed directly above them on the same card.
 */
function tradeoffSentence(
  t: Translate,
  tradeoff: NonNullable<Recommendation["evidence"]["tradeoff"]>,
): string {
  const carbon =
    Math.abs(tradeoff.carbon_delta_t) < 0.5
      ? t("rec.carbonSame")
      : tradeoff.carbon_delta_t > 0
        ? t("rec.carbonMore", { v: formatTonnes(tradeoff.carbon_delta_t) })
        : t("rec.carbonLess", { v: formatTonnes(Math.abs(tradeoff.carbon_delta_t)) });

  const cost =
    Math.abs(tradeoff.cost_delta_usd) < 500
      ? t("rec.costSame")
      : tradeoff.cost_delta_usd < 0
        ? t("rec.costCheaper", { v: formatUsdMagnitude(tradeoff.cost_delta_usd) })
        : t("rec.costCostlier", { v: formatUsdMagnitude(tradeoff.cost_delta_usd) });

  const effort =
    tradeoff.effort_delta < 0
      ? t("rec.effortLower")
      : tradeoff.effort_delta > 0
        ? t("rec.effortHigher")
        : t("rec.effortSame");

  return [carbon, cost, effort].join(", ");
}
