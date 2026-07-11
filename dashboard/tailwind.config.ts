import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#eef7ff",
          100: "#d8ecff",
          500: "#1d8cf8",
          600: "#1479dd",
          700: "#1262b2"
        },
        secondary: {
          100: "#defcf2",
          500: "#18b981",
          600: "#109d6d"
        },
        surface: {
          900: "#0f172a",
          800: "#172033",
          700: "#243147"
        }
      },
      boxShadow: {
        card: "0 12px 32px rgba(15, 23, 42, 0.14)"
      }
    }
  },
  plugins: []
};

export default config;
