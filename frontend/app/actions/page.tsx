"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ActionItem, Recommendation } from "@/lib/types";
import { RecommendationCard } from "@/components/RecommendationCard";
import { DecisionMatrix } from "@/components/DecisionMatrix";
import { MacCurve } from "@/components/MacCurve";
import { PricingPanel } from "@/components/PricingPanel";
import { SupplierTable } from "@/components/SupplierTable";
import { CourseCheck } from "@/components/CourseCheck";
import { EmptyState, ErrorBanner, Footnote, SectionHead, Skeleton } from "@/components/ui";
import { useLocale } from "@/lib/i18n";
import { formatTonnes, formatUsd } from "@/lib/format";

const STATUS_STYLE: Record<string, string> = {
  open: "border-rule-strong text-ink-muted",
  in_progress: "border-alert/50 text-alert",
  done: "border-save/50 text-save",
  cancelled: "border-rule-strong text-ink-faint",
};

export default function ActionsPage() {
  const { t } = useLocale();
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [actions, setActions] = useState<ActionItem[]>([]);
  const [totals, setTotals] = useState<{ expected_carbon_t: number; expected_cost_usd: number } | null>(null);
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  // Bumped on every load so the course check re-fetches when the plan changes.
  const [planTick, setPlanTick] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [recs, actionList] = await Promise.all([api.recommendations(), api.actions()]);
      setRecommendations(recs.recommendations);
      setActions(actionList.actions);
      setTotals(actionList.totals);
      setNote(actionList.note);
      setPlanTick((tick) => tick + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load the action plan");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function advance(action: ActionItem) {
    const next =
      action.status === "open" ? "in_progress" : action.status === "in_progress" ? "done" : "done";
    await api.updateAction(action.id, next);
    await load();
  }

  if (error) {
    return (
      <div className="space-y-6">
        <Header />
        <ErrorBanner message={error} onRetry={load} />
      </div>
    );
  }

  const visible = showAll ? recommendations : recommendations.slice(0, 8);
  // What the MAC curve can actually price: an action with no tonnage has no
  // cost per tonne. The register itself stays complete either way.
  const priced = recommendations.filter((rec) => rec.carbon_impact_t > 0);

  return (
    <div>
      <Header onReload={load} />

      {loading ? (
        <>
          <Skeleton className="mt-8 h-40" />
          <Skeleton className="mt-6 h-40" />
        </>
      ) : (
        <>
          {/* Decision matrix — the trade-off, before the ranking that assumes it */}
          <section className="mt-8 border-t border-rule pt-4">
            <SectionHead kicker={t("mx.band")} title={t("mx.title")} note={t("mx.note")} />
            {recommendations.length === 0 ? (
              <p className="py-6 text-[12px] text-ink-muted">{t("mx.empty")}</p>
            ) : (
              <DecisionMatrix recommendations={recommendations} />
            )}
          </section>

          {/* Marginal abatement cost — what each tonne costs, cheapest first */}
          <section className="mt-8 border-t border-rule pt-4">
            <SectionHead
              kicker={t("mac.band")}
              title={t("mac.title")}
              note={
                priced.length > 0
                  ? t("mac.total", {
                      total: formatTonnes(priced.reduce((sum, rec) => sum + rec.carbon_impact_t, 0)),
                      n: priced.length,
                    })
                  : undefined
              }
            />
            {priced.length === 0 ? (
              <p className="py-6 text-[12px] text-ink-muted">{t("mac.empty")}</p>
            ) : (
              <MacCurve recommendations={recommendations} />
            )}
          </section>

          <PricingPanel />

          {/* Ranked actions */}
          <section className="mt-8 border-t border-rule pt-4">
            <SectionHead
              kicker={t("act.bRegister")}
              title={t("act.ranked", { n: recommendations.length })}
              note={t("act.rankedNote")}
            />

            {recommendations.length === 0 ? (
              <EmptyState title={t("act.emptyTitle")} hint={t("act.emptyHint")} />
            ) : (
              visible.map((recommendation, index) => (
                <RecommendationCard
                  key={recommendation.id}
                  recommendation={recommendation}
                  rank={index + 1}
                  onCreated={load}
                />
              ))
            )}

            {recommendations.length > 8 && (
              <button
                type="button"
                className="btn-ghost mt-4 w-full"
                onClick={() => setShowAll((value) => !value)}
              >
                {showAll ? t("act.showTop") : t("act.showAll", { n: recommendations.length })}
              </button>
            )}
          </section>

          {/* Tracked actions */}
          <section className="mt-8 border-t border-rule pt-4">
            <SectionHead
              kicker={t("act.bPlan")}
              title={t("act.planCount", { n: actions.length })}
              note={
                totals && actions.length > 0
                  ? t("act.ifAll", {
                      carbon: totals.expected_carbon_t.toLocaleString("en-US", {
                        maximumFractionDigits: 0,
                      }),
                      cost: formatUsd(totals.expected_cost_usd),
                    })
                  : undefined
              }
              action={
                actions.length > 0 ? (
                  <div className="flex items-center gap-2">
                    <a
                      className="btn-ghost px-3 py-1.5 text-[12px]"
                      href={api.exportActionsUrl("md")}
                      title="Download this plan with its expected impact and assumptions"
                    >
                      {t("act.downloadMd")}
                    </a>
                    <a
                      className="btn-ghost px-3 py-1.5 text-[12px]"
                      href={api.exportActionsUrl("csv")}
                      title="Download this plan as a spreadsheet"
                    >
                      {t("act.downloadCsv")}
                    </a>
                  </div>
                ) : undefined
              }
            />

            {actions.length === 0 ? (
              <p className="py-6 text-[12px] text-ink-muted">{t("act.none")}</p>
            ) : (
              <ul>
                {actions.map((action) => (
                  <li
                    key={action.id}
                    className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-rule py-3 last:border-b-0"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[12.5px] text-ink">{action.task}</p>
                      <p className="fig mt-0.5 text-[11px] text-ink-muted">
                        {t("act.ownerLine", {
                          owner: action.owner,
                          carbon: formatTonnes(action.expected_carbon_t),
                          cost: formatUsd(action.expected_cost_usd),
                        })}
                      </p>
                    </div>
                    <span className={`chip ${STATUS_STYLE[action.status] ?? ""}`}>
                      {t(`status.${action.status}`)}
                    </span>
                    {action.status !== "done" && (
                      <button
                        type="button"
                        className="btn-ghost px-3 py-1.5 text-[12px]"
                        onClick={() => void advance(action)}
                      >
                        {action.status === "open" ? t("act.start") : t("act.complete")}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}

            {note && (
              <div className="mt-5">
                <Footnote>{note}</Footnote>
              </div>
            )}
          </section>

          {/* Where procurement carbon sits — always below the plan. */}
          <SupplierTable />

          {/* The approved plan against recorded emissions. */}
          <CourseCheck refreshKey={planTick} />
        </>
      )}
    </div>
  );
}

function Header({ onReload }: { onReload?: () => void }) {
  const { t } = useLocale();
  return (
    <header className="flex flex-wrap items-end justify-between gap-x-8 gap-y-3 border-b-2 border-ink pb-4">
      <div>
        <p className="kicker">{t("act.band")}</p>
        <h1 className="mt-1.5 font-serif text-[26px] font-semibold leading-none tracking-tight text-ink">
          {t("act.title")}
        </h1>
      </div>
      <div className="flex items-center gap-4">
        <p className="max-w-[40ch] font-serif text-[15px] leading-snug text-ink-soft">
          {t("act.lead")}
        </p>
        {onReload && (
          <button type="button" className="btn-ghost" onClick={onReload}>
            {t("act.refresh")}
          </button>
        )}
      </div>
    </header>
  );
}
