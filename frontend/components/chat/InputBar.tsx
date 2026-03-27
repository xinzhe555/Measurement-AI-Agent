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
  
  // 1. 新增：用來參考隱藏的檔案上傳元件
  const fileInputRef = useRef<HTMLInputElement>(null)

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

  // 2. 新增：處理點擊 📎 圖示
  const handleFileClick = () => {
    fileInputRef.current?.click()
  }

  // 3. 新增：處理檔案選取後的動作 (Demo 專用)
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      // 自動將檔名與 Demo 劇本填入對話框
      const attachmentText = `[已夾帶檔案: ${file.name}]\n請幫我分析這組 LRT 量測數據，找出 X/Y 向誤差與背隙的主因，並給我補償參數。`
      setText(prev => prev ? prev + '\n' + attachmentText : attachmentText)
      setTimeout(autoResize, 50) // 延遲一下讓 textarea 自動長高
    }
    // 重置 input，允許重複上傳同一個檔案
    e.target.value = ''
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
              {/* 4. 新增：隱藏的 file input */}
              <input 
                type="file" 
                accept=".csv" 
                className="hidden" 
                ref={fileInputRef} 
                onChange={handleFileChange} 
              />
              
              {['📎', '📊', '🗑'].map(icon => (
                <button key={icon}
                  // 5. 新增：若點擊的是 📎，觸發檔案選取
                  onClick={icon === '📎' ? handleFileClick : undefined}
                  className="w-6 h-6 flex items-center justify-center text-xs
                             text-tx-off hover:text-tx-mid hover:bg-ink-3
                             rounded transition-colors">
                  {icon}
                </button>
              ))}
            </div>
            <button
              onClick={handleSend}
              disabled={!text.trim() || isAnalyzing}
              className="flex items-center gap-1.5 px-3 py-1 rounded
                         font-mono text-[9px] tracking-widest uppercase
                         border transition-all disabled:opacity-30 disabled:cursor-not-allowed
                         border-sig-cyan/30 text-sig-cyan bg-sig-cyan/5
                         hover:bg-sig-cyan/15 hover:border-sig-cyan/55
                         hover:shadow-[0_0_8px_rgba(0,207,255,0.12)]">
              {isAnalyzing ? '處理中...' : '→ 發送'}
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