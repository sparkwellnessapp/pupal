import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Grader Vision - מערכת בדיקת מבחנים',
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
        {children}
      </body>
    </html>
  )
}
