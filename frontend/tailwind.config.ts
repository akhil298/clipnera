import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

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
      },
      backdropBlur: {
        xl: "24px",
      },
      fontFamily: {
        jakarta: ['"Plus Jakarta Sans"', "sans-serif"],
        syne: ["Syne", "sans-serif"],
        jetbrains: ['"JetBrains Mono"', "monospace"],
      },
    },
  },
  plugins: [animate],
};

export default config;
