import { Users } from 'lucide-react';

/** The roster's avatar, at the roster's size or the profile header's. */
export function StudentAvatar({ size = 'sm' }: { size?: 'sm' | 'lg' }) {
    const large = size === 'lg';
    return (
        <div
            aria-hidden="true"
            className={[
                'rounded-full bg-primary-100 flex items-center justify-center shrink-0',
                large ? 'w-16 h-16' : 'w-9 h-9',
            ].join(' ')}
        >
            <Users size={large ? 28 : 16} className="text-primary-600" />
        </div>
    );
}
