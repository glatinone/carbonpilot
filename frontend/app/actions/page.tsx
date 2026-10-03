"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ActionItem, Recommendation } from "@/lib/types";
import { RecommendationCard } from "@/components/RecommendationCard";
import { EmptyState, ErrorBanner, Skeleton } from "@/components/ui";
import { formatTonnes, formatUsd } from "@/lib/format";

const STATUS_STYLE: Record<string, string> = {
  open: "border-signal-sky/40 text-signal-sky",
  in_progress: "border-signal-amber/40 text-signal-amber",
  done: "border-signal-mint/40 text-signal-mint",
  cancelled: "border-ink-600 text-slate-500",
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
    <div className="space-y-6">
      <Header onReload={load} />

      {loading ? (
        <>
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </>
      ) : (
        <>
          {/* Ranked actions */}
          <section className="space-y-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-sm font-semibold text-white">
                Ranked recommendations ({recommendations.length})
              </h2>
              <p className="text-[11px] text-slate-500">
                Score = carbon × cost × effort, weighted by confidence. Not &ldquo;biggest number
                wins&rdquo;.
              </p>
            </div>

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
                className="btn-ghost w-full"
                onClick={() => setShowAll((value) => !value)}
              >
                {showAll ? "Show top 8 only" : `Show all ${recommendations.length}`}
              </button>
            )}
          </section>

          {/* Tracked actions */}
          <section className="card card-pad">
            <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-sm font-semibold text-white">
                Action plan ({actions.length})
              </h2>
              {totals && actions.length > 0 && (
                <span className="metric text-[11px] text-slate-400">
                  if all executed: −{totals.expected_carbon_t.toLocaleString("en-US", {
                    maximumFractionDigits: 0,
                  })}{" "}
                  tCO₂e · {formatUsd(totals.expected_cost_usd)}/yr
                </span>
              )}
            </div>

            {actions.length === 0 ? (
              <p className="py-6 text-center text-xs text-slate-500">
                No actions created yet. Approve a recommendation above to assign it an owner.
              </p>
            ) : (
              <ul className="divide-y divide-ink-800/80">
                {actions.map((action) => (
                  <li key={action.id} className="flex flex-wrap items-center gap-3 py-3">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-xs font-medium text-slate-200">{action.task}</p>
                      <p className="mt-0.5 text-[11px] text-slate-500">
                        Owner: {action.owner} · expected −
                        {formatTonnes(action.expected_carbon_t)} ·{" "}
                        {formatUsd(action.expected_cost_usd)}/yr
                      </p>
                    </div>
                    <span className={`chip ${STATUS_STYLE[action.status] ?? ""}`}>
                      {action.status.replace("_", " ")}
                    </span>
                    {action.status !== "done" && (
                      <button
                        type="button"
                        className="btn-ghost px-3 py-1.5 text-xs"
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
              <p className="mt-4 border-t border-ink-700/60 pt-3 text-[11px] text-slate-500">
                {note}
              </p>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function Header({ onReload }: { onReload?: () => void }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <p className="label">Act</p>
        <h1 className="mt-1 text-xl font-semibold tracking-tight text-white">Action Plan</h1>
      </div>
      {onReload && (
        <button type="button" className="btn-ghost" onClick={onReload}>
          Refresh analysis
        </button>
      )}
    </header>
  );
}
