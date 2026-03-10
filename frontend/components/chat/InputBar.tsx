'use client'
// components/chat/InputBar.tsx
import { useState, useRef, KeyboardEvent } from 'react'
import type { AnalyzeRequest } from '@/lib/types'

interface Props {
  onSend: (text: string) => void
  onAnalyze: (req: AnalyzeRequest) => void
  isAnalyzing: boolean
}

const MODES = ['診斷', '查詢', '設定', '報告'] as const
type Mode = typeof MODES[number]

const PLACEHOLDERS: Record<Mode, string> = {
  '診斷': '輸入問題，例如：EYC 對 DZ 的耦合原因是什麼？',
  '查詢': '查詢誤差定義、HTM 公式、ISO 230 標準...',
  '設定': '調整參數，例如：設定球半徑 R=300mm',
  '報告': '生成報告，例如：生成完整診斷 PDF 給教授',
}

export function InputBar({ onSend, onAnalyze, isAnalyzing }: Props) {
  const [text, setText]   = useState('')
  const [mode, setMode]   = useState<Mode>('診斷')
  const taRef = useRef<HTMLTextAreaElement>(null)

  const handleKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleSend = () => {
    const t = text.trim()
    if (!t) return
    onSend(t)
    setText('')
    if (taRef.current) {
      taRef.current.style.height = 'auto'
    }
  }

  const autoResize = () => {
    const el = taRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 140) + 'px'
  }

  return (
    <div className="px-5 pb-4 pt-2 border-t border-line-1 bg-ink-0">
      <div className="max-w-3xl mx-auto">
        <div className="bg-ink-2 border border-line-2 rounded-xl overflow-hidden
                        focus-within:border-sig-cyan/40 focus-within:shadow-[0_0_0_3px_rgba(0,207,255,0.05)]
                        transition-all">

          {/* 模式列 */}
          <div className="flex border-b border-line-1 px-2">
            {MODES.map(m => (
              <button key={m} onClick={() => setMode(m)}
                className={`px-3 py-1.5 font-mono text-[8.5px] tracking-widest uppercase
                            border-b-2 transition-all
                            ${mode === m
                              ? 'text-sig-cyan border-sig-cyan'
                              : 'text-tx-lo border-transparent hover:text-tx-mid'}`}>
                {m}
              </button>
            ))}
          </div>

          {/* 輸入框 */}
          <textarea
            ref={taRef}
            value={text}
            onChange={e => { setText(e.target.value); autoResize() }}
            onKeyDown={handleKey}
            placeholder={PLACEHOLDERS[mode]}
            rows={1}
            className="w-full bg-transparent px-4 py-3 text-[13px] text-tx-hi
                       placeholder:text-tx-off placeholder:italic
                       outline-none resize-none min-h-[44px] max-h-[140px]
                       leading-relaxed font-sans"
          />

          {/* 底部工具列 */}
          <div className="flex items-center justify-between px-3 py-1.5 border-t border-line-0">
            <div className="flex gap-1">
              {['📎', '📊', '🗑'].map(icon => (
                <button key={icon}
                  className="w-6 h-6 flex items-center justify-center text-xs
                             text-tx-off hover:text-tx-mid hover:bg-ink-3
                             rounded transition-colors">
                  {icon}
                </button>
              ))}
            </div>
            <button
              onClick={handleSend}
              disabled={!text.trim()}
              className="flex items-center gap-1.5 px-3 py-1 rounded
                         font-mono text-[9px] tracking-widest uppercase
                         border transition-all disabled:opacity-30 disabled:cursor-not-allowed
                         border-sig-cyan/30 text-sig-cyan bg-sig-cyan/5
                         hover:bg-sig-cyan/15 hover:border-sig-cyan/55
                         hover:shadow-[0_0_8px_rgba(0,207,255,0.12)]">
              → 發送
            </button>
          </div>
        </div>

        <div className="text-center font-mono text-[8px] text-tx-off tracking-widest uppercase mt-1.5">
          Enter 發送 · Shift+Enter 換行
        </div>
      </div>
    </div>
  )
}
