/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#F4F3EF",
        panel: "#FFFFFF",
        line: "rgba(17, 17, 16, 0.08)",
        cream: "#111110",
        mute: "#73726C",
        lime: "#111110",
        mist: "#6D5EF7",
      },
      fontFamily: {
        sans: ["Outfit", "ui-sans-serif", "system-ui"],
        serif: ["Fraunces", "Georgia", "serif"],
      },
      fontSize: {
        display: ["4.5rem", { lineHeight: "0.92", letterSpacing: "-0.04em" }],
      },
      boxShadow: {
        glow: "0 30px 80px rgba(17, 17, 16, 0.08)",
        lift: "0 1px 2px rgba(17, 17, 16, 0.04), 0 8px 24px rgba(17, 17, 16, 0.04)",
      },
      borderRadius: {
        shell: "28px",
      },
    },
  },
  plugins: [],
};
