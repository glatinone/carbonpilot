"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SeriesPoint } from "@/lib/types";
import { useLocale } from "@/lib/i18n";
import { Emphasised } from "@/components/ui";
import { monthLabel } from "@/lib/format";

type Props = {
  series: SeriesPoint[];
  highlightMonth?: string;
  compareSeries?: SeriesPoint[];
};

/**
 * A measured series, drawn flat. No gradient under the line and no rounded
 * tooltip: the fill would imply a magnitude the chart does not measure, and the
 * reading is meant to come from the figures, not the ink.
 */
export function TrendChart({ series, highlightMonth, compareSeries }: Props) {
  const { t, locale } = useLocale();
  const data = series.map((point) => {
    const compare = compareSeries?.find((other) => other.month === point.month);
    return {
      month: point.month,
      label: monthLabel(point.month),
      tco2e: point.tco2e,
      projected: compare?.tco2e,
    };
  });

  const flagged = series.find((point) => point.month === highlightMonth);

  return (
    <div className="w-full">
      <div className="h-60 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
            <CartesianGrid stroke="#eeeeea" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: "#9a9a8e", fontSize: 10, fontFamily: "var(--font-mono)" }}
              axisLine={{ stroke: "#e2e0d8" }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "#9a9a8e", fontSize: 10, fontFamily: "var(--font-mono)" }}
              axisLine={false}
              tickLine={false}
              width={54}
            />
            <Tooltip
              contentStyle={{
                background: "#ffffff",
                border: "1px solid #c9c6ba",
                borderRadius: 2,
                fontSize: 11.5,
                fontFamily: "var(--font-mono)",
                color: "#14150f",
                padding: "6px 9px",
              }}
              labelStyle={{ color: "#6d6d63", fontSize: 10, textTransform: "uppercase" }}
              formatter={(value: number, name: string) => [
                `${value.toLocaleString(locale === "id" ? "id-ID" : "en-US", { maximumFractionDigits: 1 })} tCO₂e`,
                name === "tco2e" ? t("chart.recorded") : t("chart.projected"),
              ]}
            />
            <Area
              type="linear"
              dataKey="tco2e"
              stroke="#33332e"
              strokeWidth={1.5}
              fill="#14150f"
              fillOpacity={0.04}
              dot={(props: { cx?: number; cy?: number; payload?: { month: string } }) => {
                const { cx, cy, payload } = props;
                if (cx === undefined || cy === undefined) return <g />;
                const isFlagged = flagged && payload?.month === flagged.month;
                return (
                  <rect
                    x={cx - (isFlagged ? 3 : 1.5)}
                    y={cy - (isFlagged ? 3 : 1.5)}
                    width={isFlagged ? 6 : 3}
                    height={isFlagged ? 6 : 3}
                    fill={isFlagged ? "#9c5a12" : "#fbfaf7"}
                    stroke={isFlagged ? "#9c5a12" : "#33332e"}
                    strokeWidth={1}
                  />
                );
              }}
            />
            {compareSeries && (
              <Line
                type="linear"
                dataKey="projected"
                stroke="#6d6d63"
                strokeWidth={1.5}
                strokeDasharray="3 3"
                dot={false}
              />
            )}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {highlightMonth && (
        <p className="mt-2 text-[11px] text-ink-muted">
          <Emphasised
            template={t("chart.flagged")}
            values={{ month: monthLabel(highlightMonth, locale) }}
            tone="alert"
          />
        </p>
      )}
    </div>
  );
}
