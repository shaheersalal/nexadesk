/** @type {import('tailwindcss').Config} */

/*
 * The neutral scale and `white` resolve to CSS variables defined in
 * src/index.css, so the 574 existing colour utilities across the dashboard
 * follow the system light/dark setting without any of them being edited.
 *
 * The <alpha-value> placeholder is what keeps Tailwind's slash-opacity syntax
 * working (bg-black/50, border-gray-200/60); it is why the variables hold raw
 * RGB triplets rather than hex.
 */
const withAlpha = (v) => `rgb(var(${v}) / <alpha-value>)`

export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  // 'media' is Tailwind's default, stated here because the whole theme depends
  // on it: the app follows the OS setting and offers no toggle, matching the
  // landing page.
  darkMode: 'media',
  theme: {
    extend: {
      colors: {
        // `white` stays literally white: text-white and bg-white/10 are used
        // throughout as white-on-a-coloured-fill, and remapping it made button
        // labels and the sidebar wordmark vanish in dark mode.
        surface: withAlpha('--c-surface'),
        // A surface that stays dark in both themes: tooltips, toasts and
        // code blocks. Deliberately not on the grey ramp — those invert.
        inverse: '#0b1020',
        // Muted text on an always-dark plane — the sidebar and anything on
        // `inverse`. The grey ramp cannot serve here: it follows the theme,
        // so on a fixed dark background it goes dark in light mode.
        'on-inverse': '#9aa5bd',
        gray: {
          50:  withAlpha('--c-gray-50'),
          100: withAlpha('--c-gray-100'),
          200: withAlpha('--c-gray-200'),
          300: withAlpha('--c-gray-300'),
          400: withAlpha('--c-gray-400'),
          500: withAlpha('--c-gray-500'),
          600: withAlpha('--c-gray-600'),
          700: withAlpha('--c-gray-700'),
          800: withAlpha('--c-gray-800'),
          900: withAlpha('--c-gray-900'),
        },
        navy: {
          50:  '#eef2ff',
          100: '#e0e7ff',
          200: '#c7d0f5',
          300: '#a3aee0',
          400: '#6b74b8',
          500: '#3d4480',
          600: withAlpha('--c-navy-600'),
          700: withAlpha('--c-navy-700'),
          800: '#0f3460',
          900: '#0a0a1a',
        },
        red: {
          50: withAlpha('--c-red-50'),
          100: withAlpha('--c-red-100'),
          200: withAlpha('--c-red-200'),
          300: withAlpha('--c-red-300'),
          400: '#f87171',
          500: '#ef4444',
          600: '#dc2626',
          700: withAlpha('--c-red-700'),
          800: withAlpha('--c-red-800'),
          900: withAlpha('--c-red-900'),
        },
        orange: {
          50: withAlpha('--c-orange-50'),
          100: withAlpha('--c-orange-100'),
          200: withAlpha('--c-orange-200'),
          300: withAlpha('--c-orange-300'),
          400: '#fb923c',
          500: '#f97316',
          600: '#ea580c',
          700: withAlpha('--c-orange-700'),
          800: withAlpha('--c-orange-800'),
          900: withAlpha('--c-orange-900'),
        },
        amber: {
          50: withAlpha('--c-amber-50'),
          100: withAlpha('--c-amber-100'),
          200: withAlpha('--c-amber-200'),
          300: withAlpha('--c-amber-300'),
          400: '#fbbf24',
          500: '#f59e0b',
          600: '#d97706',
          700: withAlpha('--c-amber-700'),
          800: withAlpha('--c-amber-800'),
          900: withAlpha('--c-amber-900'),
        },
        yellow: {
          50: withAlpha('--c-yellow-50'),
          100: withAlpha('--c-yellow-100'),
          200: withAlpha('--c-yellow-200'),
          300: withAlpha('--c-yellow-300'),
          400: '#facc15',
          500: '#eab308',
          600: '#ca8a04',
          700: withAlpha('--c-yellow-700'),
          800: withAlpha('--c-yellow-800'),
          900: withAlpha('--c-yellow-900'),
        },
        green: {
          50: withAlpha('--c-green-50'),
          100: withAlpha('--c-green-100'),
          200: withAlpha('--c-green-200'),
          300: withAlpha('--c-green-300'),
          400: '#4ade80',
          500: '#22c55e',
          600: '#16a34a',
          700: withAlpha('--c-green-700'),
          800: withAlpha('--c-green-800'),
          900: withAlpha('--c-green-900'),
        },
        emerald: {
          50: withAlpha('--c-emerald-50'),
          100: withAlpha('--c-emerald-100'),
          200: withAlpha('--c-emerald-200'),
          300: withAlpha('--c-emerald-300'),
          400: '#34d399',
          500: '#10b981',
          600: '#059669',
          700: withAlpha('--c-emerald-700'),
          800: withAlpha('--c-emerald-800'),
          900: withAlpha('--c-emerald-900'),
        },
        teal: {
          50: withAlpha('--c-teal-50'),
          100: withAlpha('--c-teal-100'),
          200: withAlpha('--c-teal-200'),
          300: withAlpha('--c-teal-300'),
          400: '#2dd4bf',
          500: '#14b8a6',
          600: '#0d9488',
          700: withAlpha('--c-teal-700'),
          800: withAlpha('--c-teal-800'),
          900: withAlpha('--c-teal-900'),
        },
        blue: {
          50: withAlpha('--c-blue-50'),
          100: withAlpha('--c-blue-100'),
          200: withAlpha('--c-blue-200'),
          300: withAlpha('--c-blue-300'),
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: withAlpha('--c-blue-700'),
          800: withAlpha('--c-blue-800'),
          900: withAlpha('--c-blue-900'),
        },
        purple: {
          50: withAlpha('--c-purple-50'),
          100: withAlpha('--c-purple-100'),
          200: withAlpha('--c-purple-200'),
          300: withAlpha('--c-purple-300'),
          400: '#c084fc',
          500: '#a855f7',
          600: '#9333ea',
          700: withAlpha('--c-purple-700'),
          800: withAlpha('--c-purple-800'),
          900: withAlpha('--c-purple-900'),
        },
        accent: {
          DEFAULT: withAlpha('--c-accent-cta'),
          dark:    '#a85728',
          light:   withAlpha('--c-accent-soft'),
          // accent TEXT — holds AA on surfaces in both themes, unlike the
          // CTA fill above, which is tuned for white labels sitting on it.
          ink:     withAlpha('--c-accent'),
          'ink-h': withAlpha('--c-accent-ink-h'),
        },
      },
      fontFamily: {
        sans: ['"DM Sans"', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
