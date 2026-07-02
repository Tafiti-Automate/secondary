module.exports = {
  content: ["./templates/**/*.html", "./**/templates/**/*.html", "./**/*.py"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"], display: ["Manrope", "Inter", "sans-serif"] },
      colors: { brand: { 50: "#ecfdf5", 100: "#d1fae5", 200: "#a7f3d0", 300: "#6ee7b7", 400: "#34d399", 500: "#10b981", 600: "#059669", 700: "#047857", 800: "#065f46", 900: "#064e3b", 950: "#022c22" } },
      boxShadow: { soft: "0 18px 45px -24px rgba(15, 23, 42, .28)", glow: "0 18px 60px -25px rgba(16, 185, 129, .45)" },
      animation: { "fade-up": "fadeUp .45s ease-out both" },
      keyframes: { fadeUp: { "0%": { opacity: "0", transform: "translateY(8px)" }, "100%": { opacity: "1", transform: "translateY(0)" } } }
    }
  },
  plugins: []
};
