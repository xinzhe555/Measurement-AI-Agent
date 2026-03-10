'use client'
// app/dashboard/page.tsx
// 主介面：組裝三欄佈局，管理全域狀態

import { useState, useCallback } from 'react'
import { Header } from '@/components/layout/Header'
import { LeftPanel } from '@/components/layout/LeftPanel'
import { RightPanel } from '@/components/layout/RightPanel'
import { MessageList } from '@/components/chat/MessageList'
import { InputBar } from '@/components/chat/InputBar'
import { runAnalysis, sendChat, saveSession, resetSession } from '@/lib/api'
import type { AnalyzeResponse, ChatMessage, AnalyzeRequest } from '@/lib/types'

export default function Dashboard() {
  const [messages, setMessages]     = useState<ChatMessage[]>([])
  const [analysis, setAnalysis]     = useState<AnalyzeResponse | null>(null)
  const [sessionId, setSessionId]   = useState<string>('default')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [isTyping, setIsTyping]     = useState(false)
  const [backendOk, setBackendOk]   = useState<boolean | null>(null)

  // ── 執行完整分析 ────────────────────────────────────────────
  const handleAnalyze = useCallback(async (req: AnalyzeRequest) => {
    setIsAnalyzing(true)

    const logMsg: ChatMessage = {
      id: 'log-' + Date.now().toString(),
      role: 'system',
      content: `【系統日誌】\n▶ 正在載入 BK4 循圓軌跡原始數據（A軸 ±30°, C軸 ±90°, 共 360 個採樣點）...\n▶ 已擷取原始 DX / DY / DZ 殘差數據。\n▶ 正在將數據輸入 HTM 物理模型進行非線性最小二乘辨識...`,
      timestamp: new Date().toLocaleTimeString('zh-TW', { hour12: false }),
    }
    setMessages(prev => [...prev, logMsg])

    try {
      const result = await runAnalysis(req)
      setAnalysis(result)
      setSessionId(result.session_id)
      // 把結果存到 session，讓聊天可以引用具體數值
      await saveSession(result.session_id, { last_analysis: result })

      // 系統訊息：顯示辨識結果
      const sysMsg: ChatMessage = {
        id: Date.now().toString(),
        role: 'system',
        content: '分析完成',
        timestamp: new Date().toLocaleTimeString('zh-TW', { hour12: false }),
        analysisResult: result,
      }
      setMessages(prev => [...prev, sysMsg])
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
  }, [])

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
        message: `我已經匯入了一組數位孿生模擬的軌跡波型 (模式: ${modeName})，並已存入後端暫存檔。請幫我分析這組數據背後的幾何誤差根因。`,
        session_id: sessionId,
        context: analysis ? { last_analysis: analysis } : null,
      })
      
      const sysMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'system',
        content: res.reply,
        timestamp: new Date().toLocaleTimeString('zh-TW', { hour12: false }),
        usedTools: res.used_tools,
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
  const handleSend = useCallback(async (text: string) => {
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
        context: analysis ? { last_analysis: analysis } : null,
      })
      const sysMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'system',
        content: res.reply,
        timestamp: new Date().toLocaleTimeString('zh-TW', { hour12: false }),
        usedTools: res.used_tools,
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
        />

        {/* 中欄：聊天 */}
        <main className="flex flex-1 flex-col overflow-hidden bg-ink-0">
          <MessageList messages={messages} isTyping={isTyping} />
          <InputBar onSend={handleSend} onAnalyze={handleAnalyze} isAnalyzing={isAnalyzing} />
        </main>

        {/* 右欄：歷史 + 波形 */}
        <RightPanel analysis={analysis} messages={messages} onNewSession={handleNewSession} />
      </div>
    </div>
  )
}