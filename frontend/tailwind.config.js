import animate from "tailwindcss-animate";

const c = (v) => `hsl(var(--${v}-hsl) / <alpha-value>)`;

/** Kajo tokens — values live in src/styles/globals.css. */
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["selector", '[data-theme="dark"]'],
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        paper: c("paper"),
        surface: c("surface"),
        sunk: c("sunk"),
        ink: c("ink"),
        muted: c("muted"),
        line: c("line"),
        "on-ink": c("on-ink"),
        newsroom: { DEFAULT: c("newsroom"), weak: c("newsroom-weak") },
        community: { DEFAULT: c("community"), weak: c("community-weak") },
        confirmed: { DEFAULT: c("confirmed"), weak: c("confirmed-weak") },
        danger: { DEFAULT: c("danger"), weak: c("danger-weak") },
        // Legacy alias for the first two rebuilt screens; same as newsroom.
        accent: { DEFAULT: c("newsroom"), weak: c("newsroom-weak"), ink: c("on-ink") },
      },
      fontFamily: {
        // Wordmark only: the Kalevalo name. Everything else stays in Plex.
        display: ['"Archivo Black"', '"IBM Plex Sans"', "system-ui", "sans-serif"],
        sans: ['"IBM Plex Sans"', '"IBM Plex Sans Arabic"', "system-ui", "-apple-system", '"Segoe UI"', "sans-serif"],
      },
      // Type scale (~1.2 ratio on a 15px UI / 17px reading base). [size, {lineHeight, letterSpacing, fontWeight}]
      fontSize: {
        caption: ["12px", { lineHeight: "16px", letterSpacing: "0.01em" }],
        meta: ["13px", { lineHeight: "18px" }],
        ui: ["15px", { lineHeight: "22px" }],
        body: ["17px", { lineHeight: "28px" }],
        lead: ["19px", { lineHeight: "29px" }],
        title: ["17px", { lineHeight: "23px", letterSpacing: "-0.005em", fontWeight: "600" }],
        headline: ["22px", { lineHeight: "28px", letterSpacing: "-0.012em", fontWeight: "600" }],
        display: ["30px", { lineHeight: "34px", letterSpacing: "-0.02em", fontWeight: "600" }],
        hero: ["44px", { lineHeight: "46px", letterSpacing: "-0.028em", fontWeight: "600" }],
      },
      // Small, flat shapes (Notion feel): controls < panels < dialogs; pills only for tags.
      borderRadius: {
        control: "6px",
        card: "8px",
        sheet: "12px",
        pill: "999px",
        lg: "8px",
        md: "6px",
        sm: "4px",
      },
      // Elevation only for things that float above the page.
      boxShadow: {
        float: "0 1px 2px hsl(var(--ink-hsl) / 0.06), 0 18px 48px -12px hsl(var(--ink-hsl) / 0.22)",
        soft: "0 1px 2px hsl(var(--ink-hsl) / 0.06), 0 8px 24px -10px hsl(var(--ink-hsl) / 0.16)",
      },
      transitionTimingFunction: { kajo: "cubic-bezier(0.2, 0.8, 0.2, 1)" },
      maxWidth: { read: "40rem" },
    },
  },
  plugins: [animate],
};
