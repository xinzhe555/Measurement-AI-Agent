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

  // 1. 集中管理所有數位孿生環境參數
  const [pathType, setPathType] = useState<string>('cone')
  const [viewMode, setViewMode] = useState<string>('relative')
  const [ballX, setBallX] = useState<number>(200.0)
  const [ballY, setBallY] = useState<number>(0.0)
  const [ballZ, setBallZ] = useState<number>(0.0)
  const [toolLen, setToolLen] = useState<number>(0.0)

  const errItems = [
    { sym: 'XOC', val: p ? `${p.xoc_um > 0 ? '+' : ''}${p.xoc_um} μm`   : '—', pct: p ? (Math.abs(p.xoc_um)/50)*100 : 0,  color: 'text-sig-amber', bar: '#FFB830' },
    { sym: 'YOC', val: p ? `${p.yoc_um > 0 ? '+' : ''}${p.yoc_um} μm`   : '—', pct: p ? (Math.abs(p.yoc_um)/20)*100 : 0,  color: 'text-sig-lime',  bar: '#7EFF6E' },
    { sym: 'AOC', val: p ? `${p.aoc_deg > 0 ? '+' : ''}${p.aoc_deg} °`: '—', pct: p ? (Math.abs(p.aoc_deg)/0.3)*100:0, color: 'text-sig-red',   bar: '#FF4560' },
    { sym: 'BOA', val: p ? `${p.boa_deg > 0 ? '+' : ''}${p.boa_deg} °`: '—', pct: p ? (Math.abs(p.boa_deg)/0.2)*100:0, color: 'text-sig-amber', bar: '#FFB830' },
    { sym: 'EXC', val: d ? `${d.exc_amp_um} μm`  : '—', pct: d ? (d.exc_amp_um/10)*100  : 0, color: 'text-sig-cyan',   bar: '#00CFFF' },
    { sym: 'EYC', val: d ? `${d.eyc_amp_um} μm`  : '—', pct: d ? (d.eyc_amp_um/10)*100  : 0, color: 'text-sig-cyan',   bar: '#00CFFF' },
    { sym: 'EZC', val: d ? `${d.ezc_amp_um} μm`  : '—', pct: d ? (d.ezc_amp_um/5)*100   : 0, color: 'text-sig-lime',   bar: '#7EFF6E' },
    { sym: 'EAC', val: d ? `${d.eac_deg} °`    : '—', pct: d ? Math.min(d.eac_deg/0.006*100,100): 0, color: 'text-sig-lime', bar: '#7EFF6E' },
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
        
        {/* === 數位孿生卡片 === */}
        <div className="p-3 border-b border-line-0">
          <TwinPanel 
            onExportToAgent={onExportToAgent}
            pathType={pathType} 
            viewMode={viewMode} 
            toolLength={toolLen}
          />
        </div>

        {/* 4格儀表 */}
        <div className="grid grid-cols-2 border-b border-line-0 shrink-0">
          {[
            { lbl: 'XOC',     val: p ? `${p.xoc_um}` : '—',      unit: 'μm',  c: 'text-sig-amber', sub: '靜態偏心 X' },
            { lbl: 'AOC',     val: p ? `${p.aoc_deg}` : '—',    unit: '°',  c: 'text-sig-red',   sub: '阿貝誤差' },
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

        {/* 2. 全新的「量測環境設定區」整合版 */}
        <div className="w-full mb-3 flex flex-col gap-2 text-[10px] font-mono border-t border-line-0 pt-3">
            <div className="text-[11px] text-tx-hi font-bold mb-1">⚙️ 量測環境設定</div>
            
            {/* 軌跡與視角選擇 (取代 TwinPanel 的選項) */}
            <div className="grid grid-cols-2 gap-2 mb-1">
              <label className="flex flex-col gap-1 text-tx-lo">
                軌跡類型
                <select value={pathType} onChange={e=>setPathType(e.target.value)}
                        className="bg-ink-2 border border-line-0 p-1 rounded text-tx-hi outline-none focus:border-sig-cyan">
                  <option value="cone">BK4 圓錐</option>
                  <option value="sine">S 型曲線</option>
                </select>
              </label>
              <label className="flex flex-col gap-1 text-tx-lo">
                觀測視角
                <select value={viewMode} onChange={e=>setViewMode(e.target.value)}
                        className="bg-ink-2 border border-line-0 p-1 rounded text-tx-hi outline-none focus:border-sig-cyan">
                  <option value="relative">相對 (LRT)</option>
                  <option value="absolute">絕對 (機台)</option>
                </select>
              </label>
            </div>

        {/* 座標與刀長設定 */}
            <div className="grid grid-cols-2 gap-2">
                <label className="flex flex-col gap-1 text-tx-lo">
                    球心 X (mm)
                    <input type="number" step="10" value={ballX} onChange={e=>setBallX(Number(e.target.value))} 
                           className="bg-ink-2 border border-line-0 p-1 rounded text-tx-hi outline-none focus:border-sig-cyan" />
                </label>
                <label className="flex flex-col gap-1 text-tx-lo">
                    球心 Y (mm)
                    <input type="number" step="10" value={ballY} onChange={e=>setBallY(Number(e.target.value))} 
                           className="bg-ink-2 border border-line-0 p-1 rounded text-tx-hi outline-none focus:border-sig-cyan" />
                </label>
                <label className="flex flex-col gap-1 text-tx-lo">
                    球心 Z (mm)
                    <input type="number" step="10" value={ballZ} onChange={e=>setBallZ(Number(e.target.value))} 
                           className="bg-ink-2 border border-line-0 p-1 rounded text-tx-hi outline-none focus:border-sig-cyan" />
                </label>
                <label className="flex flex-col gap-1 text-tx-lo font-bold text-sig-amber">
                    刀長 L (mm)
                    <input type="number" step="10" value={toolLen} onChange={e=>setToolLen(Number(e.target.value))} 
                           className="bg-ink-2 border border-sig-amber/50 p-1 rounded text-tx-hi outline-none focus:border-sig-amber" />
                </label>
            </div>
        </div>

        {/* 開始分析按鈕 */}
        <button
          disabled={isAnalyzing}
          onClick={() => onAnalyze({ 
            mode: 'simulate', 
            path_type: pathType,   
            view_mode: viewMode,   
            ball_x: ballX, 
            ball_y: ballY, 
            ball_z: ballZ, 
            tool_length: toolLen,
            run_ai_layer: true 
          })}
          className="w-full py-2 font-mono text-[11px] tracking-widest uppercase
                     rounded border transition-all font-bold
                     disabled:opacity-40 disabled:cursor-not-allowed
                     border-sig-cyan/50 text-sig-cyan bg-sig-cyan/10
                     hover:bg-sig-cyan/20 hover:border-sig-cyan">
          {isAnalyzing ? '分析中...' : '▶  執行數位孿生分析'}
        </button>
      </div>
    </aside>
  )
}