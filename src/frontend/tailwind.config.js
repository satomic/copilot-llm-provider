/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        /* 3-tier background hierarchy */
        canvas:  "rgb(var(--color-canvas)  / <alpha-value>)",
        surface: "rgb(var(--color-surface) / <alpha-value>)",
        overlay: "rgb(var(--color-overlay) / <alpha-value>)",

        /* Border */
        edge: "rgb(var(--color-edge) / <alpha-value>)",

        /* Foreground / text */
        fg: {
          DEFAULT:   "rgb(var(--color-fg) / <alpha-value>)",
          secondary: "rgb(var(--color-fg-secondary) / <alpha-value>)",
          muted:     "rgb(var(--color-fg-muted) / <alpha-value>)",
        },

        /* Accent (primary blue) */
        accent: {
          DEFAULT: "rgb(var(--color-accent) / <alpha-value>)",
          hover:   "rgb(var(--color-accent-hover) / <alpha-value>)",
        },

        /* Semantic */
        success: "rgb(var(--color-success) / <alpha-value>)",
        warning: "rgb(var(--color-warning) / <alpha-value>)",
        danger:  "rgb(var(--color-danger) / <alpha-value>)",
      },
    },
  },
  plugins: [],
};
