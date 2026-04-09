// lib/api.ts
// 所有呼叫後端的函式集中在這裡
// 後端 URL 從環境變數讀取，本機開發和部署都只需改 .env

import type { AnalyzeRequest, AnalyzeResponse, ChatRequest, KBFileInfo } from './types'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

// ── 主要分析 ────────────────────────────────────────────────

export async function runAnalysis(req: AnalyzeRequest): Promise<AnalyzeResponse> {
  const res = await fetch(`${BASE_URL}/api/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

// ── 聊天 ────────────────────────────────────────────────────

export async function sendChat(req: ChatRequest) {
  const res = await fetch(`${BASE_URL}/api/session/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// ── Session 重置（新對話）────────────────────────────────────

export async function resetSession(sessionId: string): Promise<void> {
  await fetch(`${BASE_URL}/api/session/reset/${sessionId}`, {
    method: 'DELETE',
  }).catch(() => {})
}

// ── Session 管理 ─────────────────────────────────────────────

export async function saveSession(sessionId: string, data: unknown) {
  await fetch(`${BASE_URL}/api/session/save/${sessionId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

// ── 知識庫管理 ───────────────────────────────────────────────

export async function uploadKBFile(file: File, equipment: string): Promise<KBFileInfo> {
  const form = new FormData()
  form.append('file', file)
  form.append('equipment', equipment)
  const res = await fetch(`${BASE_URL}/api/kb/upload`, { method: 'POST', body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

export async function listKBFiles(): Promise<KBFileInfo[]> {
  const res = await fetch(`${BASE_URL}/api/kb/files`)
  if (!res.ok) return []
  const data = await res.json()
  return data.files ?? []
}

export async function getKBMarkdown(fileId: string): Promise<string> {
  const res = await fetch(`${BASE_URL}/api/kb/files/${fileId}/markdown`)
  if (!res.ok) return ''
  return res.text()
}

export async function deleteKBFile(fileId: string): Promise<void> {
  await fetch(`${BASE_URL}/api/kb/files/${fileId}`, { method: 'DELETE' })
}

export async function getGraphData(equipment?: string, nodeType?: string, limit?: number): Promise<any> {
  const params = new URLSearchParams()
  if (equipment) params.set('equipment', equipment)
  if (nodeType) params.set('node_type', nodeType)
  if (limit) params.set('limit', limit.toString())
  const qs = params.toString() ? `?${params}` : ''
  const res = await fetch(`${BASE_URL}/api/kb/graph-data${qs}`)
  if (!res.ok) return { nodes: [], links: [] }
  return res.json()
}

export async function getGraphStats(equipment?: string): Promise<any> {
  const qs = equipment ? `?equipment=${equipment}` : ''
  const res = await fetch(`${BASE_URL}/api/kb/graph-stats${qs}`)
  if (!res.ok) return null
  return res.json()
}

// ── 健康檢查 ─────────────────────────────────────────────────

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/health`, { cache: 'no-store' })
    return res.ok
  } catch {
    return false
  }
}
