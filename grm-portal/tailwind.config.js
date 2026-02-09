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
          secondary: "#525252",
          muted: "#7C7C7C",
          border: "#EDEDED",
          bg: "#F8F8F8",
        },
      },
    },
  },
  plugins: [],
};
