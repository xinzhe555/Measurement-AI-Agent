'use client'
// components/chat/MessageBubble.tsx
import { useState } from 'react'
import type { ChatMessage } from '@/lib/types'
import { PigeResultCard } from '../cards/PigeResultCard'
import { PdgeResultCard } from '../cards/PdgeResultCard'
import { RmsCompareCard } from '../cards/RmsCompareCard'
import { AgentCard } from '../cards/AgentCard'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from 'recharts'

// 🌟 新增引入 Markdown 解析套件
import ReactMarkdown from 'react-markdown'
import rehypeRaw from 'rehype-raw'
import remarkGfm from 'remark-gfm'

interface Props { message: ChatMessage }

export function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user'
  const result = message.analysisResult
  const [showSources, setShowSources] = useState(false)

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
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeRaw]}
            components={{
              // 段落
              p: ({ node, ...props }) => <p className="mb-2 last:mb-0" {...props} />,

              // 圖片（科技感卡片）
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

              // 程式碼區塊
              pre: ({ node, ...props }) => (
                <pre className="bg-ink-3/80 p-3 rounded-md overflow-x-auto text-[11px] font-mono border border-line-2 my-2" {...props} />
              ),
              code: ({ node, className, children, ...props }) => {
                const isInline = !className
                return isInline
                  ? <code className="bg-ink-3 text-sig-cyan px-1 py-0.5 rounded text-[12px] font-mono" {...props}>{children}</code>
                  : <code className={className} {...props}>{children}</code>
              },

              // ── 表格 ──────────────────────────────────────────
              table: ({ node, ...props }) => (
                <div className="my-3 overflow-x-auto rounded-md border border-line-2">
                  <table className="w-full text-[11px] font-mono border-collapse" {...props} />
                </div>
              ),
              thead: ({ node, ...props }) => (
                <thead className="bg-ink-3 text-sig-cyan" {...props} />
              ),
              tbody: ({ node, ...props }) => (
                <tbody className="divide-y divide-line-1" {...props} />
              ),
              tr: ({ node, ...props }) => (
                <tr className="hover:bg-ink-2/60 transition-colors" {...props} />
              ),
              th: ({ node, ...props }) => (
                <th className="px-3 py-1.5 text-left font-semibold tracking-wide border-b border-line-2 whitespace-nowrap" {...props} />
              ),
              td: ({ node, ...props }) => (
                <td className="px-3 py-1.5 text-tx-hi whitespace-nowrap" {...props} />
              ),

              // 清單
              ul: ({ node, ...props }) => <ul className="list-disc list-inside mb-2 space-y-0.5" {...props} />,
              ol: ({ node, ...props }) => <ol className="list-decimal list-inside mb-2 space-y-0.5" {...props} />,
              li: ({ node, ...props }) => <li className="text-tx-hi" {...props} />,

              // 標題
              h1: ({ node, ...props }) => <h1 className="text-base font-bold text-sig-cyan mt-3 mb-1" {...props} />,
              h2: ({ node, ...props }) => <h2 className="text-sm font-bold text-sig-cyan mt-3 mb-1" {...props} />,
              h3: ({ node, ...props }) => <h3 className="text-xs font-bold text-tx-hi mt-2 mb-1" {...props} />,

              // 強調
              strong: ({ node, ...props }) => <strong className="text-tx-hi font-semibold" {...props} />,
              em: ({ node, ...props }) => <em className="text-sig-amber" {...props} />,

              // 分隔線
              hr: ({ node, ...props }) => <hr className="border-line-2 my-3" {...props} />,

              // 引用區塊
              blockquote: ({ node, ...props }) => (
                <blockquote className="border-l-2 border-sig-cyan/40 pl-3 my-2 text-tx-mid italic" {...props} />
              ),
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>

        {/* 參考來源按鈕 */}
        {!isUser && message.ragSources && (
          <div className="mt-2">
            <button
              onClick={() => setShowSources(!showSources)}
              className="flex items-center gap-1.5 font-mono text-[10px] px-2.5 py-1 rounded
                         border transition-all
                         border-sig-violet/30 text-sig-violet bg-sig-violet/5
                         hover:bg-sig-violet/15 hover:border-sig-violet/50"
            >
              <span>{showSources ? '▼' : '▶'}</span>
              <span>參考來源 (RAG)</span>
            </button>
            {showSources && (
              <div className="mt-2 bg-ink-2 border border-line-2 rounded-lg p-3
                              max-h-[40vh] overflow-y-auto
                              scrollbar-thin scrollbar-thumb-line-2 scrollbar-track-transparent">
                <div className="prose prose-invert prose-sm max-w-none
                                prose-headings:text-tx-mid prose-p:text-tx-lo
                                prose-strong:text-tx-mid prose-code:text-sig-cyan
                                text-[11px] leading-relaxed">
                  <ReactMarkdown rehypePlugins={[rehypeRaw]}>
                    {message.ragSources}
                  </ReactMarkdown>
                </div>
              </div>
            )}
          </div>
        )}

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