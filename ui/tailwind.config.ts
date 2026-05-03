import type { Config } from "tailwindcss";

// Editorial / parchment design language.
// - Cream paper background, deep ink text, terracotta accent.
// - Sharp corners on structural surfaces (cards, dialogs, tables);
//   slight 6px round on interactive controls (buttons, inputs) so the
//   click / type targets feel tappable. Use `rounded-md` for those.
// - Type pairing: Space Grotesk (display) + Inter (body) + ui-monospace (meta).
// Colors stay in lockstep with the website palette
// (docs/.vitepress/theme/custom.css) so screenshots and live UI read
// as the same product.
const config: Config = {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#faf6ec",
        "bg-soft": "#f1ece0",
        paper: "#ffffff",
        ink: "#141414",
        "ink-soft": "#2a2a28",
        "ink-mute": "#6a6a66",
        accent: "#b5563a",
        "accent-soft": "#d68870",
        "accent-wash": "rgba(181,86,58,0.10)",
        "accent-ink": "#1a0f06",
        // Dividers — bumped from 0.15/0.08 to 0.22/0.13 so structural lines
        // read as visibly thin on cream rather than ghost-thin. The editorial
        // language depends on the lines being *legible*, not invisible.
        line: "rgba(20,20,20,0.22)",
        "line-soft": "rgba(20,20,20,0.13)",
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
        // Structural surfaces stay sharp (cards, dialogs, tables, code).
        none: "0",
        sm: "0",
        DEFAULT: "0",
        lg: "0",
        xl: "0",
        "2xl": "0",
        // Interactive controls round slightly via `rounded-md`. Mirror the
        // 6px the website uses on hero buttons / form inputs.
        md: "6px",
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
        "slide-x": {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(400%)" },
        },
      },
      animation: {
        "fade-in": "fade-in 220ms ease-out",
        "dialog-in": "dialog-in 160ms ease-out",
        "pulse-dot": "pulse-dot 1.4s ease-in-out infinite",
        "slide-x": "slide-x 1.2s linear infinite",
      },
    },
  },
  plugins: [],
};

export default config;
