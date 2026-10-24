import animate from "tailwindcss-animate";

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["selector", '[data-theme="dark"]'],
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        paper: "hsl(var(--paper-hsl) / <alpha-value>)",
        surface: "hsl(var(--surface-hsl) / <alpha-value>)",
        ink: "hsl(var(--ink-hsl) / <alpha-value>)",
        muted: "hsl(var(--muted-hsl) / <alpha-value>)",
        line: "hsl(var(--line-hsl) / <alpha-value>)",
        danger: "hsl(var(--danger-hsl) / <alpha-value>)",
        accent: {
          DEFAULT: "hsl(var(--accent-hsl) / <alpha-value>)",
          weak: "hsl(var(--accent-weak-hsl) / <alpha-value>)",
          ink: "hsl(var(--accent-ink-hsl) / <alpha-value>)",
        },
      },
      fontFamily: {
        sans: ['"Schibsted Grotesk"', "system-ui", "-apple-system", '"Segoe UI"', "sans-serif"],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 4px)",
        sm: "calc(var(--radius) - 8px)",
        pill: "999px",
      },
      boxShadow: {
        soft: "0 8px 24px hsl(var(--ink-hsl) / 0.10)",
        float: "0 12px 34px hsl(var(--ink-hsl) / 0.16)",
      },
    },
  },
  plugins: [animate],
};
