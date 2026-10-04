"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { api } from "@/lib/api";
import type { ConstraintSearch, Intervention, ScenarioResult } from "@/lib/types";
import { ErrorBanner, Footnote, SectionHead, Skeleton } from "@/components/ui";
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
    <div>
      <Header />

      <div className="mt-8 grid gap-x-10 gap-y-8 lg:grid-cols-[1.15fr_1fr]">
        {/* Sliders */}
        <section className="border-t border-rule pt-4">
          <SectionHead kicker="Interventions" title="What-if simulator" note="drag to model" />

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
                        <p className="truncate text-[12.5px] text-ink">{slider.title}</p>
                        <p className="text-[10.5px] text-ink-faint">
                          {titleize(slider.activity_type)} · {slider.effort} effort · suggested{" "}
                          {slider.preset}%
                        </p>
                      </div>
                      <span className="fig shrink-0 text-[13px] text-ink">{value}%</span>
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={80}
                      step={5}
                      value={value}
                      style={{ "--fill": `${(value / 80) * 100}%` } as CSSProperties}
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
        <section className="border-t border-rule pt-4">
          <SectionHead kicker="Result" title="Estimated impact" note={result ? "live" : undefined} />

          {runError && <ErrorBanner message={runError} />}

          {!result ? (
            <p className="py-10 text-[12px] leading-relaxed text-ink-muted">
              Move a slider to simulate. Nothing leaves the baseline until you change something.
            </p>
          ) : (
            <div>
              <div className="flex items-end justify-between gap-6 border-b border-rule pb-4">
                <div>
                  <p className="kicker">Projected footprint</p>
                  <p className="fig mt-2 text-[34px] font-medium leading-none tracking-tight text-ink">
                    {result.projected.total_tco2e.toLocaleString("en-US", {
                      maximumFractionDigits: 0,
                    })}
                  </p>
                  <p className="mt-1.5 text-[11.5px] text-ink-muted">
                    from {result.baseline.total_tco2e.toLocaleString("en-US")} tCO₂e
                  </p>
                </div>
                <div className="text-right">
                  <p className="fig text-[22px] font-medium leading-none text-save">
                    −{result.impact.carbon_reduction_pct.toFixed(1)}%
                  </p>
                  <p className="fig mt-1.5 text-[12px] text-ink-muted">
                    {formatTonnes(result.impact.carbon_saving_tco2e)}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-x-8 gap-y-5 border-b border-rule py-4">
                <div>
                  <p className="kicker">Annual cost impact</p>
                  <p
                    className={`fig mt-1.5 text-[19px] font-medium leading-none ${
                      result.impact.cost_delta_usd <= 0 ? "text-save" : "text-alert"
                    }`}
                  >
                    {formatUsd(result.impact.cost_delta_usd)}
                  </p>
                  <p className="mt-1 text-[10.5px] text-ink-faint">{result.impact.cost_direction}</p>
                </div>
                <div>
                  <p className="kicker">Interventions</p>
                  <p className="fig mt-1.5 text-[19px] font-medium leading-none text-ink">
                    {result.per_intervention.filter((i) => !("error" in i)).length}
                  </p>
                  <p className="mt-1 text-[10.5px] text-ink-faint">applied together</p>
                </div>
              </div>

              <div className="pt-4">
                <p className="kicker mb-2">Per intervention</p>
                <ul>
                  {result.per_intervention
                    .filter((item) => !("error" in item))
                    .map((item) => {
                      const row = item as Record<string, number | string>;
                      return (
                        <li
                          key={String(row.activity_type)}
                          className="flex items-baseline justify-between gap-4 border-b border-rule py-2 last:border-b-0"
                        >
                          <span className="truncate text-[11.5px] text-ink-soft">
                            {String(row.title)}
                          </span>
                          <span className="fig shrink-0 text-[11.5px] text-ink">
                            −{Number(row.carbon_saving_tco2e).toFixed(1)} t ·{" "}
                            {formatUsd(Number(row.cost_delta_usd))}
                          </span>
                        </li>
                      );
                    })}
                </ul>
              </div>

              <details className="mt-4 border-t border-rule pt-3">
                <summary className="cursor-pointer text-[11.5px] text-ink-muted">
                  Assumptions ({result.assumptions.length})
                </summary>
                <ul className="mt-2">
                  {result.assumptions.map((assumption) => (
                    <li key={assumption} className="text-[11px] leading-relaxed text-ink-muted">
                      {assumption}
                    </li>
                  ))}
                </ul>
              </details>
            </div>
          )}
        </section>
      </div>

      {dashboard && projectedSeries && (
        <section className="mt-8 border-t border-rule pt-4">
          <SectionHead
            kicker="Trajectory"
            title="Recorded vs projected"
            note="solid = recorded · dashed = projected"
          />
          <TrendChart series={dashboard.series} compareSeries={projectedSeries} />
        </section>
      )}

      {/* Constraint mode */}
      <section className="mt-8 border-t border-rule pt-4">
        <SectionHead
          kicker="Inverse solve"
          title="Constraint search"
          note="reduce carbon by X% without raising cost"
        />
        <p className="max-w-[70ch] text-[12.5px] leading-relaxed text-ink-muted">
          The engine enumerates intervention combinations and returns the ones that satisfy both
          constraints — the direction a target-setting conversation actually runs.
        </p>

        <div className="mt-5 flex flex-wrap items-end gap-x-6 gap-y-4">
          <div>
            <label className="kicker mb-2 block">Minimum carbon reduction</label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={1}
                max={60}
                value={targetPct}
                style={{ "--fill": `${((targetPct - 1) / 59) * 100}%` } as CSSProperties}
                onChange={(event) => setTargetPct(Number(event.target.value))}
                className="w-48"
              />
              <span className="fig w-12 text-[13px] text-ink">{targetPct}%</span>
            </div>
          </div>

          <div>
            <label className="kicker mb-2 block">Maximum cost increase (USD/yr)</label>
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
          <div className="mt-6">
            <p className="text-[12.5px] text-ink-muted">
              {search.message}{" "}
              <span className="fig text-ink-faint">
                ({search.scenarios_evaluated} scenarios evaluated)
              </span>
            </p>

            {search.recommended && (
              <div className="mt-4 border-l-2 border-y border-r border-l-save border-rule px-4 py-3">
                <p className="kicker text-save">Best feasible scenario</p>
                <p className="mt-1.5 font-serif text-[17px] font-semibold leading-snug text-ink">
                  {search.recommended.label}
                </p>
                <div className="mt-2 flex flex-wrap items-baseline gap-x-6 gap-y-1.5">
                  <span className="fig text-[13px] text-save">
                    −{search.recommended.carbon_reduction_pct.toFixed(1)}% carbon
                  </span>
                  <span className="fig text-[13px] text-ink">
                    {formatUsd(search.recommended.cost_delta_usd)}/yr
                  </span>
                  <span className="text-[11.5px] text-ink-muted">
                    {search.recommended.effort} effort
                  </span>
                  <span className="fig text-[11.5px] text-ink-muted">
                    {search.recommended.confidence_pct.toFixed(0)}% confidence
                  </span>
                </div>
              </div>
            )}

            {search.feasible.length > 0 && (
              <div className="mt-5 overflow-x-auto">
                <table className="ledger">
                  <thead>
                    <tr>
                      <th>Scenario</th>
                      <th>Carbon</th>
                      <th>Cost</th>
                      <th>Effort</th>
                      <th>Confidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {search.feasible.map((scenario) => (
                      <tr key={scenario.label}>
                        <td>{scenario.label}</td>
                        <td className="text-save">
                          −{scenario.carbon_reduction_pct.toFixed(1)}%
                        </td>
                        <td>{formatUsd(scenario.cost_delta_usd)}</td>
                        <td>{scenario.effort}</td>
                        <td>{scenario.confidence_pct.toFixed(0)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {search.feasible.length === 0 && search.infeasible.length > 0 && (
              <div className="mt-5 border-t border-rule pt-3">
                <p className="mb-2 text-[11.5px] text-alert">
                  No combination satisfies both constraints. Closest alternatives:
                </p>
                <ul>
                  {search.infeasible.slice(0, 3).map((scenario) => (
                    <li
                      key={scenario.label}
                      className="flex items-baseline justify-between gap-4 border-b border-rule py-2 last:border-b-0"
                    >
                      <span className="truncate text-[11.5px] text-ink-soft">{scenario.label}</span>
                      <span className="fig shrink-0 text-[11.5px] text-ink">
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

        <div className="mt-5">
          <Footnote>
            <b>Method.</b> Linear scaling of each intervention against measured activity data —
            emission factors held constant, no rebound effect or learning curve modelled. Scenario
            count and the feasible set are computed, never sampled.{" "}
            <b>Estimated impact, not a precise forecast.</b>
          </Footnote>
        </div>
      </section>
    </div>
  );
}

function Header() {
  return (
    <header className="flex flex-wrap items-end justify-between gap-x-8 gap-y-3 border-b-2 border-ink pb-4">
      <div>
        <p className="kicker">Simulate</p>
        <h1 className="mt-1.5 font-serif text-[26px] font-semibold leading-none tracking-tight text-ink">
          Scenario Simulator
        </h1>
      </div>
      <p className="max-w-[44ch] font-serif text-[15px] leading-snug text-ink-soft">
        A linear engine over measured activity data — estimated impact, with every assumption shown
      </p>
    </header>
  );
}
