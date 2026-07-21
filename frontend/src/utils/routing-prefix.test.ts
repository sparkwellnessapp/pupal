import { describe, it, expect } from 'vitest';
import { splitRoutingPrefix } from './routing-prefix';

describe('splitRoutingPrefix — D-4 render-only de-emphasis', () => {
    it('splits a leading heading token + separator', () => {
        expect(splitRoutingPrefix('סעיף א: כתבו פעולה', 'סעיף א')).toEqual({ prefix: 'סעיף א: ', rest: 'כתבו פעולה' });
    });
    it('handles other separators (dash / dot / paren)', () => {
        expect(splitRoutingPrefix('שאלה 1 - חשבו את הסכום', 'שאלה 1').prefix).toBe('שאלה 1 - ');
        expect(splitRoutingPrefix('סעיף ב. הוכיחו', 'סעיף ב').rest).toBe('הוכיחו');
    });
    it('no prefix when the description does not start with the heading', () => {
        expect(splitRoutingPrefix('כתבו פעולה', 'סעיף א')).toEqual({ prefix: '', rest: 'כתבו פעולה' });
    });
    it('does not match the heading mid-string', () => {
        expect(splitRoutingPrefix('ראו סעיף א למידע', 'סעיף א').prefix).toBe('');
    });
    it('never consumes the ENTIRE description (would blank the row)', () => {
        expect(splitRoutingPrefix('סעיף א:', 'סעיף א').prefix).toBe(''); // nothing left ⇒ leave verbatim
    });
    it('is a no-op on empty inputs', () => {
        expect(splitRoutingPrefix('', 'סעיף א')).toEqual({ prefix: '', rest: '' });
        expect(splitRoutingPrefix('טקסט', '')).toEqual({ prefix: '', rest: 'טקסט' });
    });
});
