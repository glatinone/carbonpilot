export function formatTonnes(value: number, digits = 0): string {
  return `${value.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })} tCO₂e`;
}

export function formatTonnesShort(value: number): string {
  if (Math.abs(value) >= 1000) return `${(value / 1000).toFixed(1)}k`;
  return value.toFixed(0);
}

function usdCore(abs: number): string {
  if (abs >= 1_000_000) return `$${(abs / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `$${(abs / 1_000).toFixed(0)}K`;
  return `$${abs.toFixed(0)}`;
}

export function formatUsd(value: number): string {
  const sign = value < 0 ? "-" : value > 0 ? "+" : "";
  return sign + usdCore(Math.abs(value));
}

/**
 * Magnitude only, with no sign.
 *
 * For comparison clauses where the direction is already a word: "+$524K cheaper"
 * contradicts itself, and "$524K cheaper" is what the sentence needs.
 */
export function formatUsdMagnitude(value: number): string {
  return usdCore(Math.abs(value));
}

export function formatUsdFull(value: number): string {
  const sign = value < 0 ? "-" : "";
  return `${sign}$${Math.abs(value).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

export function formatPct(value: number, digits = 1): string {
  return `${value > 0 ? "+" : ""}${value.toFixed(digits)}%`;
}

export function titleize(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function monthLabel(month: string, locale: "en" | "id" = "en"): string {
  const [year, m] = month.split("-");
  const date = new Date(Number(year), Number(m) - 1, 1);
  return date.toLocaleString(locale === "id" ? "id-ID" : "en-US", {
    month: "short",
    year: "2-digit",
  });
}

export const EFFORT_COLOR: Record<string, string> = {
  low: "text-save",
  medium: "text-alert",
  high: "text-stop",
};
