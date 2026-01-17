import type { Metadata } from 'next'
import './globals.css'
import { AuthProvider } from '@/lib/auth'
import { Toaster } from 'sonner'

export const metadata: Metadata = {
  title: 'Pupal - מערכת בדיקת מבחנים',
  description: 'מערכת AI לבדיקת מבחנים בתכנות',
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
