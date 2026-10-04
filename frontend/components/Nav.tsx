"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/upload", label: "Upload data", step: "01", hint: "Ingest" },
  { href: "/", label: "Dashboard", step: "02", hint: "Measure" },
  { href: "/insights", label: "AI Insights", step: "03", hint: "Diagnose" },
  { href: "/simulator", label: "Simulator", step: "04", hint: "Simulate" },
  { href: "/actions", label: "Action Plan", step: "05", hint: "Act" },
];

export function Nav() {
  const pathname = usePathname();

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

      <p className="kicker mt-7">Decision loop</p>
      <nav className="mt-2 flex flex-col">
        {LINKS.map((link) => {
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
              <span className={active ? "font-medium" : ""}>{link.label}</span>
              <span className="kicker ml-auto">{link.hint}</span>
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto pt-8">
        <div className="border-t border-rule pt-4">
          <p className="text-[11px] leading-relaxed text-ink-muted">
            Every carbon figure is produced by the calculation engine, never the language model.
          </p>
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
