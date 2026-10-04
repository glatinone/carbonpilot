import type { Metadata } from "next";
import { IBM_Plex_Mono, Inter, Source_Serif_4 } from "next/font/google";
import "./globals.css";
import { Nav } from "@/components/Nav";
import { LocaleProvider } from "@/lib/i18n";

/**
 * Fonts are self-hosted at build time by next/font, so the demo never depends on
 * a font CDN being reachable while a judge is watching.
 */
const serif = Source_Serif_4({
  subsets: ["latin"],
  weight: ["400", "600", "700"],
  variable: "--font-serif",
  display: "swap",
});

const sans = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-sans",
  display: "swap",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "CarbonPilot — AI Carbon Decision Engine",
  description:
    "Measure. Diagnose. Simulate. Act. Turn operational data into prioritised, financially-aware decarbonisation decisions.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${serif.variable} ${sans.variable} ${mono.variable}`}>
      <body className="font-sans">
        <LocaleProvider>
          <div className="mx-auto flex min-h-screen w-full max-w-[1500px]">
            <Nav />
            <main className="min-w-0 flex-1 px-6 py-7 lg:px-10">{children}</main>
          </div>
        </LocaleProvider>
      </body>
    </html>
  );
}
