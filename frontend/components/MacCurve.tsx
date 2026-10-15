"use client";

import type { Recommendation } from "@/lib/types";
import { useLocale, useStreamLabel } from "@/lib/i18n";
import { EFFORT_COLOR, formatTonnes, formatTonnesShort, formatUsd } from "@/lib/format";

/**
 * The marginal abatement cost curve: every action priced per tonne, cheapest
 * tonne first. This is the supply curve the ranked list implies — what the next
 * tonne of abatement costs once the cheaper ones are done.
 *
 * Dots, not bars. The textbook MAC curve draws each action as a bar whose width
 * is its tonnage, but these actions span 1.9 t to 2,452 t: the smallest bar
 * would be a third of a pixel wide against the largest, and the chart would
 * read as three towers and a smear. One dot per action, centred in the tonnage
 * it adds, keeps every action visible while the horizontal position still runs
 * as cumulative supply — left to right the tonnes add up to the total.
 *
 * Y is net cost per tonne = cost_impact_usd / carbon_impact_t: both figures the
 * deterministic engine already computed, this only divides them. Below the zero
 * rule the action pays back; above it, the tonne costs money. The axis is
 * symmetric-logarithmic and the chart says so underneath: a linear Y axis would
 * flatten everything between +$237 and −$161 onto the zero rule, because one
 * cloud action sits at −$52,500/t.
 *
 * Inline SVG, same as the decision matrix beside it — see that component for
 * why no charting library.
 */
const W = 860;
const H = 520;
const PAD = { top: 34, right: 20, bottom: 64, left: 58 };
const PLOT_W = W - PAD.left - PAD.right;
const PLOT_H = H - PAD.top - PAD.bottom;

// Transition scale for the signed-log cost axis: linear within ±$300/t of zero
// (where ordinary actions live), logarithmic beyond it (where the outliers do).
const COST_C = 300;

// Round $/t values offered as axis ticks, descending. Greedy from the top with
// zero pinned first: the zero rule is the chart's reference line, so its label
// is never the one dropped when two candidates crowd each other.
const TICK_CANDIDATES = [
  500, 200, 100, 50, 20, 10, 0, -10, -20, -50, -100, -200, -500, -1_000, -2_000, -5_000, -10_000,
  -20_000, -50_000,
];

const symlog = (value: number, c: number) => Math.sign(value) * Math.log10(1 + Math.abs(value) / c);

type Row = {
  rec: Recommendation;
  rank: number;
  costPerTonne: number;
  start: number;
  end: number;
};

