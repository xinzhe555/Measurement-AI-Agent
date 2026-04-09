'use client'
// app/dashboard/page.tsx
// 主介面：組裝三欄佈局，管理全域狀態

import { useState, useCallback } from 'react'
import { Header } from '@/components/layout/Header'
import { LeftPanel } from '@/components/layout/LeftPanel'
import { RightPanel } from '@/components/layout/RightPanel'
import { MessageList } from '@/components/chat/MessageList'
import { InputBar } from '@/components/chat/InputBar'
import { KBManagerPanel } from '@/components/kb/KBManagerPanel'
import { KBGraphView } from '@/components/kb/KBGraphView'
import { runAnalysis, sendChat, saveSession, resetSession } from '@/lib/api'
import type { AnalyzeResponse, ChatMessage, AnalyzeRequest } from '@/lib/types'

export default function Dashboard() {
  const [messages, setMessages]     = useState<ChatMessage[]>([])
  const [analysis, setAnalysis]     = useState<AnalyzeResponse | null>(null)
  const [sessionId, setSessionId]   = useState<string>('default')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [isTyping, setIsTyping]     = useState(false)
  const [backendOk, setBackendOk]   = useState<boolean | null>(null)
  const [centerMode, setCenterMode] = useState<'chat' | 'kb' | 'graph'>('chat')

  // ── 執行完整分析 ────────────────────────────────────────────
  const handleAnalyze = useCallback(async (req: AnalyzeRequest) => {
    setIsAnalyzing(true)

    try {
      const result = await runAnalysis(req)
      setAnalysis(result)
      setSessionId(result.session_id)
      await saveSession(result.session_id, { last_analysis: result })

      setIsTyping(true)

      // 自動將分析結果送給 Agent，讓它給出真正的診斷
      try {
        const p = result.pige
        const d = result.pdge
        const r = result.rms
        // 將 µm 轉 mm 供 Agent 使用
        const toMm = (um: number) => (um / 1000).toFixed(4)
        const agentPrompt = [
          `【重要：前端已完成 HTM 辨識，不需要再呼叫 run_physical_analysis，直接根據以下數據診斷】`,
          ``,
          `## HTM 物理層非線性最小二乘辨識結果`,
          ``,
          `### PIGEs（位置無關靜態幾何誤差）`,
          `| 參數 | 辨識值 | 物理意義 |`,
          `|------|--------|----------|`,
          `| XOC | ${toMm(p.xoc_um)} mm | C 軸轉台相對 A 軸在 X 方向的偏心 |`,
          `| YOC | ${toMm(p.yoc_um)} mm | C 軸轉台相對 A 軸在 Y 方向的偏心 |`,
          `| YOA | ${toMm(p.yoa_um)} mm | A 軸旋轉中心在 Y 方向的偏移 |`,
          `| ZOA | ${toMm(p.zoa_um)} mm | A 軸旋轉中心在 Z 方向的偏移 |`,
          `| AOC | ${p.aoc_deg}° | C/A 軸垂直度誤差（阿貝放大效應） |`,
          `| BOC | ${p.boc_deg}° | C 軸傾斜角 |`,
          `| BOA | ${p.boa_deg}° | A 軸 Yaw 歪斜 |`,
          `| COA | ${p.coa_deg}° | A 軸 Roll 歪斜 |`,
          ``,
          `### PDGEs（位置相關動態幾何誤差 — C 軸）`,
          `| 參數 | 辨識值 | 物理意義 |`,
          `|------|--------|----------|`,
          `| EXC | ${toMm(d.exc_amp_um)} mm (相位 ${d.exc_phase_deg}°) | C 軸 X 方向徑向跳動（軸承偏心） |`,
          `| EYC | ${toMm(d.eyc_amp_um)} mm (相位 ${d.eyc_phase_deg}°) | C 軸 Y 方向徑向跳動 |`,
          `| EZC | ${toMm(d.ezc_amp_um)} mm (頻率 ${d.ezc_freq}×) | C 軸軸向竄動（端面不平） |`,
          ``,
          `### RMS 補償效果`,
          `| 軸向 | 補償前 (µm) | 補償後 (µm) | 改善率 |`,
          `|------|------------|------------|--------|`,
          `| DX | ${r.before_dx_um} | ${r.after_phys_dx_um} | ${r.phys_improvement_dx_pct}% |`,
          `| DY | ${r.before_dy_um} | ${r.after_phys_dy_um} | ${r.phys_improvement_dy_pct}% |`,
          `| DZ | ${r.before_dz_um} | ${r.after_phys_dz_um} | ${r.phys_improvement_dz_pct}% |`,
          ``,
          `請根據以上辨識結果進行診斷：`,
          `1. 找出主要誤差源（值顯著者），用 mm 和 deg 描述，說明物理根因與對加工的影響`,
          `2. 評估補償效果，判斷殘差是否合理`,
          `3. 給出具體調機建議與優先順序`,
        ].join('\n')

        const agentRes = await sendChat({
          message: agentPrompt,
          session_id: result.session_id,
          context: { last_analysis: result },
        })

        const agentMsg: ChatMessage = {
          id: (Date.now() + 1).toString(),
          role: 'system',
          content: agentRes.reply,
          timestamp: new Date().toLocaleTimeString('zh-TW', { hour12: false }),
          usedTools: agentRes.used_tools,
          ragSources: agentRes.rag_sources,
        }
        setMessages(prev => [...prev, agentMsg])
      } catch {
        // Agent 不可用時靜默跳過，不影響分析結果顯示
      } finally {
        setIsTyping(false)
      }
    } catch (err) {
      const errMsg: ChatMessage = {
        id: Date.now().toString(),
        role: 'system',
        content: `分析失敗：${err instanceof Error ? err.message : '請確認後端服務是否啟動'}`,
        timestamp: new Date().toLocaleTimeString('zh-TW', { hour12: false }),
      }
      setMessages(prev => [...prev, errMsg])
    } finally {
      setIsAnalyzing(false)
    }
  }, [sessionId])

  // ── 處理數位孿生圖表匯入並觸發 Agent ─────────────────────────
  const handleExportToAgent = useCallback(async (chartData: any[], viewMode: string) => {
    const modeName = viewMode === 'relative' ? '儀器投影 (Relative)' : '絕對幾何 (Absolute)'
    
    // 1. 建立一則包含圖表的使用者訊息，顯示在畫面上
    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: `【系統提示：已匯入數位孿生模擬數據】\n視角模式：${modeName}\n資料特徵：包含 360 個五軸同動採樣點。\n請讀取暫存的模擬數據檔，並分析此波動背後的物理幾何根因。`,
      timestamp: new Date().toLocaleTimeString('zh-TW', { hour12: false }),
      chartData: chartData // 夾帶圖表資料供 MessageBubble 渲染
    }
    setMessages(prev => [...prev, userMsg])
    setIsTyping(true)

    // 2. 自動背景呼叫 Agent 進行盲解
    try {
      const res = await sendChat({
        message: `我已經匯入了一組數位孿生模擬的軌跡波型 (模式: ${modeName})，共 ${chartData.length} 個採樣點。請直接對這組數據執行 HTM 物理層辨識，逆向分析出 PIGE/PDGE 幾何誤差根因。`,
        session_id: sessionId,
        context: {
          ...(analysis ? { last_analysis: analysis } : {}),
          twin_chart_data: chartData,  // 直接傳入圖表數據 {a_axis, c_axis, dx, dy, dz}（μm）
        },
      })
      
      const sysMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'system',
        content: res.reply,
        timestamp: new Date().toLocaleTimeString('zh-TW', { hour12: false }),
        usedTools: res.used_tools,
        ragSources: res.rag_sources,
      }
      setMessages(prev => [...prev, sysMsg])
    } catch {
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'system',
        content: '分析失敗，無法連線至 Agent 引擎。',
        timestamp: new Date().toLocaleTimeString('zh-TW', { hour12: false }),
      }])
    } finally {
      setIsTyping(false)
    }
  }, [sessionId, analysis])

  // ── 聊天傳送 ────────────────────────────────────────────────
  const handleSend = useCallback(async (text: string, kbSources?: string[]) => {
    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString('zh-TW', { hour12: false }),
    }
    setMessages(prev => [...prev, userMsg])
    setIsTyping(true)

    try {
      const res = await sendChat({
        message: text,
        session_id: sessionId,
        equipment_filters: kbSources,
        context: analysis ? { last_analysis: analysis } : null,
      })
      const sysMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'system',
        content: res.reply,
        timestamp: new Date().toLocaleTimeString('zh-TW', { hour12: false }),
        usedTools: res.used_tools,
        ragSources: res.rag_sources,
      }
      setMessages(prev => [...prev, sysMsg])
    } catch {
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'system',
        content: '後端服務目前離線，請先啟動 FastAPI（uvicorn main:app --reload）。',
        timestamp: new Date().toLocaleTimeString('zh-TW', { hour12: false }),
      }])
    } finally {
      setIsTyping(false)
    }
  }, [sessionId, analysis])

  const handleNewSession = useCallback(() => {
    setMessages([])
    setAnalysis(null)
    const newId = `session-${Date.now()}`
    resetSession(sessionId).catch(() => {})
    setSessionId(newId)
  }, [sessionId])

  return (
    <div className="flex h-screen flex-col">
      <Header backendOk={backendOk} setBackendOk={setBackendOk} />
      <div className="flex flex-1 overflow-hidden pt-11">

        {/* 左欄：誤差儀表板 (傳入 onExportToAgent) */}
        <LeftPanel
          analysis={analysis}
          isAnalyzing={isAnalyzing}
          onAnalyze={handleAnalyze}
          onExportToAgent={handleExportToAgent}
          onSetCenterMode={setCenterMode}
          centerMode={centerMode}
        />

        {/* 中欄：聊天 or 知識庫管理 */}
        <main className="flex flex-1 flex-col overflow-hidden bg-ink-0">
          {centerMode === 'chat' ? (
            <>
              <MessageList messages={messages} isTyping={isTyping} />
              <InputBar onSend={handleSend} onAnalyze={handleAnalyze} isAnalyzing={isAnalyzing} />
            </>
          ) : centerMode === 'kb' ? (
            <KBManagerPanel onBack={() => setCenterMode('chat')} />
          ) : (
            <KBGraphView onBack={() => setCenterMode('kb')} />
          )}
        </main>

        {/* 右欄：歷史 + 波形 */}
        <RightPanel analysis={analysis} messages={messages} onNewSession={handleNewSession} />
      </div>
    </div>
  )
}