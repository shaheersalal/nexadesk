/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          50:  '#eef2ff',
          100: '#e0e7ff',
          200: '#c7d0f5',
          300: '#a3aee0',
          400: '#6b74b8',
          500: '#3d4480',
          600: '#1a1a2e',
          700: '#16213e',
          800: '#0f3460',
          900: '#0a0a1a',
        },
        accent: {
          DEFAULT: '#e8a87c',
          dark:    '#d4925f',
          light:   '#f5c9a0',
        },
      },
      fontFamily: {
        sans: ['"DM Sans"', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
