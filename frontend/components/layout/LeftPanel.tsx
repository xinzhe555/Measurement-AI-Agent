'use client'
// components/layout/LeftPanel.tsx
import { useState } from 'react'
import type { AnalyzeResponse, AnalyzeRequest } from '@/lib/types'
import TwinPanel from '../cards/TwinPanel'
import MeasurementUpload, { type MeasuredPoint } from '../cards/MeasurementUpload'

interface Props {
  analysis: AnalyzeResponse | null
  isAnalyzing: boolean
  onAnalyze: (req: AnalyzeRequest) => void
  onExportToAgent?: (chartData: any[], viewMode: string) => void
  onSetCenterMode?: (mode: 'chat' | 'kb' | 'graph') => void
  centerMode?: 'chat' | 'kb' | 'graph'
}

/* ── 可收合區段 ─────────────────────────────────────────── */
function Section({ title, accent, badge, defaultOpen = false, children }: {
  title: string; accent: string; badge?: string; defaultOpen?: boolean; children: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border-b border-line-0">
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-4 py-2.5 hover:bg-ink-2 transition-colors">
        <span className={`w-1 h-3 rounded-sm ${accent}`} />
        <span className="font-mono text-[11px] font-bold text-tx-hi tracking-wider flex-1 text-left">{title}</span>
        {badge && <span className="text-[8px] font-mono px-1.5 py-0.5 rounded bg-ink-3 text-tx-lo">{badge}</span>}
        <span className={`text-tx-lo text-[10px] transition-transform ${open ? 'rotate-180' : ''}`}>▾</span>
      </button>
      {open && <div className="px-4 pb-3">{children}</div>}
    </div>
  )
}

