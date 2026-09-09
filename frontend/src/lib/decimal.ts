/**
 * The subset of Python's `decimal` that the pricing mirror needs — exactly
 * that subset, and no library.
 *
 * WHY THIS EXISTS. `utils/rubric-achievable.ts` documents that plain `number`
 * is safe for teacher point values, and it is: that function sums declared
 * totals and compares against a tolerance. This one is different in kind. It
 * produces the STRING a teacher reads beside a check and the server freezes
 * into an immutable contract, and the §1.7 parity vectors are byte-exact
 * `str(Decimal)` output. `"5.0"`, `"4.00"` and `"0"` in that file are the same
 * arithmetic at the same precision (0.25) with three different IDEAL
 * EXPONENTS — a mirror that renders `4` where the wire says `4.00`, or that
 * lets a float turn 0.1+0.2 into 0.30000000000000004, is the selection-scoring
 * incident in miniature (CLAUDE.md §5: two places deriving one number, drifting).
 *
 * A value is `coefficient × 10^exponent`, coefficient signed, exactly as
 * CPython models it. Every rule below was PROBED against CPython rather than
 * reasoned about; the probes are the test file.
 *
 * @see backend/app/services/pricing.py — the arithmetic this serves
 * @see decimal.test.ts — the CPython-probed expectations
 */

export interface Dec {
    /** Signed coefficient. */
    readonly c: bigint;
    /** Power of ten. May be positive (Decimal('2E+1') is coefficient 2, exponent 1). */
    readonly e: number;
}

const TEN = 10n;

function pow10(n: number): bigint {
    return TEN ** BigInt(n);
}

/** Parse `str(Decimal)` output: plain (`-0.75`) or scientific (`2E+1`). */
export function dec(value: string | number | Dec): Dec {
    if (typeof value === 'object') return value;
    const text = String(value).trim();
    const m = /^([+-]?)(\d*)(?:\.(\d*))?(?:[eE]([+-]?\d+))?$/.exec(text);
    if (!m || (m[2] === '' && (m[3] ?? '') === '')) {
        throw new Error(`decimal: cannot parse ${JSON.stringify(text)}`);
    }
    const [, sign, intPart, fracPart = '', expPart] = m;
    const digits = `${intPart}${fracPart}` || '0';
    const c = BigInt(digits) * (sign === '-' ? -1n : 1n);
    const e = (expPart ? parseInt(expPart, 10) : 0) - fracPart.length;
    return { c, e };
}

/** Rescale to a (smaller or equal) exponent without changing the value. */
function at(a: Dec, e: number): bigint {
    if (e > a.e) throw new Error('decimal: rescale would lose digits');
    return a.c * pow10(a.e - e);
}

/** Decimal addition takes the MINIMUM exponent. */
export function add(a: Dec, b: Dec): Dec {
    const e = Math.min(a.e, b.e);
    return { c: at(a, e) + at(b, e), e };
}

export function sub(a: Dec, b: Dec): Dec {
    const e = Math.min(a.e, b.e);
    return { c: at(a, e) - at(b, e), e };
}

/** Decimal multiplication ADDS exponents — this is what makes `n × 0.25`
 *  render as `4.00` and `2E+1 × 0.25` render as `5.0`. */
export function mul(a: Dec, b: Dec): Dec {
    return { c: a.c * b.c, e: a.e + b.e };
}

/**
 * Exact division, with CPython's ideal-exponent rule: the result carries the
 * ideal exponent `a.e - b.e` when the coefficient allows, otherwise the
 * fewest digits that represent the quotient exactly.
 *
 * A non-terminating quotient THROWS rather than rounding to 28 significant
 * digits. The pricer only ever divides by a precision grid (0.25, 0.5, 0.1),
 * so a non-terminating result means the inputs are not what this mirror
 * assumes — and a silent rounding there would be a number nobody could
 * account for.
 */
export function divideExact(a: Dec, b: Dec): Dec {
    if (b.c === 0n) throw new Error('decimal: division by zero');
    const ideal = a.e - b.e;
    if (a.c === 0n) return { c: 0n, e: ideal };

    // Find the fewest extra decimal places that make the quotient an integer.
    const LIMIT = 40;
    for (let k = 0; k <= LIMIT; k += 1) {
        const numerator = a.c * pow10(k);
        if (numerator % b.c === 0n) {
            let c = numerator / b.c;
            let e = ideal - k;
            // Reduce toward the ideal exponent (no-op for minimal k, kept
            // because the rule — not the shortcut — is the contract).
            while (e < ideal && c % TEN === 0n) {
                c /= TEN;
                e += 1;
            }
            return { c, e };
        }
    }
    throw new Error(
        `decimal: non-terminating quotient ${toString(a)} / ${toString(b)} — ` +
        'the pricer only divides by a precision grid, so this is bad input',
    );
}

