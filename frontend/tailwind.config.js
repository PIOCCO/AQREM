/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
      colors: {
        surface: {
          DEFAULT: "var(--color-surface)",
          muted: "var(--color-background)",
          subtle: "var(--color-surface-raised)",
          canvas: "var(--color-background)",
        },
        border: {
          DEFAULT: "var(--color-border)",
          strong: "var(--color-border-strong)",
        },
        brand: {
          violet: "var(--color-accent)",
          blue: "var(--color-accent)",
        },
        primary: {
          DEFAULT: "var(--color-text-primary)",
          hover: "var(--color-text-secondary)",
          foreground: "var(--color-accent-fg)",
        },
        success: {
          DEFAULT: "var(--color-success)",
          bg: "var(--color-success-bg)",
          border: "var(--color-success-border)",
          text: "var(--color-success)",
        },
        warning: {
          DEFAULT: "var(--color-warning)",
          bg: "var(--color-warning-bg)",
          border: "var(--color-warning-border)",
          text: "var(--color-warning)",
        },
        error: {
          DEFAULT: "var(--color-danger)",
          bg: "var(--color-danger-bg)",
          border: "var(--color-danger-border)",
          text: "var(--color-danger)",
        },
        info: {
          DEFAULT: "var(--color-accent)",
          bg: "var(--color-accent-bg)",
          border: "var(--color-border)",
          text: "var(--color-accent)",
        },
        review: {
          bg: "var(--color-warning-bg)",
          text: "var(--color-warning)",
          border: "var(--color-warning-border)",
        },
        chat: {
          accent: "var(--color-accent)",
        },
        fg: {
          DEFAULT: "var(--color-text-primary)",
          muted: "var(--color-text-muted)",
          secondary: "var(--color-text-secondary)",
        },
        link: "var(--color-link)",
      },
      width: {
        sidebar: "280px",
      },
      boxShadow: {
        sm: "0 1px 2px 0 rgb(0 0 0 / 0.08)",
        card: "0 1px 3px 0 rgb(0 0 0 / 0.12), 0 1px 2px -1px rgb(0 0 0 / 0.1)",
        panel: "0 4px 6px -1px rgb(0 0 0 / 0.12), 0 2px 4px -2px rgb(0 0 0 / 0.08)",
        composer: "0 0 0 1px rgb(0 0 0 / 0.05), 0 4px 16px rgb(0 0 0 / 0.08)",
      },
      height: {
        header: "52px",
      },
      borderRadius: {
        card: "12px",
        control: "8px",
      },
      fontSize: {
        "page-title": ["1.75rem", { lineHeight: "2.125rem", fontWeight: "600" }],
        "section-title": ["1rem", { lineHeight: "1.5rem", fontWeight: "600" }],
        label: ["0.6875rem", { lineHeight: "1rem", fontWeight: "500" }],
      },
    },
  },
  plugins: [],
};
