"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLocale } from "@/lib/i18n";

const LOOP = [
  { href: "/upload", step: "01", labelKey: "nav.upload", hintKey: "nav.hDesc" },
  { href: "/", step: "02", labelKey: "nav.dashboard", hintKey: "nav.hMeasure" },
  { href: "/insights", step: "03", labelKey: "nav.insights", hintKey: "nav.hDiagnose" },
  { href: "/simulator", step: "04", labelKey: "nav.simulator", hintKey: "nav.hSimulate" },
  { href: "/actions", step: "05", labelKey: "nav.actions", hintKey: "nav.hAct" },
];

// Deliberately outside the decision loop: a benchmark is something you compare
// against, not a step you take in the cycle.
const REFERENCE = [{ href: "/japac", step: "06", labelKey: "nav.japac", hintKey: "nav.hCompare" }];

type NavLink = { href: string; step: string; labelKey: string; hintKey: string };

export function Nav() {
  const pathname = usePathname();
  const { locale, setLocale, t } = useLocale();

  function renderRow(link: NavLink) {
    const active = pathname === link.href;
    return (
      <Link
        key={link.href}
        href={link.href}
        className={`-ml-px flex items-baseline gap-3 border-l-2 py-2.5 pl-3 text-[13px] transition ${
          active
            ? "border-l-ink text-ink"
            : "border-l-transparent text-ink-muted hover:border-l-rule-strong hover:text-ink"
        }`}
      >
        <span className={`fig text-[10px] ${active ? "text-ink" : "text-ink-faint"}`}>
          {link.step}
        </span>
        <span className={active ? "font-medium" : ""}>{t(link.labelKey)}</span>
        <span className="kicker ml-auto">{t(link.hintKey)}</span>
      </Link>
    );
  }

  return (
    <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-rule bg-paper-band px-6 py-8 lg:flex">
      <Link href="/" className="flex items-baseline gap-2.5">
        <span className="grid h-7 w-7 shrink-0 place-items-center border border-ink bg-ink text-[11px] font-medium text-paper">
          C
        </span>
        <span className="font-serif text-[19px] font-semibold tracking-tight text-ink">
          CarbonPilot
        </span>
      </Link>

      <p className="kicker mt-7">{t("nav.decisionLoop")}</p>
      <nav className="mt-2 flex flex-col">{LOOP.map(renderRow)}</nav>

      <p className="kicker mt-6">{t("nav.reference")}</p>
      <nav className="mt-2 flex flex-col">{REFERENCE.map(renderRow)}</nav>

      <div className="mt-auto pt-8">
        <div className="border-t border-rule pt-4">
          <p className="text-[11px] leading-relaxed text-ink-muted">{t("nav.engineNote")}</p>
        </div>

        <div className="mt-4 flex items-center border-t border-rule pt-4">
          <span className="kicker">{t("nav.language")}</span>
          <div className="ml-auto flex border border-rule-strong">
            {(["en", "id"] as const).map((code) => (
              <button
                key={code}
                type="button"
                onClick={() => setLocale(code)}
                aria-pressed={locale === code}
                title={code === "en" ? "English" : "Bahasa Indonesia"}
                className={`px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.08em] transition ${
                  locale === code ? "bg-ink text-paper" : "text-ink-muted hover:text-ink"
                }`}
              >
                {code}
              </button>
            ))}
          </div>
        </div>

        <p className="mt-4 font-mono text-[9.5px] leading-relaxed text-ink-faint">
          GHG PROTOCOL
          <br />
          UK GHG CONVERSION FACTORS 2026
          <br />
          CLOUD CARBON FOOTPRINT
        </p>
      </div>
    </aside>
  );
}
