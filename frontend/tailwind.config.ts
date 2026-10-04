import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: { DEFAULT: "#fbfaf7", band: "#f6f5f1", panel: "#ffffff" },
        ink: { DEFAULT: "#14150f", soft: "#33332e", muted: "#6d6d63", faint: "#9a9a8e" },
        rule: { DEFAULT: "#e2e0d8", strong: "#c9c6ba" },
        save: "#1c4b36",
        alert: "#9c5a12",
        stop: "#8f2f22",
        bar: "#d6d3c8",
      },
      fontFamily: {
        serif: ["var(--font-serif)", "Georgia", "Times New Roman", "serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      // Small radii on purpose: a 2px corner reads as a printed rule, not a bubble.
      borderRadius: { DEFAULT: "2px", sm: "2px", md: "3px", lg: "4px" },
      letterSpacing: { kicker: "0.14em" },
    },
  },
  plugins: [],
};

export default config;
