"use client";

import { useState } from "react";
import type { Insight } from "@/lib/types";
import { useLocale, useStreamLabel } from "@/lib/i18n";
import { Emphasised } from "@/components/ui";
import { formatPct, formatTonnes, formatUsd } from "@/lib/format";

/**
 * One signal, as a ledger row that opens. Collapsed it is scannable in a list of
 * signals; open, the evidence reads as an audit trail rather than a card.
 */
export function InsightCard({ insight, index }: { insight: Insight; index: number }) {
  const { t } = useLocale();
  const streamLabel = useStreamLabel();
  const [open, setOpen] = useState(index === 0);
  const evidence = insight.evidence as Record<string, number | string | string[] | null>;

  return (
    <article className="border-b border-rule">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-start gap-4 py-3.5 text-left transition hover:bg-paper-band/70"
      >
        <span className="fig w-5 shrink-0 pt-0.5 text-[11px] text-alert">
          {String(index + 1).padStart(2, "0")}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[13px] font-medium leading-snug text-ink">
            {insight.headline}
          </span>
          <span className="mt-1 block text-[12px] leading-relaxed text-ink-muted">
            {insight.detail}
          </span>
        </span>
        <span className="kicker shrink-0">{open ? t("insight.hide") : t("insight.evidence")}</span>
      </button>

      {open && (
        <div className="pb-5 pl-9">
          <div className="grid gap-5 border-t border-rule pt-4 sm:grid-cols-3">
            <Figure
              label={t("insight.potential")}
              value={formatTonnes(insight.carbon_impact_t)}
              tone="save"
            />
            <Figure
              label={t("insight.financial")}
              value={formatUsd(insight.cost_impact_usd)}
              sub={t("insight.perYear")}
            />
            <Figure label={t("insight.confidence")} value={`${insight.confidence_pct.toFixed(0)}%`} />
          </div>

          <div className="mt-4 border-t border-rule pt-3">
            <p className="kicker mb-2">{t("insight.evTitle")}</p>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-[11.5px] sm:grid-cols-3">
              <Row label={t("insight.observed")} value={`${evidence.observed_tco2e} tCO₂e`} />
              <Row label={t("insight.baseline")} value={`${evidence.baseline_tco2e} tCO₂e`} />
              <Row label={t("insight.delta")} value={formatPct(Number(evidence.change_pct))} />
              <Row label={t("insight.zscore")} value={String(evidence.z_score)} />
              <Row label={t("insight.severity")} value={String(evidence.severity)} />
              <Row
                label={t("insight.window")}
                value={t("insight.months", {
                  n: (evidence.baseline_months as string[])?.length ?? 0,
                })}
              />
            </dl>
            {evidence.suggested_action ? (
              <p className="mt-3 border-t border-rule pt-2.5 text-[11.5px] text-ink-muted">
                {t("insight.suggested")}{" "}
                <span className="text-save">{String(evidence.suggested_action)}</span>
              </p>
            ) : null}
          </div>

          <p className="mt-3 text-[11px] leading-relaxed text-ink-faint">
            <Emphasised
              template={t("insight.method")}
              values={{
                stream: streamLabel(String(insight.activity_type)),
                month: insight.month,
              }}
            />
          </p>
        </div>
      )}
    </article>
  );
}

function Figure({
  label,
  value,
  sub,
  tone = "ink",
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "ink" | "save";
}) {
  return (
    <div>
      <p className="kicker">{label}</p>
      <p className={`fig mt-1.5 text-[18px] font-medium leading-none ${tone === "save" ? "text-save" : "text-ink"}`}>
        {value}
      </p>
      {sub && <p className="mt-1 text-[10.5px] text-ink-faint">{sub}</p>}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 border-b border-rule/70 pb-1.5">
      <dt className="text-ink-muted">{label}</dt>
      <dd className="fig text-ink">{value}</dd>
    </div>
  );
}