export function LeftPanel({ analysis, isAnalyzing, onAnalyze, onExportToAgent, onSetCenterMode, centerMode }: Props) {
  const p = analysis?.pige
  const d = analysis?.pdge

  const [uploadedData, setUploadedData] = useState<MeasuredPoint[] | null>(null)
  const [pathType, setPathType] = useState<string>('cone')
  const [viewMode, setViewMode] = useState<string>('relative')
  const [ballX, setBallX] = useState<number>(200.0)
  const [ballY, setBallY] = useState<number>(0.0)
  const [ballZ, setBallZ] = useState<number>(0.0)
  const [toolLen, setToolLen] = useState<number>(0.0)

  // 所有誤差項定義（含顯著性門檻用的正規化比例 & 類別標籤）
  const allErrItems = [
    // PIGEs — 平移類
    { sym: 'XOC', raw: p ? Math.abs(p.xoc_um) : 0, val: p ? `${p.xoc_um > 0 ? '+' : ''}${p.xoc_um} μm`  : '—', pct: p ? (Math.abs(p.xoc_um)/50)*100 : 0,  color: 'text-sig-amber', bar: '#FFB830', cat: 'PIGE', sub: '靜態偏心 X',  unit: 'μm', numVal: p?.xoc_um ?? 0, threshold: 5 },
    { sym: 'YOC', raw: p ? Math.abs(p.yoc_um) : 0, val: p ? `${p.yoc_um > 0 ? '+' : ''}${p.yoc_um} μm`  : '—', pct: p ? (Math.abs(p.yoc_um)/20)*100 : 0,  color: 'text-sig-lime',  bar: '#7EFF6E', cat: 'PIGE', sub: '靜態偏心 Y',  unit: 'μm', numVal: p?.yoc_um ?? 0, threshold: 5 },
    { sym: 'YOA', raw: p ? Math.abs(p.yoa_um) : 0, val: p ? `${p.yoa_um > 0 ? '+' : ''}${p.yoa_um} μm`  : '—', pct: p ? (Math.abs(p.yoa_um)/50)*100 : 0,  color: 'text-sig-lime',  bar: '#7EFF6E', cat: 'PIGE', sub: 'A軸偏移 Y',  unit: 'μm', numVal: p?.yoa_um ?? 0, threshold: 5 },
    { sym: 'ZOA', raw: p ? Math.abs(p.zoa_um) : 0, val: p ? `${p.zoa_um > 0 ? '+' : ''}${p.zoa_um} μm`  : '—', pct: p ? (Math.abs(p.zoa_um)/50)*100 : 0,  color: 'text-sig-lime',  bar: '#7EFF6E', cat: 'PIGE', sub: 'A軸偏移 Z',  unit: 'μm', numVal: p?.zoa_um ?? 0, threshold: 5 },
    // PIGEs — 角度類
    { sym: 'AOC', raw: p ? Math.abs(p.aoc_deg) : 0, val: p ? `${p.aoc_deg > 0 ? '+' : ''}${p.aoc_deg} °` : '—', pct: p ? (Math.abs(p.aoc_deg)/0.3)*100:0, color: 'text-sig-red',   bar: '#FF4560', cat: 'PIGE', sub: '阿貝誤差',    unit: '°',  numVal: p?.aoc_deg ?? 0, threshold: 0.001 },
    { sym: 'BOA', raw: p ? Math.abs(p.boa_deg) : 0, val: p ? `${p.boa_deg > 0 ? '+' : ''}${p.boa_deg} °` : '—', pct: p ? (Math.abs(p.boa_deg)/0.2)*100:0, color: 'text-sig-amber', bar: '#FFB830', cat: 'PIGE', sub: 'A軸 Yaw',     unit: '°',  numVal: p?.boa_deg ?? 0, threshold: 0.001 },
    // PDGEs
    { sym: 'EXC', raw: d ? d.exc_amp_um : 0,        val: d ? `${d.exc_amp_um} μm`  : '—', pct: d ? (d.exc_amp_um/10)*100  : 0, color: 'text-sig-cyan',   bar: '#00CFFF', cat: 'PDGE', sub: '徑向跳動 X',  unit: 'μm', numVal: d?.exc_amp_um ?? 0, threshold: 1 },
    { sym: 'EYC', raw: d ? d.eyc_amp_um : 0,        val: d ? `${d.eyc_amp_um} μm`  : '—', pct: d ? (d.eyc_amp_um/10)*100  : 0, color: 'text-sig-cyan',   bar: '#00CFFF', cat: 'PDGE', sub: '徑向跳動 Y',  unit: 'μm', numVal: d?.eyc_amp_um ?? 0, threshold: 1 },
    { sym: 'EZC', raw: d ? d.ezc_amp_um : 0,        val: d ? `${d.ezc_amp_um} μm`  : '—', pct: d ? (d.ezc_amp_um/5)*100   : 0, color: 'text-sig-lime',   bar: '#7EFF6E', cat: 'PDGE', sub: '軸向竄動 Z',  unit: 'μm', numVal: d?.ezc_amp_um ?? 0, threshold: 1 },
    { sym: 'EAC', raw: d ? d.eac_deg : 0,           val: d ? `${d.eac_deg} °`      : '—', pct: d ? Math.min(d.eac_deg/0.006*100,100): 0, color: 'text-sig-lime', bar: '#7EFF6E', cat: 'PDGE', sub: '搖擺 A', unit: '°', numVal: d?.eac_deg ?? 0, threshold: 0.001 },
  ]

  // 依顯著性排序（raw / threshold 越大越顯著），取前 4 個做快速儀表
  const topItems = [...allErrItems]
    .filter(e => e.raw > 0)
    .sort((a, b) => (b.raw / b.threshold) - (a.raw / a.threshold))
    .slice(0, 4)

  // errItems 保留全部供 PIGE/PDGE 列表用
  const errItems = allErrItems

  const ring = analysis?.rms
    ? Math.round((1 - (analysis.rms.after_phys_dx_um / analysis.rms.before_dx_um)) * 100)
    : 0
  const circumference = 182.2
  const dash = circumference - (ring / 100) * circumference

  return (
    <aside className="w-72 flex-shrink-0 bg-ink-1 border-r border-line-0 flex flex-col overflow-hidden">

      {/* 標題 */}
      <div className="flex items-center gap-2 px-4 py-3 bg-ink-2 border-b-2 border-line-1 shrink-0">
        <span className="w-1 h-3.5 rounded-sm bg-sig-cyan"/>
        <span className="font-sans text-[13px] font-bold tracking-wider text-tx-hi">
          PREC·OS 控制面板
        </span>
      </div>

      {/* 內容捲動區 */}
      <div className="flex-1 overflow-y-auto scrollbar-custom flex flex-col">

        {/* ═══ 0. 知識庫管理 ═══ */}
        <Section title="知識庫管理" accent="bg-sig-amber" badge="KB">
          <div className="flex flex-col gap-1.5">
            <button
              onClick={() => onSetCenterMode?.(centerMode === 'kb' ? 'chat' : 'kb')}
              className={`w-full py-2 font-mono text-[11px] tracking-wide rounded
                          border transition-all
                          ${centerMode === 'kb'
                            ? 'border-sig-amber/50 text-sig-amber bg-sig-amber/10'
                            : 'border-line-2 text-tx-mid hover:text-tx-hi hover:border-sig-amber/30 hover:bg-ink-3'
                          }`}
            >
              {centerMode === 'kb' ? '← 返回對話模式' : '檔案管理 →'}
            </button>
            <button
              onClick={() => onSetCenterMode?.(centerMode === 'graph' ? 'chat' : 'graph')}
              className={`w-full py-2 font-mono text-[11px] tracking-wide rounded
                          border transition-all
                          ${centerMode === 'graph'
                            ? 'border-sig-violet/50 text-sig-violet bg-sig-violet/10'
                            : 'border-line-2 text-tx-mid hover:text-tx-hi hover:border-sig-violet/30 hover:bg-ink-3'
                          }`}
            >
              {centerMode === 'graph' ? '← 返回對話模式' : '圖譜瀏覽 →'}
            </button>
          </div>
        </Section>

        {/* ═══ 1. 量測數據匯入 ═══ */}
        <Section title="量測數據匯入" accent="bg-sig-amber" defaultOpen={true}>
          <MeasurementUpload onDataReady={(data) => setUploadedData(data)} />
        </Section>

        {/* ═══ 2. 數位孿生生成器 ═══ */}
        <Section title="數位孿生生成器" accent="bg-sig-cyan" badge="Twin">
          <TwinPanel
            onExportToAgent={onExportToAgent}
            pathType={pathType}
            viewMode={viewMode}
            toolLength={toolLen}
          />
        </Section>

        {/* ═══ 3. 辨識結果 ═══ */}
        <Section title="辨識結果" accent="bg-sig-lime" defaultOpen={true}
          badge={analysis ? 'OK' : undefined}>

          {/* 動態快速儀表 — 取顯著性最高的 4 項 */}
          <div className="grid grid-cols-2 gap-2 mb-3">
            {(topItems.length > 0 ? topItems : [
              { sym: '—', numVal: 0, unit: '', color: 'text-tx-lo', sub: '尚無數據' },
              { sym: '—', numVal: 0, unit: '', color: 'text-tx-lo', sub: '尚無數據' },
              { sym: '—', numVal: 0, unit: '', color: 'text-tx-lo', sub: '尚無數據' },
              { sym: '—', numVal: 0, unit: '', color: 'text-tx-lo', sub: '尚無數據' },
            ]).map((item, idx) => (
              <div key={item.sym + idx} className="bg-ink-2 rounded p-2 border border-line-0">
                <div className="font-mono text-[7.5px] tracking-wider text-tx-lo mb-1">{item.sym}</div>
                <div className={`font-mono text-base font-bold leading-none ${item.color}`}>
                  {item.numVal !== 0 ? item.numVal : '—'}
                  <span className="text-[8px] font-light opacity-60 ml-0.5">{item.unit}</span>
                </div>
                <div className="font-mono text-[7px] text-tx-lo mt-1">{item.sub}</div>
              </div>
            ))}
          </div>

          {/* PIGE 列表 */}
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-[7.5px] tracking-widest uppercase text-tx-lo">PIGE</span>
            <span className="flex-1 h-px bg-line-0"/>
          </div>
          <div className="flex flex-col gap-1 mb-3">
            {errItems.filter(e => e.cat === 'PIGE').map(item => (
              <div key={item.sym} className="flex items-center gap-2 py-1 hover:bg-ink-2 rounded px-1 transition-colors">
                <span className={`font-mono text-[10px] font-medium w-8 ${item.color}`}>{item.sym}</span>
                <div className="flex-1 h-[3px] bg-line-1 rounded overflow-hidden">
                  <div className="h-full rounded transition-all duration-1000"
                    style={{ width: `${Math.min(item.pct, 100)}%`, background: item.bar }}/>
                </div>
                <span className={`font-mono text-[9px] w-20 text-right ${item.color}`}>{item.val}</span>
              </div>
            ))}
          </div>

          {/* PDGE 列表 */}
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-[7.5px] tracking-widest uppercase text-tx-lo">PDGE</span>
            <span className="flex-1 h-px bg-line-0"/>
          </div>
          <div className="flex flex-col gap-1">
            {errItems.filter(e => e.cat === 'PDGE').map(item => (
              <div key={item.sym} className="flex items-center gap-2 py-1 hover:bg-ink-2 rounded px-1 transition-colors">
                <span className={`font-mono text-[10px] font-medium w-8 ${item.color}`}>{item.sym}</span>
                <div className="flex-1 h-[3px] bg-line-1 rounded overflow-hidden">
                  <div className="h-full rounded transition-all duration-1000"
                    style={{ width: `${Math.min(item.pct, 100)}%`, background: item.bar }}/>
                </div>
                <span className={`font-mono text-[9px] w-20 text-right ${item.color}`}>{item.val}</span>
              </div>
            ))}
          </div>
        </Section>

        {/* ═══ 4. 量測環境設定 ═══ */}
        <Section title="量測環境設定" accent="bg-tx-lo">
          <div className="flex flex-col gap-3 text-[10px] font-mono">
            <div className="grid grid-cols-2 gap-2">
              <label className="flex flex-col gap-1 text-tx-lo">
                軌跡類型
                <select value={pathType} onChange={e=>setPathType(e.target.value)}
                  className="bg-ink-2 border border-line-0 p-1.5 rounded text-tx-hi outline-none focus:border-sig-cyan">
                  <option value="cone">BK4 圓錐 (K4)</option>
                  <option value="K1">K1 搖籃軸</option>
                  <option value="K2">K2 C軸</option>
                  <option value="sine">S 型曲線</option>
                </select>
              </label>
              <label className="flex flex-col gap-1 text-tx-lo">
                觀測視角
                <select value={viewMode} onChange={e=>setViewMode(e.target.value)}
                  className="bg-ink-2 border border-line-0 p-1.5 rounded text-tx-hi outline-none focus:border-sig-cyan">
                  <option value="relative">相對 (LRT)</option>
                  <option value="absolute">絕對 (機台)</option>
                </select>
              </label>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <label className="flex flex-col gap-1 text-tx-lo">
                球心 X (mm)
                <input type="number" step="10" value={ballX} onChange={e=>setBallX(Number(e.target.value))}
                  className="bg-ink-2 border border-line-0 p-1.5 rounded text-tx-hi outline-none focus:border-sig-cyan" />
              </label>
              <label className="flex flex-col gap-1 text-tx-lo">
                球心 Y (mm)
                <input type="number" step="10" value={ballY} onChange={e=>setBallY(Number(e.target.value))}
                  className="bg-ink-2 border border-line-0 p-1.5 rounded text-tx-hi outline-none focus:border-sig-cyan" />
              </label>
              <label className="flex flex-col gap-1 text-tx-lo">
                球心 Z (mm)
                <input type="number" step="10" value={ballZ} onChange={e=>setBallZ(Number(e.target.value))}
                  className="bg-ink-2 border border-line-0 p-1.5 rounded text-tx-hi outline-none focus:border-sig-cyan" />
              </label>
              <label className="flex flex-col gap-1 text-sig-amber font-bold">
                刀長 L (mm)
                <input type="number" step="10" value={toolLen} onChange={e=>setToolLen(Number(e.target.value))}
                  className="bg-ink-2 border border-sig-amber/50 p-1.5 rounded text-tx-hi outline-none focus:border-sig-amber" />
              </label>
            </div>
          </div>
        </Section>

      </div>

      {/* ═══ 底部固定區：進度環 + 分析按鈕 ═══ */}
      <div className="border-t border-line-0 p-3 flex items-center gap-3 shrink-0 bg-ink-2">

        {/* 進度環 */}
        <div className="relative w-14 h-14 shrink-0">
          <svg className="-rotate-90" width="56" height="56" viewBox="0 0 72 72">
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
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="font-mono text-sm font-bold text-sig-cyan">{ring}%</span>
            <span className="font-mono text-[6px] text-tx-lo tracking-wider">RMS</span>
          </div>
        </div>

        {/* 分析按鈕 */}
        <button
          disabled={isAnalyzing}
          onClick={() => {
            if (uploadedData) {
              onAnalyze({
                mode: 'upload',
                path_type: pathType,
                view_mode: viewMode,
                ball_x: ballX,
                ball_y: ballY,
                ball_z: ballZ,
                tool_length: toolLen,
                dx: uploadedData.map(p => p.dx / 1000),
                dy: uploadedData.map(p => p.dy / 1000),
                dz: uploadedData.map(p => p.dz / 1000),
                a_cmd: uploadedData.map(p => p.a_deg * Math.PI / 180),
                c_cmd: uploadedData.map(p => p.c_deg * Math.PI / 180),
                run_ai_layer: true,
              })
            } else {
              onAnalyze({
                mode: 'simulate',
                path_type: pathType,
                view_mode: viewMode,
                ball_x: ballX,
                ball_y: ballY,
                ball_z: ballZ,
                tool_length: toolLen,
                run_ai_layer: true,
              })
            }
          }}
          className="flex-1 py-2.5 font-mono text-[11px] tracking-widest uppercase
                     rounded border transition-all font-bold
                     disabled:opacity-40 disabled:cursor-not-allowed
                     border-sig-cyan/50 text-sig-cyan bg-sig-cyan/10
                     hover:bg-sig-cyan/20 hover:border-sig-cyan">
          {isAnalyzing ? '分析中...' : uploadedData ? '▶ 分析量測數據' : '▶ 執行模擬分析'}
        </button>
      </div>
    </aside>
  )
}
