// components/cards/RmsCompareCard.tsx
import { CardShell } from './_CardShell'
import type { RmsComparison } from '@/lib/types'

interface Props { rms: RmsComparison; aiR2?: number }

export function RmsCompareCard({ rms, aiR2 }: Props) {
  const axes = [
    { ax: 'DX', before: rms.before_dx_um, phys: rms.after_phys_dx_um, ai: rms.after_ai_dx_um, color: '#FF4560' },
    { ax: 'DY', before: rms.before_dy_um, phys: rms.after_phys_dy_um, ai: rms.after_ai_dy_um, color: '#7EFF6E' },
    { ax: 'DZ', before: rms.before_dz_um, phys: rms.after_phys_dz_um, ai: rms.after_ai_dz_um, color: '#00CFFF' },
  ]
  const maxBefore = Math.max(rms.before_dx_um, rms.before_dy_um, rms.before_dz_um)

  return (
    <CardShell
      titleText="補償效果 RMS 比較"
      titleColor="#00CFFF" accentColor="#00CFFF">
      <div className="p-3 space-y-3">
        {axes.map(({ ax, before, phys, ai, color }) => (
          <div key={ax}>
            <div className="flex items-center gap-2 mb-1">
              <span className="font-mono text-[9px] w-5" style={{ color }}>{ax}</span>
              <span className="font-mono text-[8px] text-tx-lo">原始</span>
              <div className="flex-1 h-[4px] bg-line-1 rounded overflow-hidden">
                <div className="h-full rounded" style={{ width: `${(before/maxBefore)*100}%`, background: color, opacity: 0.35 }}/>
              </div>
              <span className="font-mono text-[9px] text-tx-lo w-14 text-right">{before} μm</span>
            </div>
            <div className="flex items-center gap-2 mb-1">
              <span className="font-mono text-[9px] w-5"/>
              <span className="font-mono text-[8px] text-tx-lo">物理層</span>
              <div className="flex-1 h-[4px] bg-line-1 rounded overflow-hidden">
                <div className="h-full rounded transition-all duration-1000"
                     style={{ width: `${(phys/maxBefore)*100}%`, background: color }}/>
              </div>
              <span className="font-mono text-[9px] w-14 text-right" style={{ color }}>{phys} μm</span>
            </div>
            {ai !== undefined && (
              <div className="flex items-center gap-2">
                <span className="font-mono text-[9px] w-5"/>
                <span className="font-mono text-[8px] text-tx-lo">AI 層</span>
                <div className="flex-1 h-[4px] bg-line-1 rounded overflow-hidden">
                  <div className="h-full rounded transition-all duration-1000"
                       style={{ width: `${(ai/maxBefore)*100}%`, background: '#00E8D0' }}/>
                </div>
                <span className="font-mono text-[9px] text-sig-teal w-14 text-right">{ai} μm</span>
              </div>
            )}
          </div>
        ))}
        {aiR2 && (
          <div className="font-mono text-[8.5px] text-tx-lo border-t border-line-0 pt-2">
            AI 殘差層 R² = <span className="text-sig-teal">{aiR2.toFixed(3)}</span>
            <span className="ml-3 text-tx-off">early stopping 防過擬合</span>
          </div>
        )}
      </div>
    </CardShell>
  )
}