export function MacCurve({ recommendations }: { recommendations: Recommendation[] }) {
  const { t } = useLocale();
  const streamLabel = useStreamLabel();

  // Ranks come from the register order (by score), so a dot's number is the
  // card's number below. An action with no tonnage has no price per tonne and
  // leaves the plot; the engine emits positive savings by construction, so this
  // guard is defensive, not a path the current data reaches.
  const rankOf = new Map(recommendations.map((rec, index) => [rec.id, index + 1]));
  const rows: Row[] = recommendations
    .filter((rec) => rec.carbon_impact_t > 0)
    .map((rec) => ({
      rec,
      rank: rankOf.get(rec.id) ?? 0,
      costPerTonne: rec.cost_impact_usd / rec.carbon_impact_t,
      start: 0,
      end: 0,
    }));

  if (rows.length === 0) return null;

  // Cumulative supply runs in cost order: cheapest tonne first, which is what
  // makes the horizontal axis a supply curve rather than an arbitrary sort.
  rows.sort((a, b) => a.costPerTonne - b.costPerTonne || a.rec.id - b.rec.id);
  let cumulative = 0;
  for (const row of rows) {
    row.start = cumulative;
    cumulative += row.rec.carbon_impact_t;
    row.end = cumulative;
  }
  const total = cumulative;

  const ys = rows.map((row) => symlog(row.costPerTonne, COST_C));
  const yLo = Math.min(...ys, 0);
  const yHi = Math.max(...ys, 0);
  const yPad = (yHi - yLo) * 0.08 || 1;
  const yMin = yLo - yPad;
  const yMax = yHi + yPad;

  const px = (tonnes: number) => PAD.left + (tonnes / total) * PLOT_W;
  const py = (value: number) =>
    PAD.top + PLOT_H - ((symlog(value, COST_C) - yMin) / (yMax - yMin)) * PLOT_H;

  const zeroY = py(0);

  const yTicks: number[] = [];
  if (zeroY > PAD.top + 8 && zeroY < PAD.top + PLOT_H - 8) yTicks.push(0);
  for (const value of TICK_CANDIDATES) {
    if (value === 0) continue;
    const y = py(value);
    if (y < PAD.top + 8 || y > PAD.top + PLOT_H - 8) continue;
    if (yTicks.every((kept) => Math.abs(y - py(kept)) >= 16)) yTicks.push(value);
  }

  // Linear X: nice round tonnes. Cumulative axes do not get a log scale — the
  // reading is "these add up", and log positions do not add.
  const rawStep = total / 5;
  const magnitude = 10 ** Math.floor(Math.log10(rawStep));
  const step = [1, 2, 5, 10].map((m) => m * magnitude).find((s) => s >= rawStep) ?? magnitude;
  const xTicks: number[] = [];
  for (let value = 0, guard = 0; value <= total && guard < 40; value += step, guard += 1) {
    xTicks.push(value);
  }

  return (
    <figure className="border-t border-rule pt-4">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label={t("mac.aria")}
        preserveAspectRatio="xMidYMid meet"
      >
        {/* plot frame: hairline rules only, no fill, no gradient */}
        <rect
          x={PAD.left}
          y={PAD.top}
          width={PLOT_W}
          height={PLOT_H}
          fill="none"
          className="stroke-rule"
          strokeWidth={1}
        />

        {/* the zero rule: the one line on this chart a reader must find instantly */}
        <line
          x1={PAD.left}
          y1={zeroY}
          x2={PAD.left + PLOT_W}
          y2={zeroY}
          className="stroke-ink"
          strokeWidth={1}
        />

        {/* zones, named the way the industry reads a MAC chart */}
        <text
          x={PAD.left + 10}
          y={PAD.top + 16}
          className="fill-current text-ink-faint"
          style={{ fontSize: 9.5, letterSpacing: "0.12em", textTransform: "uppercase" }}
        >
          {t("mac.costs")}
        </text>
        <text
          x={PAD.left + PLOT_W - 10}
          y={PAD.top + PLOT_H - 12}
          textAnchor="end"
          className="fill-current text-ink-faint"
          style={{ fontSize: 9.5, letterSpacing: "0.12em", textTransform: "uppercase" }}
        >
          {t("mac.saves")}
        </text>

        {/* axis ticks */}
        {xTicks.map((value) => (
          <g key={`t${value}`}>
            <line
              x1={px(value)}
              y1={PAD.top + PLOT_H}
              x2={px(value)}
              y2={PAD.top + PLOT_H + 4}
              className="stroke-rule"
              strokeWidth={1}
            />
            <text
              x={px(value)}
              y={PAD.top + PLOT_H + 16}
              textAnchor="middle"
              className="fill-current text-ink-faint"
              style={{ fontSize: 9.5, fontFamily: "var(--font-mono), monospace" }}
            >
              {formatTonnesShort(value)}
            </text>
          </g>
        ))}
        {yTicks.map((value) => (
          <g key={`c${value}`}>
            <line
              x1={PAD.left - 4}
              y1={py(value)}
              x2={PAD.left}
              y2={py(value)}
              className="stroke-rule"
              strokeWidth={1}
            />
            <text
              x={PAD.left - 8}
              y={py(value) + 3}
              textAnchor="end"
              className="fill-current text-ink-faint"
              style={{ fontSize: 9.5, fontFamily: "var(--font-mono), monospace" }}
            >
              {formatUsd(value)}
            </text>
          </g>
        ))}

        {/* axis titles */}
        <text
          x={PAD.left}
          y={PAD.top - 12}
          className="fill-current text-ink-muted"
          style={{ fontSize: 9.5, letterSpacing: "0.12em", textTransform: "uppercase" }}
        >
          {t("mac.axisCost")}
        </text>
        <text
          x={PAD.left}
          y={PAD.top + PLOT_H + 40}
          className="fill-current text-ink-muted"
          style={{ fontSize: 9.5, letterSpacing: "0.12em", textTransform: "uppercase" }}
        >
          {t("mac.axisCarbon")}
        </text>

        {/* one dot per action, in curve order; each links to its card */}
        {rows.map((row) => {
          const cx = px((row.start + row.end) / 2);
          const cy = py(row.costPerTonne);
          return (
            <a key={row.rec.id} href={`#rec-${row.rec.id}`} className={EFFORT_COLOR[row.rec.effort]}>
              <title>
                {`#${String(row.rank).padStart(2, "0")} ${row.rec.title} — −${formatTonnes(row.rec.carbon_impact_t)}/yr, ${formatUsd(row.costPerTonne)}/tCO₂e, ${t(`effort.${row.rec.effort}`)}`}
              </title>
              <circle
                cx={cx}
                cy={cy}
                r={7}
                fill="currentColor"
                fillOpacity={0.9}
                className="stroke-paper"
                strokeWidth={1.5}
              />
              <text
                x={cx}
                y={cy + 2.6}
                textAnchor="middle"
                className="fill-current text-paper"
                style={{ fontSize: 8, fontFamily: "var(--font-mono), monospace" }}
                pointerEvents="none"
              >
                {String(row.rank).padStart(2, "0")}
              </text>
            </a>
          );
        })}
      </svg>

      <figcaption className="mt-3 flex flex-wrap items-start justify-between gap-x-6 gap-y-2">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          {(["low", "medium", "high"] as const).map((effort) => (
            <span key={effort} className="flex items-center gap-1.5 text-[11px] text-ink-muted">
              <span className={`inline-block h-2.5 w-2.5 rounded-full bg-current ${EFFORT_COLOR[effort]}`} />
              {t(`effort.${effort}`)}
            </span>
          ))}
        </div>
        <p className="text-[11px] text-ink-faint">{t("mac.scaleNote")}</p>
      </figcaption>

      {/* the same 16, keyed by rank and named: the chart must work without hover */}
      <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1.5">
        {recommendations.map((rec, index) => (
          <a
            key={rec.id}
            href={`#rec-${rec.id}`}
            className="flex items-center gap-1.5 text-[11px] text-ink-muted transition hover:text-ink"
          >
            <span className={`inline-block h-2 w-2 rounded-full bg-current ${EFFORT_COLOR[rec.effort]}`} />
            <span className="fig text-[10.5px]">{String(index + 1).padStart(2, "0")}</span>
            <span>{streamLabel(rec.activity_type)}</span>
          </a>
        ))}
      </div>
    </figure>
  );
}
