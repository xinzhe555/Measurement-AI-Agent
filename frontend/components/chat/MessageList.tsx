'use client'
// components/chat/MessageList.tsx
import { useEffect, useRef } from 'react'
import { MessageBubble } from './MessageBubble'
import type { ChatMessage } from '@/lib/types'

interface Props {
  messages: ChatMessage[]
  isTyping: boolean
}

export function MessageList({ messages, isTyping }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  return (
    <div className="flex-1 overflow-y-auto px-5 py-6 space-y-6
                    scrollbar-thin scrollbar-thumb-line-2 scrollbar-track-transparent">
      {messages.length === 0 && (
        <div className="flex flex-col items-center justify-center h-full gap-5 text-center pb-10">
          <div className="w-14 h-14 flex items-center justify-center text-2xl
                          animate-float border border-sig-cyan/20 bg-sig-cyan/5"
               style={{ clipPath: 'polygon(50% 0%,100% 25%,100% 75%,50% 100%,0% 75%,0% 25%)' }}>
            ⬡
          </div>
          <div>
            <div className="text-lg font-semibold text-tx-hi mb-1">PREC·OS 就緒</div>
            <div className="text-sm text-tx-mid leading-relaxed">
              點擊左欄「開始分析」執行完整辨識<br/>或直接輸入問題開始對話
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 max-w-md w-full mt-2">
            {[
              { icon: '📊', title: '分析量測數據', desc: '自動識別 PIGE / PDGE 誤差項' },
              { icon: '🔍', title: 'EYC 耦合分析', desc: '解析 EYC 對 DZ 的耦合機制' },
              { icon: '🔧', title: '儀器配置建議', desc: '依誤差項推薦量測設備' },
              { icon: '🤖', title: 'AI 層設定',    desc: '殘差學習特徵設計' },
            ].map(({ icon, title, desc }) => (
              <div key={title}
                className="bg-ink-2 border border-line-1 rounded-lg p-3 text-left
                           hover:bg-ink-3 hover:border-line-2 transition-all cursor-default">
                <div className="text-base mb-1">{icon}</div>
                <div className="text-xs font-semibold text-tx-hi mb-0.5">{title}</div>
                <div className="text-[10.5px] text-tx-mid leading-snug">{desc}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {messages.map(msg => (
        <MessageBubble key={msg.id} message={msg} />
      ))}

      {isTyping && (
        <div className="flex gap-3 max-w-3xl mx-auto w-full p-4 bg-ink-1 border border-sig-cyan/30 rounded-lg shadow-sm">
          <div className="w-8 h-8 rounded flex items-center justify-center flex-shrink-0 mt-0.5
                          font-mono text-xs font-bold text-sig-cyan
                          bg-sig-cyan/10 border border-sig-cyan/25">PO</div>
          <div className="flex flex-col gap-1.5 pt-1">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full border-2 border-sig-cyan border-t-transparent animate-spin"/>
              <span className="font-sans text-[13px] font-bold text-tx-hi">PREC·OS Agent 診斷中...</span>
            </div>
            <div className="font-mono text-[11px] text-tx-lo">
              ▶ 正在根據辨識結果進行物理根因分析...
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef}/>
    </div>
  )
}
