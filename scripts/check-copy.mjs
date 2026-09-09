#!/usr/bin/env node
/**
 * §4.5 copy gates (P5) — the first EXECUTABLE version. Until now "grep gate"
 * meant a convention nobody could run; F3's guarantee rested on reviewer
 * memory. This script is the guarantee.
 *
 * Gates (each reports hits; only BLOCKING ones fail the build):
 *   1. BLOCKING  `אצווה` anywhere in src/ (OD4: מקבץ, never אצווה) — including
 *                inside the copy module itself, which shipped a violation.
 *   2. BLOCKING  raw batch-status enums rendered as user-visible TEXT.
 *   3. BLOCKING  file sizes printed without a dir="ltr" island (§3.1) — the
 *                `KB` form and bare `.toFixed(n) MB` arithmetic in JSX.
 *   4. REPORT    masculine imperatives (OD5). Scoped BLOCKING to the five
 *                batch surfaces; elsewhere it prints inherited debt with
 *                provenance rather than failing a sweep that never touched it
 *                (owner ruling, P4 review).
 *
 * Anchoring matters: the naive wordlist matches inside נבחר / לאשר / תיצור.
 * Every pattern below requires a word boundary (start-of-string or a
 * non-Hebrew-letter before the verb), which is what makes the gate credible
 * instead of noisy.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

// fileURLToPath, not URL.pathname — the repo path contains a space and
// pathname hands back a percent-encoded string.
const ROOT = fileURLToPath(new URL('..', import.meta.url))
const SRC = join(ROOT, 'src')

/** The five batch surfaces (§2) — where OD5 is BLOCKING. */
const BATCH_SURFACES = [
  join('src', 'app', 'batches'),
  join('src', 'components', 'batch'),
  join('src', 'components', 'batch-review'),
  join('src', 'copy'),
  join('src', 'utils', 'batch-'),
]

/**
 * The grade-review surfaces (S12, PR spec §6: "check:copy extended to these
 * three routes"). Two of the three already sit under src/app/batches and are
 * therefore covered above; these are the rest. Added at F0, while they are
 * still empty — a gate switched on before the first string is a guarantee,
 * one switched on afterwards is an inventory of debt.
 */
const GRADE_REVIEW_SURFACES = [
  join('src', 'app', 'graded-tests'),
  join('src', 'components', 'grade-review'),
]

/**
 * Onboarding. Gated from its FIRST string, like the grade-review surfaces
 * above: a gate switched on before the copy exists is a guarantee, one switched
 * on afterwards is an inventory of debt. It is also the first screen a teacher
 * ever reads, so masculine-imperative debt here would be the product's opening
 * sentence about who it thinks she is.
 */
const ONBOARDING_SURFACES = [
  join('src', 'app', 'onboarding'),
  join('src', 'components', 'onboarding'),
  join('src', 'components', 'OnboardingGate'),
]

/**
 * Auth (024). Gated from its first string, like onboarding: sign-in and sign-up
 * are the two screens EVERY teacher reads, including the ones who never get
 * further, so masculine-imperative debt here is the product's first sentence
 * about who it thinks she is.
 */
const AUTH_SURFACES = [
  join('src', 'app', 'login'),
  join('src', 'app', 'signup'),
  join('src', 'components', 'auth'),
  join('src', 'copy', 'auth'),
]

const BLOCKING_SURFACES = [
  ...BATCH_SURFACES,
  ...GRADE_REVIEW_SURFACES,
  ...ONBOARDING_SURFACES,
  ...AUTH_SURFACES,
]

const SKIP_DIRS = new Set(['node_modules', '.next', 'dist'])
const isTest = (p) => /\.test\.[tj]sx?$/.test(p) || p.includes(`${sep}__tests__${sep}`)

function walk(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    if (SKIP_DIRS.has(entry)) continue
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) walk(full, out)
    else if (/\.[tj]sx?$/.test(full) && !isTest(full)) out.push(full)
  }
  return out
}

const files = walk(SRC)
const onGatedSurface = (rel) => BLOCKING_SURFACES.some((s) => rel.startsWith(s))

/**
 * Comments are NOT UI, and this codebase documents its own copy laws in
 * Hebrew ("OD4: מקבץ, never אצווה") — a gate that flags its own rulebook is
 * noise. Strips block comments (with cross-line state) and trailing `//`,
 * the latter only when the slashes sit outside a string literal so a URL
 * survives. Returns '' for a line that is entirely comment.
 */
