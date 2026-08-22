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
        rail: '13rem',       // 208px outline rail (3 indent levels + label + points)
      },
      screens: {
        rail: '1100px',      // the rail appears at/above this width (else it collapses)
        // P3/D11 — the mockup's own review breakpoint: below it the review
        // module yields to the honest mobile interstitial; the kbd legend
        // keys off it too. CSS-only (logged decision 4).
        desk: '941px',
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
        },
        // Batch-redesign tokens (P2/F8) — transcribed from the approved
        // mockup's :root palette (vivi-batch-redesign-mockup.html). Scoped
        // under `batch` so nothing collides with the rubric surfaces; the
        // batch dashboard/review/list/upload consume ONLY these + primary.
        batch: {
          paper: '#FBFAF7',
          ink: '#1B2733',
          muted: '#6E7B89',
          faint: '#9AA6B2',
          line: '#E9E4D9',
          'line-soft': '#F1EDE4',
          'teal-soft': '#E4F6F2',
          'teal-ink': '#0B6B62',
          'teal-deep': '#0E8F84',
          amber: '#D97706',
          'amber-soft': '#FDF3E3',
          'amber-ink': '#92580A',
          'amber-line': '#F3DDBB',
          blue: '#3B82F6',
          'blue-soft': '#EDF3FE',
          'blue-ink': '#2456B0',
          green: '#0E9F6E',
          'green-soft': '#E8F6EF',
          'green-ink': '#0B7A55',
          red: '#DC2626',
          'red-soft': '#FCEDED',
          'red-ink': '#A31D1D',
          'red-line': '#F2CBCB',
          // Honesty-bar segment hues (D2; approved reuses batch.green).
          'seg-clean': '#7FD9CC',
          'seg-eyes': '#F0B24E',
          'seg-moving': '#8DB4F5',
          'seg-failed': '#E88A8A',
        },
      },
      borderRadius: {
        zone: '14px',       // mockup --r
        'zone-sm': '9px',   // mockup --r-sm
      },
      boxShadow: {
        zone: '0 1px 2px rgba(27,39,51,.05), 0 6px 20px -12px rgba(27,39,51,.12)',
      },
      fontFamily: {
        sans: ['Rubik', 'system-ui', 'sans-serif'],
        mono: ['Fira Code', 'monospace'],
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'pulse-soft': 'pulseSoft 2s infinite',
        // Batch redesign (P2): render via `motion-safe:` variants ONLY, so
        // prefers-reduced-motion kills them (the mockup's own media rule).
        shimmer: 'shimmer 1.7s linear infinite',
        'check-pop': 'checkPop 0.45s cubic-bezier(.2,1.6,.4,1)',
        // P3/R1 — anchor feedback (motion-safe: only).
        'anchor-pulse': 'anchorPulse 1.2s ease-out',
        shake: 'shake 0.4s ease-in-out',
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
        shimmer: {
          from: { backgroundPosition: '200% 0' },
          to: { backgroundPosition: '-200% 0' },
        },
        checkPop: {
          from: { transform: 'scale(.4)', opacity: '0' },
        },
        anchorPulse: {
          '0%': { boxShadow: '0 0 0 0 rgba(217,119,6,.45)' },
          '100%': { boxShadow: '0 0 0 12px rgba(217,119,6,0)' },
        },
        shake: {
          '0%, 100%': { transform: 'translateX(0)' },
          '25%': { transform: 'translateX(3px)' },
          '75%': { transform: 'translateX(-3px)' },
        },
      },
    },
  },
  plugins: [],
}
export default config
