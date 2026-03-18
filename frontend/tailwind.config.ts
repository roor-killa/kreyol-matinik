import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "Inter",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
      colors: {
        // Accent teal caraïbe
        teal: {
          700: "#0E7490",
          600: "#0891B2",
          50:  "#F0FDFF",
        },
        // Palette principale
        surface: {
          DEFAULT: "#FFFFFF",
          muted:   "#F9FAFB",
          border:  "#E5E7EB",
        },
      },
      borderRadius: {
        "2xl": "1rem",
        "3xl": "1.5rem",
      },
      boxShadow: {
        card: "0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.06)",
      },
      transitionDuration: {
        DEFAULT: "200",
      },
    },
  },
  plugins: [],
};

export default config;
