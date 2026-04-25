import type { Config } from "tailwindcss";

// Editorial / parchment design language.
// - Cream paper background, deep ink text, burnt orange accent.
// - Sharp corners (no border-radius) — bookprint vibe.
// - Type pairing: Space Grotesk (display) + Inter (body) + ui-monospace (meta).
// All values are direct color tokens (no CSS variables) so the theme is
// readable at a glance and survives ShadCN updates.
const config: Config = {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#f1ede3",
        "bg-soft": "#e8e2d3",
        paper: "#ffffff",
        ink: "#141414",
        "ink-soft": "#2a2a28",
        "ink-mute": "#6a6a66",
        accent: "#c46a37",
        "accent-soft": "#e9a577",
        "accent-ink": "#1a0f06",
        line: "rgba(20,20,20,0.15)",
        "line-soft": "rgba(20,20,20,0.08)",
        danger: "#c0392b",
        ok: "#3d8a55",
      },
      fontFamily: {
        display: [
          "Space Grotesk",
          "Inter",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "sans-serif",
        ],
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
        serif: ["Crimson Pro", "Georgia", "serif"],
      },
      borderRadius: {
        none: "0",
        sm: "0",
        DEFAULT: "0",
        md: "0",
        lg: "0",
        xl: "0",
        "2xl": "0",
      },
      boxShadow: {
        // Hard editorial shadow — no soft gaussian.
        editorial: "4px 4px 0 #141414",
        "editorial-soft": "3px 3px 0 rgba(20,20,20,0.18)",
      },
      letterSpacing: {
        wide: "0.025em",
        tight: "-0.025em",
        widest: "0.18em",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        // dialog-in is opacity-only: Radix DialogContent uses its own
        // -translate-x-1/2 -translate-y-1/2 to center, and a transform-
        // animating keyframe would override that mid-animation, causing
        // the visible "jump" when the animation finishes. Keep this
        // separate from fade-in so non-Radix call sites still get the
        // subtle 4px slide.
        "dialog-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "pulse-dot": {
          "0%, 80%, 100%": { opacity: "0.2" },
          "40%": { opacity: "1" },
        },
      },
      animation: {
        "fade-in": "fade-in 220ms ease-out",
        "dialog-in": "dialog-in 160ms ease-out",
        "pulse-dot": "pulse-dot 1.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
