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
    User,
    Sparkles,
    CheckCircle2,
} from 'lucide-react';
import { useAuth } from '@/lib/auth';

type FocusedField = 'name' | 'email' | 'password' | 'confirmPassword' | null;

export default function SignupPage() {
    const router = useRouter();
    const { signup, isAuthenticated } = useAuth();

    const [fullName, setFullName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [focusedField, setFocusedField] = useState<FocusedField>(null);

    // Redirect if already authenticated
    if (isAuthenticated) {
        router.push('/');
        return null;
    }

    // Password validation
    const passwordLength = password.length >= 6;
    const passwordsMatch = password === confirmPassword && confirmPassword.length > 0;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);

        // Validate passwords match
        if (password !== confirmPassword) {
            setError('הסיסמאות אינן תואמות');
            return;
        }

        // Validate password length
        if (password.length < 6) {
            setError('הסיסמה חייבת להכיל לפחות 6 תווים');
            return;
        }

        setIsLoading(true);

        try {
            await signup(email, password, fullName);
            router.push('/');
        } catch (err) {
            setError(err instanceof Error ? err.message : 'שגיאה ביצירת החשבון');
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
                <div className="absolute top-[60%] left-[70%] w-[250px] h-[250px] rounded-full bg-gradient-to-br from-amber-200/30 to-transparent blur-2xl" />

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
                <div className="text-center mb-6 animate-fade-in">
                    <div className="relative inline-block">
                        <img
                            src="/vivi-logo-no-background-no-slogan.png"
                            alt="Vivi"
                            className="h-20 w-auto mx-auto mb-3 drop-shadow-lg"
                        />
                        {/* Sparkle decoration */}
                        <Sparkles
                            className="absolute -top-1 -right-3 text-amber-400 animate-pulse"
                            size={18}
                        />
                    </div>
                    <p className="text-gray-500 mt-1 text-lg font-light tracking-wide">
                        העוזרת האישית למורים
                    </p>
                </div>

                {/* Signup Card */}
                <div className="relative">
                    {/* Card glow effect */}
                    <div className="absolute -inset-1 bg-gradient-to-r from-primary-400/20 via-[#aa77f7]/20 to-primary-400/20 rounded-3xl blur-xl opacity-60" />

                    <div className="relative bg-white/80 backdrop-blur-xl rounded-2xl shadow-2xl shadow-gray-200/50 p-8 border border-white/50">
                        <div className="text-center mb-6">
                            <h2 className="text-2xl font-bold bg-gradient-to-r from-gray-800 via-gray-700 to-gray-800 bg-clip-text text-transparent">
                                הרשמה
                            </h2>
                            <p className="text-gray-400 mt-2 text-sm">
                                צרי חשבון חדש והתחילי לבדוק מבחנים
                            </p>
                        </div>

                        <form onSubmit={handleSubmit} className="space-y-4">
                            {/* Full Name */}
                            <div className="space-y-1.5">
                                <label className="block text-sm font-medium text-gray-600">
                                    שם מלא
                                </label>
                                <div className={`relative group transition-all duration-300 ${focusedField === 'name' ? 'scale-[1.02]' : ''}`}>
                                    <div className={`absolute inset-0 bg-gradient-to-r from-primary-400 to-[#aa77f7] rounded-xl opacity-0 blur transition-opacity duration-300 ${focusedField === 'name' ? 'opacity-20' : 'group-hover:opacity-10'}`} />
                                    <div className="relative flex items-center">
                                        <User
                                            className={`absolute right-4 transition-colors duration-300 ${focusedField === 'name' ? 'text-primary-500' : 'text-gray-400'}`}
                                            size={18}
                                        />
                                        <input
                                            type="text"
                                            value={fullName}
                                            onChange={(e) => setFullName(e.target.value)}
                                            onFocus={() => setFocusedField('name')}
                                            onBlur={() => setFocusedField(null)}
                                            placeholder="מיכל כהן"
                                            className="w-full pr-12 pl-4 py-3 bg-surface-50/50 border border-surface-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/50 focus:border-primary-400 focus:bg-white transition-all duration-300"
                                            required
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* Email */}
                            <div className="space-y-1.5">
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
                                            className="w-full pr-12 pl-4 py-3 bg-surface-50/50 border border-surface-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/50 focus:border-primary-400 focus:bg-white transition-all duration-300"
                                            required
                                            dir="ltr"
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* Password */}
                            <div className="space-y-1.5">
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
                                            placeholder="לפחות 6 תווים"
                                            className="w-full pr-12 pl-14 py-3 bg-surface-50/50 border border-surface-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/50 focus:border-primary-400 focus:bg-white transition-all duration-300"
                                            required
                                            minLength={6}
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

                            {/* Confirm Password */}
                            <div className="space-y-1.5">
                                <label className="block text-sm font-medium text-gray-600">
                                    אימות סיסמה
                                </label>
                                <div className={`relative group transition-all duration-300 ${focusedField === 'confirmPassword' ? 'scale-[1.02]' : ''}`}>
                                    <div className={`absolute inset-0 bg-gradient-to-r from-primary-400 to-[#aa77f7] rounded-xl opacity-0 blur transition-opacity duration-300 ${focusedField === 'confirmPassword' ? 'opacity-20' : 'group-hover:opacity-10'}`} />
                                    <div className="relative flex items-center">
                                        <Lock
                                            className={`absolute right-4 transition-colors duration-300 ${focusedField === 'confirmPassword' ? 'text-primary-500' : 'text-gray-400'}`}
                                            size={18}
                                        />
                                        <input
                                            type={showPassword ? 'text' : 'password'}
                                            value={confirmPassword}
                                            onChange={(e) => setConfirmPassword(e.target.value)}
                                            onFocus={() => setFocusedField('confirmPassword')}
                                            onBlur={() => setFocusedField(null)}
                                            placeholder="הזיני שוב את הסיסמה"
                                            className="w-full pr-12 pl-4 py-3 bg-surface-50/50 border border-surface-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/50 focus:border-primary-400 focus:bg-white transition-all duration-300"
                                            required
                                            dir="ltr"
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* Password Requirements Indicators */}
                            {(password.length > 0 || confirmPassword.length > 0) && (
                                <div className="flex flex-wrap gap-3 text-xs animate-fade-in">
                                    <div className={`flex items-center gap-1.5 transition-colors duration-300 ${passwordLength ? 'text-green-600' : 'text-gray-400'}`}>
                                        <CheckCircle2 size={14} className={passwordLength ? 'text-green-500' : ''} />
                                        <span>לפחות 6 תווים</span>
                                    </div>
                                    <div className={`flex items-center gap-1.5 transition-colors duration-300 ${passwordsMatch ? 'text-green-600' : 'text-gray-400'}`}>
                                        <CheckCircle2 size={14} className={passwordsMatch ? 'text-green-500' : ''} />
                                        <span>סיסמאות תואמות</span>
                                    </div>
                                </div>
                            )}

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
                                className="relative w-full py-4 rounded-xl font-semibold text-white overflow-hidden transition-all duration-300 disabled:opacity-60 disabled:cursor-not-allowed group mt-2"
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
                                            <span>יוצר חשבון...</span>
                                        </>
                                    ) : (
                                        <span>צרי חשבון</span>
                                    )}
                                </span>
                            </button>
                        </form>

                        {/* Divider */}
                        <div className="relative my-6">
                            <div className="absolute inset-0 flex items-center">
                                <div className="w-full border-t border-surface-200" />
                            </div>
                            <div className="relative flex justify-center">
                                <span className="px-4 bg-white/80 text-sm text-gray-400">או</span>
                            </div>
                        </div>

                        {/* Login Link */}
                        <div className="text-center">
                            <p className="text-gray-500 text-sm">
                                כבר יש לך חשבון?{' '}
                                <Link
                                    href="/login"
                                    className="font-semibold text-transparent bg-clip-text bg-gradient-to-r from-primary-600 to-[#aa77f7] hover:from-primary-700 hover:to-[#9966e6] transition-all duration-300"
                                >
                                    התחברי
                                </Link>
                            </p>
                        </div>
                    </div>
                </div>

                {/* Footer */}
                <p className="text-center text-xs text-gray-400 mt-6">
                    © 2026 Vivi. All rights reserved.
                </p>
            </div>
        </div>
    );
}
