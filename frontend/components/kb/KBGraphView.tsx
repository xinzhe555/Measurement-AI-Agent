'use client'
// components/kb/KBGraphView.tsx
// Neo4j 知識圖譜視覺化 — 使用 react-force-graph-2d

import { useState, useEffect, useCallback, useRef } from 'react'
import { getGraphData } from '@/lib/api'
import dynamic from 'next/dynamic'

// react-force-graph-2d 需要 dynamic import（它用 canvas，SSR 不支援）
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), { ssr: false })

// 節點顏色對映
const NODE_COLORS: Record<string, string> = {
  Chunk:                   '#00CFFF',  // cyan
  Event:                   '#FFB830',  // amber
  Document:                '#7EFF6E',  // lime
  TNCFunction:             '#FF4560',  // red
  ErrorType:               '#FF6B6B',  // light red
  SoftwareOption:          '#C084FC',  // violet
  MachineParameter:        '#60A5FA',  // blue
  MeasurementPhenomenon:   '#FBBF24',  // yellow
  Summary:                 '#8B949E',  // gray
}

// 邊顏色
const EDGE_COLORS: Record<string, string> = {
  CAUSAL_LINK:     '#FFB830',
  MENTIONS:        '#00CFFF',
  COMPENSATED_BY:  '#FF4560',
  PROCEDURE_STEP:  '#7EFF6E',
  BELONGS_TO:      '#484F58',
  TEMPORAL_NEXT:   '#484F58',
  OCCURRED_IN:     '#484F58',
  REQUIRES_OPTION: '#C084FC',
  CONFIGURED_BY:   '#60A5FA',
  INDICATES:       '#FBBF24',
  SUMMARIZES:      '#8B949E',
}

const EQUIPMENT_OPTIONS = ['', 'LRT', 'Heidenhain', 'BallBar', 'Other']
const NODE_TYPE_OPTIONS = ['', 'Chunk', 'Event', 'Document', 'TNCFunction', 'ErrorType', 'MeasurementPhenomenon']

interface Props {
  onBack: () => void
}

