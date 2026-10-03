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
import { monthLabel } from "@/lib/format";

type Props = {
  series: SeriesPoint[];
  highlightMonth?: string;
  compareSeries?: SeriesPoint[];
};

export function TrendChart({ series, highlightMonth, compareSeries }: Props) {
  const data = series.map((point) => {
    const compare = compareSeries?.find((other) => other.month === point.month);
    return {
      month: point.month,
      label: monthLabel(point.month),
      tco2e: point.tco2e,
      projected: compare?.tco2e,
    };
  });

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
          <defs>
            <linearGradient id="fillCarbon" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#34d399" stopOpacity={0.35} />
              <stop offset="100%" stopColor="#34d399" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#1d2938" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fill: "#64748b", fontSize: 11 }}
            axisLine={{ stroke: "#1d2938" }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "#64748b", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={54}
          />
          <Tooltip
            contentStyle={{
              background: "#0f1720",
              border: "1px solid #1d2938",
              borderRadius: 8,
              fontSize: 12,
              color: "#e2e8f0",
            }}
            formatter={(value: number, name: string) => [
              `${value.toLocaleString("en-US", { maximumFractionDigits: 1 })} tCO₂e`,
              name === "tco2e" ? "Recorded" : "Projected",
            ]}
          />
          <Area
            type="monotone"
            dataKey="tco2e"
            stroke="#34d399"
            strokeWidth={2}
            fill="url(#fillCarbon)"
          />
          {compareSeries && (
            <Line
              type="monotone"
              dataKey="projected"
              stroke="#38bdf8"
              strokeWidth={2}
              strokeDasharray="5 4"
              dot={false}
            />
          )}
        </AreaChart>
      </ResponsiveContainer>

      {highlightMonth && (
        <p className="mt-1 text-center text-[11px] text-slate-500">
          Anomaly flagged in{" "}
          <span className="text-signal-amber">{monthLabel(highlightMonth)}</span>
        </p>
      )}
    </div>
  );
}
