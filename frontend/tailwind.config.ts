import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Neutral zinc palette. "ink" is intentionally close to true black,
        // not blue-tinted slate, so the product reads as a console tool, not
        // an AI-app cliche.
        ink: {
          50: "#FAFAFA",
          100: "#F4F4F5",
          200: "#E4E4E7",
          300: "#D4D4D8",
          400: "#A1A1AA",
          500: "#71717A",
          600: "#52525B",
          700: "#3F3F46",
          800: "#27272A",
          900: "#18181B",
          950: "#09090B",
        },
        // "brand" used to be indigo. Now it's just an off-white scale so any
        // existing `bg-brand-500` etc. resolves to a neutral accent. New code
        // should prefer pure white or ink-* tokens directly.
        brand: {
          50: "#FFFFFF",
          100: "#FAFAFA",
          200: "#F4F4F5",
          300: "#E4E4E7",
          400: "#D4D4D8",
          500: "#FAFAFA",
          600: "#E4E4E7",
          700: "#D4D4D8",
        },
        // Severity is the ONLY semantic color usage. Slightly desaturated
        // from the prior values so they sit better on the new neutral bg.
        sev: {
          p1: "#F43F5E",
          p2: "#F59E0B",
          p3: "#22C55E",
        },
      },
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Inter",
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "Liberation Mono",
          "monospace",
        ],
      },
      boxShadow: {
        // Subtle white-ish elevation. Used on cards and hero panels.
        // No colored glows, ever.
        glow: "0 24px 60px -24px rgba(0, 0, 0, 0.6), 0 1px 0 rgba(255, 255, 255, 0.04) inset",
        card: "0 1px 0 rgba(255,255,255,0.04) inset, 0 8px 24px -12px rgba(0,0,0,0.6)",
      },
      keyframes: {
        pulseSlow: {
          "0%, 100%": { opacity: "0.9" },
          "50%": { opacity: "0.4" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        fadeIn: {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "pulse-slow": "pulseSlow 2.4s ease-in-out infinite",
        shimmer: "shimmer 2.5s linear infinite",
        "fade-in": "fadeIn 220ms ease-out",
      },
      backgroundImage: {
        "grid-fade":
          "radial-gradient(circle at top, rgba(99,102,241,0.12), transparent 60%)",
      },
    },
  },
  plugins: [],
};

export default config;
