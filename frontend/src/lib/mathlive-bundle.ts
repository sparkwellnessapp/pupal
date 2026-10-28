// The MathLive chunk (≈230 KB gzipped): loaded ONLY when a teacher opens a formula for
// editing (MATH_RENDERING_PLAN §4, "lazy-loaded"). Never import this file statically.
//
// Fonts travel through the bundler (`mathlive/fonts.css`), so `fontsDirectory = null`
// tells MathLive not to fetch its own; keypress sounds are off — a review screen is a
// quiet place.
//
// The element is read off the WHOLE module object, never by a named import: Next also
// compiles this module for the server, where `mathlive` resolves to its SSR build
// (converters only, no MathfieldElement), and webpack reports a named import — or a
// namespace member it can see statically — as an import error there. The module only ever
// RUNS in the browser (MathSpanEditor's effect), where the export exists.
import * as MathLive from 'mathlive';
import 'mathlive/fonts.css';

type MathfieldClass = typeof import('mathlive').MathfieldElement;

const lib: Record<string, unknown> = { ...MathLive };
const MathfieldElement = lib.MathfieldElement as MathfieldClass;
MathfieldElement.fontsDirectory = null;
MathfieldElement.soundsDirectory = null;

export { MathfieldElement };
