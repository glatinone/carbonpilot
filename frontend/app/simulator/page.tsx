"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { ConstraintSearch, Intervention, ScenarioResult } from "@/lib/types";
import { ErrorBanner, Skeleton } from "@/components/ui";
import { TrendChart } from "@/components/TrendChart";
import { formatTonnes, formatUsd, titleize } from "@/lib/format";
import { useDashboard } from "@/lib/hooks";

type Slider = { activity_type: string; title: string; effort: string; preset: number; costRatio: number };

export default function SimulatorPage() {
  const { data: dashboard, loading: dashLoading, error: dashError, reload } = useDashboard();
  const [sliders, setSliders] = useState<Slider[]>([]);
  const [values, setValues] = useState<Record<string, number>>({});
  const [result, setResult] = useState<ScenarioResult | null>(null);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  // Constraint mode
  const [targetPct, setTargetPct] = useState(15);
  const [costCeiling, setCostCeiling] = useState(0);
  const [search, setSearch] = useState<ConstraintSearch | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const { interventions } = await api.interventions();
        if (cancelled) return;

        // One slider per activity stream, using the most conservative preset
        // as the starting point and deriving a linear cost ratio from it.
        const byType = new Map<string, Intervention>();
        for (const item of interventions) {
          const existing = byType.get(item.activity_type);
          if (!existing || item.reduction_pct < existing.reduction_pct) {
            byType.set(item.activity_type, item);
          }
        }
        const next: Slider[] = [...byType.values()].map((item) => ({
          activity_type: item.activity_type,
          title: item.title,
          effort: item.effort,
          preset: item.reduction_pct,
          costRatio: item.cost_delta_pct / item.reduction_pct,
        }));
        setSliders(next);
        setValues(Object.fromEntries(next.map((slider) => [slider.activity_type, 0])));
      } catch (err) {
        if (!cancelled) setRunError(err instanceof Error ? err.message : "Failed to load options");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const activeInterventions = useMemo(
    () =>
      sliders
        .filter((slider) => (values[slider.activity_type] ?? 0) > 0)
        .map((slider) => ({
          activity_type: slider.activity_type,
          reduction_pct: values[slider.activity_type],
          cost_delta_pct: slider.costRatio * values[slider.activity_type],
        })),
    [sliders, values],
  );

  const runScenario = useCallback(async () => {
    if (activeInterventions.length === 0) return;
    setRunning(true);
    setRunError(null);
    try {
      setResult(await api.runScenario(activeInterventions));
    } catch (err) {
      setRunError(err instanceof Error ? err.message : "Simulation failed");
    } finally {
      setRunning(false);
    }
  }, [activeInterventions]);

  // Live-update the projection while the user drags, without hammering the API.
  useEffect(() => {
    if (activeInterventions.length === 0) {
      setResult(null);
      return;
    }
    const timer = setTimeout(() => void runScenario(), 280);
    return () => clearTimeout(timer);
  }, [activeInterventions, runScenario]);

  async function runSearch() {
    setSearching(true);
    setSearchError(null);
    try {
      setSearch(
        await api.constraints({
          min_carbon_reduction_pct: targetPct,
          max_cost_increase_usd: costCeiling,
        }),
      );
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setSearching(false);
    }
  }

  if (dashError) {
    return (
      <div className="space-y-6">
        <Header />
        <ErrorBanner message={dashError} onRetry={reload} />
      </div>
    );
  }

  const projectedSeries = useMemo(() => {
    if (!dashboard || !result) return undefined;
    const factor = result.projected.total_tco2e / (result.baseline.total_tco2e || 1);
    return dashboard.series.map((point) => ({ ...point, tco2e: point.tco2e * factor }));
  }, [dashboard, result]);

  return (
    <div className="space-y-6">
      <Header />

      <div className="grid gap-5 lg:grid-cols-[1.25fr_1fr]">
        {/* Sliders */}
        <section className="card card-pad">
          <div className="mb-4 flex items-baseline justify-between">
            <h2 className="text-sm font-semibold text-white">What-if simulator</h2>
            <span className="text-[11px] text-slate-500">drag to model an intervention</span>
          </div>

          {dashLoading || sliders.length === 0 ? (
            <Skeleton className="h-72" />
          ) : (
            <div className="space-y-5">
              {sliders.map((slider) => {
                const value = values[slider.activity_type] ?? 0;
                return (
                  <div key={slider.activity_type}>
                    <div className="mb-2 flex items-baseline justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-xs font-medium text-slate-300">
                          {slider.title}
                        </p>
                        <p className="text-[10px] text-slate-600">
                          {titleize(slider.activity_type)} · {slider.effort} effort · suggested{" "}
                          {slider.preset}%
                        </p>
                      </div>
                      <span className="metric shrink-0 text-sm font-semibold text-signal-mint">
                        {value}%
                      </span>
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={80}
                      step={5}
                      value={value}
                      onChange={(event) =>
                        setValues((previous) => ({
                          ...previous,
                          [slider.activity_type]: Number(event.target.value),
                        }))
                      }
                    />
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Projection */}
        <section className="card card-pad">
          <h2 className="mb-4 text-sm font-semibold text-white">Estimated impact</h2>

          {runError && <ErrorBanner message={runError} />}

          {!result ? (
            <div className="py-10 text-center">
              <p className="text-xs text-slate-500">
                Move a slider to simulate. Nothing leaves the baseline until you change something.
              </p>
            </div>
          ) : (
            <div className="space-y-5">
              <div className="flex items-end justify-between rounded-lg border border-ink-700/60 bg-ink-950/50 p-4">
                <div>
                  <p className="label">Projected footprint</p>
                  <p className="metric mt-1.5 text-3xl font-semibold text-white">
                    {result.projected.total_tco2e.toLocaleString("en-US", {
                      maximumFractionDigits: 0,
                    })}
                  </p>
                  <p className="text-[11px] text-slate-500">
                    from {result.baseline.total_tco2e.toLocaleString("en-US")} tCO₂e
                  </p>
                </div>
                <div className="text-right">
                  <p className="metric text-2xl font-semibold text-signal-mint">
                    −{result.impact.carbon_reduction_pct.toFixed(1)}%
                  </p>
                  <p className="metric text-xs text-slate-400">
                    {formatTonnes(result.impact.carbon_saving_tco2e)}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-lg border border-ink-700/60 p-3">
                  <p className="label">Annual cost impact</p>
                  <p
                    className={`metric mt-1 text-lg font-semibold ${
                      result.impact.cost_delta_usd <= 0 ? "text-signal-mint" : "text-signal-rose"
                    }`}
                  >
                    {formatUsd(result.impact.cost_delta_usd)}
                  </p>
                  <p className="text-[10px] text-slate-500">{result.impact.cost_direction}</p>
                </div>
                <div className="rounded-lg border border-ink-700/60 p-3">
                  <p className="label">Interventions</p>
                  <p className="metric mt-1 text-lg font-semibold text-white">
                    {result.per_intervention.filter((i) => !("error" in i)).length}
                  </p>
                  <p className="text-[10px] text-slate-500">applied together</p>
                </div>
              </div>

              <div>
                <p className="label mb-2">Per intervention</p>
                <ul className="space-y-1.5">
                  {result.per_intervention
                    .filter((item) => !("error" in item))
                    .map((item) => {
                      const row = item as Record<string, number | string>;
                      return (
                        <li
                          key={String(row.activity_type)}
                          className="flex items-center justify-between gap-3 text-[11px]"
                        >
                          <span className="truncate text-slate-400">{String(row.title)}</span>
                          <span className="metric shrink-0 text-slate-300">
                            −{Number(row.carbon_saving_tco2e).toFixed(1)} t ·{" "}
                            {formatUsd(Number(row.cost_delta_usd))}
                          </span>
                        </li>
                      );
                    })}
                </ul>
              </div>

              <details className="rounded-lg border border-ink-700/60 bg-ink-950/40 p-3">
                <summary className="cursor-pointer text-[11px] font-medium text-slate-400">
                  Assumptions ({result.assumptions.length})
                </summary>
                <ul className="mt-2 space-y-1">
                  {result.assumptions.map((assumption) => (
                    <li key={assumption} className="text-[11px] leading-relaxed text-slate-500">
                      • {assumption}
                    </li>
                  ))}
                </ul>
                <p className="mt-2 text-[11px] text-signal-amber">
                  Estimated impact — not a precise forecast.
                </p>
              </details>
            </div>
          )}
        </section>
      </div>

      {dashboard && projectedSeries && (
        <section className="card card-pad">
          <h2 className="mb-4 text-sm font-semibold text-white">
            Recorded vs projected trajectory
          </h2>
          <TrendChart series={dashboard.series} compareSeries={projectedSeries} />
        </section>
      )}

      {/* Constraint mode */}
      <section className="card card-pad">
        <div className="mb-4">
          <h2 className="text-sm font-semibold text-white">Constraint search</h2>
          <p className="mt-1 text-xs text-slate-500">
            &ldquo;Reduce carbon by X% without increasing operating cost&rdquo; — the engine
            enumerates intervention combinations and returns the ones that satisfy both
            constraints.
          </p>
        </div>

        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="label mb-1.5 block">Min. carbon reduction</label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={1}
                max={60}
                value={targetPct}
                onChange={(event) => setTargetPct(Number(event.target.value))}
                className="w-48"
              />
              <span className="metric w-12 text-sm font-semibold text-signal-mint">{targetPct}%</span>
            </div>
          </div>

          <div>
            <label className="label mb-1.5 block">Max. cost increase (USD/yr)</label>
            <input
              type="number"
              className="input w-40"
              value={costCeiling}
              onChange={(event) => setCostCeiling(Number(event.target.value))}
            />
          </div>

          <button
            type="button"
            className="btn-primary"
            onClick={() => void runSearch()}
            disabled={searching}
          >
            {searching ? "Searching scenarios…" : "Find scenarios"}
          </button>
        </div>

        {searchError && (
          <div className="mt-4">
            <ErrorBanner message={searchError} />
          </div>
        )}

        {search && (
          <div className="mt-5 space-y-4">
            <p className="text-xs text-slate-400">
              {search.message}{" "}
              <span className="text-slate-600">
                ({search.scenarios_evaluated} scenarios evaluated)
              </span>
            </p>

            {search.recommended && (
              <div className="rounded-lg border border-signal-mint/40 bg-signal-mint/5 p-4">
                <p className="label text-signal-mint">Best feasible scenario</p>
                <p className="mt-1 text-sm font-medium text-white">{search.recommended.label}</p>
                <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs">
                  <span className="metric text-signal-mint">
                    −{search.recommended.carbon_reduction_pct.toFixed(1)}% carbon
                  </span>
                  <span className="metric text-slate-300">
                    {formatUsd(search.recommended.cost_delta_usd)}/yr
                  </span>
                  <span className="text-slate-400">{search.recommended.effort} effort</span>
                  <span className="metric text-slate-400">
                    {search.recommended.confidence_pct.toFixed(0)}% confidence
                  </span>
                </div>
              </div>
            )}

            {search.feasible.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-ink-700/60 text-[10px] uppercase tracking-wider text-slate-500">
                      <th className="pb-2 pr-4 font-medium">Scenario</th>
                      <th className="pb-2 pr-4 text-right font-medium">Carbon</th>
                      <th className="pb-2 pr-4 text-right font-medium">Cost</th>
                      <th className="pb-2 pr-4 font-medium">Effort</th>
                      <th className="pb-2 text-right font-medium">Confidence</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-800/80">
                    {search.feasible.map((scenario) => (
                      <tr key={scenario.label}>
                        <td className="max-w-md truncate py-2.5 pr-4 text-slate-300">
                          {scenario.label}
                        </td>
                        <td className="py-2.5 pr-4 text-right font-mono text-signal-mint">
                          −{scenario.carbon_reduction_pct.toFixed(1)}%
                        </td>
                        <td className="py-2.5 pr-4 text-right font-mono text-slate-300">
                          {formatUsd(scenario.cost_delta_usd)}
                        </td>
                        <td className="py-2.5 pr-4 text-slate-400">{scenario.effort}</td>
                        <td className="py-2.5 text-right font-mono text-slate-400">
                          {scenario.confidence_pct.toFixed(0)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {search.feasible.length === 0 && search.infeasible.length > 0 && (
              <div>
                <p className="mb-2 text-[11px] text-signal-amber">
                  No combination satisfies both constraints. Closest alternatives:
                </p>
                <ul className="space-y-1.5">
                  {search.infeasible.slice(0, 3).map((scenario) => (
                    <li
                      key={scenario.label}
                      className="flex items-center justify-between gap-3 text-[11px]"
                    >
                      <span className="truncate text-slate-400">{scenario.label}</span>
                      <span className="metric shrink-0 text-slate-300">
                        {scenario.carbon_reduction_pct.toFixed(1)}% ·{" "}
                        {formatUsd(scenario.cost_delta_usd)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

function Header() {
  return (
    <header className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <p className="label">Simulate</p>
        <h1 className="mt-1 text-xl font-semibold tracking-tight text-white">
          Scenario Simulator
        </h1>
      </div>
      <span className="chip">Estimated impact · assumptions shown</span>
    </header>
  );
}
