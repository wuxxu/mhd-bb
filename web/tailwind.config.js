/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Banská Bystrica heraldic palette: deep red shield, silver tower, black anvil.
        bb: {
          red: {
            50: "#fef3f2",
            100: "#fde4e2",
            200: "#fbcdc9",
            300: "#f7a8a1",
            400: "#f17c70",
            500: "#e54e3f",
            600: "#c8102e", // primary heraldic red
            700: "#a50c26",
            800: "#7a0a1e",
            900: "#560716"
          },
          gold: {
            400: "#e6b54a",
            500: "#d4a017"
          },
          cream: "#fbf6ee",
          charcoal: "#1c1917"
        }
      },
      fontFamily: {
        sans: [
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif"
        ]
      },
      boxShadow: {
        tile: "0 1px 2px rgba(28, 25, 23, 0.06), 0 4px 12px -2px rgba(28, 25, 23, 0.05)",
        "tile-active": "0 1px 2px rgba(28, 25, 23, 0.1), 0 8px 18px -4px rgba(200, 16, 46, 0.18)"
      }
    }
  },
  plugins: []
};
