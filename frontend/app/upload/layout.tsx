import type { Metadata } from "next";

// The page below is a client component and cannot export metadata, so the
// per-route title lives on the route's server layout; the root template
// renders it as "<title> — CarbonPilot". Resolved at build time, so the
// static export ships the right <title> in out/upload/index.html.
export const metadata: Metadata = {
  title: "Upload data",
};

export default function UploadLayout({ children }: { children: React.ReactNode }) {
  return children;
}
