/** @type {import('tailwindcss').Config} */
export default {
	content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
	theme: {
		extend: {
			colors: {
				grm: {
					text: "#171717",
					// Body copy on white, so it is held at or above the 4.5:1
					// WCAG AA floor rather than chosen by eye: #707070
					// measures 4.95:1. The #7C7C7C it replaced measured
					// 4.17:1.
					secondary: "#707070",
					// The resting border of every text input, select and
					// textarea. Tailwind's gray-300 (#d1d5db) measures 1.47:1
					// on white, well under the 3:1 WCAG 1.4.11 floor for the
					// boundary of a control. #8a8a8a clears 3:1 on all five
					// surfaces the portal puts a field on: white 3.45,
					// gray-50 3.30, gray-100 3.14, primary-50 3.24,
					// amber-50 3.33.
					field: "#8a8a8a",
					border: "#EDEDED",
				},
				// White text is only legible from 700 down: 500 measures 2.27:1
				// and 600 measures 3.11:1 against white, both below the 4.5:1
				// AA floor. 500/600 are for icons, borders and fills only --
				// every white-on-colour button uses 700 or darker.
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
			},
		},
	},
	plugins: [],
};
