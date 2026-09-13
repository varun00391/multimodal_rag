/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#07080c",
        panel: "#10131a",
        line: "rgba(255,255,255,0.08)",
        cream: "#f3eee4",
        mute: "#8b93a7",
        lime: "#d7ff3c",
        mist: "#9bb7ff",
      },
      fontFamily: {
        sans: ["Plus Jakarta Sans", "ui-sans-serif", "system-ui"],
        serif: ["Instrument Serif", "Georgia", "serif"],
      },
      boxShadow: {
        glow: "0 0 80px rgba(215, 255, 60, 0.12)",
      },
    },
  },
  plugins: [],
};
