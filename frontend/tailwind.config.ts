import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";
import * as cn from "./lib/design/tokens";

// Design-system keys, all prefixed `cn-` and fed by lib/design/tokens.ts.
// They sit beside the legacy keys below and change nothing that exists.
const prefixed = <V>(scale: Record<string, V>): Record<string, V> =>
  Object.fromEntries(Object.entries(scale).map(([name, value]) => [`cn-${name}`, value]));
const cnColors = Object.fromEntries(
  Object.keys(cn.colors.dark).map((name) => [name, `rgb(var(--cn-${name}) / <alpha-value>)`]),
);
const cnShadows = Object.fromEntries(Object.keys(cn.shadows.dark).map((level) => [level, `var(--cn-shadow-${level})`]));
const cnDurations = Object.fromEntries(Object.entries(cn.duration).map(([name, ms]) => [name, `${ms}ms`]));

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Lighter than Tailwind's #737373 so secondary text meets WCAG AA
        // (4.5:1) on the app's neutral-800/900/950 backgrounds.
        neutral: {
          500: "#8c8c8c",
        },
        border: "hsl(var(--border))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        cn: cnColors,
      },
      fontSize: prefixed(cn.fontSize as unknown as Record<string, [string, { lineHeight: string; letterSpacing?: string }]>),
      borderRadius: prefixed(cn.radius),
      boxShadow: prefixed(cnShadows),
      zIndex: prefixed(cn.zIndex),
      transitionDuration: prefixed(cnDurations),
      transitionTimingFunction: prefixed(cn.easing),
      animation: {
        "cn-highlight": `cn-highlight ${cn.duration.highlight}ms ${cn.easing.out} forwards`,
        "cn-pulse": "cn-pulse 1.6s ease-in-out infinite",
        "cn-sweep": `cn-sweep 1.4s ${cn.easing["in-out"]} infinite`,
      },
      backdropBlur: {
        xl: "24px",
      },
      aspectRatio: {
        "cn-portrait": "9 / 16",
      },
      padding: {
        safe: "env(safe-area-inset-bottom, 0px)",
      },
      fontFamily: {
        jakarta: ['"Plus Jakarta Sans"', "sans-serif"],
        syne: ["Syne", "sans-serif"],
        jetbrains: ['"JetBrains Mono"', "monospace"],
        ...prefixed<string[]>(cn.fontFamily as unknown as Record<string, string[]>),
      },
    },
  },
  plugins: [animate],
};

export default config;
