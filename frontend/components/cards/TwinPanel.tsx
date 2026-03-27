"use client"
import React, { useState, useRef } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { CardShell } from './_CardShell'
import ExcelJS from 'exceljs'
import { saveAs } from 'file-saver'
import html2canvas from 'html2canvas'

interface TwinPanelProps {
  onExportToAgent?: (chartData: any[], viewMode: string) => void
  pathType: string
  viewMode: string
  toolLength: number
}

export default function TwinPanel({ onExportToAgent, pathType, viewMode, toolLength }: TwinPanelProps) {
  const [activeTab, setActiveTab] = useState<'trans' | 'rot' | 'dims' | 'pdge'>('trans')
  const [params, setParams] = useState({
    x_oc: 0, y_oc: 0, z_oc: 0, x_oa: 0, y_oa: 0, z_oa: 0,
    a_oc: 0, b_oc: 0, c_oc: 0, a_oa: 0, b_oa: 0, c_oa: 0,
    pivot_x: 0, pivot_y: 0, pivot_z: 0,
    enable_pdge: false,
    n_points: 19
  })
  
  const [chartData, setChartData] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isModalOpen, setIsModalOpen] = useState(false)
  
  // 🔴 新增：用來抓取圖表區塊進行截圖的 Ref
  const chartContainerRef = useRef<HTMLDivElement>(null)

  const handleSimulate = async () => {
    setIsLoading(true)
    try {
      const payload = {
        ...params,
        path_type: pathType,
        view_mode: viewMode,
        tool_length: toolLength
      }
      const res = await fetch('http://localhost:8000/api/twin_simulate', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
      })
      const result = await res.json()
      if (result.status === 'success') {
        const { dx_um, dy_um, dz_um, a_deg, c_deg } = result.data
        // 🔴 修改：將 A 軸與 C 軸角度加入前端狀態中
        const formattedData = dx_um.map((dx: number, i: number) => ({
          index: i, 
          a_axis: a_deg ? Number(a_deg[i].toFixed(2)) : 0,
          c_axis: c_deg ? Number(c_deg[i].toFixed(2)) : 0,
          dx: Number(dx.toFixed(4)), 
          dy: Number(dy_um[i].toFixed(4)), 
          dz: Number(dz_um[i].toFixed(4))
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

  const handleExportToAgent = () => {
    if (onExportToAgent) {
      onExportToAgent(chartData, viewMode)
    }
    setIsModalOpen(false)
  }

  // 🔴 新增：匯出 Excel 的核心邏輯
  const handleExportExcel = async () => {
    try {
      const workbook = new ExcelJS.Workbook()
      workbook.creator = 'Digital Twin System'
      workbook.created = new Date()

      // --- Sheet 1: 誤差參數設定 ---
      const sheetParams = workbook.addWorksheet('誤差參數設定')
      sheetParams.columns = [
        { header: '參數類別', key: 'category', width: 20 },
        { header: '誤差代號', key: 'name', width: 20 },
        { header: '設定數值', key: 'value', width: 15 },
        { header: '單位', key: 'unit', width: 10 }
      ]
      
      // 填入 PIGE 與 PDGE 資料
      const pigeKeys = [
        { k: 'x_oc', n: 'X_OC (X軸平移)', u: 'mm', c: 'PIGE (線性)' },
        { k: 'y_oc', n: 'Y_OC (Y軸平移)', u: 'mm', c: 'PIGE (線性)' },
        { k: 'z_oc', n: 'Z_OC (Z軸平移)', u: 'mm', c: 'PIGE (線性)' },
        { k: 'x_oa', n: 'X_OA', u: 'mm', c: 'PIGE (線性)' },
        { k: 'y_oa', n: 'Y_OA', u: 'mm', c: 'PIGE (線性)' },
        { k: 'z_oa', n: 'Z_OA', u: 'mm', c: 'PIGE (線性)' },
        { k: 'a_oc', n: 'A_OC (X軸滾轉)', u: 'deg', c: 'PIGE (旋轉)' },
        { k: 'b_oc', n: 'B_OC (Y軸滾轉)', u: 'deg', c: 'PIGE (旋轉)' },
        { k: 'c_oc', n: 'C_OC (Z軸滾轉)', u: 'deg', c: 'PIGE (旋轉)' },
        { k: 'a_oa', n: 'A_OA', u: 'deg', c: 'PIGE (旋轉)' },
        { k: 'b_oa', n: 'B_OA', u: 'deg', c: 'PIGE (旋轉)' },
        { k: 'c_oa', n: 'C_OA', u: 'deg', c: 'PIGE (旋轉)' }
      ]
      
      pigeKeys.forEach(p => {
        sheetParams.addRow({ category: p.c, name: p.n, value: (params as any)[p.k], unit: p.u })
      })
      sheetParams.addRow({ category: 'PDGE', name: '動態幾何誤差', value: params.enable_pdge ? '啟用' : '未啟用', unit: '-' })

      // --- Sheet 2: 軌跡與量測數據 ---
      const sheetData = workbook.addWorksheet('軌跡量測數據')
      sheetData.columns = [
        { header: '點位序號', key: 'index', width: 10 },
        { header: 'A軸角度 (deg)', key: 'a_axis', width: 15 },
        { header: 'C軸角度 (deg)', key: 'c_axis', width: 15 },
        { header: '偏差 Err_X (µm)', key: 'dx', width: 15 },
        { header: '偏差 Err_Y (µm)', key: 'dy', width: 15 },
        { header: '偏差 Err_Z (µm)', key: 'dz', width: 15 }
      ]
      sheetData.addRows(chartData)

      // --- Sheet 3: 視覺化圖表 ---
      const sheetChart = workbook.addWorksheet('圖表預覽')
      if (chartContainerRef.current) {
        // 使用 html2canvas 將圖表轉為圖片
        const canvas = await html2canvas(chartContainerRef.current, {
          background: '#1A1A1A' // 保持暗色背景
        })
        const base64Image = canvas.toDataURL('image/png')
        
        // 將圖片加入 Excel 活頁簿
        const imageId = workbook.addImage({
          base64: base64Image,
          extension: 'png',
        })
        
        // 放置圖片到 Sheet 3 的指定儲存格範圍
        sheetChart.addImage(imageId, {
          tl: { col: 1, row: 1 },
          ext: { width: 800, height: 400 }
        })
      }

      // --- 觸發下載 ---
      const buffer = await workbook.xlsx.writeBuffer()
      const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
      saveAs(blob, `Twin_Simulation_${new Date().getTime()}.xlsx`)

    } catch (err) {
      console.error('匯出 Excel 失敗', err)
      alert('匯出失敗，請檢查主控台訊息。')
    }
  }

  // 渲染不同 Tab 的輸入框
  const renderInputs = () => {
    // ...(這部分維持原樣，不需更動)...
    if (activeTab === 'trans') return (
      <div className="grid grid-cols-2 gap-2">
        {['x_oc', 'y_oc', 'z_oc', 'x_oa', 'y_oa', 'z_oa'].map(k => (
          <div key={k}>
            <label className="block text-tx-mid text-[9px] mb-0.5 font-mono uppercase">{k} (mm)</label>
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
            <label className="block text-tx-mid text-[9px] mb-0.5 font-mono uppercase">{k} (deg)</label>
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
      </div>
    )
    return (
      <div className="flex flex-col gap-2">
        <label className="flex items-center gap-2 text-[10px] text-tx-hi bg-ink-3 p-2 rounded cursor-pointer border border-line-1">
          <input type="checkbox" className="accent-sig-cyan" checked={params.enable_pdge} onChange={e => setParams({...params, enable_pdge: e.target.checked})} />
          疊加真實機台 C 軸高頻動態跳動 (PDGE)
        </label>
      </div>
    )
  }

  return (
    <>
      <CardShell titleText="數位孿生生成器" titleColor="text-tx-hi" accentColor="#00CFFF" badge="Twin" badgeStyle="bg-sig-cyan/20 text-sig-cyan">
        <div className="p-3 flex flex-col gap-3">
          
          <div className="flex gap-1 border-b border-line-1 pb-1">
            <button onClick={() => setActiveTab('trans')} className={`text-[9px] px-2 py-1 rounded transition ${activeTab === 'trans' ? 'bg-sig-cyan/20 text-sig-cyan' : 'text-tx-lo hover:text-tx-mid'}`}>平移</button>
            <button onClick={() => setActiveTab('rot')} className={`text-[9px] px-2 py-1 rounded transition ${activeTab === 'rot' ? 'bg-sig-cyan/20 text-sig-cyan' : 'text-tx-lo hover:text-tx-mid'}`}>旋轉</button>
            <button onClick={() => setActiveTab('dims')} className={`text-[9px] px-2 py-1 rounded transition ${activeTab === 'dims' ? 'bg-sig-cyan/20 text-sig-cyan' : 'text-tx-lo hover:text-tx-mid'}`}>機台尺寸</button>
            <button onClick={() => setActiveTab('pdge')} className={`text-[9px] px-2 py-1 rounded transition ${activeTab === 'pdge' ? 'bg-sig-cyan/20 text-sig-cyan' : 'text-tx-lo hover:text-tx-mid'}`}>動態</button>
          </div>

          {renderInputs()}

          <div className="flex items-center justify-between border-t border-line-1 pt-2 mt-1">
            <label className="text-[10px] text-tx-mid">取樣密度 (資料點數):</label>
            <select 
              className="bg-ink-1 border border-line-1 text-tx-hi text-[10px] rounded px-1.5 py-1 w-3/5"
              value={params.n_points}
              onChange={e => setParams({...params, n_points: Number(e.target.value)})}
            >
              <option value={19}>19 點 (C軸20度 - 實機格式)</option>
              <option value={37}>37 點 (C軸10度)</option>
              <option value={360}>360 點 (1度平滑預覽)</option>
            </select>
          </div>

          <button onClick={handleSimulate} disabled={isLoading} className="w-full mt-1 py-1.5 font-mono text-[10px] rounded border border-sig-cyan/30 text-sig-cyan bg-sig-cyan/5 hover:bg-sig-cyan/15 transition disabled:opacity-50">
            {isLoading ? '生成中...' : '▶ 執行軌跡圖形預覽'}
          </button>
        </div>
      </CardShell>

      {/* 彈出大圖表 Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-8">
          <div className="bg-ink-1 border border-line-1 rounded-xl w-full max-w-5xl h-[70vh] flex flex-col p-6 shadow-2xl relative">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-tx-hi">📊 軌跡波型預覽</h2>
              <button onClick={() => setIsModalOpen(false)} className="text-tx-mid hover:text-sig-red text-xl">✕</button>
            </div>
            
            {/* 🔴 加入 Ref 以便讓 html2canvas 截取這個區塊 */}
            <div ref={chartContainerRef} className="flex-1 w-full bg-ink-2 rounded border border-line-2 p-2 relative">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                  {/* 使用 A 軸角度作為 X 軸標籤，讓視覺化更有工程意義 */}
                  <XAxis dataKey="a_axis" stroke="#888" tick={{fontSize: 12}} label={{ value: 'A 軸角度 (deg)', position: 'insideBottomRight', fill: '#888', offset: -5 }} />
                  <YAxis stroke="#888" tick={{fontSize: 12}} label={{ value: '誤差 (µm)', angle: -90, position: 'insideLeft', fill: '#888' }} />
                  <Tooltip contentStyle={{ backgroundColor: '#1A1A1A', border: 'none' }} labelFormatter={(label) => `A 軸角度: ${label}°`} />
                  <Legend />
                  <Line type="monotone" dataKey="dx" name="ΔX (Err_X)" stroke="#FF5C5C" dot={false} />
                  <Line type="monotone" dataKey="dy" name="ΔY (Err_Y)" stroke="#228B22" dot={false} />
                  <Line type="monotone" dataKey="dz" name="ΔZ (Err_Z)" stroke="#4da6ff" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            
            {/* 🔴 按鈕區塊：加入匯出 Excel 按鈕 */}
            <div className="mt-6 flex gap-4">
              <button 
                onClick={handleExportExcel}
                className="flex-1 py-3 bg-ink-3 border border-line-1 text-tx-hi text-sm font-bold tracking-widest rounded hover:bg-ink-4 transition flex items-center justify-center gap-2"
              >
                📥 匯出 Excel (含參數、數據與圖表)
              </button>

              <button 
                onClick={handleExportToAgent}
                className="flex-1 py-3 bg-sig-cyan text-ink-1 text-sm font-bold tracking-widest rounded shadow-[0_0_15px_rgba(0,207,255,0.4)] hover:bg-opacity-90 transition"
              >
                🚀 將此波型匯入至 Agent 進行根因診斷
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}