/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['"IBM Plex Mono"', 'monospace'],
        sans: ['"DM Sans"', 'sans-serif'],
      },
      colors: {
        navy: '#1a1a2e',
        paper: '#f4f1ec',
        accent: '#e63946',
        verde: '#22c55e',
        giallo: '#f59e0b',
        rosso: '#ef4444',
      },
    },
  },
  plugins: [],
}
