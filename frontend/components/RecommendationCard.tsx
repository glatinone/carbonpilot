"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Recommendation } from "@/lib/types";
import { EFFORT_COLOR, formatTonnes, formatUsd, titleize } from "@/lib/format";

const OWNERS = ["Engineering", "Facilities", "Procurement", "Travel & Ops", "Finance"];

export function RecommendationCard({
  recommendation,
  rank,
  onCreated,
}: {
  recommendation: Recommendation;
  rank: number;
  onCreated?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [owner, setOwner] = useState(OWNERS[0]);
  const [created, setCreated] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const evidence = recommendation.evidence as Record<string, unknown>;

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
    <article className="card overflow-hidden">
      <div className="flex items-start gap-4 px-5 py-4">
        <div className="shrink-0 text-center">
          <p className="label">Score</p>
          <p className="metric text-xl font-semibold text-signal-mint">
            {recommendation.score.toFixed(0)}
          </p>
          <p className="mt-0.5 text-[10px] text-slate-600">#{rank}</p>
        </div>

        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-white">{recommendation.title}</h3>
          <p className="mt-1 text-xs leading-relaxed text-slate-400">{recommendation.description}</p>

          <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs">
            <span className="metric text-signal-mint">
              −{formatTonnes(recommendation.carbon_impact_t)}
              <span className="ml-1 text-[10px] text-slate-500">/year</span>
            </span>
            <span className="metric text-slate-300">
              {formatUsd(recommendation.cost_impact_usd)}
              <span className="ml-1 text-[10px] text-slate-500">/year</span>
            </span>
            <span className={`text-[11px] font-medium ${EFFORT_COLOR[recommendation.effort]}`}>
              {recommendation.effort} effort
            </span>
            <span className="metric text-[11px] text-slate-400">
              {recommendation.confidence_pct.toFixed(0)}% confidence
            </span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 border-t border-ink-700/60 px-5 py-3">
        <select
          value={owner}
          onChange={(event) => setOwner(event.target.value)}
          className="rounded-lg border border-ink-600 bg-ink-950/60 px-2.5 py-1.5 text-xs text-slate-300 focus:border-signal-mint focus:outline-none"
        >
          {OWNERS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>

        <button
          type="button"
          className="btn-primary px-3 py-1.5 text-xs"
          onClick={() => void createAction()}
          disabled={busy || created}
        >
          {created ? "Action created ✓" : busy ? "Creating…" : "Create Action"}
        </button>

        <button
          type="button"
          className="ml-auto text-xs text-slate-500 hover:text-slate-300"
          onClick={() => setOpen((value) => !value)}
        >
          {open ? "Hide evidence" : "Why?"}
        </button>
      </div>

      {error && (
        <p className="border-t border-signal-rose/30 bg-signal-rose/5 px-5 py-2 text-[11px] text-signal-rose">
          {error}
        </p>
      )}

      {open && (
        <div className="border-t border-ink-700/60 bg-ink-950/40 px-5 py-4">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-[11px] sm:grid-cols-3">
            <Evidence label="Activity stream" value={titleize(recommendation.activity_type)} />
            <Evidence label="Share of footprint" value={`${evidence.share_of_footprint_pct ?? "—"}%`} />
            <Evidence label="Baseline" value={`${evidence.baseline_tco2e ?? "—"} tCO₂e`} />
            <Evidence label="Method" value={String(evidence.method ?? "—")} />
            <Evidence label="Unit" value={String(evidence.unit ?? "—")} />
            <Evidence label="Basis" value="GHG Protocol" />
          </dl>

          {Array.isArray(evidence.assumptions) && (
            <div className="mt-3 border-t border-ink-700/60 pt-3">
              <p className="label mb-1.5">Assumptions</p>
              <ul className="space-y-1">
                {(evidence.assumptions as string[]).map((assumption) => (
                  <li key={assumption} className="text-[11px] leading-relaxed text-slate-500">
                    • {assumption}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {Array.isArray(evidence.driver) && evidence.driver.length > 0 && (
            <div className="mt-3 border-t border-ink-700/60 pt-3">
              <p className="label mb-1.5">Attributed driver</p>
              {(evidence.driver as Array<{ description: string }>).map((driver) => (
                <p key={driver.description} className="text-[11px] text-slate-400">
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
    <div className="flex justify-between gap-2">
      <dt className="text-slate-500">{label}</dt>
      <dd className="metric truncate text-right text-slate-300">{value}</dd>
    </div>
  );
}
