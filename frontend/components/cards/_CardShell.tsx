// components/cards/_CardShell.tsx
// 所有分析卡片共用的外殼

interface Props {
  titleColor: string
  titleText: string
  accentColor: string
  badge?: string
  badgeStyle?: string
  children: React.ReactNode
}

export function CardShell({ titleColor, titleText, accentColor, badge, badgeStyle, children }: Props) {
  return (
    <div className="bg-ink-2 border border-line-1 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 bg-ink-3 border-b border-line-1">
        <div className="flex items-center gap-2 font-mono text-[9px] tracking-widest uppercase">
          <span className="w-0.5 h-2.5 rounded"
                style={{ background: accentColor, boxShadow: `0 0 4px ${accentColor}` }}/>
          <span style={{ color: accentColor }}>{titleText}</span>
        </div>
        {badge && (
          <span className={`font-mono text-[8px] tracking-wider px-2 py-0.5 rounded ${badgeStyle}`}>
            {badge}
          </span>
        )}
      </div>
      {children}
    </div>
  )
}

// 單格指標元件
interface MetricProps {
  label: string
  value: string
  unit?: string
  sub?: string
  valueColor?: string
}
export function Metric({ label, value, unit, sub, valueColor = 'text-sig-lime' }: MetricProps) {
  return (
    <div className="bg-ink-2 p-3">
      <div className="font-mono text-[7.5px] tracking-widest uppercase text-tx-lo mb-1">{label}</div>
      <div className={`font-mono text-[17px] font-bold leading-none ${valueColor}`}>
        {value}
        {unit && <span className="text-[9px] font-light opacity-55 ml-0.5">{unit}</span>}
      </div>
      {sub && <div className="font-mono text-[7.5px] text-tx-lo mt-1">{sub}</div>}
    </div>
  )
}

// 誤差行
interface ErrRowProps {
  sym: string
  symColor: string
  desc: string
  barPct: number
  barColor: string
  val: string
  valColor: string
}
export function ErrRow({ sym, symColor, desc, barPct, barColor, val, valColor }: ErrRowProps) {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 border-b border-line-0
                    last:border-0 hover:bg-ink-3 transition-colors">
      <span className="font-mono text-[10px] font-medium w-9" style={{ color: symColor }}>{sym}</span>
      <span className="flex-1 text-[11px] text-tx-mid">{desc}</span>
      <div className="w-16 h-[3px] bg-line-1 rounded overflow-hidden flex-shrink-0">
        <div className="h-full rounded transition-all duration-1000"
             style={{ width: `${Math.min(barPct, 100)}%`, background: barColor }}/>
      </div>
      <span className="font-mono text-[10px] w-16 text-right" style={{ color: valColor }}>{val}</span>
    </div>
  )
}
