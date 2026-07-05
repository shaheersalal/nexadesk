/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/**/*.{js,jsx}', './components/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        accent: '#1e3a5f',
        'accent-light': '#2a5080',
      },
    },
  },
  plugins: [],
}
