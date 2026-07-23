import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      // Design Recovery §1a — hardened layout tokens (no raw values in components).
      maxWidth: {
        document: '52rem',   // the mirror's content column
      },
      width: {
        rail: '10rem',       // 160px outline rail
      },
      screens: {
        rail: '1100px',      // the rail appears at/above this width (else it collapses)
      },
      // §1a type scale (Rubik). One token per role — used only on the mirror surface.
      fontSize: {
        'doc-title': ['28px', { lineHeight: '1.25', fontWeight: '600' }],
        'doc-q':     ['20px', { lineHeight: '1.3', fontWeight: '600' }],
        'doc-sq':    ['17px', { lineHeight: '1.35', fontWeight: '600' }],
        'doc-body':  ['16px', { lineHeight: '1.7' }],
        'doc-table': ['15px', { lineHeight: '1.5' }],
        'doc-meta':  ['13px', { lineHeight: '1.4' }],
      },
      colors: {
        // Turquoise-focused palette for Pupil
        primary: {
          50: '#f0fdfa',
          100: '#ccfbf1',
          200: '#99f6e4',
          300: '#5eead4',
          400: '#2dd4bf',
          500: '#14b8a6',
          600: '#0d9488',
          700: '#0f766e',
          800: '#115e59',
          900: '#134e4a',
        },
        accent: {
          50: '#fef7ee',
          100: '#fdedd6',
          200: '#f9d7ad',
          300: '#f5bb78',
          400: '#f09442',
          500: '#ec751d',
          600: '#dd5a13',
          700: '#b74312',
          800: '#923617',
          900: '#762f16',
        },
        surface: {
          50: '#fafafa',
          100: '#f5f5f4',
          200: '#e7e5e4',
          300: '#d6d3d1',
        }
      },
      fontFamily: {
        sans: ['Rubik', 'system-ui', 'sans-serif'],
        mono: ['Fira Code', 'monospace'],
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'pulse-soft': 'pulseSoft 2s infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.7' },
        },
      },
    },
  },
  plugins: [],
}
export default config