export function KBGraphView({ onBack }: Props) {
  const [graphData, setGraphData] = useState<any>({ nodes: [], links: [] })
  const [loading, setLoading]     = useState(true)
  const [eqFilter, setEqFilter]   = useState('')
  const [ntFilter, setNtFilter]   = useState('')
  const [nodeLimit, setNodeLimit]  = useState(200)
  const [hoverNode, setHoverNode]  = useState<any>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [dimensions, setDimensions] = useState({ w: 800, h: 500 })

  // 取得容器尺寸
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const obs = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect
      setDimensions({ w: width, h: height })
    })
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  const fetchGraph = useCallback(async () => {
    setLoading(true)
    const data = await getGraphData(
      eqFilter || undefined,
      ntFilter || undefined,
      nodeLimit,
    )
    setGraphData(data)
    setLoading(false)
  }, [eqFilter, ntFilter, nodeLimit])

  useEffect(() => {
    fetchGraph()
  }, [fetchGraph])

  return (
    <div className="flex flex-col h-full bg-ink-0">
      {/* 頂部列 */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-line-1 bg-ink-1 shrink-0">
        <div className="flex items-center gap-2">
          <span className="w-1 h-4 rounded-sm bg-sig-violet" />
          <span className="font-sans text-[14px] font-bold text-tx-hi tracking-wide">
            知識圖譜瀏覽器
          </span>
          <span className="font-mono text-[10px] text-tx-lo ml-2">
            {graphData.nodes?.length ?? 0} nodes / {graphData.links?.length ?? 0} edges
          </span>
        </div>
        <button
          onClick={onBack}
          className="font-mono text-[10px] text-sig-cyan hover:text-tx-hi
                     border border-sig-cyan/30 rounded px-3 py-1
                     hover:bg-sig-cyan/10 transition-all"
        >
          ← 返回
        </button>
      </div>

      {/* 篩選列 */}
      <div className="flex items-center gap-3 px-5 py-2 border-b border-line-0 bg-ink-1/50 shrink-0">
        <span className="font-mono text-[9px] text-tx-lo">篩選</span>

        <select value={eqFilter} onChange={e => setEqFilter(e.target.value)}
          className="bg-ink-2 border border-line-2 rounded px-2 py-1
                     font-mono text-[10px] text-tx-mid outline-none">
          <option value="">Equipment: 全部</option>
          {EQUIPMENT_OPTIONS.filter(Boolean).map(eq => (
            <option key={eq} value={eq}>{eq}</option>
          ))}
        </select>

        <select value={ntFilter} onChange={e => setNtFilter(e.target.value)}
          className="bg-ink-2 border border-line-2 rounded px-2 py-1
                     font-mono text-[10px] text-tx-mid outline-none">
          <option value="">節點類型: 全部</option>
          {NODE_TYPE_OPTIONS.filter(Boolean).map(nt => (
            <option key={nt} value={nt}>{nt}</option>
          ))}
        </select>

        <select value={nodeLimit} onChange={e => setNodeLimit(Number(e.target.value))}
          className="bg-ink-2 border border-line-2 rounded px-2 py-1
                     font-mono text-[10px] text-tx-mid outline-none">
          {[50, 100, 200, 500].map(n => (
            <option key={n} value={n}>上限: {n}</option>
          ))}
        </select>

        {/* 圖例 */}
        <div className="flex-1" />
        <div className="flex items-center gap-2 flex-wrap">
          {Object.entries(NODE_COLORS).slice(0, 6).map(([label, color]) => (
            <div key={label} className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full" style={{ background: color }} />
              <span className="font-mono text-[8px] text-tx-lo">{label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 圖譜區域 */}
      <div ref={containerRef} className="flex-1 relative">
        {loading ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="font-mono text-[12px] text-tx-lo">載入圖譜中...</span>
          </div>
        ) : graphData.nodes?.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="font-mono text-[12px] text-tx-lo">目前無圖譜資料（請先上傳文件）</span>
          </div>
        ) : (
          <ForceGraph2D
            graphData={graphData}
            width={dimensions.w}
            height={dimensions.h}
            backgroundColor="#0D1117"
            nodeLabel={(node: any) => `[${node.label}] ${node.name}`}
            nodeColor={(node: any) => NODE_COLORS[node.label] ?? '#8B949E'}
            nodeRelSize={5}
            nodeVal={(node: any) => {
              // 讓重要節點更大
              if (node.label === 'TNCFunction' || node.label === 'Document') return 8
              if (node.label === 'ErrorType' || node.label === 'MeasurementPhenomenon') return 6
              return 3
            }}
            linkColor={(link: any) => EDGE_COLORS[link.type] ?? '#30363D'}
            linkWidth={1}
            linkDirectionalArrowLength={4}
            linkDirectionalArrowRelPos={1}
            linkLabel={(link: any) => link.type}
            onNodeHover={(node: any) => setHoverNode(node)}
            nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
              const label = node.name?.slice(0, 15) || ''
              const fontSize = Math.max(10 / globalScale, 2)
              const nodeR = Math.sqrt(node.label === 'TNCFunction' || node.label === 'Document' ? 8 : node.label === 'ErrorType' ? 6 : 3) * 5

              // 圓形
              ctx.beginPath()
              ctx.arc(node.x, node.y, nodeR, 0, 2 * Math.PI)
              ctx.fillStyle = NODE_COLORS[node.label] ?? '#8B949E'
              ctx.fill()

              // 標籤（夠大才顯示）
              if (globalScale > 0.8) {
                ctx.font = `${fontSize}px Consolas, monospace`
                ctx.textAlign = 'center'
                ctx.textBaseline = 'top'
                ctx.fillStyle = '#E6EDF3'
                ctx.fillText(label, node.x, node.y + nodeR + 2)
              }
            }}
          />
        )}

        {/* Hover 資訊面板 */}
        {hoverNode && (
          <div className="absolute top-3 right-3 bg-ink-2/95 border border-line-2
                          rounded-lg p-3 max-w-[280px] pointer-events-none
                          shadow-lg backdrop-blur-sm">
            <div className="font-mono text-[10px] text-tx-lo mb-1">{hoverNode.label}</div>
            <div className="font-sans text-[12px] text-tx-hi break-words">{hoverNode.name}</div>
          </div>
        )}
      </div>
    </div>
  )
}
