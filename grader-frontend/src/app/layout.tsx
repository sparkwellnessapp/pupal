import type { Metadata } from 'next'
import './globals.css'
import { AuthProvider } from '@/lib/auth'
import { OnboardingGate } from '@/components/OnboardingGate'
import { UploadQueueProvider } from '@/contexts/UploadQueueProvider'
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
          {/* Renders nothing; redirects a teacher who has not finished
              onboarding. Inside AuthProvider because it reads the session. */}
          <OnboardingGate />
          {/* [Stage B] The upload queue lives ABOVE the routes on purpose:
              pages unmount on navigation and their XHRs abort with them, which
              is the only reason the teacher used to wait for the last byte
              before she could leave the upload page. Nothing renders here —
              the queue's surface is the dashboard's lane. */}
          <UploadQueueProvider>
            {children}
          </UploadQueueProvider>
        </AuthProvider>
        <Toaster position="top-center" richColors dir="rtl" />
      </body>
    </html>
  )
}
