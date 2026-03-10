// tailwind.config.js
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // 背景層次
        'ink-0': '#F8FAFC', // 整體大背景 (Slate 50)
        'ink-1': '#FFFFFF', // 面板背景 (純白)
        'ink-2': '#F1F5F9', // 卡片/輸入框背景
        'ink-3': '#E2E8F0', // Hover 狀態
        'ink-4': '#CBD5E1',
        // 邊框
        'line-0': '#E2E8F0',
        'line-1': '#CBD5E1',
        'line-2': '#94A3B8',
        'line-3': '#64748B',
        // 文字
        'tx-hi':  '#0F172A', // 主要文字 (極黑)
        'tx-mid': '#334155', // 次要文字 (深灰)
        'tx-lo':  '#475569', // 標籤/輔助說明
        'tx-off': '#94A3B8',
        // 訊號色（儀器磷光）
        'sig-cyan':   '#0284C7',
        'sig-teal':   '#0D9488',
        'sig-lime':   '#16A34A',
        'sig-amber':  '#D97706',
        'sig-red':    '#DC2626',
        'sig-violet': '#7C3AED',
      },
      fontFamily: {
        mono: ['var(--font-mono)', 'monospace'],
        sans: ['var(--font-sans)', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
