// The KaTeX chunk: the library and its stylesheet travel together, and ONLY through
// `loadKatex()`'s dynamic import (lib/katex.ts) — never import this file statically.
import katex from 'katex';
import 'katex/dist/katex.min.css';

export default katex;
