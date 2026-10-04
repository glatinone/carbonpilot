"use client";

import type { ReactNode } from "react";
import { useLocale } from "@/lib/i18n";

const TONE = {
  ink: "text-ink",
  save: "text-save",
  alert: "text-alert",
  stop: "text-stop",
} as const;

/**
 * A measured figure. Deliberately not a card: in the ledger language a number is
 * a column entry, so the same component can sit in a ruled row or a table cell
 * without changing its meaning.
 */
export function Stat({
  label,
  value,
  sub,
  tone = "ink",
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: keyof typeof TONE;
}) {
  return (
    <div>
      <p className="kicker">{label}</p>
      <p className={`fig mt-1.5 text-[22px] font-medium leading-none tracking-tight ${TONE[tone]}`}>
        {value}
      </p>
      {sub && <p className="mt-1.5 text-[11px] leading-snug text-ink-muted">{sub}</p>}
    </div>
  );
}

/** Every band opens the same way: a small mono kicker over a serif title. */
export function SectionHead({
  kicker,
  title,
  note,
  action,
}: {
  kicker: string;
  title: string;
  note?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2 pb-3">
      <div>
        <p className="kicker">{kicker}</p>
        <h2 className="mt-1 font-serif text-[17px] font-semibold tracking-tight text-ink">{title}</h2>
      </div>
      <div className="flex items-center gap-4">
        {note && <span className="text-[11.5px] text-ink-muted">{note}</span>}
        {action}
      </div>
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="border-t border-rule py-8">
      <p className="text-[13px] font-medium text-ink">{title}</p>
      <p className="mt-1.5 text-[12px] leading-relaxed text-ink-muted">{hint}</p>
    </div>
  );
}

/** Flat, squared, no pulse of colour — a placeholder should look like empty paper. */
export function Skeleton({ className = "h-24" }: { className?: string }) {
  return <div className={`animate-pulse bg-rule/60 ${className}`} />;
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const { t } = useLocale();
  return (
    <div className="border-l-2 border-l-stop border-y border-r border-rule bg-paper-panel px-4 py-3">
      <p className="text-[13px] font-medium text-stop">{t("error.title")}</p>
      <p className="mt-1 text-[12px] text-ink-muted">{message}</p>
      <p className="mt-1.5 text-[12px] text-ink-muted">
        {t("error.startWith")}{" "}
        <code className="fig border border-rule-strong bg-paper px-1.5 py-0.5 text-[11px] text-ink-soft">
          python -m uvicorn app.main:app --port 8008
        </code>
      </p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="btn-ghost mt-3">
          {t("error.retry")}
        </button>
      )}
    </div>
  );
}

/** Provenance strip. The product's differentiator, so it gets a component, not a footnote *string*. */
export function Footnote({ children }: { children: ReactNode }) {
  return <div className="footnote">{children}</div>;
}

/**
 * Renders a translated sentence with every `{placeholder}` emphasised.
 *
 * Composing "Nusantara moved +165% in May" by concatenating JSX fragments cannot be
 * translated: word order differs per language and the emphasis would land on the
 * wrong words. Keeping the whole sentence in the dictionary as a template with
 * placeholders, and bolding the substitutions here, lets each language own its own
 * grammar while the emphasis survives.
 */
export function Emphasised({
  template,
  values,
  tone = "ink",
}: {
  template: string;
  values: Record<string, string>;
  tone?: "ink" | "alert";
}) {
  return (
    <>
      {template.split(/(\{\w+\})/g).map((part, index) => {
        const match = part.match(/^\{(\w+)\}$/);
        if (!match) return <span key={index}>{part}</span>;
        return (
          <b
            key={index}
            className={tone === "alert" ? "font-semibold text-alert" : "font-semibold text-ink"}
          >
            {values[match[1]] ?? part}
          </b>
        );
      })}
    </>
  );
}
