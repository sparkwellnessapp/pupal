'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
    Mail,
    Lock,
    Eye,
    EyeOff,
    Loader2,
    AlertCircle,
    Sparkles,
} from 'lucide-react';
import { useAuth } from '@/lib/auth';

export default function LoginPage() {
    const router = useRouter();
    const { login, isAuthenticated } = useAuth();

    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [focusedField, setFocusedField] = useState<'email' | 'password' | null>(null);

    // Redirect if already authenticated
    if (isAuthenticated) {
        router.push('/');
        return null;
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        setIsLoading(true);

        try {
            await login(email, password);
            router.push('/');
        } catch (err) {
            setError(err instanceof Error ? err.message : 'שגיאה בהתחברות');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-[#FFFaf2] flex items-center justify-center p-4 relative overflow-hidden">
            {/* Decorative background elements */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                {/* Gradient orbs */}
                <div className="absolute top-[-20%] right-[-10%] w-[600px] h-[600px] rounded-full bg-gradient-to-br from-primary-200/40 via-primary-300/20 to-transparent blur-3xl" />
                <div className="absolute bottom-[-30%] left-[-15%] w-[700px] h-[700px] rounded-full bg-gradient-to-tr from-[#aa77f7]/20 via-[#aa77f7]/10 to-transparent blur-3xl" />
                <div className="absolute top-[40%] left-[60%] w-[300px] h-[300px] rounded-full bg-gradient-to-br from-amber-200/30 to-transparent blur-2xl" />

                {/* Subtle grid pattern */}
                <div
                    className="absolute inset-0 opacity-[0.02]"
                    style={{
                        backgroundImage: `linear-gradient(rgba(0,0,0,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(0,0,0,0.1) 1px, transparent 1px)`,
                        backgroundSize: '40px 40px'
                    }}
                />
            </div>

            <div className="w-full max-w-md relative z-10">
                {/* Logo Section */}
                <div className="text-center mb-8 animate-fade-in">
                    <div className="relative inline-block">
                        <img
                            src="/vivi-logo-no-background-no-slogan.png"
                            alt="Vivi"
                            className="h-28 w-auto mx-auto mb-4 drop-shadow-lg"
                        />
                        {/* Sparkle decoration */}
                        <Sparkles
                            className="absolute -top-2 -right-4 text-amber-400 animate-pulse"
                            size={20}
                        />
                    </div>
                    <p className="text-gray-500 mt-2 text-lg font-light tracking-wide">
                        העוזרת האישית למורים
                    </p>
                </div>

                {/* Login Card */}
                <div className="relative">
                    {/* Card glow effect */}
                    <div className="absolute -inset-1 bg-gradient-to-r from-primary-400/20 via-[#aa77f7]/20 to-primary-400/20 rounded-3xl blur-xl opacity-60" />

                    <div className="relative bg-white/80 backdrop-blur-xl rounded-2xl shadow-2xl shadow-gray-200/50 p-8 border border-white/50">
                        <div className="text-center mb-8">
                            <h2 className="text-2xl font-bold bg-gradient-to-r from-gray-800 via-gray-700 to-gray-800 bg-clip-text text-transparent">
                                התחברות
                            </h2>
                            <p className="text-gray-400 mt-2 text-sm">
                                הזיני את פרטי ההתחברות שלך
                            </p>
                        </div>

                        <form onSubmit={handleSubmit} className="space-y-5">
                            {/* Email Field */}
                            <div className="space-y-2">
                                <label className="block text-sm font-medium text-gray-600">
                                    כתובת אימייל
                                </label>
                                <div className={`relative group transition-all duration-300 ${focusedField === 'email' ? 'scale-[1.02]' : ''}`}>
                                    <div className={`absolute inset-0 bg-gradient-to-r from-primary-400 to-[#aa77f7] rounded-xl opacity-0 blur transition-opacity duration-300 ${focusedField === 'email' ? 'opacity-20' : 'group-hover:opacity-10'}`} />
                                    <div className="relative flex items-center">
                                        <Mail
                                            className={`absolute right-4 transition-colors duration-300 ${focusedField === 'email' ? 'text-primary-500' : 'text-gray-400'}`}
                                            size={18}
                                        />
                                        <input
                                            type="email"
                                            value={email}
                                            onChange={(e) => setEmail(e.target.value)}
                                            onFocus={() => setFocusedField('email')}
                                            onBlur={() => setFocusedField(null)}
                                            placeholder="email@example.com"
                                            className="w-full pr-12 pl-4 py-3.5 bg-surface-50/50 border border-surface-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/50 focus:border-primary-400 focus:bg-white transition-all duration-300"
                                            required
                                            dir="ltr"
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* Password Field */}
                            <div className="space-y-2">
                                <label className="block text-sm font-medium text-gray-600">
                                    סיסמה
                                </label>
                                <div className={`relative group transition-all duration-300 ${focusedField === 'password' ? 'scale-[1.02]' : ''}`}>
                                    <div className={`absolute inset-0 bg-gradient-to-r from-primary-400 to-[#aa77f7] rounded-xl opacity-0 blur transition-opacity duration-300 ${focusedField === 'password' ? 'opacity-20' : 'group-hover:opacity-10'}`} />
                                    <div className="relative flex items-center">
                                        <Lock
                                            className={`absolute right-4 transition-colors duration-300 ${focusedField === 'password' ? 'text-primary-500' : 'text-gray-400'}`}
                                            size={18}
                                        />
                                        <input
                                            type={showPassword ? 'text' : 'password'}
                                            value={password}
                                            onChange={(e) => setPassword(e.target.value)}
                                            onFocus={() => setFocusedField('password')}
                                            onBlur={() => setFocusedField(null)}
                                            placeholder="••••••••"
                                            className="w-full pr-12 pl-14 py-3.5 bg-surface-50/50 border border-surface-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/50 focus:border-primary-400 focus:bg-white transition-all duration-300"
                                            required
                                            dir="ltr"
                                        />
                                        <button
                                            type="button"
                                            onClick={() => setShowPassword(!showPassword)}
                                            className="absolute left-4 text-gray-400 hover:text-gray-600 transition-colors duration-200"
                                        >
                                            {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                                        </button>
                                    </div>
                                </div>
                            </div>

                            {/* Error Message */}
                            {error && (
                                <div className="p-4 bg-red-50/80 backdrop-blur border border-red-200 rounded-xl text-red-600 text-sm flex items-center gap-3 animate-fade-in">
                                    <div className="p-1.5 bg-red-100 rounded-lg">
                                        <AlertCircle size={16} />
                                    </div>
                                    <span>{error}</span>
                                </div>
                            )}

                            {/* Submit Button */}
                            <button
                                type="submit"
                                disabled={isLoading}
                                className="relative w-full py-4 rounded-xl font-semibold text-white overflow-hidden transition-all duration-300 disabled:opacity-60 disabled:cursor-not-allowed group"
                            >
                                {/* Button gradient background */}
                                <div className="absolute inset-0 bg-gradient-to-r from-primary-500 via-primary-600 to-[#aa77f7] transition-transform duration-500 group-hover:scale-105" />

                                {/* Shine effect */}
                                <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500">
                                    <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-1000" />
                                </div>

                                {/* Button content */}
                                <span className="relative flex items-center justify-center gap-2">
                                    {isLoading ? (
                                        <>
                                            <Loader2 className="animate-spin" size={20} />
                                            <span>מתחבר...</span>
                                        </>
                                    ) : (
                                        <span>התחבר</span>
                                    )}
                                </span>
                            </button>
                        </form>

                        {/* Divider */}
                        <div className="relative my-8">
                            <div className="absolute inset-0 flex items-center">
                                <div className="w-full border-t border-surface-200" />
                            </div>
                            <div className="relative flex justify-center">
                                <span className="px-4 bg-white/80 text-sm text-gray-400">או</span>
                            </div>
                        </div>

                        {/* Signup Link */}
                        <div className="text-center">
                            <p className="text-gray-500 text-sm">
                                אין לך חשבון?{' '}
                                <Link
                                    href="/signup"
                                    className="font-semibold text-transparent bg-clip-text bg-gradient-to-r from-primary-600 to-[#aa77f7] hover:from-primary-700 hover:to-[#9966e6] transition-all duration-300"
                                >
                                    הרשמי עכשיו
                                </Link>
                            </p>
                        </div>
                    </div>
                </div>

                {/* Footer */}
                <p className="text-center text-xs text-gray-400 mt-8">
                    © 2026 Vivi. All rights reserved.
                </p>
            </div>
        </div>
    );
}