/**
 * `a / b` under Python's DEFAULT context — the one place the pricer divides by
 * something other than the grid: a counted check's `points × units / unit_count`
 * (PLAN COMPILER v2, C3), e.g. 12 × 15 / 17 = 10.58823529411764705882352941.
 *
 * Exact when the quotient terminates (`divideExact`); otherwise 28 significant
 * digits, ROUND_HALF_EVEN — CPython's `getcontext()` defaults, which is what
 * `pricing.py` runs under. The 28-digit string is what the backend's `raw`
 * carries, so it must be reproduced digit for digit, not "close enough".
 * Probed against CPython in decimal.test.ts.
 */
export function divideContext(a: Dec, b: Dec): Dec {
    if (b.c === 0n) throw new Error('decimal: division by zero');
    try {
        return divideExact(a, b);
    } catch {
        // non-terminating: fall through to the context division
    }
    const PREC = 28;
    const neg = (a.c < 0n) !== (b.c < 0n);
    const A = a.c < 0n ? -a.c : a.c;
    const B = b.c < 0n ? -b.c : b.c;
    const digits = (x: bigint) => x.toString().length;
    let k = PREC + digits(B) - digits(A) + 1;
    if (k < 0) k = 0;
    const num = A * pow10(k);
    const q = num / B;
    const r = num % B;
    const d = digits(q) - PREC;                 // ≥ 1 by construction of k
    if (d <= 0) return { c: neg ? -q : q, e: a.e - b.e - k };
    const div = pow10(d);
    const tail = q % div;
    let head = q / div;
    const twice = tail * 2n;
    if (twice > div || (twice === div && r > 0n)) {
        head += 1n;
    } else if (twice === div && r === 0n && head % 2n === 1n) {
        head += 1n;                             // the tie: to even
    }
    return { c: neg ? -head : head, e: a.e - b.e - k + d };
}

/**
 * `Decimal.to_integral_value(rounding=ROUND_HALF_UP)`.
 *
 * HALF_UP is away from zero (2.5 → 3, −2.5 → −3), NOT banker's rounding — the
 * pricer passes the flag explicitly and the difference is a real point.
 * A non-negative exponent is already integral and is returned untouched,
 * exponent and all (that is how `0E+2` survives to render as `0`).
 */
export function toIntegralValueHalfUp(a: Dec): Dec {
    if (a.e >= 0) return a;
    const scale = pow10(-a.e);
    const negative = a.c < 0n;
    const magnitude = negative ? -a.c : a.c;
    const quotient = magnitude / scale;
    const remainder = magnitude % scale;
    const rounded = remainder * 2n >= scale ? quotient + 1n : quotient;
    return { c: negative ? -rounded : rounded, e: 0 };
}

/** −1 / 0 / 1. Numeric comparison — `5` and `5.00` compare equal. */
export function cmp(a: Dec, b: Dec): number {
    const e = Math.min(a.e, b.e);
    const x = at(a, e);
    const y = at(b, e);
    return x === y ? 0 : x < y ? -1 : 1;
}

/**
 * CPython's `min(a, b)` / `max(a, b)`: the FIRST argument wins a tie.
 *
 * Load-bearing, not pedantry. `_snap`'s `max(lo, min(value, hi))` returns the
 * literal `Decimal("0")` on a zero award, and that argument's exponent is what
 * makes the vector say `"0"` instead of `"0.00"`.
 */
export function pyMin(a: Dec, b: Dec): Dec {
    return cmp(b, a) < 0 ? b : a;
}

export function pyMax(a: Dec, b: Dec): Dec {
    return cmp(b, a) > 0 ? b : a;
}

/** CPython's `str(Decimal)` (the to-scientific-string conversion). */
export function toString(a: Dec): string {
    const negative = a.c < 0n;
    const digits = (negative ? -a.c : a.c).toString();
    const adjusted = a.e + digits.length - 1;
    const sign = negative ? '-' : '';

    if (a.e <= 0 && adjusted >= -6) {
        if (a.e === 0) return `${sign}${digits}`;
        const pointAt = digits.length + a.e;
        if (pointAt > 0) {
            return `${sign}${digits.slice(0, pointAt)}.${digits.slice(pointAt)}`;
        }
        return `${sign}0.${'0'.repeat(-pointAt)}${digits}`;
    }

    const head = digits.slice(0, 1);
    const tail = digits.slice(1);
    const mantissa = tail ? `${head}.${tail}` : head;
    const exponent = adjusted >= 0 ? `+${adjusted}` : `${adjusted}`;
    return `${sign}${mantissa}E${exponent}`;
}
