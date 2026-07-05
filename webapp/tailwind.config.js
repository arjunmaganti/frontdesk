/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          base: "#06090e",
          primary: "#00D2FF",
          secondary: "#0080FF",
          charcoal: "#1E2229",
          gold: "#C5A880",
          cream: "#FAF8F5"
        }
      },
      fontFamily: {
        sans: ['Outfit', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
