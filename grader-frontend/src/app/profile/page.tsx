'use client';

import { useState, useEffect } from 'react';
import {
    User,
    Mail,
    CreditCard,
    Calendar,
    BookOpen,
    Settings,
    Bell,
    Shield,
    ChevronLeft,
    Save,
    Loader2,
    CheckCircle,
} from 'lucide-react';
import { SidebarLayout } from '@/components/SidebarLayout';
import { useAuth } from '@/lib/auth';

// Subscription Status Badge
function SubscriptionBadge({ status }: { status: string }) {
    const styles: Record<string, string> = {
        trial: 'bg-amber-100 text-amber-700 border-amber-200',
        active: 'bg-green-100 text-green-700 border-green-200',
        expired: 'bg-red-100 text-red-700 border-red-200',
        cancelled: 'bg-gray-100 text-gray-700 border-gray-200',
    };

    const labels: Record<string, string> = {
        trial: 'תקופת ניסיון',
        active: 'מנוי פעיל',
        expired: 'פג תוקף',
        cancelled: 'בוטל',
    };

    return (
        <span className={`px-3 py-1 rounded-full text-sm font-medium border ${styles[status] || styles.trial}`}>
            {labels[status] || status}
        </span>
    );
}

// Settings Section Component
function SettingsSection({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
    return (
        <div className="bg-white rounded-xl border border-surface-200 p-6">
            <div className="mb-4">
                <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
                {description && <p className="text-sm text-gray-500 mt-1">{description}</p>}
            </div>
            {children}
        </div>
    );
}

// Format date for display
function formatDate(dateStr?: string): string {
    if (!dateStr) return 'לא זמין';
    try {
        const date = new Date(dateStr);
        return date.toLocaleDateString('he-IL', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
        });
    } catch {
        return dateStr;
    }
}

