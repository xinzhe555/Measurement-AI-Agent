"use client"
import React, { useState, useRef, useCallback } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer
} from 'recharts'

/* ── 資料點型別 ─────────────────────────────────────────────────────── */
export interface MeasuredPoint {
  index: number
  a_deg: number
  c_deg: number
  dx: number   // µm
  dy: number   // µm
  dz: number   // µm
}

interface Props {
  /** 資料解析完成後回傳，讓父層持有數據（不觸發分析） */
  onDataReady: (data: MeasuredPoint[] | null) => void
}

/* ── CSV 解析 ─────────────────────────────────────────────────────── */
function parseCsv(text: string): MeasuredPoint[] {
  const lines = text.trim().split(/\r?\n/).filter(l => l.trim())
  if (lines.length < 2) return []

  const header = lines[0].toLowerCase().split(',').map(h => h.trim())
  const colA = header.findIndex(h => h === 'a' || h === 'a_deg' || h === 'a_axis')
  const colC = header.findIndex(h => h === 'c' || h === 'c_deg' || h === 'c_axis')
  const colX = header.findIndex(h => h === 'x' || h === 'dx' || h === 'dx_um' || h === 'err_x')
  const colY = header.findIndex(h => h === 'y' || h === 'dy' || h === 'dy_um' || h === 'err_y')
  const colZ = header.findIndex(h => h === 'z' || h === 'dz' || h === 'dz_um' || h === 'err_z')

  if (colX < 0 || colY < 0 || colZ < 0) return []

  const rows = lines.slice(1)
  return rows.map((line, i) => {
    const cols = line.split(',').map(Number)
    return {
      index: i,
      a_deg: colA >= 0 ? Number(cols[colA].toFixed(2)) : 0,
      c_deg: colC >= 0 ? Number(cols[colC].toFixed(2)) : 0,
      dx: Number(cols[colX].toFixed(4)),
      dy: Number(cols[colY].toFixed(4)),
      dz: Number(cols[colZ].toFixed(4)),
    }
  }).filter(p => !isNaN(p.dx) && !isNaN(p.dy) && !isNaN(p.dz))
}

/* ── 元件 ─────────────────────────────────────────────────────────── */
export default function MeasurementUpload({ onDataReady }: Props) {
  const [data, setData] = useState<MeasuredPoint[] | null>(null)
  const [fileName, setFileName] = useState('')
  const [error, setError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const handleFile = useCallback((file: File) => {
    setError('')
    setFileName(file.name)
    const reader = new FileReader()
    reader.onload = (e) => {
      const text = e.target?.result as string
      const parsed = parseCsv(text)
      if (parsed.length === 0) {
        setError('CSV 格式無法辨識。需要含有 A, C, X(DX), Y(DY), Z(DZ) 欄位的 CSV 檔案。')
        setData(null)
        onDataReady(null)
        return
      }
      setData(parsed)
      onDataReady(parsed)
    }
    reader.readAsText(file)
  }, [onDataReady])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

  const handleClear = () => {
    setData(null)
    setFileName('')
    setError('')
    onDataReady(null)
    if (fileRef.current) fileRef.current.value = ''
  }

  return (
    <div className="flex flex-col gap-2">
      {/* ── 上傳區 ──────────────────────────────────── */}
      <div
        className="border border-dashed border-line-1 rounded-lg p-3 text-center cursor-pointer
                   hover:border-sig-cyan/50 hover:bg-sig-cyan/5 transition-all"
        onDragOver={e => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => fileRef.current?.click()}
      >
        <input ref={fileRef} type="file" accept=".csv" className="hidden"
          onChange={e => { if (e.target.files?.[0]) handleFile(e.target.files[0]) }} />
        <div className="text-tx-lo text-[10px] font-mono">
          {fileName
            ? <><span className="text-sig-cyan">{fileName}</span> ({data?.length ?? 0} 點)</>
            : '拖曳 CSV 或點擊上傳量測數據'}
        </div>
      </div>

      {error && <div className="text-sig-red text-[9px] font-mono">{error}</div>}

      {/* ── 內嵌誤差合成圖 ──────────────────────────── */}
      {data && (
        <>
          <div className="text-[9px] text-tx-lo font-mono">
            A: {data[0].a_deg}° ~ {data[data.length-1].a_deg}° | C: {data[0].c_deg}° ~ {data[data.length-1].c_deg}°
          </div>
          <div className="w-full h-40 bg-ink-2 rounded border border-line-2 p-1">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data} margin={{ top: 4, right: 8, bottom: 16, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                <XAxis dataKey="c_deg" stroke="#555" tick={{ fontSize: 8 }}
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
          <button onClick={handleClear}
            className="w-full py-1 font-mono text-[9px] rounded border border-line-1
                       text-tx-lo hover:text-sig-red hover:border-sig-red/30 transition">
            清除數據
          </button>
        </>
      )}
    </div>
  )
}