function makeCommentStripper() {
  let inBlock = false
  return (line) => {
    let out = ''
    let i = 0
    let quote = null
    while (i < line.length) {
      const c = line[i]
      const next = line[i + 1]
      if (inBlock) {
        if (c === '*' && next === '/') { inBlock = false; i += 2; continue }
        i += 1
        continue
      }
      if (quote) {
        out += c
        if (c === quote && line[i - 1] !== '\\') quote = null
        i += 1
        continue
      }
      if (c === '"' || c === "'" || c === '`') { quote = c; out += c; i += 1; continue }
      if (c === '/' && next === '*') { inBlock = true; i += 2; continue }
      if (c === '/' && next === '/') break          // trailing line comment
      out += c
      i += 1
    }
    return out
  }
}

// A Hebrew letter immediately before the verb means it's a different word
// (נבחר, לאשר, תיצור) — require a non-letter or line start.
const HEB = '\\u0590-\\u05FF'
const imperative = (verb) => new RegExp(`(^|[^${HEB}])${verb}(?=[^${HEB}]|$)`, 'u')

const MASCULINE = [
  ['נסה שוב', 'נסי שוב'],
  ['בחר', 'בחרי'],
  ['העלה', 'העלי'],
  ['גרור', 'גררי'],
  ['לחץ', 'לחצי'],
  ['צור', 'צרי'],
  ['אשר', 'אשרי'],
  ['פתח', 'פתחי'],
  ['רענן', 'רענני'],
  ['חזור', 'חזרי'],
]

const STATUS_ENUMS = ['in_progress', 'partially_completed']

const findings = { batchWord: [], statusText: [], sizes: [], masculineBlocking: [], masculineDebt: [] }

for (const file of files) {
  const rel = relative(ROOT, file)
  const strip = makeCommentStripper()
  const lines = readFileSync(file, 'utf8').split(/\r?\n/)
  lines.forEach((raw, i) => {
    const at = `${rel}:${i + 1}`
    const line = strip(raw)          // comments are not UI
    const code = line.trim()
    if (code === '') return

    if (/אצווה|אצוות/u.test(line)) findings.batchWord.push([at, code])

    // Enum as TEXT: inside a JSX text node or a template literal, not a key
    // (`in_progress:`) and not a comparison (`=== 'in_progress'`).
    for (const e of STATUS_ENUMS) {
      const asText = new RegExp(`(>\\s*|\`[^\`]*)${e}`)
      if (asText.test(line) && !new RegExp(`${e}\\s*:`).test(line) && !line.includes(`'${e}'`)) {
        findings.statusText.push([at, code])
      }
    }

    if (/\bKB\b/.test(line)) findings.sizes.push([at, code])
    if (/\/\s*1024\s*\/\s*1024/.test(line) && !line.includes('formatMB')) {
      findings.sizes.push([at, code])
    }

    for (const [masc, fem] of MASCULINE) {
      // src/data is DATA, not UI: the Ministry school export contains
      // «מתי"א זבולון-אשר», whose city name matches the `אשר` imperative. A gate
      // that permanently reports a school's name as a copy violation trains
      // exactly the dismissal reflex this gate exists to prevent.
      if (rel.startsWith(join('src', 'data'))) continue
      if (imperative(masc).test(line) && /["'`>]/.test(line)) {
        const entry = [at, `${code}   → ${fem}`]
        if (onGatedSurface(rel)) findings.masculineBlocking.push(entry)
        else findings.masculineDebt.push(entry)
      }
    }
  })
}

const show = (title, hits) => {
  console.log(`\n${title}: ${hits.length}`)
  for (const [at, code] of hits) console.log(`  ${at}  ${code.slice(0, 120)}`)
}

show('1. אצווה (OD4) [BLOCKING]', findings.batchWord)
show('2. raw status enum as text (F3) [BLOCKING]', findings.statusText)
show('3. un-isolated file sizes (§3.1) [BLOCKING]', findings.sizes)
show('4a. masculine imperatives on batch + grade-review surfaces (OD5) [BLOCKING]', findings.masculineBlocking)
show('4b. masculine imperatives elsewhere — INHERITED DEBT (reported, not blocking)', findings.masculineDebt)

const blocking = findings.batchWord.length + findings.statusText.length
  + findings.sizes.length + findings.masculineBlocking.length
console.log(`\n${blocking === 0 ? 'COPY GATES PASS' : `COPY GATES FAIL — ${blocking} blocking hit(s)`}`)
process.exit(blocking === 0 ? 0 : 1)
