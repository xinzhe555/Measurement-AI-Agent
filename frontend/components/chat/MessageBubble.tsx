'use client'
// components/chat/MessageBubble.tsx
import type { ChatMessage } from '@/lib/types'
import { PigeResultCard } from '../cards/PigeResultCard'
import { PdgeResultCard } from '../cards/PdgeResultCard'
import { RmsCompareCard } from '../cards/RmsCompareCard'
import { AgentCard } from '../cards/AgentCard'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from 'recharts'

interface Props { message: ChatMessage }

export function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user'
  const result = message.analysisResult

  return (
    <div className="flex gap-3 max-w-3xl mx-auto w-full animate-rise">
      {/* 頭像 */}
      <div className={`w-7 h-7 rounded flex-shrink-0 mt-0.5
                       flex items-center justify-center
                       font-mono text-[10px] font-bold
                       ${isUser
                         ? 'bg-ink-4 border border-line-3 text-tx-mid'
                         : 'bg-sig-cyan/10 border border-sig-cyan/25 text-sig-cyan'}`}>
        {isUser ? 'RD' : 'PO'}
      </div>

      {/* 內容 */}
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2 mb-1.5">
          <span className={`text-xs font-semibold tracking-wide
            ${isUser ? 'text-tx-mid' : 'text-sig-cyan'}`}>
            {isUser ? '研究者' : 'PREC·OS'}
          </span>
          <span className="font-mono text-[9px] text-tx-off">{message.timestamp}</span>
        </div>

        {/* 使用過的工具 */}
        {!isUser && message.usedTools && message.usedTools.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2">
            {message.usedTools.map(tool => (
              <span key={tool} className="flex items-center gap-1 font-mono text-[10px] bg-ink-2 border border-line-2 text-tx-mid px-2 py-0.5 rounded-full">
                <span className="text-sig-violet">⚙</span> {tool}
              </span>
            ))}
          </div>
        )}

        {/* 訊息文字 */}
        <div className="text-[13px] text-tx-hi leading-7">
          {message.content.split('\n').map((line, i) => (
            <p key={i} className={line ? 'mb-2 last:mb-0' : 'mb-1'}>{line || '\u00A0'}</p>
          ))}
        </div>

        {message.chartData && (
          <div className="mt-3 h-48 w-full bg-ink-2 border border-line-2 rounded-lg p-2 overflow-hidden shadow-inner">
             <div className="text-[10px] font-mono text-sig-cyan mb-1 ml-1">Attachment: simulated_data.csv</div>
             <ResponsiveContainer width="100%" height="100%">
               <LineChart data={message.chartData}>
                 <CartesianGrid strokeDasharray="2 2" stroke="#2A2A2A" vertical={false} />
                 <XAxis dataKey="index" tick={false} axisLine={false} />
                 <YAxis stroke="#666" tick={{fontSize: 9}} width={30} axisLine={false} tickLine={false} />
                 <Line type="monotone" dataKey="dx" stroke="#FF5C5C" strokeWidth={1.5} dot={false} isAnimationActive={false}/>
                 <Line type="monotone" dataKey="dy" stroke="#4DA6FF" strokeWidth={1.5} dot={false} isAnimationActive={false}/>
                 <Line type="monotone" dataKey="dz" stroke="#4DFF4D" strokeWidth={1.5} dot={false} isAnimationActive={false}/>
               </LineChart>
             </ResponsiveContainer>
          </div>
        )}

        {/* 分析結果卡片（只在系統訊息且有分析結果時顯示）*/}
        {!isUser && result && (
          <div className="mt-3 space-y-2">
            <PigeResultCard pige={result.pige} />
            <PdgeResultCard pdge={result.pdge} />
            <RmsCompareCard rms={result.rms} aiR2={result.ai_r2} />
            {result.findings.length > 0 && (
              <AgentCard findings={result.findings} />
            )}
          </div>
        )}
      </div>
    </div>
  )
}
