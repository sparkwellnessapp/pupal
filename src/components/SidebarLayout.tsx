'use client';

import { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
    BookOpen,
    GraduationCap,
    ClipboardCheck,
    Home,
    ChevronRight,
    ChevronLeft,
    User,
    LogOut,
    Settings,
    Menu,
    Loader2,
} from 'lucide-react';
import { useAuth } from '@/lib/auth';

interface SidebarProps {
    children: React.ReactNode;
}

interface NavItem {
    href: string;
    label: string;
    icon: React.ReactNode;
    description?: string;
}

const navItems: NavItem[] = [
    {
        href: '/',
        label: 'דף הבית',
        icon: <Home size={20} />,
        description: 'חזור לדף הבית',
    },
    {
        href: '/my-rubrics',
        label: 'המחוונים שלי',
        icon: <BookOpen size={20} />,
        description: 'צפה ונהל את המחוונים שלך',
    },
    {
        href: '/my-graded-tests',
        label: 'מבחנים בדוקים',
        icon: <ClipboardCheck size={20} />,
        description: 'צפה בתוצאות הבדיקה',
    },
];

// Profile Dropdown Component
function ProfileDropdown() {
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);
    const router = useRouter();
    const { user, logout, isAuthenticated } = useAuth();

    // Close dropdown when clicking outside
    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        }
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const handleLogout = () => {
        setIsOpen(false);
        logout();
        router.push('/login');
    };

    if (!isAuthenticated) {
        return (
            <Link
                href="/login"
                className="flex items-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors text-sm font-medium"
            >
                התחבר
            </Link>
        );
    }

    return (
        <div className="relative" ref={dropdownRef}>
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center justify-center w-10 h-10 rounded-full bg-primary-100 text-primary-700 hover:bg-primary-200 transition-colors"
                aria-label="פרופיל"
            >
                <User size={20} />
            </button>

            {isOpen && (
                <div className="absolute right-0 top-12 w-56 bg-white rounded-lg shadow-xl border border-surface-200 py-2 z-[60] animate-fade-in">
                    {/* User Info */}
                    <div className="px-4 py-3 border-b border-surface-200">
                        <p className="text-sm font-medium text-gray-900">
                            שלום, {user?.full_name || 'משתמש'}
                        </p>
                        <p className="text-xs text-gray-500 truncate">{user?.email}</p>
                    </div>

                    {/* Menu Items */}
                    <div className="py-1">
                        <Link
                            href="/profile"
                            onClick={() => setIsOpen(false)}
                            className="flex items-center gap-3 px-4 py-2 text-sm text-gray-700 hover:bg-surface-50 transition-colors"
                        >
                            <Settings size={16} />
                            <span>הגדרות פרופיל</span>
                        </Link>
                        <button
                            onClick={handleLogout}
                            className="flex items-center gap-3 w-full px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
                        >
                            <LogOut size={16} />
                            <span>התנתק</span>
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}

// Get subscription label
function getSubscriptionLabel(status: string | undefined): string {
    switch (status) {
        case 'active':
            return 'מנוי פעיל';
        case 'trial':
            return 'תקופת ניסיון';
        case 'expired':
            return 'פג תוקף';
        default:
            return 'חשבון חינמי';
    }
}

// Sidebar Layout Component
export function SidebarLayout({ children }: SidebarProps) {
    const [isCollapsed, setIsCollapsed] = useState(false);
    const [isMobileOpen, setIsMobileOpen] = useState(false);
    const pathname = usePathname();
    const router = useRouter();
    const { user, isLoading, isAuthenticated } = useAuth();

    // Redirect to login if not authenticated (after loading)
    useEffect(() => {
        if (!isLoading && !isAuthenticated) {
            router.push('/login');
        }
    }, [isLoading, isAuthenticated, router]);

    // Show loading while checking auth
    if (isLoading) {
        return (
            <div className="min-h-screen bg-[#FFFaf2] flex items-center justify-center">
                <div className="text-center">
                    <Loader2 className="animate-spin text-primary-500 mx-auto mb-4" size={40} />
                    <p className="text-gray-500">טוען...</p>
                </div>
            </div>
        );
    }

    // Don't render if not authenticated
    if (!isAuthenticated) {
        return null;
    }

    return (
        <div className="min-h-screen bg-[#FFFaf2]">
            {/* Mobile Header */}
            <div className="lg:hidden fixed top-0 left-0 right-0 h-16 bg-[#fcfbf5] border-b border-surface-200 z-40 flex items-center justify-between px-4">
                <button
                    onClick={() => setIsMobileOpen(!isMobileOpen)}
                    className="p-2 text-gray-600 hover:text-primary-600 transition-colors"
                >
                    <Menu size={24} />
                </button>
                <div className="flex items-center">
                    <img src="/vivi-logo-no-background-no-slogan.png" alt="Vivi" className="h-8 w-auto" />
                </div>
                <ProfileDropdown />
            </div>

            {/* Mobile Overlay */}
            {isMobileOpen && (
                <div
                    className="lg:hidden fixed inset-0 bg-black/50 z-40"
                    onClick={() => setIsMobileOpen(false)}
                />
            )}

            {/* Sidebar */}
            <aside
                className={`
          fixed top-0 right-0 h-full bg-[#fcfbf5] border-l border-surface-200 z-50
          transition-all duration-300 ease-in-out
          ${isCollapsed ? 'w-20' : 'w-64'}
          ${isMobileOpen ? 'translate-x-0' : 'translate-x-full lg:translate-x-0'}
        `}
            >
                {/* Sidebar Header */}
                <div className="h-16 flex items-center justify-start px-4 border-b border-surface-200">
                    <button
                        onClick={() => setIsCollapsed(!isCollapsed)}
                        className="p-2 text-gray-500 hover:text-gray-700 hover:bg-surface-100 rounded-lg transition-colors"
                        title={isCollapsed ? 'הרחב תפריט' : 'כווץ תפריט'}
                    >
                        <Menu size={22} />
                    </button>
                </div>

                {/* Navigation */}
                <nav className="p-3 space-y-1">
                    {navItems.map((item) => {
                        const isActive = pathname === item.href;
                        return (
                            <Link
                                key={item.href}
                                href={item.href}
                                onClick={() => setIsMobileOpen(false)}
                                className={`
                  flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all
                  ${isActive
                                        ? 'bg-primary-100 text-primary-700 font-medium'
                                        : 'text-gray-600 hover:bg-surface-100 hover:text-gray-900'
                                    }
                  ${isCollapsed ? 'justify-center' : ''}
                `}
                                title={isCollapsed ? item.label : undefined}
                            >
                                <span className={isActive ? 'text-primary-600' : 'text-gray-500'}>
                                    {item.icon}
                                </span>
                                {!isCollapsed && <span className="text-sm">{item.label}</span>}
                            </Link>
                        );
                    })}
                </nav>

                {/* Sidebar Footer */}
                <div className="absolute bottom-0 left-0 right-0 p-3 border-t border-surface-200">
                    {!isCollapsed ? (
                        <div className="flex items-center gap-3 px-3 py-2">
                            <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center">
                                <User size={16} className="text-primary-600" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-gray-900 truncate">
                                    {user?.full_name || 'משתמש'}
                                </p>
                                <p className="text-xs text-gray-500 truncate">
                                    {getSubscriptionLabel(user?.subscription_status)}
                                </p>
                            </div>
                        </div>
                    ) : (
                        <div className="flex justify-center">
                            <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center">
                                <User size={16} className="text-primary-600" />
                            </div>
                        </div>
                    )}
                </div>
            </aside>

            {/* Main Content */}
            <div
                className={`
          transition-all duration-300
          ${isCollapsed ? 'lg:mr-20' : 'lg:mr-64'}
          pt-16 lg:pt-0
        `}
            >
                {/* Desktop Header */}
                <header className="hidden lg:flex h-16 bg-[#fcfbf5] border-b border-surface-200 items-center justify-between px-6 sticky top-0 z-30">
                    <ProfileDropdown />
                    <div className="absolute left-1/2 transform -translate-x-1/2">
                        <img src="/vivi-logo-no-background-no-slogan.png" alt="Vivi" className="h-12 w-auto" />
                    </div>
                    <div></div>
                </header>

                {/* Page Content */}
                <main className="p-6">
                    {children}
                </main>
            </div>
        </div>
    );
}
