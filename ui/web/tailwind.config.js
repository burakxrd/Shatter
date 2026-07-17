/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./**/*.{html,js}"],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bgPrimary: '#0a0a0a',
        bgCard: '#171717',
        bgCardHover: '#1c1c1c',
        borderSubtle: 'rgba(255, 255, 255, 0.05)',
        textPrimary: '#e2e8f0',
        textDim: '#94a3b8',
        accent: '#f97316',
        accentHover: '#ea580c',
        danger: '#ef4444',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      }
    }
  },
  plugins: [],
}
