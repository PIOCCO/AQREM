/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#ffffff",
          muted: "#f8fafc",
          subtle: "#f1f5f9",
        },
        border: {
          DEFAULT: "#e2e8f0",
          strong: "#cbd5e1",
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
          text: "#065f46",
        },
        warning: {
          DEFAULT: "#d97706",
          bg: "#fffbeb",
          border: "#fde68a",
          text: "#92400e",
        },
        error: {
          DEFAULT: "#dc2626",
          bg: "#fef2f2",
          border: "#fecaca",
          text: "#991b1b",
        },
        info: {
          DEFAULT: "#2563eb",
          bg: "#eff6ff",
          border: "#bfdbfe",
          text: "#1e40af",
        },
      },
      borderRadius: {
        sm: "0.375rem",
        md: "0.5rem",
        lg: "0.75rem",
      },
      boxShadow: {
        sm: "0 1px 2px 0 rgb(15 23 42 / 0.04)",
        card: "0 1px 3px 0 rgb(15 23 42 / 0.06)",
      },
      fontSize: {
        "page-title": ["1.375rem", { lineHeight: "1.75rem", fontWeight: "600" }],
        "section-title": ["0.9375rem", { lineHeight: "1.375rem", fontWeight: "600" }],
        label: ["0.75rem", { lineHeight: "1rem", fontWeight: "500" }],
      },
    },
  },
  plugins: [],
};
