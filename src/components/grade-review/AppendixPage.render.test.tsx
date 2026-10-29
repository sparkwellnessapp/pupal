import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { renderToStaticMarkup } from 'react-dom/server';

import { AppendixPage } from './AppendixPage';
import { APPENDIX_SCOPE_ORDER, type Appendix } from '@/utils/returned-exam';

/**
 * The preview prints a scope's blocks in the order the PDF prints them —
 * points, feedback, her notes, breakdown (owner-ruled 2026-10-26). Both sides
 * read the SAME fixture, so neither can drift alone again.
 */

const FIXTURE = join(process.cwd(), '..', 'backend', 'tests', 'fixtures', 'appendix_scope_order.json');

const APPENDIX: Appendix = {
    total: '7', possible: '9', summary: null,
    scopes: [{
        scopeId: 'q1', title: 'שאלה 1', awarded: '7', possible: '9',
        feedback: 'alpha feedback',
        notes: [{ criterion: 'beta', text: 'note' }],
        criteria: [{ description: 'gamma criterion', awarded: '1', possible: '2' }],
    }],
};

describe('appendix scope order', () => {
    it('is the order pinned for both renderers', () => {
        const pinned = JSON.parse(readFileSync(FIXTURE, 'utf-8')).order;
        expect([...APPENDIX_SCOPE_ORDER]).toEqual(pinned);
    });

    it('is the order the preview actually prints', () => {
        const html = renderToStaticMarkup(
            <AppendixPage appendix={APPENDIX} page={{ scopes: APPENDIX.scopes, withHeader: false, withSummary: false }}
                pageNumber={1} pageCount={1} examName="x" studentName="Dan" />);
        const at = (attr: string) => html.indexOf(`data-appendix-${attr}`);
        const blocks = ['points', 'feedback', 'notes', 'breakdown'];
        blocks.forEach((b) => expect(at(b)).toBeGreaterThan(-1));
        expect([...blocks].sort((a, b) => at(a) - at(b))).toEqual([...APPENDIX_SCOPE_ORDER]);
    });
});
