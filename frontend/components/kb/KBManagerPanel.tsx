'use client'
// components/kb/KBManagerPanel.tsx
// 知識庫管理主面板 — 取代中間的 ChatUI

import { useState, useEffect, useCallback } from 'react'
import { listKBFiles, uploadKBFile, deleteKBFile, getKBMarkdown, getGraphStats } from '@/lib/api'
import type { KBFileInfo } from '@/lib/types'
import ReactMarkdown from 'react-markdown'

// 狀態顏色/文字對映
const STATUS_MAP: Record<string, { label: string; color: string }> = {
  uploaded:    { label: '已上傳',  color: 'text-tx-mid' },
  converting:  { label: '轉換中',  color: 'text-sig-amber' },
  chunking:    { label: '分段中',  color: 'text-sig-amber' },
  vectorizing: { label: '向量化',  color: 'text-sig-cyan' },
  extracting:  { label: '圖譜建構', color: 'text-sig-cyan' },
  done:        { label: '完成',    color: 'text-sig-lime' },
  error:       { label: '錯誤',    color: 'text-sig-red' },
}

const EQUIPMENT_OPTIONS = ['LRT', 'Heidenhain', 'BallBar', 'Other']

interface Props {
  onBack: () => void
}

export function KBManagerPanel({ onBack }: Props) {
  const [files, setFiles]           = useState<KBFileInfo[]>([])
  const [uploading, setUploading]   = useState(false)
  const [equipment, setEquipment]   = useState('Heidenhain')
  const [previewId, setPreviewId]   = useState<string | null>(null)
  const [previewMd, setPreviewMd]   = useState<string>('')
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [graphStats, setGraphStats]       = useState<any>(null)
  const [eqFilter, setEqFilter]           = useState<string>('')

  // 載入檔案清單 + 圖譜統計
  const fetchFiles = useCallback(async () => {
    const list = await listKBFiles()
    setFiles(list)
    const stats = await getGraphStats(eqFilter || undefined)
    setGraphStats(stats)
  }, [eqFilter])

  useEffect(() => {
    fetchFiles()
  }, [fetchFiles])

  // 輪詢（有處理中的檔案時每 3 秒更新）
  useEffect(() => {
    const hasProcessing = files.some(
      f => !['done', 'error'].includes(f.status)
    )
    if (!hasProcessing) return
    const timer = setInterval(fetchFiles, 3000)
    return () => clearInterval(timer)
  }, [files, fetchFiles])

  // 上傳
  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      await uploadKBFile(file, equipment)
      await fetchFiles()
    } catch (err) {
      alert(`上傳失敗：${err instanceof Error ? err.message : '未知錯誤'}`)
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  // 刪除
  const handleDelete = async (fileId: string) => {
    if (!confirm('確定要刪除此檔案及其所有知識庫資料？')) return
    await deleteKBFile(fileId)
    if (previewId === fileId) {
      setPreviewId(null)
      setPreviewMd('')
    }
    await fetchFiles()
  }

  // 預覽
  const handlePreview = async (fileId: string) => {
    if (previewId === fileId) {
      setPreviewId(null)
      setPreviewMd('')
      return
    }
    setPreviewId(fileId)
    setLoadingPreview(true)
    const md = await getKBMarkdown(fileId)
    setPreviewMd(md)
    setLoadingPreview(false)
  }

  return (
    <div className="flex flex-col h-full bg-ink-0">
      {/* 頂部標題列 */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-line-1 bg-ink-1 shrink-0">
        <div className="flex items-center gap-2">
          <span className="w-1 h-4 rounded-sm bg-sig-amber" />
          <span className="font-sans text-[14px] font-bold text-tx-hi tracking-wide">
            知識庫管理
          </span>
          <span className="font-mono text-[10px] text-tx-lo ml-2">
            {files.length} 個檔案
          </span>
        </div>
        <button
          onClick={onBack}
          className="font-mono text-[10px] text-sig-cyan hover:text-tx-hi
                     border border-sig-cyan/30 rounded px-3 py-1
                     hover:bg-sig-cyan/10 transition-all"
        >
          ← 返回對話
        </button>
      </div>

      {/* 內容區（可捲動） */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4
                      scrollbar-thin scrollbar-thumb-line-2 scrollbar-track-transparent">

        {/* 上傳區 */}
        <div className="bg-ink-1 border border-line-1 rounded-lg p-4">
          <div className="font-mono text-[9px] text-tx-lo tracking-widest uppercase mb-3">
            上傳新文件
          </div>
          <div className="flex items-center gap-3">
            <select
              value={equipment}
              onChange={e => setEquipment(e.target.value)}
              className="bg-ink-2 border border-line-2 rounded px-2 py-1.5
                         font-mono text-[11px] text-tx-hi outline-none
                         focus:border-sig-cyan/40"
            >
              {EQUIPMENT_OPTIONS.map(eq => (
                <option key={eq} value={eq}>{eq}</option>
              ))}
            </select>

            <label className="flex-1 flex items-center justify-center gap-2
                              bg-ink-2 border border-dashed border-line-2
                              rounded-lg py-3 cursor-pointer
                              hover:border-sig-cyan/40 hover:bg-ink-3 transition-all">
              <input
                type="file"
                accept=".pdf"
                onChange={handleUpload}
                className="hidden"
                disabled={uploading}
              />
              <span className="font-sans text-[12px] text-tx-mid">
                {uploading ? '上傳中...' : '選擇 PDF 檔案'}
              </span>
            </label>
          </div>
        </div>

        {/* 檔案清單 */}
        <div className="bg-ink-1 border border-line-1 rounded-lg overflow-hidden">
          <div className="font-mono text-[9px] text-tx-lo tracking-widest uppercase px-4 py-2 border-b border-line-0">
            已上傳檔案
          </div>

          {files.length === 0 ? (
            <div className="px-4 py-8 text-center text-tx-lo text-[12px]">
              尚無檔案，請上傳 PDF
            </div>
          ) : (
            <div className="divide-y divide-line-0">
              {files.map(f => {
                const st = STATUS_MAP[f.status] ?? STATUS_MAP.error
                return (
                  <div key={f.file_id} className="px-4 py-3 hover:bg-ink-2 transition-colors">
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-sans text-[12px] text-tx-hi truncate">
                            {f.filename}
                          </span>
                          <span className="font-mono text-[9px] px-1.5 py-0.5 rounded
                                           bg-ink-3 border border-line-0 text-tx-mid shrink-0">
                            {f.equipment}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 mt-1">
                          <span className={`font-mono text-[10px] ${st.color}`}>
                            {f.status === 'converting' || f.status === 'chunking' ||
                             f.status === 'vectorizing' || f.status === 'extracting'
                              ? '⏳ ' : f.status === 'done' ? '✓ ' : f.status === 'error' ? '✕ ' : ''}
                            {st.label}
                          </span>
                          {f.chunk_count != null && (
                            <span className="font-mono text-[9px] text-tx-lo">
                              {f.chunk_count} chunks
                            </span>
                          )}
                          <span className="font-mono text-[9px] text-tx-lo">
                            {f.upload_time}
                          </span>
                        </div>
                        {f.error_message && (
                          <div className="font-mono text-[9px] text-sig-red mt-1 truncate">
                            {f.error_message}
                          </div>
                        )}
                      </div>

                      <div className="flex items-center gap-1 ml-3 shrink-0">
                        {(f.status === 'done' || f.status === 'error') && (
                          <button
                            onClick={() => handlePreview(f.file_id)}
                            className="w-7 h-7 flex items-center justify-center text-[12px]
                                       text-tx-mid hover:text-tx-hi hover:bg-ink-3 rounded transition-colors"
                            title="預覽 Markdown"
                          >
                            {previewId === f.file_id ? '✕' : '👁'}
                          </button>
                        )}
                        <button
                          onClick={() => handleDelete(f.file_id)}
                          className="w-7 h-7 flex items-center justify-center text-[12px]
                                     text-tx-mid hover:text-sig-red hover:bg-ink-3 rounded transition-colors"
                          title="刪除"
                        >
                          🗑
                        </button>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* 知識圖譜儀表板 */}
        <div className="bg-ink-1 border border-line-1 rounded-lg overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 border-b border-line-0">
            <span className="font-mono text-[9px] text-tx-lo tracking-widest uppercase">
              知識圖譜狀態
            </span>
            <select
              value={eqFilter}
              onChange={e => setEqFilter(e.target.value)}
              className="bg-ink-2 border border-line-2 rounded px-2 py-0.5
                         font-mono text-[10px] text-tx-mid outline-none"
            >
              <option value="">全部</option>
              {EQUIPMENT_OPTIONS.map(eq => (
                <option key={eq} value={eq}>{eq}</option>
              ))}
            </select>
          </div>

          {graphStats ? (
            <div className="p-4">
              {/* FAISS 統計 */}
              <div className="grid grid-cols-3 gap-3 mb-4">
                <div className="bg-ink-2 rounded p-3 border border-line-0 text-center">
                  <div className="font-mono text-2xl font-bold text-sig-cyan">
                    {graphStats.total_chunks}
                  </div>
                  <div className="font-mono text-[8px] text-tx-lo mt-1">FAISS Chunks</div>
                </div>
                <div className="bg-ink-2 rounded p-3 border border-line-0 text-center">
                  <div className="font-mono text-2xl font-bold text-sig-lime">
                    {graphStats.neo4j?.Chunk ?? 0}
                  </div>
                  <div className="font-mono text-[8px] text-tx-lo mt-1">Neo4j Chunks</div>
                </div>
                <div className="bg-ink-2 rounded p-3 border border-line-0 text-center">
                  <div className="font-mono text-2xl font-bold text-sig-amber">
                    {graphStats.neo4j?.Event ?? 0}
                  </div>
                  <div className="font-mono text-[8px] text-tx-lo mt-1">Events</div>
                </div>
              </div>

              {/* 依 equipment 分布 */}
              {Object.keys(graphStats.chunks_by_equipment || {}).length > 0 && (
                <div className="mb-4">
                  <div className="font-mono text-[9px] text-tx-lo mb-2">Chunks 分布</div>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(graphStats.chunks_by_equipment as Record<string, number>).map(([eq, cnt]) => (
                      <div key={eq} className="flex items-center gap-1.5 bg-ink-2 border border-line-0 rounded px-2 py-1">
                        <span className="font-mono text-[10px] text-tx-hi">{eq}</span>
                        <span className="font-mono text-[10px] text-sig-cyan font-bold">{cnt}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Neo4j 邊統計 */}
              <div className="grid grid-cols-2 gap-2">
                {['CAUSAL_LINK', 'MENTIONS', 'COMPENSATED_BY', 'PROCEDURE_STEP'].map(rel => {
                  const cnt = graphStats.neo4j?.[`edge_${rel}`] ?? 0
                  return (
                    <div key={rel} className="flex items-center justify-between bg-ink-2 rounded px-2 py-1.5 border border-line-0">
                      <span className="font-mono text-[9px] text-tx-mid truncate">{rel}</span>
                      <span className="font-mono text-[10px] text-tx-hi font-bold ml-2">{cnt}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          ) : (
            <div className="p-4 text-center text-tx-lo text-[11px]">載入中...</div>
          )}
        </div>

        {/* Markdown 預覽 */}
        {previewId && (
          <div className="bg-ink-1 border border-line-1 rounded-lg overflow-hidden">
            <div className="font-mono text-[9px] text-tx-lo tracking-widest uppercase px-4 py-2 border-b border-line-0">
              Markdown 預覽
            </div>
            <div className="px-5 py-4 max-h-[60vh] overflow-y-auto
                            scrollbar-thin scrollbar-thumb-line-2 scrollbar-track-transparent">
              {loadingPreview ? (
                <div className="text-tx-lo text-[12px]">載入中...</div>
              ) : (
                <div className="prose prose-invert prose-sm max-w-none
                                prose-headings:text-tx-hi prose-p:text-tx-mid prose-strong:text-tx-hi
                                prose-table:text-[11px] prose-td:border-line-1 prose-th:border-line-1
                                prose-code:text-sig-cyan prose-code:bg-ink-3 prose-code:px-1 prose-code:rounded">
                  <ReactMarkdown>{previewMd}</ReactMarkdown>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
