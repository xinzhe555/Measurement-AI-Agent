// app/layout.tsx
import type { Metadata } from 'next'
import { JetBrains_Mono, IBM_Plex_Sans } from 'next/font/google'
import './globals.css'

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  weight: ['300', '400', '500', '700'],
})

const ibmPlexSans = IBM_Plex_Sans({
  subsets: ['latin'],
  variable: '--font-sans',
  weight: ['300', '400', '500', '600'],
})

export const metadata: Metadata = {
  title: 'PREC·OS — BK4 五軸誤差診斷系統',
  description: '基於 HTM 非線性辨識與 AI 殘差學習的五軸機台誤差補償系統',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-TW" className={`${jetbrainsMono.variable} ${ibmPlexSans.variable}`}>
      <body className="bg-ink-0 text-tx-hi antialiased overflow-hidden">
        {children}
      </body>
    </html>
  )
}
