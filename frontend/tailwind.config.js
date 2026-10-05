/** @type {import('tailwindcss').Config} */
export default {
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
          DEFAULT: "#ffffff",
          muted: "#f9fafb",
          subtle: "#f3f4f6",
          canvas: "#f1f5f9",
        },
        border: {
          DEFAULT: "#e5e7eb",
          strong: "#d1d5db",
        },
        brand: {
          violet: "#7c3aed",
          blue: "#2563eb",
        },
        primary: {
          DEFAULT: "#0f172a",
          hover: "#1e293b",
          foreground: "#ffffff",
        },
        success: {
          DEFAULT: "#059669",
          bg: "#ecfdf5",
          border: "#a7f3d0",
          text: "#047857",
        },
        warning: {
          DEFAULT: "#d97706",
          bg: "#fffbeb",
          border: "#fde68a",
          text: "#b45309",
        },
        error: {
          DEFAULT: "#dc2626",
          bg: "#fef2f2",
          border: "#fecaca",
          text: "#b91c1c",
        },
        info: {
          DEFAULT: "#2563eb",
          bg: "#eff6ff",
          border: "#bfdbfe",
          text: "#1d4ed8",
        },
        review: {
          bg: "#fef2f2",
          text: "#b91c1c",
          border: "#fecaca",
        },
      },
      width: {
        sidebar: "240px",
      },
      height: {
        header: "64px",
      },
      borderRadius: {
        card: "12px",
        control: "8px",
      },
      boxShadow: {
        sm: "0 1px 2px 0 rgb(15 23 42 / 0.04)",
        card: "0 1px 3px 0 rgb(15 23 42 / 0.06), 0 1px 2px -1px rgb(15 23 42 / 0.06)",
        panel: "0 4px 6px -1px rgb(15 23 42 / 0.07), 0 2px 4px -2px rgb(15 23 42 / 0.05)",
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
