"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ActionItem, Recommendation } from "@/lib/types";
import { RecommendationCard } from "@/components/RecommendationCard";
import { EmptyState, ErrorBanner, Footnote, SectionHead, Skeleton } from "@/components/ui";
import { formatTonnes, formatUsd } from "@/lib/format";

const STATUS_STYLE: Record<string, string> = {
  open: "border-rule-strong text-ink-muted",
  in_progress: "border-alert/50 text-alert",
  done: "border-save/50 text-save",
  cancelled: "border-rule-strong text-ink-faint",
};

export default function ActionsPage() {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [actions, setActions] = useState<ActionItem[]>([]);
  const [totals, setTotals] = useState<{ expected_carbon_t: number; expected_cost_usd: number } | null>(null);
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [recs, actionList] = await Promise.all([api.recommendations(), api.actions()]);
      setRecommendations(recs.recommendations);
      setActions(actionList.actions);
      setTotals(actionList.totals);
      setNote(actionList.note);
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
          {/* Ranked actions */}
          <section className="mt-8 border-t border-rule pt-4">
            <SectionHead
              kicker="Register"
              title={`Ranked recommendations (${recommendations.length})`}
              note="carbon × cost × effort, weighted by confidence"
            />

            {recommendations.length === 0 ? (
              <EmptyState
                title="No recommendations yet"
                hint="Load activity data, then regenerate the action plan."
              />
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
                {showAll ? "Show top 8 only" : `Show all ${recommendations.length}`}
              </button>
            )}
          </section>

          {/* Tracked actions */}
          <section className="mt-8 border-t border-rule pt-4">
            <SectionHead
              kicker="Plan"
              title={`Action plan (${actions.length})`}
              note={
                totals && actions.length > 0
                  ? `if all executed: −${totals.expected_carbon_t.toLocaleString("en-US", {
                      maximumFractionDigits: 0,
                    })} tCO₂e · ${formatUsd(totals.expected_cost_usd)}/yr`
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
                      Download .md
                    </a>
                    <a
                      className="btn-ghost px-3 py-1.5 text-[12px]"
                      href={api.exportActionsUrl("csv")}
                      title="Download this plan as a spreadsheet"
                    >
                      Download .csv
                    </a>
                  </div>
                ) : undefined
              }
            />

            {actions.length === 0 ? (
              <p className="py-6 text-[12px] text-ink-muted">
                No actions created yet. Approve a recommendation above to assign it an owner.
              </p>
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
                        Owner: {action.owner} · expected −{formatTonnes(action.expected_carbon_t)} ·{" "}
                        {formatUsd(action.expected_cost_usd)}/yr
                      </p>
                    </div>
                    <span className={`chip ${STATUS_STYLE[action.status] ?? ""}`}>
                      {action.status.replace("_", " ")}
                    </span>
                    {action.status !== "done" && (
                      <button
                        type="button"
                        className="btn-ghost px-3 py-1.5 text-[12px]"
                        onClick={() => void advance(action)}
                      >
                        {action.status === "open" ? "Start" : "Complete"}
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
        </>
      )}
    </div>
  );
}

function Header({ onReload }: { onReload?: () => void }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-x-8 gap-y-3 border-b-2 border-ink pb-4">
      <div>
        <p className="kicker">Act</p>
        <h1 className="mt-1.5 font-serif text-[26px] font-semibold leading-none tracking-tight text-ink">
          Action Plan
        </h1>
      </div>
      <div className="flex items-center gap-4">
        <p className="max-w-[40ch] font-serif text-[15px] leading-snug text-ink-soft">
          Ranked by impact and effort, then tracked to an owner
        </p>
        {onReload && (
          <button type="button" className="btn-ghost" onClick={onReload}>
            Refresh analysis
          </button>
        )}
      </div>
    </header>
  );
}
