// components/cards/AgentCard.tsx
import { CardShell } from './_CardShell'
import type { DiagnosticFinding } from '@/lib/types'

const SEVERITY_STYLE: Record<string, string> = {
  critical: 'bg-sig-red/10 text-sig-red border-sig-red/20',
  warning:  'bg-sig-amber/10 text-sig-amber border-sig-amber/20',
  info:     'bg-sig-cyan/10 text-sig-cyan border-sig-cyan/20',
}
const SEVERITY_ICON: Record<string, string> = {
  critical: '⚠', warning: '●', info: '○',
}

export function AgentCard({ findings }: { findings: DiagnosticFinding[] }) {
  return (
    <CardShell
      titleText="Agent 診斷建議"
      titleColor="#C084FC" accentColor="#C084FC"
      badge={`${findings.length} 項建議`}
      badgeStyle="bg-sig-amber/10 text-sig-amber">
      <div>
        {findings.map((f, i) => (
          <div key={i}
            className="flex gap-3 px-3 py-2 border-b border-line-0 last:border-0
                       hover:bg-ink-3 transition-colors">
            <span className={`font-mono text-[8px] px-1.5 py-0.5 rounded border h-fit mt-0.5
                              ${SEVERITY_STYLE[f.severity] ?? SEVERITY_STYLE.info}`}>
              {SEVERITY_ICON[f.severity]} {f.parameter}
            </span>
            <div className="flex-1 min-w-0">
              <div className="text-[11.5px] text-tx-hi leading-snug">{f.message}</div>
              {f.instrument && (
                <div className="font-mono text-[9px] text-tx-lo mt-1">
                  建議儀器：<span className="text-sig-cyan">{f.instrument}</span>
                </div>
              )}
            </div>
          </div>
        ))}

        {/* 固定的儀器配置總表（補足 findings 可能不完整的情況）*/}
        <div className="grid grid-cols-2 gap-2 p-3 border-t border-line-0">
          {[
            { name: 'Laser R-Test',   meta: 'C軸跳動 / A/C同動\n<1μm / 0.0006°' },
            { name: '電子自準直儀',    meta: 'A/C垂直度 (AOC)\n<0.0003°' },
            { name: '主軸誤差分析儀',  meta: 'EXC / EYC / EZC\n<0.01μm' },
            { name: '預計調機時間',    meta: '傳統 5~7天\n本系統 ≤ 1天', highlight: true },
          ].map(({ name, meta, highlight }) => (
            <div key={name}
              className={`rounded-lg p-2 border ${
                highlight
                  ? 'border-sig-teal/25 bg-sig-teal/5'
                  : 'border-line-2 bg-ink-3'
              }`}>
              <div className={`text-[11px] font-semibold mb-1 ${highlight ? 'text-sig-teal' : 'text-tx-hi'}`}>
                {!highlight && <span className="text-sig-lime mr-1">✅</span>}
                {name}
              </div>
              <div className={`font-mono text-[8.5px] leading-relaxed whitespace-pre-line
                              ${highlight ? 'text-sig-teal' : 'text-tx-lo'}`}>
                {meta}
              </div>
            </div>
          ))}
        </div>
      </div>
    </CardShell>
  )
}
