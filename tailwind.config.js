/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        void: "#05080d",
        panel: "#0a121b",
        "panel-raised": "#0f1c29",
        line: "#193348",
        cyan: "#43d9ff",
        "cyan-dim": "#1b6179",
        amber: "#ffb45c",
        green: "#72f0b0",
        red: "#ff6275",
        text: "#dcecf4",
        "text-dim": "#8ca7b8",
        "text-faint": "#526b7b",
      },
      fontFamily: {
        display: ["var(--font-display)", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
        body: ["var(--font-body)", "sans-serif"],
      },
    },
  },
  plugins: [],
}
