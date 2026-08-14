import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0b0f14",
        surface: "#121821",
        border: "#232c38",
        accent: "#6366f1",
        "accent-hover": "#818cf8",
        muted: "#8b95a5",
      },
    },
  },
  plugins: [],
};

export default config;
