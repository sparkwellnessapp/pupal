import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

import { SchoolCombobox } from './SchoolCombobox';
import { IdentityStep } from './steps/IdentityStep';
import { SCHOOLS_CHOSEN, SCHOOLS_PLACEHOLDER, SCHOOLS_REMOVE } from '@/copy/onboarding';
import type { PickedSchool } from '@/lib/onboarding';

const blich: PickedSchool = {
    id: '2',
    name: 'בליך',
    city: 'רמת גן',
    label: 'בליך, רמת גן',
    ministrySymbol: '540151',
};

describe('SchoolCombobox', () => {
    it('renders an empty search field with no picks', () => {
        const out = renderToStaticMarkup(
            <SchoolCombobox picked={[]} onChange={() => {}} />,
        );
        expect(out).toContain(SCHOOLS_PLACEHOLDER);
        expect(out).toContain('value=""');
    });

    it('shows no chip list until something is picked', () => {
        const out = renderToStaticMarkup(
            <SchoolCombobox picked={[]} onChange={() => {}} />,
        );
        expect(out).not.toContain(SCHOOLS_CHOSEN);
    });

    it('renders each pick as a removable chip', () => {
        const out = renderToStaticMarkup(
            <SchoolCombobox picked={[blich]} onChange={() => {}} />,
        );
        expect(out).toContain('בליך, רמת גן');
        expect(out).toContain(SCHOOLS_REMOVE('בליך, רמת גן'));
    });

    it('keeps picks in the given order — the first is the attribution key', () => {
        const second: PickedSchool = {
            id: '9',
            name: 'הרצוג',
            city: 'כפר סבא',
            label: 'הרצוג, כפר סבא',
            ministrySymbol: '470169',
        };
        const out = renderToStaticMarkup(
            <SchoolCombobox picked={[blich, second]} onChange={() => {}} />,
        );
        expect(out.indexOf('בליך, רמת גן')).toBeLessThan(out.indexOf('הרצוג, כפר סבא'));
    });

    it('does not open a result list before anything is typed', () => {
        const out = renderToStaticMarkup(
            <SchoolCombobox picked={[]} onChange={() => {}} />,
        );
        expect(out).not.toContain('school-results');
    });
});

describe('IdentityStep', () => {
    const render = (props: Partial<Parameters<typeof IdentityStep>[0]> = {}) =>
        renderToStaticMarkup(
            <IdentityStep
                fullName="מיכל כהן"
                gender={null}
                onNameChange={() => {}}
                onGenderChange={() => {}}
                showHint={false}
                {...props}
            />,
        );

    it('prefills the name from the session', () => {
        expect(render()).toContain('value="מיכל כהן"');
    });

    it('offers a third option so anyone can answer honestly', () => {
        const out = render();
        expect(out).toContain('gender-female');
        expect(out).toContain('gender-male');
        expect(out).toContain('gender-unspecified');
    });

    it('marks the chosen gender pressed', () => {
        expect(render({ gender: 'unspecified' })).toContain('aria-pressed="true"');
    });

    it('stays quiet until she has tried to advance', () => {
        expect(render({ fullName: '' })).not.toContain('onboarding-name-hint');
    });

    it('explains the block once she has', () => {
        const out = render({ fullName: '', showHint: true });
        expect(out).toContain('onboarding-name-hint');
        expect(out).toContain('aria-invalid="true"');
    });
});
