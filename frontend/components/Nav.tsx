"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Dashboard", hint: "Measure" },
  { href: "/insights", label: "AI Insights", hint: "Diagnose" },
  { href: "/simulator", label: "Simulator", hint: "Simulate" },
  { href: "/actions", label: "Action Plan", hint: "Act" },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-ink-800/80 bg-ink-950/60 px-5 py-7 lg:flex">
      <Link href="/" className="flex items-center gap-2.5">
        <span className="grid h-8 w-8 place-items-center rounded-lg bg-signal-mint text-ink-950">
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.4">
            <path d="M12 3v6" strokeLinecap="round" />
            <circle cx="12" cy="14" r="6" />
            <path d="M12 11v6" strokeLinecap="round" />
          </svg>
        </span>
        <span className="text-[15px] font-semibold tracking-tight text-white">CarbonPilot</span>
      </Link>

      <p className="mt-8 label">Decision loop</p>
      <nav className="mt-3 flex flex-col gap-1">
        {LINKS.map((link) => {
          const active = pathname === link.href;
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`group flex items-center justify-between rounded-lg px-3 py-2.5 text-sm transition ${
                active
                  ? "bg-ink-800/80 text-white"
                  : "text-slate-400 hover:bg-ink-850/60 hover:text-slate-200"
              }`}
            >
              <span className="font-medium">{link.label}</span>
              <span
                className={`text-[10px] uppercase tracking-wider ${
                  active ? "text-signal-mint" : "text-slate-600 group-hover:text-slate-500"
                }`}
              >
                {link.hint}
              </span>
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto space-y-3 pt-8">
        <div className="rounded-lg border border-ink-700/70 bg-ink-900/60 p-3">
          <p className="text-[11px] leading-relaxed text-slate-500">
            Every carbon figure is produced by the calculation engine, not the language model.
          </p>
        </div>
        <p className="text-[10px] leading-relaxed text-slate-600">
          GHG Protocol · UK GHG Conversion Factors 2026 · Cloud Carbon Footprint
        </p>
      </div>
    </aside>
  );
}
