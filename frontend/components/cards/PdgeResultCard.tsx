// components/cards/PdgeResultCard.tsx
import { CardShell, ErrRow } from './_CardShell'
import type { PdgeResult } from '@/lib/types'

export function PdgeResultCard({ pdge }: { pdge: PdgeResult }) {
  return (
    <CardShell
      titleText="PDGE 辨識結果"
      titleColor="#00CFFF" accentColor="#00CFFF"
      badge="諧波擬合完成" badgeStyle="bg-sig-lime/10 text-sig-lime">
      <div>
        <ErrRow sym="EXC" symColor="#00CFFF" desc={`C軸 X徑向跳動 @ 1倍頻  Phase: ${pdge.exc_phase_deg}°`}
          barPct={(pdge.exc_amp_um/10)*100} barColor="#00CFFF"
          val={`${pdge.exc_amp_um} μm`} valColor="#00CFFF"/>
        <ErrRow sym="EYC" symColor="#00CFFF" desc={`C軸 Y徑向跳動 @ 1倍頻  Phase: ${pdge.eyc_phase_deg}°`}
          barPct={(pdge.eyc_amp_um/10)*100} barColor="#00CFFF"
          val={`${pdge.eyc_amp_um} μm`} valColor="#00CFFF"/>
        <ErrRow sym="EZC" symColor="#7EFF6E" desc={`C軸 Z軸向竄動 @ ${pdge.ezc_freq}倍頻（馬鞍形）`}
          barPct={(pdge.ezc_amp_um/5)*100} barColor="#7EFF6E"
          val={`${pdge.ezc_amp_um} μm`} valColor="#7EFF6E"/>
        <ErrRow sym="EAC" symColor="#7EFF6E" desc="C軸 A向角度擺動（Wobble）"
          barPct={Math.min((pdge.eac_deg/0.006)*100, 100)} barColor="#7EFF6E"
          val={`${pdge.eac_deg} deg`} valColor="#7EFF6E"/>
        <ErrRow sym="EBC" symColor="#7EFF6E" desc="C軸 B向角度擺動（Wobble）"
          barPct={Math.min((pdge.ebc_deg/0.006)*100, 100)} barColor="#7EFF6E"
          val={`${pdge.ebc_deg} deg`} valColor="#7EFF6E"/>
      </div>
    </CardShell>
  )
}
