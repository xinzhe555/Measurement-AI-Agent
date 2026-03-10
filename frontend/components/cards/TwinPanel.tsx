"use client"
import React, { useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { CardShell } from './_CardShell'
import path from 'path'

interface TwinPanelProps {
  onExportToAgent?: (chartData: any[], viewMode: string) => void
}

export default function TwinPanel({ onExportToAgent }: TwinPanelProps) {
  const [activeTab, setActiveTab] = useState<'trans' | 'rot' | 'dims' | 'pdge'>('trans')
  const [params, setParams] = useState({
    x_oc: 0, y_oc: -20, z_oc: 0, x_oa: 0, y_oa: 0, z_oa: 0,
    a_oc: 0, b_oc: 0, c_oc: 0, a_oa: 0, b_oa: 0, c_oa: 0,
    pivot_x: 0, pivot_y: 0, pivot_z: 50,
    tool_length: 200, view_mode: 'relative', enable_pdge: false, path_type: 'cone',
  })
  
  const [chartData, setChartData] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isModalOpen, setIsModalOpen] = useState(false)

  const handleSimulate = async () => {
    setIsLoading(true)
    try {
      const res = await fetch('http://localhost:8000/api/twin_simulate', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(params)
      })
      const result = await res.json()
      if (result.status === 'success') {
        const { dx_um, dy_um, dz_um } = result.data
        const formattedData = dx_um.map((dx: number, i: number) => ({
          index: i, dx: Number(dx.toFixed(2)), dy: Number(dy_um[i].toFixed(2)), dz: Number(dz_um[i].toFixed(2))
        }))
        setChartData(formattedData)
        setIsModalOpen(true)
      }
    } catch (error) {
      console.error(error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleExport = () => {
    if (onExportToAgent) {
      onExportToAgent(chartData, params.view_mode)
    }
    setIsModalOpen(false)
  }

  // 渲染不同 Tab 的輸入框
  const renderInputs = () => {
    if (activeTab === 'trans') return (
      <div className="grid grid-cols-2 gap-2">
        {['x_oc', 'y_oc', 'z_oc', 'x_oa', 'y_oa', 'z_oa'].map(k => (
          <div key={k}>
            <label className="block text-tx-mid text-[9px] mb-0.5 font-mono uppercase">{k} (µm)</label>
            <input type="number" className="w-full bg-ink-1 border border-line-1 text-tx-hi text-[10px] rounded px-1.5 py-1"
              value={(params as any)[k]} onChange={e => setParams({...params, [k]: Number(e.target.value)})} />
          </div>
        ))}
      </div>
    )
    if (activeTab === 'rot') return (
      <div className="grid grid-cols-2 gap-2">
        {['a_oc', 'b_oc', 'c_oc', 'a_oa', 'b_oa', 'c_oa'].map(k => (
          <div key={k}>
            <label className="block text-tx-mid text-[9px] mb-0.5 font-mono uppercase">{k} (mrad)</label>
            <input type="number" className="w-full bg-ink-1 border border-line-1 text-tx-hi text-[10px] rounded px-1.5 py-1"
              value={(params as any)[k]} onChange={e => setParams({...params, [k]: Number(e.target.value)})} />
          </div>
        ))}
      </div>
    )
    if (activeTab === 'dims') return (
      <div className="grid grid-cols-2 gap-2">
        {['pivot_x', 'pivot_y', 'pivot_z'].map(k => (
          <div key={k}>
            <label className="block text-tx-mid text-[9px] mb-0.5 font-mono uppercase">{k.replace('_', ' ')} (mm)</label>
            <input type="number" className="w-full bg-ink-1 border border-line-1 text-tx-hi text-[10px] rounded px-1.5 py-1"
              value={(params as any)[k]} onChange={e => setParams({...params, [k]: Number(e.target.value)})} />
          </div>
        ))}
        <div className="col-span-2 mt-1">
          <p className="text-[9px] text-tx-lo leading-relaxed">
            *樞紐尺寸代表量測球到各旋轉軸的實體距離。此參數將啟動阿貝效應，影響角度誤差(AOC/BOC)的投影波型。
          </p>
        </div>
      </div>
    )
    return (
      <div className="flex flex-col gap-2">
        <label className="flex items-center gap-2 text-[10px] text-tx-hi bg-ink-3 p-2 rounded cursor-pointer border border-line-1">
          <input type="checkbox" className="accent-sig-cyan" checked={params.enable_pdge} onChange={e => setParams({...params, enable_pdge: e.target.checked})} />
          疊加真實機台 C 軸高頻動態跳動 (PDGE)
        </label>
        <p className="text-[9px] text-tx-lo">開啟後將引入軸承偏心與伺服不匹配等非線性特徵。</p>
      </div>
    )
  }

  return (
    <>
      <CardShell titleText="數位孿生生成器" titleColor="text-tx-hi" accentColor="#00CFFF" badge="Twin" badgeStyle="bg-sig-cyan/20 text-sig-cyan">
        <div className="p-3 flex flex-col gap-3">
          
          {/* 分類標籤 Tabs */}
          <div className="flex gap-1 border-b border-line-1 pb-1">
            <button onClick={() => setActiveTab('trans')} className={`text-[9px] px-2 py-1 rounded transition ${activeTab === 'trans' ? 'bg-sig-cyan/20 text-sig-cyan' : 'text-tx-lo hover:text-tx-mid'}`}>平移</button>
            <button onClick={() => setActiveTab('rot')} className={`text-[9px] px-2 py-1 rounded transition ${activeTab === 'rot' ? 'bg-sig-cyan/20 text-sig-cyan' : 'text-tx-lo hover:text-tx-mid'}`}>旋轉</button>
            <button onClick={() => setActiveTab('dims')} className={`text-[9px] px-2 py-1 rounded transition ${activeTab === 'dims' ? 'bg-sig-cyan/20 text-sig-cyan' : 'text-tx-lo hover:text-tx-mid'}`}>機台尺寸</button>
            <button onClick={() => setActiveTab('pdge')} className={`text-[9px] px-2 py-1 rounded transition ${activeTab === 'pdge' ? 'bg-sig-cyan/20 text-sig-cyan' : 'text-tx-lo hover:text-tx-mid'}`}>動態</button>
          </div>

          {renderInputs()}

          {/* 共通設定區 */}
          <div className="grid grid-cols-3 gap-2 pt-1 border-t border-line-1">
            {/* 1. 軌跡類型 */}
            <div>
              <label className="block text-tx-mid text-[9px] mb-0.5 font-mono">軌跡類型</label>
              <select className="w-full bg-ink-1 border border-line-1 text-tx-hi text-[10px] rounded px-1.5 py-1"
                value={params.path_type} onChange={e => setParams({...params, path_type: e.target.value})}>
                <option value="cone">NAS 979 圓錐 (A:0-90-0)</option>
                <option value="sine">正弦同動 (A:±30° C:±90°)</option>
              </select>
            </div>
            {/* 2. 刀長 */}
            <div>
              <label className="block text-tx-mid text-[9px] mb-0.5 font-mono">刀長/半徑 (mm)</label>
              <input type="number" className="w-full bg-ink-1 border border-line-1 text-tx-hi text-[10px] rounded px-1.5 py-1"
                value={params.tool_length} onChange={e => setParams({...params, tool_length: Number(e.target.value)})} />
            </div>
            {/* 3. 視角 */}
            <div>
              <label className="block text-tx-mid text-[9px] mb-0.5 font-mono">觀測視角</label>
              <select className="w-full bg-ink-1 border border-line-1 text-tx-hi text-[10px] rounded px-1.5 py-1"
                value={params.view_mode} onChange={e => setParams({...params, view_mode: e.target.value})}>
                <option value="relative">儀器投影 (Relative)</option>
                <option value="absolute">絕對幾何 (Absolute)</option>
              </select>
            </div>
          </div>

          <button onClick={handleSimulate} disabled={isLoading} className="w-full mt-1 py-1.5 font-mono text-[10px] rounded border border-sig-cyan/30 text-sig-cyan bg-sig-cyan/5 hover:bg-sig-cyan/15 transition disabled:opacity-50">
            {isLoading ? '生成中...' : '▶ 執行軌跡生成'}
          </button>
        </div>
      </CardShell>

      {/* 彈出大圖表 */}
      {isModalOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-8">
          <div className="bg-ink-1 border border-line-1 rounded-xl w-full max-w-5xl h-[70vh] flex flex-col p-6 shadow-2xl relative">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-tx-hi">📊 軌跡波型預覽</h2>
              <button onClick={() => setIsModalOpen(false)} className="text-tx-mid hover:text-sig-red text-xl">✕</button>
            </div>
            
            <div className="flex-1 w-full bg-ink-2 rounded border border-line-2 p-2">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                  <XAxis dataKey="index" stroke="#888" tick={false} />
                  <YAxis stroke="#888" tick={{fontSize: 12}} />
                  <Tooltip contentStyle={{ backgroundColor: '#1A1A1A', border: 'none' }} />
                  <Legend />
                  <Line type="monotone" dataKey="dx" name="ΔX" stroke="#FF5C5C" dot={false} />
                  <Line type="monotone" dataKey="dy" name="ΔY" stroke="#228B22" dot={false} />
                  <Line type="monotone" dataKey="dz" name="ΔZ" stroke="#4da6ff" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            
            {/* 匯入 Agent 的魔術按鈕 */}
            <button 
              onClick={handleExport}
              className="mt-6 w-full py-3 bg-sig-cyan text-ink-1 text-sm font-bold tracking-widest rounded shadow-[0_0_15px_rgba(0,207,255,0.4)] hover:bg-opacity-90 transition"
            >
              🚀 將此波型匯入至 Agent 進行根因診斷
            </button>
          </div>
        </div>
      )}
    </>
  )
}