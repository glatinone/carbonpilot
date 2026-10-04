"use client";

import type { Recommendation } from "@/lib/types";
import { useLocale } from "@/lib/i18n";
import { EFFORT_COLOR, formatTonnes, formatUsd } from "@/lib/format";

/**
 * The carbon x cost x effort decision matrix.
 *
 * Exists because a ranked list answers "which is best" but not "why is this above
 * that". Plotting the same 16 actions on two axes makes the trade-off visible in
 * one glance: the top-left quadrant is where the cheap large reductions live, and
 * an action that ranks lower can be defended by where it sits.
 *
 * Both axes are logarithmic. The alternatives were worse: a linear cost axis
 * squashes everything except the $3.4M outlier against the left wall, and a linear
 * carbon axis hides the eight actions under 100 t. The note under the chart says so
 * rather than letting the reader assume proportionality.
 *
 * No charting dependency: this is inline SVG. Recharts is already in the bundle for
 * the trend line, but a quadrant plot is rules, labels and circles — a library would
 * add weight and its own visual defaults, and the visual defaults are exactly what
 * this design system exists to avoid.
 */

const W = 760;
const H = 470;
const PAD = { top: 34, right: 24, bottom: 62, left: 62 };
const PLOT_W = W - PAD.left - PAD.right;
const PLOT_H = H - PAD.top - PAD.bottom;

// Constants for the two symlog scales. COST_C is 1k so the $3.4M and $74K actions
// both stay readable; CARBON_C is 10 t so the small policy actions do not collapse
// onto the axis.
const COST_C = 1_000;
const CARBON_C = 10;

const symlog = (value: number, c: number) => Math.sign(value) * Math.log10(1 + Math.abs(value) / c);
const logish = (value: number, c: number) => Math.log10(1 + Math.max(0, value) / c);

export function DecisionMatrix({ recommendations }: { recommendations: Recommendation[] }) {
  const { t } = useLocale();
  if (recommendations.length < 3) return null;

  const xs = recommendations.map((r) => symlog(r.cost_impact_usd, COST_C));
  const ys = recommendations.map((r) => logish(r.carbon_impact_t, CARBON_C));

  const xLo = Math.min(...xs, 0);
  const xHi = Math.max(...xs, 0);
  const xPad = (xHi - xLo) * 0.1 || 0.5;
  const xMin = xLo - xPad;
  const xMax = xHi + xPad;

  const yMax = Math.max(...ys, 0.5) * 1.1;

  const px = (value: number) =>
    PAD.left + ((symlog(value, COST_C) - xMin) / (xMax - xMin)) * PLOT_W;
  const py = (value: number) =>
    PAD.top + PLOT_H - ((logish(value, CARBON_C) / yMax) * PLOT_H);

  // The horizontal split is the median saving, so "high impact" means high for this
  // portfolio rather than against an invented absolute threshold.
  const sortedCarbon = recommendations.map((r) => r.carbon_impact_t).sort((a, b) => a - b);
  const medianCarbon = sortedCarbon[Math.floor(sortedCarbon.length / 2)];
  const splitY = py(medianCarbon);
  const zeroX = px(0);

  const costTicks = [-3_000_000, -1_000_000, -100_000, -10_000, 100_000, 1_000_000].filter(
    (value) => px(value) > PAD.left + 12 && px(value) < PAD.left + PLOT_W - 12,
  );
  const carbonTicks = [10, 100, 1_000].filter((value) => py(value) > PAD.top + 10);

  const quadrants = [
    { key: "mx.doFirst", x: PAD.left + 10, y: PAD.top + 16, anchor: "start" as const },
    { key: "mx.invest", x: PAD.left + PLOT_W - 10, y: PAD.top + 16, anchor: "end" as const },
    { key: "mx.quickWins", x: PAD.left + 10, y: PAD.top + PLOT_H - 12, anchor: "start" as const },
    {
      key: "mx.reconsider",
      x: PAD.left + PLOT_W - 10,
      y: PAD.top + PLOT_H - 12,
      anchor: "end" as const,
    },
  ];

  return (
    <figure className="border-t border-rule pt-4">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label={t("mx.aria")}
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

        {/* quadrant split: the cost zero line is the meaningful one and is drawn heavier */}
        <line
          x1={PAD.left}
          y1={splitY}
          x2={PAD.left + PLOT_W}
          y2={splitY}
          className="stroke-rule"
          strokeWidth={1}
          strokeDasharray="3 4"
        />
        <line
          x1={zeroX}
          y1={PAD.top}
          x2={zeroX}
          y2={PAD.top + PLOT_H}
          className="stroke-rule-strong"
          strokeWidth={1}
        />

        {quadrants.map((q) => (
          <text
            key={q.key}
            x={q.x}
            y={q.y}
            textAnchor={q.anchor}
            className="fill-current text-ink-faint"
            style={{ fontSize: 9.5, letterSpacing: "0.12em", textTransform: "uppercase" }}
          >
            {t(q.key)}
          </text>
        ))}

        {/* axis ticks */}
        {costTicks.map((value) => (
          <g key={`c${value}`}>
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
              {formatUsd(value)}
            </text>
          </g>
        ))}
        {carbonTicks.map((value) => (
          <g key={`k${value}`}>
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
              {value}
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
          {t("mx.axisCarbon")}
        </text>
        <text
          x={PAD.left}
          y={PAD.top + PLOT_H + 36}
          className="fill-current text-ink-muted"
          style={{ fontSize: 9.5, letterSpacing: "0.12em", textTransform: "uppercase" }}
        >
          {t("mx.axisCost")}
        </text>

        {/* the actions */}
        {recommendations.map((rec, index) => {
          const cx = px(rec.cost_impact_usd);
          const cy = py(rec.carbon_impact_t);
          const rank = index + 1;
          return (
            <a key={rec.id} href={`#rec-${rec.id}`} className={EFFORT_COLOR[rec.effort]}>
              <title>
                {`#${String(rank).padStart(2, "0")} ${rec.title} — −${formatTonnes(rec.carbon_impact_t)}/yr, ${formatUsd(rec.cost_impact_usd)}/yr, ${t(`effort.${rec.effort}`)}`}
              </title>
              <circle
                cx={cx}
                cy={cy}
                r={9}
                fill="currentColor"
                fillOpacity={0.9}
                className="stroke-paper"
                strokeWidth={1.5}
              />
              <text
                x={cx}
                y={cy + 3}
                textAnchor="middle"
                className="fill-current text-paper"
                style={{ fontSize: 9, fontFamily: "var(--font-mono), monospace" }}
                pointerEvents="none"
              >
                {String(rank).padStart(2, "0")}
              </text>
            </a>
          );
        })}
      </svg>

      <figcaption className="mt-3 flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          {(["low", "medium", "high"] as const).map((effort) => (
            <span key={effort} className="flex items-center gap-1.5 text-[11px] text-ink-muted">
              <span className={`inline-block h-2.5 w-2.5 rounded-full bg-current ${EFFORT_COLOR[effort]}`} />
              {t(`effort.${effort}`)}
            </span>
          ))}
        </div>
        <p className="text-[11px] text-ink-faint">{t("mx.scaleNote")}</p>
      </figcaption>
    </figure>
  );
}
