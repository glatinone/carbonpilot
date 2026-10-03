"use client";

import { useState } from "react";
import type { Insight } from "@/lib/types";
import { formatPct, formatTonnes, formatUsd, titleize } from "@/lib/format";

export function InsightCard({ insight, index }: { insight: Insight; index: number }) {
  const [open, setOpen] = useState(index === 0);
  const evidence = insight.evidence as Record<string, number | string | string[] | null>;

  return (
    <article className="card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="w-full px-5 py-4 text-left transition hover:bg-ink-850/50"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-signal-rose/15 text-[11px] font-bold text-signal-rose">
              {index + 1}
            </span>
            <div>
              <h3 className="text-sm font-semibold text-white">{insight.headline}</h3>
              <p className="mt-1 text-xs leading-relaxed text-slate-400">{insight.detail}</p>
            </div>
          </div>
          <span className="shrink-0 text-xs text-slate-500">{open ? "−" : "+"}</span>
        </div>
      </button>

      {open && (
        <div className="border-t border-ink-700/60 px-5 py-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <Metric label="Potential carbon" value={formatTonnes(insight.carbon_impact_t)} />
            <Metric label="Financial impact" value={formatUsd(insight.cost_impact_usd)} sub="per year" />
            <Metric label="Confidence" value={`${insight.confidence_pct.toFixed(0)}%`} />
          </div>

          <div className="mt-4 rounded-lg border border-ink-700/60 bg-ink-950/50 p-3">
            <p className="label mb-2">Evidence</p>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[11px] sm:grid-cols-3">
              <Row label="Observed" value={`${evidence.observed_tco2e} tCO₂e`} />
              <Row label="Baseline" value={`${evidence.baseline_tco2e} tCO₂e`} />
              <Row label="Delta" value={formatPct(Number(evidence.change_pct))} />
              <Row label="Z-score" value={String(evidence.z_score)} />
              <Row label="Severity" value={String(evidence.severity)} />
              <Row
                label="Baseline window"
                value={`${(evidence.baseline_months as string[])?.length ?? 0} months`}
              />
            </dl>
            {evidence.suggested_action ? (
              <p className="mt-3 border-t border-ink-700/60 pt-2.5 text-[11px] text-slate-400">
                Suggested action:{" "}
                <span className="text-signal-mint">{String(evidence.suggested_action)}</span>
              </p>
            ) : null}
          </div>

          <p className="mt-3 text-[11px] text-slate-500">
            Detected on {titleize(String(insight.activity_type))} in {insight.month} using a robust
            median/MAD z-score over the monthly series.
          </p>
        </div>
      )}
    </article>
  );
}

function Metric({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div>
      <p className="label">{label}</p>
      <p className="metric mt-1 text-lg font-semibold text-white">{value}</p>
      {sub && <p className="text-[11px] text-slate-500">{sub}</p>}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2">
      <dt className="text-slate-500">{label}</dt>
      <dd className="metric text-slate-300">{value}</dd>
    </div>
  );
}
