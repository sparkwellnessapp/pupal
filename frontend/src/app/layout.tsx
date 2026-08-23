import type { Metadata } from 'next'
import './globals.css'
import { AuthProvider } from '@/lib/auth'
import { Toaster } from 'sonner'

export const metadata: Metadata = {
  title: 'Vivi - עוזר המורה',
  description: 'פלטפורמת AI לבדיקת מבחנים, יצירת מחוונים, ניהול תלמידים ועוד.',
  other: {
    // curl -s https://www.vivi-assistant.com | grep build-sha → deployed commit
    'build-sha': process.env.NEXT_PUBLIC_BUILD_SHA || 'unknown',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="he" dir="rtl">
      <body className="min-h-screen bg-surface-50">
        <AuthProvider>
          {children}
        </AuthProvider>
        <Toaster position="top-center" richColors dir="rtl" />
      </body>
    </html>
  )
}
