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
        review: '1180px',    // the grade-review content column (mockup)
        modal: '520px',      // the mockup's own modal width
        // F3: the returned exam's page. One A4 at the mockup's own size; the
        // aspect (1/1.41) does the rest, so this is the ONLY page dimension.
        page: '660px',
        tip: '300px',        // the (i) explainer's width (mockup `.tip`)
      },
      /**
       * Grade-review measurements (S12/F0, extended in F2). Every one is a
       * value the mockup states; naming them is what lets `check:tokens` stay
       * BLOCKING on this surface instead of printing a list nobody acts on.
       */
      spacing: {
        dot: '7px',          // the marker dot
        verdict: '30px',     // the verdict control
        tariff: '52px',      // the points column — one rule down the page
        'focus-rail': '3px', // the focused row's edge
        'nav-btn': '112px',  // prev/next, so they cannot jitter in width
        total: '130px',      // the total column
        'mini-thumb': '47px',
        'scope-nav': '132px', // the nav's sticky offset
        'answer-max': '340px',
        'fb-min': '54px',
        gutter: '22px',      // the code island's line-number gutter
        // ── F3 · the returned exam (mockup `.pv`, `.pg`, `.appxdoc`) ──────
        'appx-x': '54px',    // the feedback page's side margin
        'appx-top': '46px',  // …and its head margin
        'appx-foot': '18px', // the footer's distance from the page edge
        'strip-gap': '9px',  // between page thumbnails
        'strip-thumb': '60px', // a thumbnail below `md`, where the rail wraps
        'info-i': '17px',    // the (i) circle
        'tip-nudge': '-8px', // the explainer's start offset under the (i)
      },
      scrollMargin: {
        scope: '150px',      // clears the sticky top bar on a jump
      },
      borderWidth: {
        hairline: '1.5px',   // the verdict ring while Vivi proposes
        decided: '2.2px',    // …and once the teacher has decided
      },
      ringWidth: {
        decided: '3px',
      },
      textUnderlineOffset: {
        link: '3px',
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

        // Grade review (S12/F0) — one token per role in the mockup, so F1–F3
        // never reach for text-[21px]. Numerals render tabular (§0.3).
        'gr-h1':     ['25px', { lineHeight: '1.2', fontWeight: '600' }],
        'gr-h2':     ['21px', { lineHeight: '1.25', fontWeight: '600' }],
        'gr-name':   ['20px', { lineHeight: '1.2', fontWeight: '600' }],
        'gr-total':  ['34px', { lineHeight: '1', fontWeight: '300' }],
        'gr-score':  ['28px', { lineHeight: '1', fontWeight: '300' }],
        'gr-pts':    ['24px', { lineHeight: '1', fontWeight: '300' }],
        'gr-body':   ['14px', { lineHeight: '1.5' }],
        'gr-prose':  ['14.5px', { lineHeight: '1.75' }],
        'gr-answer': ['13px', { lineHeight: '1.7' }],
        'gr-meta':   ['12.5px', { lineHeight: '1.4' }],
        'gr-chip':   ['11.5px', { lineHeight: '1.6' }],
        'gr-label':  ['12px', { lineHeight: '1.4' }],
        'gr-sm':     ['11px', { lineHeight: '1.4' }],
        'gr-crit':   ['16px', { lineHeight: '1' }],
        'gr-rtl':    ['13.5px', { lineHeight: '1.7' }],
        'gr-arrow':  ['18px', { lineHeight: '1' }],
        'gr-quote':  ['17px', { lineHeight: '0' }],
        // ── F3 · the returned exam ───────────────────────────────────────
        'gr-pv-h1':  ['23px', { lineHeight: '1.2', fontWeight: '600' }],
        'gr-appx-h': ['18px', { lineHeight: '1.2', fontWeight: '600' }],
        // The grade on the feedback page — the one number a student looks for.
        'gr-appx-total': ['36px', { lineHeight: '1' }],
        'gr-appx-q': ['14px', { lineHeight: '1.4', fontWeight: '600' }],
        'gr-num':    ['15px', { lineHeight: '1' }],
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
        // Grade-review tokens (S12/F0) — transcribed from the approved mockup's
        // :root (vivi-grade-review-mockup-v2.html) and normalized against
        // globals.css + the home screen, exactly as `batch` was.
        //
        // WHAT IS NOT HERE, DELIBERATELY: teal. The mockup's --teal / --teal-700
        // / --teal-100 / --teal-50 are BYTE-IDENTICAL to primary.600 / .700 /
        // .100 / .50, which the home screen already uses. Re-declaring them
        // under `grade` would be a second home for one palette (§0.4), and the
        // two copies would drift the first time anyone re-themes. Actions,
        // "met", the evidence highlight and the active state all use `primary`.
        // The one teal value the ramp lacks is the hairline these chips and
        // banners draw, so only THAT lands here.
        //
        // The ink grammar (§0.3) made literal: grade.pencil* = "Vivi proposes",
        // grade.red = "the teacher decided", and nothing else is ever red.
        grade: {
          canvas: '#FFFAF2',      // == globals.css --background
          bar: '#FBF9F3',
          card: '#FFFFFF',
          paper: '#FFFDF8',       // a page of the student's scan

          ink: '#1F2937',
          'ink-2': '#4B5563',
          pencil: '#6B7280',      // Vivi's proposal — never the teacher's mark
          'pencil-2': '#9CA3AF',
          line: '#E8E4DC',
          'line-2': '#F1EEE7',
          'teal-line': '#99E6D8', // the hairline primary.100 cannot draw

          violet: '#7C3AED',      // partial verdict; audit marks (audit is v2)
          'violet-100': '#EEE4FD',
          'violet-50': '#F7F2FE',
          'violet-line': '#DCCBFB',
          'violet-ink': '#4C1D95',

          red: '#C8102E',         // teacher red: overrides, the total, the stamp
          'red-100': '#FDE8EA',
          'red-line': '#F5C2C8',

          amber: '#B45309',       // "לבדוק", stale
          'amber-100': '#FEF3C7',
          'amber-200': '#FDE68A',
          'amber-50': '#FFFBEB',
          'amber-dot': '#D97706',
          'amber-ink': '#78350F',
        },
      },
      borderRadius: {
        zone: '14px',       // mockup --r
        'zone-sm': '9px',   // mockup --r-sm
        // Grade review (§0.3): 16 cards / 12 controls / 10 small.
        grade: '16px',
        'grade-ctl': '12px',
        'grade-sm': '10px',
        mark: '3px',        // the evidence highlight's corner
        modal: '18px',      // the mockup's modal corner
      },
      blur: {
        scrim: '1px',      // the card score's contrast scrim
      },
      boxShadow: {
        zone: '0 1px 2px rgba(27,39,51,.05), 0 6px 20px -12px rgba(27,39,51,.12)',
        grade: '0 1px 2px rgba(31,41,55,.04), 0 12px 32px -20px rgba(31,41,55,.25)',
      },
      fontFamily: {
        // OD-F1 ruled 2026-08-31: Assistant is the app face. Moves in lockstep
        // with `body` in globals.css — see the note there.
        sans: ['Assistant', 'system-ui', 'sans-serif'],
        mono: ['Fira Code', 'monospace'],
        // Kept as an explicit alias of `sans` now that OD-F1 is ruled: a
        // surface that means "the app face" can say so, and the grade-review
        // components already read this token.
        assistant: ['Assistant', 'system-ui', 'sans-serif'],
        // Caveat. Two uses, and both are THE GRADE written by the teacher:
        // inside the stamp SVG, and the total on the returned exam's feedback
        // page (mockup `.appxdoc .hd .tot`). Nothing else takes this face —
        // it marks what a pen wrote, not what the product typed.
        hand: ['Caveat', 'cursive'],
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
        // Grade review (S12/F0). `motion-safe:` variants ONLY, like the batch
        // set above — prefers-reduced-motion must kill all three.
        'stamp-press': 'stampPress 0.26s cubic-bezier(.2,.9,.3,1.2)',
        'step-pulse': 'stepPulse 1.8s ease-in-out infinite',
        'pencil-line': 'pencilLine 1.4s ease-in-out infinite',
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
        // The stamp comes DOWN on approval. It carries no rotation: StampSvg
        // owns the −7° internally, so an animation that re-stated it would be
        // the second geometry `stamp-svg-single-source` exists to forbid.
        stampPress: {
          '0%': { transform: 'scale(1.25)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
        stepPulse: {
          '0%, 100%': { transform: 'scale(1)' },
          '50%': { transform: 'scale(1.5)' },
        },
        // The "Vivi is marking this one" pencil stroke on a grading card.
        pencilLine: {
          '0%': { transform: 'scaleX(.2)' },
          '60%': { transform: 'scaleX(1)' },
          '100%': { transform: 'scaleX(.2)' },
        },
      },
    },
  },
  plugins: [],
}
export default config