// Main Profile Page
export default function ProfilePage() {
    const { user, refreshUser } = useAuth();
    const [isEditing, setIsEditing] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [showSaved, setShowSaved] = useState(false);
    const [editedName, setEditedName] = useState('');

    // Initialize edited name when user loads
    useEffect(() => {
        if (user?.full_name) {
            setEditedName(user.full_name);
        }
    }, [user?.full_name]);

    const handleSave = async () => {
        setIsSaving(true);
        // TODO: Implement API call to update user profile
        // For now, just simulate
        await new Promise(resolve => setTimeout(resolve, 1000));
        setIsSaving(false);
        setIsEditing(false);
        setShowSaved(true);
        setTimeout(() => setShowSaved(false), 3000);
        // Refresh user data after save
        await refreshUser();
    };

    // Get subject matters from user or empty array
    const subjectMatters = user?.subject_matters || [];

    return (
        <SidebarLayout>
            <div className="max-w-3xl mx-auto">
                {/* Page Header */}
                <div className="mb-6">
                    <h1 className="text-2xl font-bold text-gray-900">הגדרות פרופיל</h1>
                    <p className="text-gray-500 mt-1">נהל את פרטי החשבון וההעדפות שלך</p>
                </div>

                {/* Success Toast */}
                {showSaved && (
                    <div className="fixed top-4 left-1/2 -translate-x-1/2 bg-green-500 text-white px-4 py-2 rounded-lg shadow-lg flex items-center gap-2 z-50 animate-fade-in">
                        <CheckCircle size={18} />
                        <span>השינויים נשמרו בהצלחה</span>
                    </div>
                )}

                <div className="space-y-6">
                    {/* Profile Info Section */}
                    <SettingsSection title="פרטים אישיים" description="עדכן את פרטי החשבון שלך">
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">שם מלא</label>
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center">
                                        <User size={18} className="text-primary-600" />
                                    </div>
                                    {isEditing ? (
                                        <input
                                            type="text"
                                            value={editedName}
                                            onChange={(e) => setEditedName(e.target.value)}
                                            className="flex-1 p-2.5 border border-surface-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                                        />
                                    ) : (
                                        <span className="text-gray-900">{user?.full_name || 'לא הוגדר'}</span>
                                    )}
                                </div>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">כתובת אימייל</label>
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 rounded-full bg-surface-100 flex items-center justify-center">
                                        <Mail size={18} className="text-gray-500" />
                                    </div>
                                    <span className="text-gray-600">{user?.email || 'לא זמין'}</span>
                                    <span className="text-xs text-gray-400">(לא ניתן לשינוי)</span>
                                </div>
                            </div>

                            <div className="pt-4 flex justify-end gap-3">
                                {isEditing ? (
                                    <>
                                        <button
                                            onClick={() => {
                                                setIsEditing(false);
                                                setEditedName(user?.full_name || '');
                                            }}
                                            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 transition-colors"
                                        >
                                            ביטול
                                        </button>
                                        <button
                                            onClick={handleSave}
                                            disabled={isSaving}
                                            className="flex items-center gap-2 bg-primary-500 text-white px-4 py-2 rounded-lg hover:bg-primary-600 disabled:opacity-50 transition-colors"
                                        >
                                            {isSaving ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}
                                            {isSaving ? 'שומר...' : 'שמור שינויים'}
                                        </button>
                                    </>
                                ) : (
                                    <button
                                        onClick={() => setIsEditing(true)}
                                        className="flex items-center gap-2 text-primary-600 hover:text-primary-700 transition-colors"
                                    >
                                        <Settings size={16} />
                                        ערוך פרטים
                                    </button>
                                )}
                            </div>
                        </div>
                    </SettingsSection>

                    {/* Subscription Section */}
                    <SettingsSection title="מנוי" description="פרטי המנוי והחיוב שלך">
                        <div className="space-y-4">
                            <div className="flex items-center justify-between p-4 bg-surface-50 rounded-lg">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center">
                                        <CreditCard size={18} className="text-primary-600" />
                                    </div>
                                    <div>
                                        <p className="font-medium text-gray-900">סטטוס מנוי</p>
                                        <p className="text-sm text-gray-500">
                                            {user?.subscription_status === 'trial'
                                                ? `תקופת הניסיון מסתיימת ב-${formatDate(user?.trial_ends_at)}`
                                                : user?.subscription_status === 'active'
                                                    ? `מנוי פעיל מאז ${formatDate(user?.started_pro_at)}`
                                                    : 'מנוי פעיל'
                                            }
                                        </p>
                                    </div>
                                </div>
                                <SubscriptionBadge status={user?.subscription_status || 'trial'} />
                            </div>

                            {user?.subscription_status === 'trial' && (
                                <button className="w-full py-3 bg-gradient-to-r from-primary-500 to-primary-600 text-white rounded-lg font-medium hover:from-primary-600 hover:to-primary-700 transition-all shadow-lg shadow-primary-500/25">
                                    שדרג לחשבון פרימיום
                                </button>
                            )}
                        </div>
                    </SettingsSection>

                    {/* Subject Matters Section */}
                    <SettingsSection title="מקצועות לימוד" description="בחר את המקצועות שאתה מלמד">
                        <div className="flex flex-wrap gap-2">
                            {subjectMatters.length > 0 ? (
                                subjectMatters.map((subject) => (
                                    <span
                                        key={subject.id}
                                        className="px-3 py-1.5 bg-primary-100 text-primary-700 rounded-full text-sm font-medium"
                                    >
                                        {subject.name_he || subject.name_en}
                                    </span>
                                ))
                            ) : (
                                <p className="text-gray-500 text-sm">לא נבחרו מקצועות</p>
                            )}
                            <button className="px-3 py-1.5 border border-dashed border-surface-300 text-gray-500 rounded-full text-sm hover:border-primary-300 hover:text-primary-600 transition-colors">
                                + הוסף מקצוע
                            </button>
                        </div>
                    </SettingsSection>

                    {/* Security Section */}
                    <SettingsSection title="אבטחה" description="הגדרות אבטחת החשבון">
                        <div className="space-y-3">
                            <button className="flex items-center justify-between w-full p-3 hover:bg-surface-50 rounded-lg transition-colors group">
                                <div className="flex items-center gap-3">
                                    <Shield size={18} className="text-gray-500" />
                                    <span className="text-gray-700">שינוי סיסמה</span>
                                </div>
                                <ChevronLeft size={18} className="text-gray-400 group-hover:text-gray-600" />
                            </button>
                            <button className="flex items-center justify-between w-full p-3 hover:bg-surface-50 rounded-lg transition-colors group">
                                <div className="flex items-center gap-3">
                                    <Bell size={18} className="text-gray-500" />
                                    <span className="text-gray-700">התראות</span>
                                </div>
                                <ChevronLeft size={18} className="text-gray-400 group-hover:text-gray-600" />
                            </button>
                        </div>
                    </SettingsSection>
                </div>
            </div>
        </SidebarLayout>
    );
}
