'use client'
// components/layout/RightPanel.tsx
import type { AnalyzeResponse, ChatMessage } from '@/lib/types'

interface Props {
  analysis: AnalyzeResponse | null
  messages: ChatMessage[]
  onNewSession: () => void
}

export function RightPanel({ analysis, messages, onNewSession }: Props) {
  const rms = analysis?.rms

  return (
    <aside className="w-56 flex-shrink-0 bg-ink-1 border-l border-line-0 flex flex-col overflow-hidden">

      {/* 標題 */}
      <div className="flex items-center gap-2 px-4 py-3 bg-ink-2 border-b-2 border-line-1">
        <span className="w-1 h-3.5 rounded-sm bg-sig-cyan"/>
        <span className="font-sans text-[13px] font-bold tracking-wider text-tx-hi">
          補償效果與診斷歷史
        </span>
      </div>

      {/* RMS 數字摘要 */}
      {rms && (
        <div className="border-b border-line-0 p-3">
          <div className="font-mono text-[8px] text-tx-lo tracking-widest uppercase mb-2">
            RMS 比較 (μm)
          </div>
          {[
            { ax: 'DX', before: rms.before_dx_um, after: rms.after_phys_dx_um, c: 'text-sig-red',   bar: '#FF4560' },
            { ax: 'DY', before: rms.before_dy_um, after: rms.after_phys_dy_um, c: 'text-sig-lime',  bar: '#7EFF6E' },
            { ax: 'DZ', before: rms.before_dz_um, after: rms.after_phys_dz_um, c: 'text-sig-cyan',  bar: '#00CFFF' },
          ].map(({ ax, before, after, c, bar }) => {
            const beforePct = 100
            const afterPct  = (after / before) * 100
            return (
              <div key={ax} className="flex items-center gap-1.5 mb-1.5">
                <span className={`font-mono text-[9px] w-5 ${c}`}>{ax}</span>
                <div className="flex-1 flex flex-col gap-0.5">
                  <div className="h-[3px] bg-line-1 rounded overflow-hidden">
                    <div className="h-full rounded" style={{ width: `${beforePct}%`, background: bar, opacity: 0.35 }}/>
                  </div>
                  <div className="h-[3px] bg-line-1 rounded overflow-hidden">
                    <div className="h-full rounded transition-all duration-1000"
                      style={{ width: `${afterPct}%`, background: bar }}/>
                  </div>
                </div>
                <div className="font-mono text-[8px] text-tx-lo w-12 text-right leading-tight">
                  <div className="opacity-40">{before}</div>
                  <div className={c}>{after}</div>
                </div>
              </div>
            )
          })}
          {analysis?.ai_r2 && (
            <div className="font-mono text-[8px] text-tx-lo mt-2">
              AI R² = <span className="text-sig-teal">{analysis.ai_r2.toFixed(3)}</span>
            </div>
          )}
        </div>
      )}

      {/* 對話歷史 */}
      <div className="flex-1 overflow-y-auto">
        <div className="flex items-center gap-2 px-3 py-1.5">
          <span className="font-mono text-[7.5px] tracking-widest uppercase text-tx-lo">對話歷史</span>
          <span className="flex-1 h-px bg-line-0"/>
        </div>

        {messages.length === 0 ? (
          <div className="px-3 py-4 text-center font-mono text-[9px] text-tx-lo">
            尚無對話記錄
          </div>
        ) : (
          [...messages].reverse().map((msg) => (
            <div key={msg.id}
              className="px-3 py-2 border-b border-line-0 hover:bg-ink-2 transition-colors cursor-default">
              <div className="flex items-center gap-1.5 mb-1">
                <span className={`font-mono text-[8px] font-medium
                  ${msg.role === 'user' ? 'text-tx-mid' : 'text-sig-cyan'}`}>
                  {msg.role === 'user' ? '研究者' : 'PREC·OS'}
                </span>
                <span className="font-mono text-[8px] text-tx-off">{msg.timestamp}</span>
                {msg.analysisResult && (
                  <span className="font-mono text-[7px] px-1 rounded
                    bg-sig-cyan/10 text-sig-cyan">分析</span>
                )}
              </div>
              <div className="text-[10.5px] text-tx-mid leading-snug
                              whitespace-nowrap overflow-hidden text-ellipsis">
                {msg.content}
              </div>
            </div>
          ))
        )}
      </div>

      {/* 新建 */}
      <div className="border-t border-line-0 p-3">
        <button
          onClick={onNewSession}
          className="w-full py-1.5 font-mono text-[9px] tracking-widest uppercase
                     rounded border border-sig-cyan/20 text-sig-cyan bg-sig-cyan/5
                     hover:bg-sig-cyan/12 transition-colors">
          ＋ 新建診斷對話
        </button>
      </div>
    </aside>
  )
}
