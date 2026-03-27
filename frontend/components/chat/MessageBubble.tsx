'use client'
// components/chat/MessageBubble.tsx
import type { ChatMessage } from '@/lib/types'
import { PigeResultCard } from '../cards/PigeResultCard'
import { PdgeResultCard } from '../cards/PdgeResultCard'
import { RmsCompareCard } from '../cards/RmsCompareCard'
import { AgentCard } from '../cards/AgentCard'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from 'recharts'

// 🌟 新增引入 Markdown 解析套件
import ReactMarkdown from 'react-markdown'
import rehypeRaw from 'rehype-raw'

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

        {/* 🌟 修改區塊：使用 ReactMarkdown 替換原本的 split('\\n') */}
        <div className="text-[13px] text-tx-hi leading-7">
          <ReactMarkdown
            rehypePlugins={[rehypeRaw]}
            components={{
              // 1. 保留原本 P 標籤的間距邏輯
              p: ({ node, ...props }) => <p className="mb-2 last:mb-0" {...props} />,
              
              // 2. 完美移植你的「科技感圖片卡片」UI
              img: ({ node, ...props }) => (
                <div className="my-3 overflow-hidden rounded-md border border-sig-cyan/30 shadow-sm bg-ink-2 max-w-sm">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={props.src} alt={props.alt} className="w-full h-auto object-contain max-h-56 bg-black/20" />
                  {props.alt && (
                    <div className="px-3 py-1.5 text-[11px] text-sig-cyan bg-ink-3/50 border-t border-sig-cyan/20 text-center font-medium tracking-wide">
                      {props.alt}
                    </div>
                  )}
                </div>
              ),
              
              // 3. 讓程式碼區塊 (日誌內容) 更好看一點
              pre: ({ node, ...props }) => (
                <pre className="bg-ink-3/80 p-3 rounded-md overflow-x-auto text-[11px] font-mono border border-line-2 my-2" {...props} />
              )
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>

        {/* 附加圖表 */}
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

        {/* 物理層/AI層分析結果卡片 */}
        {!isUser && result && (
          <div className="mt-3 space-y-2">
            <PigeResultCard pige={result.pige} />
            <PdgeResultCard pdge={result.pdge} />
            <RmsCompareCard rms={result.rms} aiR2={result.ai_r2} />
            {result.findings && result.findings.length > 0 && (
              <AgentCard findings={result.findings} />
            )}
          </div>
        )}
      </div>
    </div>
  )
}