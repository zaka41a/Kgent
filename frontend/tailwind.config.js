/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "#0d0d0d",
          soft: "#171717",
          card: "#1f1f1f",
        },
        ink: {
          DEFAULT: "#ececec",
          muted: "#a1a1a1",
          dim: "#666",
        },
        accent: {
          DEFAULT: "#10a37f",
          hover: "#0e8c6c",
        },
        border: "#2a2a2a",
      },
      fontFamily: {
        sans: ['"Söhne"', '"Helvetica Neue"', "Helvetica", "Arial", "sans-serif"],
        mono: ['"JetBrains Mono"', '"SF Mono"', "Menlo", "monospace"],
      },
      animation: {
        "fade-in": "fadeIn 0.25s ease-out",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
