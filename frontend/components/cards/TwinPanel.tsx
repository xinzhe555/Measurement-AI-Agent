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

  // ── 模型 / 機型選擇 ──────────────────────────────────────────────────────
  const [modelType, setModelType] = useState<'pure_htm' | 'htm_rodrigues'>('pure_htm')
  const [machineType, setMachineType] = useState<'AC' | 'BC'>('AC')

  const [params, setParams] = useState({
    // ── C 軸 PIGEs（兩種機型共用）──────────────────────────────────────────
    xoc: 0, yoc: 0, zoc: 0,
    aoc: 0, boc: 0, coc: 0,

    // ── A 軸 PIGEs（AC 機型）──────────────────────────────────────────────
    yoa: 0, zoa: 0,
    aoa: 0, boa: 0, coa: 0,

    // ── B 軸 PIGEs（BC 機型）──────────────────────────────────────────────
    xob: 0, zob: 0,
    aob: 0, cob: 0,

    // ── 量測球位置 ──────────────────────────────────────────────────────────
    ball_x: 200, ball_y: 0, ball_z: 0,
    // ── 機台尺寸 ──────────────────────────────────────────────────────────
    pivot_x: 0, pivot_y: 0, pivot_z: 0,
    zoa_geom: 0,  // 搖籃軸 Z 方向幾何距離

    // ── C 軸 PDGEs ────────────────────────────────────────────────────────
    c_runout_x_amp:   0.010,
    c_runout_x_phase: 0.0,
    c_runout_y_amp:   0.010,
    c_runout_y_phase: 90.0,
    c_runout_z_amp:   0.005,
    c_runout_z_freq:  2.0,
    c_wobble_a_amp:   0.0001,
    c_wobble_b_amp:   0.0001,

    // ── A 軸 PDGEs ────────────────────────────────────────────────────────
    a_runout_y_amp:   0.005,
    a_runout_y_phase: 0.0,
    a_runout_z_amp:   0.005,
    a_runout_z_phase: 90.0,
    a_runout_x_amp:   0.002,
    a_runout_x_freq:  1.0,
    a_wobble_b_amp:   0.00005,
    a_wobble_c_amp:   0.00005,

    // ── PDGEs 開關 ────────────────────────────────────────────────────────
    enable_c_pdge: false,
    enable_a_pdge: false,

    n_points: 19
  })

  const [chartData, setChartData] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [lastCradleLabel, setLastCradleLabel] = useState<string>('A')
  const chartContainerRef = useRef<HTMLDivElement>(null)

  const handleSimulate = async () => {
    setIsLoading(true)
    try {
      const payload = {
        model_type: modelType,
        machine_type: machineType,
        // C 軸 PIGEs
        xoc: params.xoc, yoc: params.yoc, zoc: params.zoc,
        aoc: params.aoc, boc: params.boc, coc: params.coc,
        // A 軸 PIGEs
        yoa: params.yoa, zoa: params.zoa,
        aoa: params.aoa, boa: params.boa, coa: params.coa,
        // B 軸 PIGEs
        xob: params.xob, zob: params.zob,
        aob: params.aob, cob: params.cob,
        // 機台尺寸
        pivot_z: params.pivot_z,
        zoa_geom: params.zoa_geom,
        // C 軸 PDGEs
        c_runout_x_amp:   params.c_runout_x_amp,
        c_runout_x_phase: params.c_runout_x_phase,
        c_runout_y_amp:   params.c_runout_y_amp,
        c_runout_y_phase: params.c_runout_y_phase,
        c_runout_z_amp:   params.c_runout_z_amp,
        c_runout_z_freq:  params.c_runout_z_freq,
        c_wobble_a_amp:   params.c_wobble_a_amp,
        c_wobble_b_amp:   params.c_wobble_b_amp,
        // A 軸 PDGEs
        a_runout_y_amp:   params.a_runout_y_amp,
        a_runout_y_phase: params.a_runout_y_phase,
        a_runout_z_amp:   params.a_runout_z_amp,
        a_runout_z_phase: params.a_runout_z_phase,
        a_runout_x_amp:   params.a_runout_x_amp,
        a_runout_x_freq:  params.a_runout_x_freq,
        a_wobble_b_amp:   params.a_wobble_b_amp,
        a_wobble_c_amp:   params.a_wobble_c_amp,
        // 開關
        enable_c_pdge: params.enable_c_pdge,
        enable_a_pdge: params.enable_a_pdge,
        // 其他
        path_type: pathType,
        view_mode: viewMode,
        tool_length: toolLength,
        n_points: params.n_points,
        ball_x: params.ball_x, ball_y: params.ball_y, ball_z: params.ball_z,
      }
      const res = await fetch('http://localhost:8000/api/twin_simulate', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
      })
      const result = await res.json()
      if (result.status === 'success') {
        const { dx_um, dy_um, dz_um, cradle_deg, c_deg } = result.data
        const cLabel = result.cradle_label || (machineType === 'BC' ? 'B' : 'A')
        setLastCradleLabel(cLabel)
        const formattedData = dx_um.map((dx: number, i: number) => ({
          index: i,
          cradle_axis: cradle_deg ? Number(cradle_deg[i].toFixed(2)) : 0,
          a_axis: cradle_deg ? Number(cradle_deg[i].toFixed(2)) : 0,
          c_axis: c_deg ? Number(c_deg[i].toFixed(2)) : 0,
          dx: Number(dx.toFixed(4)),
          dy: Number(dy_um[i].toFixed(4)),
          dz: Number(dz_um[i].toFixed(4))
        }))
        setChartData(formattedData)
      }
    } catch (error) {
      console.error(error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleExportToAgent = () => {
    if (onExportToAgent) onExportToAgent(chartData, viewMode)
  }

  const handleClearChart = () => {
    setChartData([])
  }

  const handleExportExcel = async () => {
    try {
      const workbook = new ExcelJS.Workbook()
      workbook.creator = 'Digital Twin System'
      workbook.created = new Date()

      const sheetParams = workbook.addWorksheet('誤差參數設定')
      sheetParams.columns = [
        { header: '參數類別', key: 'category', width: 22 },
        { header: '誤差代號', key: 'name', width: 28 },
        { header: '設定數值', key: 'value', width: 15 },
        { header: '單位', key: 'unit', width: 10 }
      ]

      // 根據機型選擇要輸出的參數
      const allKeys = [
        // C 軸 PIGEs（兩種機型共用）
        { k: 'xoc',             n: 'XOC',             u: 'mm',  c: 'C軸 PIGEs 平移' },
        { k: 'yoc',             n: 'YOC',             u: 'mm',  c: 'C軸 PIGEs 平移' },
        { k: 'zoc',             n: 'ZOC',             u: 'mm',  c: 'C軸 PIGEs 平移' },
        { k: 'aoc',             n: 'AOC',             u: 'deg', c: 'C軸 PIGEs 旋轉' },
        { k: 'boc',             n: 'BOC',             u: 'deg', c: 'C軸 PIGEs 旋轉' },
        { k: 'coc',             n: 'COC',             u: 'deg', c: 'C軸 PIGEs 旋轉' },
        // 搖籃軸 PIGEs（依機型）
        ...(machineType === 'BC' ? [
          { k: 'xob',           n: 'XOB',             u: 'mm',  c: 'B軸 PIGEs 平移' },
          { k: 'zob',           n: 'ZOB',             u: 'mm',  c: 'B軸 PIGEs 平移' },
          { k: 'aob',           n: 'AOB',             u: 'deg', c: 'B軸 PIGEs 旋轉' },
          { k: 'cob',           n: 'COB',             u: 'deg', c: 'B軸 PIGEs 旋轉' },
        ] : [
          { k: 'yoa',           n: 'YOA',             u: 'mm',  c: 'A軸 PIGEs 平移' },
          { k: 'zoa',           n: 'ZOA',             u: 'mm',  c: 'A軸 PIGEs 平移' },
          { k: 'aoa',           n: 'AOA',             u: 'deg', c: 'A軸 PIGEs 旋轉' },
          { k: 'boa',           n: 'BOA',             u: 'deg', c: 'A軸 PIGEs 旋轉' },
          { k: 'coa',           n: 'COA',             u: 'deg', c: 'A軸 PIGEs 旋轉' },
        ]),
        // C 軸 PDGEs
        { k: 'c_runout_x_amp',   n: 'C_Runout_X_Amp',   u: 'mm',  c: 'C軸 PDGEs 徑向' },
        { k: 'c_runout_x_phase', n: 'C_Runout_X_Phase', u: 'deg', c: 'C軸 PDGEs 徑向' },
        { k: 'c_runout_y_amp',   n: 'C_Runout_Y_Amp',   u: 'mm',  c: 'C軸 PDGEs 徑向' },
        { k: 'c_runout_y_phase', n: 'C_Runout_Y_Phase', u: 'deg', c: 'C軸 PDGEs 徑向' },
        { k: 'c_runout_z_amp',   n: 'C_Runout_Z_Amp',   u: 'mm',  c: 'C軸 PDGEs 軸向' },
        { k: 'c_runout_z_freq',  n: 'C_Runout_Z_Freq',  u: '倍頻', c: 'C軸 PDGEs 軸向' },
        { k: 'c_wobble_a_amp',   n: 'C_Wobble_A_Amp',   u: 'rad', c: 'C軸 PDGEs Wobble' },
        { k: 'c_wobble_b_amp',   n: 'C_Wobble_B_Amp',   u: 'rad', c: 'C軸 PDGEs Wobble' },
      ]
      allKeys.forEach(p => {
        sheetParams.addRow({ category: p.c, name: p.n, value: (params as any)[p.k], unit: p.u })
      })
      sheetParams.addRow({ category: '模型類型', name: 'model_type', value: modelType === 'pure_htm' ? '純 HTM' : 'HTM + Rodrigues', unit: '-' })
      sheetParams.addRow({ category: '機型', name: 'machine_type', value: machineType === 'AC' ? 'A/C 軸' : 'B/C 軸', unit: '-' })

      const cradleLabel = machineType === 'BC' ? 'B' : 'A'
      const sheetData = workbook.addWorksheet('軌跡量測數據')
      sheetData.columns = [
        { header: '點位序號',                    key: 'index',       width: 10 },
        { header: `${cradleLabel}軸角度 (deg)`,  key: 'cradle_axis', width: 15 },
        { header: 'C軸角度 (deg)',               key: 'c_axis',      width: 15 },
        { header: 'Err_X (µm)',                  key: 'dx',          width: 15 },
        { header: 'Err_Y (µm)',                  key: 'dy',          width: 15 },
        { header: 'Err_Z (µm)',                  key: 'dz',          width: 15 }
      ]
      sheetData.addRows(chartData)

      const sheetChart = workbook.addWorksheet('圖表預覽')
      if (chartContainerRef.current) {
        const canvas = await html2canvas(chartContainerRef.current, { background: '#1A1A1A' })
        const base64Image = canvas.toDataURL('image/png')
        const imageId = workbook.addImage({ base64: base64Image, extension: 'png' })
        sheetChart.addImage(imageId, { tl: { col: 1, row: 1 }, ext: { width: 800, height: 400 } })
      }

      const buffer = await workbook.xlsx.writeBuffer()
      saveAs(new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }),
        `Twin_${machineType}_${modelType}_${new Date().getTime()}.xlsx`)
    } catch (err) {
      console.error('匯出 Excel 失敗', err)
      alert('匯出失敗，請檢查主控台訊息。')
    }
  }

  // ── 輸入框小元件 ──────────────────────────────────────────────────────────
  // 使用 onBlur 提交，避免打字中途因 state 更新導致失焦
  const Field = ({ k, label, unit, step = 'any' }: { k: string; label: string; unit: string; step?: string }) => (
    <div>
      <label className="block text-tx-mid text-[9px] mb-0.5 font-mono">{label}</label>
      <div className="flex items-center gap-1">
        <input type="number" step={step}
          className="w-full bg-ink-1 border border-line-1 text-tx-hi text-[10px] rounded px-1.5 py-1"
          defaultValue={(params as any)[k]}
          key={`${k}-${(params as any)[k]}`}
          onBlur={e => {
            const v = Number(e.target.value)
            if (!isNaN(v)) setParams(prev => ({ ...prev, [k]: v }))
          }}
          onKeyDown={e => {
            if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
          }} />
        <span className="text-tx-lo text-[9px] whitespace-nowrap">{unit}</span>
      </div>
    </div>
  )

  const SectionLabel = ({ text, note }: { text: string; note?: string }) => (
    <div className="col-span-2 flex items-center gap-2 mt-2 mb-0.5">
      <span className="text-[9px] text-sig-cyan font-mono font-bold">{text}</span>
      {note && <span className="text-[8px] text-tx-lo">{note}</span>}
    </div>
  )

  const cradleLabel = machineType === 'BC' ? 'B' : 'A'

  const renderInputs = () => {
    if (activeTab === 'trans') return (
      <div className="grid grid-cols-2 gap-x-3 gap-y-2">
        <SectionLabel text="C 軸平移 PIGEs" note="旋轉中心偏移誤差" />
        <Field k="xoc" label="XOC" unit="mm" />
        <Field k="yoc" label="YOC" unit="mm" />
        {machineType === 'BC' ? (
          <>
            <SectionLabel text="B 軸平移 PIGEs" note="（YOB 不存在）" />
            <Field k="xob" label="XOB" unit="mm" />
            <Field k="zob" label="ZOB" unit="mm" />
          </>
        ) : (
          <>
            <SectionLabel text="A 軸平移 PIGEs" note="（XOA 不存在）" />
            <Field k="yoa" label="YOA" unit="mm" />
            <Field k="zoa" label="ZOA" unit="mm" />
          </>
        )}
      </div>
    )

    if (activeTab === 'rot') return (
      <div className="grid grid-cols-2 gap-x-3 gap-y-2">
        <SectionLabel text="C 軸旋轉 PIGEs" />
        <Field k="aoc" label="AOC" unit="deg" />
        <Field k="boc" label="BOC" unit="deg" />
        <Field k="coc" label="COC" unit="deg" />
        {machineType === 'BC' ? (
          <>
            <SectionLabel text="B 軸旋轉 PIGEs" />
            <Field k="aob" label="AOB" unit="deg" />
            <Field k="cob" label="COB" unit="deg" />
          </>
        ) : (
          <>
            <SectionLabel text="A 軸旋轉 PIGEs" />
            <Field k="aoa" label="AOA" unit="deg" />
            <Field k="boa" label="BOA" unit="deg" />
            <Field k="coa" label="COA" unit="deg" />
          </>
        )}
      </div>
    )

    if (activeTab === 'dims') return (
      <div className="grid grid-cols-2 gap-x-3 gap-y-2">
        <SectionLabel text="量測球位置" />
        <Field k="ball_x" label="Ball X" unit="mm" />
        <Field k="ball_y" label="Ball Y" unit="mm" />
        <Field k="ball_z" label="Ball Z" unit="mm" />
        <SectionLabel text="幾何距離 (HTM+Rodrigues)" note="影響偏擺誤差放大倍率" />
        <Field k="zoc" label="ZOC 距離" unit="mm" />
        <Field k="zoa_geom" label="ZOA 距離" unit="mm" />
        <SectionLabel text="純 HTM 幾何" />
        <Field k="pivot_x" label="Pivot X" unit="mm" />
        <Field k="pivot_y" label="Pivot Y" unit="mm" />
        <Field k="pivot_z" label="Pivot Z" unit="mm" />
      </div>
    )

    // PDGE tab
    return (
      <div className="flex flex-col gap-3 overflow-y-auto max-h-[340px] pr-1">

        {/* ── C 軸 PDGEs ── */}
        <div className="border border-line-1 rounded p-2">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] text-sig-cyan font-mono font-bold">C 軸 PDGEs</span>
            <label className="flex items-center gap-1.5 text-[9px] text-tx-hi cursor-pointer">
              <input type="checkbox" className="accent-sig-cyan"
                checked={params.enable_c_pdge}
                onChange={e => setParams({ ...params, enable_c_pdge: e.target.checked })} />
              啟用
            </label>
          </div>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
            <div className="col-span-2 text-[8px] text-tx-lo font-mono">徑向跳動 (Radial Runout)</div>
            <Field k="c_runout_x_amp"   label="X_Amp"   unit="mm"  />
            <Field k="c_runout_x_phase" label="X_Phase" unit="deg" />
            <Field k="c_runout_y_amp"   label="Y_Amp"   unit="mm"  />
            <Field k="c_runout_y_phase" label="Y_Phase" unit="deg" />
            <div className="col-span-2 text-[8px] text-tx-lo font-mono mt-1">軸向竄動 (Axial Runout)</div>
            <Field k="c_runout_z_amp"  label="Z_Amp"  unit="mm"   />
            <Field k="c_runout_z_freq" label="Z_Freq" unit="倍頻" />
            <div className="col-span-2 text-[8px] text-tx-lo font-mono mt-1">角度擺動 (Wobble)</div>
            <Field k="c_wobble_a_amp" label="A_Amp" unit="rad" />
            <Field k="c_wobble_b_amp" label="B_Amp" unit="rad" />
          </div>
        </div>

        {/* ── 搖籃軸 PDGEs（僅 AC 機型顯示 A 軸 PDGEs）── */}
        {machineType === 'AC' && (
          <div className="border border-line-1 rounded p-2">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] text-sig-cyan font-mono font-bold">A 軸 PDGEs</span>
              <label className="flex items-center gap-1.5 text-[9px] text-tx-hi cursor-pointer">
                <input type="checkbox" className="accent-sig-cyan"
                  checked={params.enable_a_pdge}
                  onChange={e => setParams({ ...params, enable_a_pdge: e.target.checked })} />
                啟用
              </label>
            </div>
            <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
              <div className="col-span-2 text-[8px] text-tx-lo font-mono">徑向跳動 (Radial Runout)</div>
              <Field k="a_runout_y_amp"   label="Y_Amp"   unit="mm"  />
              <Field k="a_runout_y_phase" label="Y_Phase" unit="deg" />
              <Field k="a_runout_z_amp"   label="Z_Amp"   unit="mm"  />
              <Field k="a_runout_z_phase" label="Z_Phase" unit="deg" />
              <div className="col-span-2 text-[8px] text-tx-lo font-mono mt-1">軸向竄動 (Axial Runout)</div>
              <Field k="a_runout_x_amp"  label="X_Amp"  unit="mm"   />
              <Field k="a_runout_x_freq" label="X_Freq" unit="倍頻" />
              <div className="col-span-2 text-[8px] text-tx-lo font-mono mt-1">角度擺動 (Wobble)</div>
              <Field k="a_wobble_b_amp" label="B_Amp" unit="rad" />
              <Field k="a_wobble_c_amp" label="C_Amp" unit="rad" />
            </div>
          </div>
        )}

      </div>
    )
  }

  return (
    <>
      <CardShell titleText="數位孿生生成器" titleColor="text-tx-hi" accentColor="#00CFFF" badge="Twin" badgeStyle="bg-sig-cyan/20 text-sig-cyan">
        <div className="p-3 flex flex-col gap-3">

          {/* ── 模型 / 機型選擇 ── */}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-tx-lo text-[8px] mb-1 font-mono">數學模型</label>
              <select
                value={modelType}
                onChange={e => setModelType(e.target.value as any)}
                className="w-full bg-ink-1 border border-line-1 text-tx-hi text-[10px] rounded px-1.5 py-1 font-mono">
                <option value="pure_htm">純 HTM</option>
                <option value="htm_rodrigues">HTM + Rodrigues</option>
              </select>
            </div>
            <div>
              <label className="block text-tx-lo text-[8px] mb-1 font-mono">機型</label>
              <select
                value={machineType}
                onChange={e => setMachineType(e.target.value as any)}
                className="w-full bg-ink-1 border border-line-1 text-tx-hi text-[10px] rounded px-1.5 py-1 font-mono">
                <option value="AC">A/C 軸 (A搖籃)</option>
                <option value="BC">B/C 軸 (B搖籃)</option>
              </select>
            </div>
          </div>

          {/* ── 頁籤 ── */}
          <div className="flex gap-1 border-b border-line-1 pb-1">
            {(['trans', 'rot', 'dims', 'pdge'] as const).map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)}
                className={`text-[9px] px-2 py-1 rounded transition ${activeTab === tab ? 'bg-sig-cyan/20 text-sig-cyan' : 'text-tx-lo hover:text-tx-mid'}`}>
                {{ trans: '平移', rot: '旋轉', dims: '機台尺寸', pdge: '動態' }[tab]}
              </button>
            ))}
          </div>

          {renderInputs()}

          <div className="flex items-center justify-between border-t border-line-1 pt-2 mt-1">
            <label className="text-[10px] text-tx-mid">取樣密度 (資料點數):</label>
            <select className="bg-ink-1 border border-line-1 text-tx-hi text-[10px] rounded px-1.5 py-1 w-3/5"
              value={params.n_points}
              onChange={e => setParams({ ...params, n_points: Number(e.target.value) })}>
              <option value={19}>19 點 (C軸20度 - 實機格式)</option>
              <option value={37}>37 點 (C軸10度)</option>
              <option value={360}>360 點 (1度平滑預覽)</option>
            </select>
          </div>

          <button onClick={handleSimulate} disabled={isLoading}
            className="w-full mt-1 py-1.5 font-mono text-[10px] rounded border border-sig-cyan/30 text-sig-cyan bg-sig-cyan/5 hover:bg-sig-cyan/15 transition disabled:opacity-50">
            {isLoading ? '生成中...' : '▶ 執行軌跡圖形預覽'}
          </button>

          {/* ── 內嵌誤差合成圖 ── */}
          {chartData.length > 0 && (
            <>
              <div ref={chartContainerRef} className="w-full h-40 bg-ink-2 rounded border border-line-2 p-1 mt-1">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 16, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                    <XAxis dataKey="c_axis" stroke="#555" tick={{ fontSize: 8 }}
                      label={{ value: 'C 軸 (deg)', position: 'insideBottomRight', fill: '#666', fontSize: 8, offset: -4 }} />
                    <YAxis stroke="#555" tick={{ fontSize: 8 }} width={35}
                      label={{ value: 'µm', angle: -90, position: 'insideLeft', fill: '#666', fontSize: 8 }} />
                    <Tooltip contentStyle={{ backgroundColor: '#1A1A1A', border: 'none', fontSize: 10 }}
                      labelFormatter={(label) => `C: ${label}°`} />
                    <Legend wrapperStyle={{ fontSize: 9 }} />
                    <Line type="monotone" dataKey="dx" name="ΔX" stroke="#FF5C5C" dot={false} strokeWidth={1.2} />
                    <Line type="monotone" dataKey="dy" name="ΔY" stroke="#228B22" dot={false} strokeWidth={1.2} />
                    <Line type="monotone" dataKey="dz" name="ΔZ" stroke="#4da6ff" dot={false} strokeWidth={1.2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div className="flex gap-1.5 mt-1">
                <button onClick={handleExportExcel}
                  className="flex-1 py-1 font-mono text-[9px] rounded border border-line-1 text-tx-lo hover:text-tx-hi hover:bg-ink-2 transition">
                  Excel
                </button>
                <button onClick={handleExportToAgent}
                  className="flex-1 py-1 font-mono text-[9px] rounded border border-sig-cyan/30 text-sig-cyan bg-sig-cyan/5 hover:bg-sig-cyan/15 transition">
                  Agent 診斷
                </button>
                <button onClick={handleClearChart}
                  className="py-1 px-2 font-mono text-[9px] rounded border border-line-1 text-tx-lo hover:text-sig-red hover:border-sig-red/30 transition">
                  ✕
                </button>
              </div>
            </>
          )}
        </div>
      </CardShell>
    </>
  )
}
