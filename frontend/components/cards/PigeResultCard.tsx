// components/cards/PigeResultCard.tsx
import { CardShell, Metric, ErrRow } from './_CardShell'
import type { PigeResult } from '@/lib/types'

export function PigeResultCard({ pige }: { pige: PigeResult }) {
  const sign = (v: number) => v >= 0 ? `+${v}` : `${v}`
  const improv = pige.xoc_error_pct ? `DX ${100 - (pige.xoc_error_pct ?? 0)}% 改善` : '辨識完成'

  return (
    <CardShell
      titleText="PIGE 辨識結果"
      titleColor="#FFB830" accentColor="#FFB830"
      badge={improv} badgeStyle="bg-sig-lime/10 text-sig-lime">

      {/* 3格指標 */}
      <div className="grid grid-cols-3 gap-px bg-line-0">
        <Metric label="XOC" value={sign(pige.xoc_um)} unit="μm"
          sub={pige.xoc_error_pct ? `識別誤差 ${pige.xoc_error_pct}%` : undefined}
          valueColor={pige.xoc_error_pct && pige.xoc_error_pct > 10 ? 'text-sig-amber' : 'text-sig-lime'}/>
        <Metric label="AOC" value={sign(pige.aoc_mrad)} unit="mr"
          sub={pige.aoc_error_pct ? `識別誤差 ${pige.aoc_error_pct}%` : undefined}
          valueColor="text-sig-lime"/>
        <Metric label="BOA" value={sign(pige.boa_mrad)} unit="mr"
          sub={pige.boa_error_pct ? `識別誤差 ${pige.boa_error_pct}%` : undefined}
          valueColor="text-sig-lime"/>
      </div>

      {/* 誤差列 */}
      <div>
        <ErrRow sym="XOC" symColor="#FFB830" desc="C軸 X方向靜態偏心"
          barPct={(Math.abs(pige.xoc_um)/50)*100} barColor="#FFB830"
          val={`${sign(pige.xoc_um)} μm`} valColor="#FFB830"/>
        <ErrRow sym="YOC" symColor="#7EFF6E" desc="C軸 Y方向靜態偏心"
          barPct={(Math.abs(pige.yoc_um)/20)*100} barColor="#7EFF6E"
          val={`${sign(pige.yoc_um)} μm`} valColor="#7EFF6E"/>
        <ErrRow sym="AOC" symColor="#FF4560" desc="C/A 垂直度（阿貝放大）"
          barPct={(Math.abs(pige.aoc_mrad)/0.3)*100} barColor="#FF4560"
          val={`${sign(pige.aoc_mrad)} mr`} valColor="#FF4560"/>
        <ErrRow sym="BOA" symColor="#FFB830" desc="A軸歪斜（yaw）"
          barPct={(Math.abs(pige.boa_mrad)/0.2)*100} barColor="#FFB830"
          val={`${sign(pige.boa_mrad)} mr`} valColor="#FFB830"/>
      </div>
    </CardShell>
  )
}
