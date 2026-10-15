import type { Metadata } from "next";

// Server-side counterpart of the client page: metadata is disallowed in
// "use client" files, so the route's title is declared here and rendered by
// the root template as "<title> — CarbonPilot" in the static export.
export const metadata: Metadata = {
  title: "Grid benchmarks",
};

export default function JapacLayout({ children }: { children: React.ReactNode }) {
  return children;
}
