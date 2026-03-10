'use client'
// components/layout/LeftPanel.tsx
import { useState } from 'react'
import type { AnalyzeResponse, AnalyzeRequest } from '@/lib/types'
import TwinPanel from '../cards/TwinPanel'

interface Props {
  analysis: AnalyzeResponse | null
  isAnalyzing: boolean
  onAnalyze: (req: AnalyzeRequest) => void
  onExportToAgent?: (chartData: any[], viewMode: string) => void
}

export function LeftPanel({ analysis, isAnalyzing, onAnalyze, onExportToAgent }: Props) {
  const p = analysis?.pige
  const d = analysis?.pdge

  const [ballX, setBallX] = useState<number>(200.0)
  const [ballY, setBallY] = useState<number>(0.0)
  const [ballZ, setBallZ] = useState<number>(0.0)
  const [toolLen, setToolLen] = useState<number>(0.0)

  const errItems = [
    { sym: 'XOC', val: p ? `${p.xoc_um > 0 ? '+' : ''}${p.xoc_um} μm`   : '—', pct: p ? (Math.abs(p.xoc_um)/50)*100 : 0,  color: 'text-sig-amber', bar: '#FFB830' },
    { sym: 'YOC', val: p ? `${p.yoc_um > 0 ? '+' : ''}${p.yoc_um} μm`   : '—', pct: p ? (Math.abs(p.yoc_um)/20)*100 : 0,  color: 'text-sig-lime',  bar: '#7EFF6E' },
    { sym: 'AOC', val: p ? `${p.aoc_mrad > 0 ? '+' : ''}${p.aoc_mrad} mr`: '—', pct: p ? (Math.abs(p.aoc_mrad)/0.3)*100:0, color: 'text-sig-red',   bar: '#FF4560' },
    { sym: 'BOA', val: p ? `${p.boa_mrad > 0 ? '+' : ''}${p.boa_mrad} mr`: '—', pct: p ? (Math.abs(p.boa_mrad)/0.2)*100:0, color: 'text-sig-amber', bar: '#FFB830' },
    { sym: 'EXC', val: d ? `${d.exc_amp_um} μm`  : '—', pct: d ? (d.exc_amp_um/10)*100  : 0, color: 'text-sig-cyan',   bar: '#00CFFF' },
    { sym: 'EYC', val: d ? `${d.eyc_amp_um} μm`  : '—', pct: d ? (d.eyc_amp_um/10)*100  : 0, color: 'text-sig-cyan',   bar: '#00CFFF' },
    { sym: 'EZC', val: d ? `${d.ezc_amp_um} μm`  : '—', pct: d ? (d.ezc_amp_um/5)*100   : 0, color: 'text-sig-lime',   bar: '#7EFF6E' },
    { sym: 'EAC', val: d ? `${d.eac_mrad} mr`    : '—', pct: d ? Math.min(d.eac_mrad/0.1*100,100): 0, color: 'text-sig-lime', bar: '#7EFF6E' },
  ]

  const ring = analysis?.rms
    ? Math.round((1 - (analysis.rms.after_phys_dx_um / analysis.rms.before_dx_um)) * 100)
    : 0
  const circumference = 182.2
  const dash = circumference - (ring / 100) * circumference

  return (
    <aside className="w-56 flex-shrink-0 bg-ink-1 border-r border-line-0 flex flex-col overflow-hidden">

      {/* 標題 */}
      <div className="flex items-center gap-2 px-4 py-3 bg-ink-2 border-b-2 border-line-1 shrink-0">
        <span className="w-1 h-3.5 rounded-sm bg-sig-cyan"/>
        <span className="font-sans text-[13px] font-bold tracking-wider text-tx-hi">
          即時誤差儀表面板
        </span>
      </div>

      {/* 內容捲動區 */}
      <div className="flex-1 overflow-y-auto scrollbar-custom flex flex-col">
        
        {/* === 新增的數位孿生卡片 === */}
        <div className="p-3 border-b border-line-0">
          <TwinPanel onExportToAgent={onExportToAgent} />
        </div>

        {/* 4格儀表 */}
        <div className="grid grid-cols-2 border-b border-line-0 shrink-0">
          {[
            { lbl: 'XOC',     val: p ? `${p.xoc_um}` : '—',      unit: 'μm',  c: 'text-sig-amber', sub: '靜態偏心 X' },
            { lbl: 'AOC',     val: p ? `${p.aoc_mrad}` : '—',    unit: 'mr',  c: 'text-sig-red',   sub: '阿貝誤差' },
            { lbl: 'EXC',     val: d ? `${d.exc_amp_um}` : '—',  unit: 'μm',  c: 'text-sig-cyan',  sub: '徑向跳動 X' },
            { lbl: 'EYC',     val: d ? `${d.eyc_amp_um}` : '—',  unit: 'μm',  c: 'text-sig-cyan',  sub: '徑向跳動 Y' },
          ].map(({ lbl, val, unit, c, sub }, i) => (
            <div key={lbl}
              className={`p-2.5 border-b border-line-0 ${i % 2 === 0 ? 'border-r' : ''}`}>
              <div className="font-mono text-[7.5px] tracking-wider text-tx-lo mb-1">{lbl}</div>
              <div className={`font-mono text-lg font-bold leading-none ${c}`}>
                {val}<span className="text-[9px] font-light opacity-60 ml-0.5">{unit}</span>
              </div>
              <div className="font-mono text-[7px] text-tx-lo mt-1">{sub}</div>
            </div>
          ))}
        </div>

        {/* 誤差列表 */}
        <div className="flex-1 shrink-0">
          <div className="flex items-center gap-2 px-3 py-1.5">
            <span className="font-mono text-[7.5px] tracking-widest uppercase text-tx-lo">PIGE</span>
            <span className="flex-1 h-px bg-line-0"/>
          </div>
          {errItems.slice(0,4).map(item => (
            <div key={item.sym}
              className="flex items-center gap-2 px-3 py-1.5 border-b border-line-0
                         hover:bg-ink-2 transition-colors">
              <span className={`font-mono text-[10px] font-medium w-8 ${item.color}`}>{item.sym}</span>
              <div className="flex-1 h-[3px] bg-line-1 rounded overflow-hidden">
                <div className="h-full rounded transition-all duration-1000"
                  style={{ width: `${Math.min(item.pct, 100)}%`, background: item.bar }}/>
              </div>
              <span className={`font-mono text-[9px] w-16 text-right ${item.color}`}>{item.val}</span>
            </div>
          ))}

          <div className="flex items-center gap-2 px-3 py-1.5">
            <span className="font-mono text-[7.5px] tracking-widest uppercase text-tx-lo">PDGE</span>
            <span className="flex-1 h-px bg-line-0"/>
          </div>
          {errItems.slice(4).map(item => (
            <div key={item.sym}
              className="flex items-center gap-2 px-3 py-1.5 border-b border-line-0
                         hover:bg-ink-2 transition-colors">
              <span className={`font-mono text-[10px] font-medium w-8 ${item.color}`}>{item.sym}</span>
              <div className="flex-1 h-[3px] bg-line-1 rounded overflow-hidden">
                <div className="h-full rounded transition-all duration-1000"
                  style={{ width: `${Math.min(item.pct, 100)}%`, background: item.bar }}/>
              </div>
              <span className={`font-mono text-[9px] w-16 text-right ${item.color}`}>{item.val}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 補償進度環 (固定在底部) */}
      <div className="border-t border-line-0 p-3 flex flex-col items-center shrink-0">
        
        {/* 進度環 SVG 容器 */}
        <div className="relative w-16 h-16 mb-2">
          <svg className="-rotate-90" width="64" height="64" viewBox="0 0 72 72">
            <circle cx="36" cy="36" r="29" fill="none" stroke="#162232" strokeWidth="7"/>
            <circle cx="36" cy="36" r="29" fill="none"
              stroke="url(#ringGrad)" strokeWidth="7" strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={dash}
              style={{ transition: 'stroke-dashoffset 1.2s cubic-bezier(0.16,1,0.3,1)',
                       filter: 'drop-shadow(0 0 4px #00CFFF)' }}/>
            <defs>
              <linearGradient id="ringGrad">
                <stop offset="0%" stopColor="#00CFFF"/>
                <stop offset="100%" stopColor="#00E8D0"/>
              </linearGradient>
            </defs>
          </svg>
          {/* 修正：把文字補回來 */}
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="font-mono text-base font-bold text-sig-cyan">{ring}%</span>
            <span className="font-mono text-[7px] text-tx-lo tracking-wider">RMS 改善</span>
          </div>
        </div>

        {/* 修正：把文字說明補回來 */}
        <div className="font-mono text-[9px] text-tx-mid text-center leading-relaxed mb-2">
          物理層 HTM 辨識<br/>
          {analysis ? `DX ${analysis.rms.phys_improvement_dx_pct}% / DZ ${analysis.rms.phys_improvement_dz_pct}%` : '等待分析'}
        </div>

        {/* 修正：輸入框拉到外層正確位置 */}
        <div className="w-full mb-2 grid grid-cols-2 gap-2 text-[10px] font-mono">
            <label className="flex flex-col gap-1 text-tx-lo">
                球心 X (mm)
                <input type="number" step="0.1" value={ballX} onChange={e=>setBallX(Number(e.target.value))} 
                       className="bg-ink-2 border border-line-0 p-1 rounded text-tx-hi outline-none focus:border-sig-cyan" />
            </label>
            <label className="flex flex-col gap-1 text-tx-lo">
                球心 Y (mm)
                <input type="number" step="0.1" value={ballY} onChange={e=>setBallY(Number(e.target.value))} 
                       className="bg-ink-2 border border-line-0 p-1 rounded text-tx-hi outline-none focus:border-sig-cyan" />
            </label>
            <label className="flex flex-col gap-1 text-tx-lo">
                球心 Z (mm)
                <input type="number" step="0.1" value={ballZ} onChange={e=>setBallZ(Number(e.target.value))} 
                       className="bg-ink-2 border border-line-0 p-1 rounded text-tx-hi outline-none focus:border-sig-cyan" />
            </label>
            <label className="flex flex-col gap-1 text-tx-lo">
                刀長 (mm)
                <input type="number" step="0.1" value={toolLen} onChange={e=>setToolLen(Number(e.target.value))} 
                       className="bg-ink-2 border border-line-0 p-1 rounded text-tx-hi outline-none focus:border-sig-cyan" />
            </label>
        </div>

        {/* 開始分析按鈕 */}
        <button
          disabled={isAnalyzing}
          onClick={() => onAnalyze({ 
            mode: 'simulate', 
            ball_x: ballX, 
            ball_y: ballY, 
            ball_z: ballZ, 
            tool_length: toolLen,
            run_ai_layer: true 
          })}
          className="mt-1 w-full py-1.5 font-mono text-[10px] tracking-widest uppercase
                     rounded border transition-all
                     disabled:opacity-40 disabled:cursor-not-allowed
                     border-sig-cyan/30 text-sig-cyan bg-sig-cyan/5
                     hover:bg-sig-cyan/15 hover:border-sig-cyan/60">
          {isAnalyzing ? '分析中...' : '▶  開始分析'}
        </button>
      </div>
    </aside>
  )
}