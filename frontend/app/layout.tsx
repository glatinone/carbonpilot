import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/Nav";

export const metadata: Metadata = {
  title: "CarbonPilot — AI Carbon Decision Engine",
  description:
    "Measure. Diagnose. Simulate. Act. Turn operational data into prioritised, financially-aware decarbonisation decisions.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="mx-auto flex min-h-screen w-full max-w-[1500px]">
          <Nav />
          <main className="min-w-0 flex-1 px-6 py-7 lg:px-9">{children}</main>
        </div>
      </body>
    </html>
  );
}
