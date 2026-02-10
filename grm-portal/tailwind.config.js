/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        grm: {
          accent: "#2490EF",
          text: "#171717",
          secondary: "#707070",
          muted: "#7C7C7C",
          border: "#EDEDED",
          bg: "#F8F8F8",
        },
        primary: {
          50: "#edfaf4",
          100: "#e1f2eb",
          200: "#b3e8d1",
          300: "#7adab4",
          400: "#3fcc96",
          500: "#24c38b",
          600: "#1da672",
          700: "#17855b",
          800: "#136949",
          900: "#0f563c",
          950: "#083022",
        },
        dark: "#4A4A4A",
        error: "#ef6a78",
        "in-progress": "#f5ba74",
      },
    },
  },
  plugins: [],
};
