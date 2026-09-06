import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f0f9ff",
          100: "#e0f2fe",
          400: "#38bdf8",
          500: "#0ea5e9",
          700: "#0369a1",
          900: "#0c4a6e",
        },
      },
      boxShadow: {
        panel: "0 10px 25px -10px rgba(15, 23, 42, 0.22)",
      },
    },
  },
  plugins: [],
};

export default config;
