'use client'
// components/layout/Header.tsx
import { useEffect } from 'react'
import { checkHealth } from '@/lib/api'

interface Props {
  backendOk: boolean | null
  setBackendOk: (v: boolean) => void
}

export function Header({ backendOk, setBackendOk }: Props) {
  useEffect(() => {
    checkHealth().then(setBackendOk)
    const t = setInterval(() => checkHealth().then(setBackendOk), 10_000)
    return () => clearInterval(t)
  }, [setBackendOk])

  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-11 flex items-center justify-between
                       bg-ink-1 border-b border-line-1 px-4">
      {/* 左：品牌 */}
      <div className="flex items-center gap-3">
        <svg width="22" height="22" viewBox="0 0 26 26" fill="none">
          <polygon points="13,2 24,7.5 24,18.5 13,24 2,18.5 2,7.5"
            stroke="#00CFFF" strokeWidth="1" fill="rgba(0,207,255,0.06)"/>
          <circle cx="13" cy="13" r="2.5" fill="#00CFFF" opacity="0.8"/>
        </svg>
        <span className="font-mono text-sm font-bold tracking-widest text-tx-hi">
          PREC·<span className="text-sig-cyan">OS</span>
        </span>
        <div className="w-px h-4 bg-line-2"/>
        <span className="font-mono text-[9px] tracking-widest text-tx-lo uppercase">
          BK4 五軸誤差診斷系統 v2.1
        </span>
      </div>

      {/* 中：狀態指示 */}
      <div className="flex items-center gap-5">
        {[
          { label: 'PIGE 模組',  color: 'bg-sig-lime  shadow-sig-lime' },
          { label: 'PDGE 模組',  color: 'bg-sig-cyan  shadow-sig-cyan' },
          { label: 'AI 殘差層',  color: 'bg-sig-amber shadow-sig-amber' },
          { label: 'Agent 診斷', color: 'bg-sig-violet shadow-sig-violet' },
        ].map(({ label, color }) => (
          <div key={label} className="flex items-center gap-1.5 font-mono text-[9px]
                                      tracking-widest text-tx-lo uppercase">
            <span className={`w-1.5 h-1.5 rounded-full animate-blink ${color}
                             shadow-[0_0_4px_currentColor]`}/>
            {label}
          </div>
        ))}
      </div>

      {/* 右：後端狀態 + 工具 */}
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1.5 font-mono text-[9px] tracking-wide
                        text-tx-lo border border-line-2 rounded px-2 py-1">
          <span className={`w-1.5 h-1.5 rounded-full ${
            backendOk === null ? 'bg-tx-off' :
            backendOk ? 'bg-sig-lime shadow-[0_0_5px_#7EFF6E]' :
            'bg-sig-red shadow-[0_0_5px_#FF4560]'
          }`}/>
          {backendOk === null ? 'CHECKING' : backendOk ? 'API ONLINE' : 'API OFFLINE'}
        </div>
        <button className="font-mono text-[9px] tracking-widest text-sig-cyan uppercase
                           border border-sig-cyan/30 rounded px-3 py-1
                           bg-sig-cyan/5 hover:bg-sig-cyan/15 transition-colors">
          + 新建診斷
        </button>
      </div>
    </header>
  )
}
