"""
core/bk4_bridge.py

橋接層：把你現有的 Python 模組包裝成 FastAPI 可以呼叫的介面。
你的 bk4/ 資料夾裡的程式碼完全不需要修改。
"""
import sys
import os
import numpy as np
from typing import Optional

# 確保 bk4/ 在 import 路徑裡
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bk4'))

from bk4.pige_full_generator import BK4_Full_PIGE_Generator
from bk4.pdge_generator import Physical_PDGE_Generator
from bk4.generator import Integrated_BK4_Simulator
from bk4.physical_analyzer import PhysicalLayerAnalyzer, AgentDiagnosticReport
from bk4.ai_residual_learner import AIResidualLearner, inject_nonlinear_residuals

from schemas.response import (
    AnalyzeResponse, PigeResult, PdgeResult,
    RmsComparison, DiagnosticFinding
)


def run_full_analysis(
    ball_x: float = 200.0,      
    ball_y: float = 0.0,         
    ball_z: float = 0.0,        
    tool_length: float = 0.0,   
    inject_xoc: float = 0.050,
    inject_yoc: float = -0.020,
    inject_aoc: float = 0.0003,
    inject_boa: float = 0.0002,
    inject_exc: float = 10e-6,
    inject_eyc: float = 10e-6,
    inject_ezc: float = 5e-6,
    run_ai: bool = True,
    measured_error: Optional[np.ndarray] = None,
    a_cmd_ext: Optional[np.ndarray] = None,
    c_cmd_ext: Optional[np.ndarray] = None,
) -> AnalyzeResponse:
    """
    執行完整的 BK4 分析流程：
      1. 生成或接收量測數據
      2. 物理層 HTM 辨識
      3. AI 殘差層（可選）
      4. Agent 診斷建議

    Returns:
        AnalyzeResponse  可直接被 FastAPI 序列化回傳給前端
    """

    # ── Step 1：準備數據 ──────────────────────────────────
    if measured_error is None:
        # simulate 模式：用你現有的 generator 生成
        config = _build_config(inject_xoc, inject_yoc, inject_aoc, inject_boa,
                               inject_exc, inject_eyc, inject_ezc)
        sim = Integrated_BK4_Simulator(config)

        raw_error, a_cmd, c_cmd = sim.generate(
            ball_x=ball_x, 
            ball_y=ball_y, 
            ball_z=ball_z, 
            pivot_z=tool_length
        )
    else:
        # upload 模式：直接使用上傳的數據
        raw_error = measured_error
        a_cmd = a_cmd_ext
        c_cmd = c_cmd_ext

    # ── Step 2：物理層辨識 ────────────────────────────────
    identifier = PhysicalLayerAnalyzer()
    params, phys_residual = identifier.identify(
        measured_error=raw_error,
        a_cmd=a_cmd,
        c_cmd=c_cmd,
        ball_x=ball_x,           
        ball_y=ball_y,           
        ball_z=ball_z,           
        tool_length=tool_length, 
        verbose=False
    )

    rms_before = np.sqrt(np.mean(raw_error**2, axis=0)) * 1e6   # → μm
    rms_phys   = np.sqrt(np.mean(phys_residual**2, axis=0)) * 1e6

    # ── Step 3：AI 殘差層 ─────────────────────────────────
    ai_r2 = None
    final_residual = phys_residual

    if run_ai:
        mlp = AIResidualLearner()
        # 注入非線性殘差（有 nonlinear residuals 時才有意義）
        nlr = inject_nonlinear_residuals(a_cmd, c_cmd)
        train_target = phys_residual + nlr
        mlp.train(a_cmd, c_cmd, train_target, verbose=False)
        ai_pred = mlp.predict(a_cmd, c_cmd)
        final_residual = phys_residual - ai_pred
        ai_r2 = float(mlp.r2_score) if hasattr(mlp, 'r2_score') else None

    rms_ai = np.sqrt(np.mean(final_residual**2, axis=0)) * 1e6

    # ── Step 4：Agent 診斷 ────────────────────────────────
    agent = AgentDiagnosticReport()
    report = agent.generate(
        identified_params=params,
        residual_rms_after=float(np.mean(rms_phys)),
        verbose=False
    )
    findings = _parse_findings(report.get('findings', []))

    # ── Step 5：組裝回應 ──────────────────────────────────
    pige = _build_pige_result(params, inject_xoc, inject_yoc, inject_aoc, inject_boa)
    pdge = _build_pdge_result(params)
    rms  = _build_rms_comparison(rms_before, rms_phys, rms_ai)

    return AnalyzeResponse(
        success=True,
        session_id=_gen_session_id(),
        pige=pige,
        pdge=pdge,
        rms=rms,
        findings=findings,
        ai_r2=ai_r2,
    )


# ── 工具函式 ─────────────────────────────────────────────────

def _build_config(xoc, yoc, aoc, boa, exc, eyc, ezc):
    """用注入參數建立 CONFIG dict（對應你的 pige_full_generator.py）"""
    from bk4.pige_full_generator import CONFIG as BASE_CONFIG
    import copy
    cfg = copy.deepcopy(BASE_CONFIG)
    cfg['errors']['X_OC'] = xoc
    cfg['errors']['Y_OC'] = yoc
    cfg['errors']['A_OC'] = aoc
    cfg['errors']['B_OA']  = boa
    cfg['PDGE'] = {
        'C_Runout_X_Amp': exc,
        'C_Runout_Y_Amp': eyc,
        'C_Runout_Z_Amp': ezc
    }
    return cfg


def _build_pige_result(params, inj_xoc, inj_yoc, inj_aoc, inj_boa) -> PigeResult:
    to_um   = lambda v: round(float(v) * 1e6, 2)
    to_mrad = lambda v: round(float(v) * 1e3, 4)
    pct = lambda identified, injected: (
        round(abs(identified - injected) / abs(injected) * 100, 1)
        if injected != 0 else None
    )

    return PigeResult(
        xoc_um=to_um(params['X_OC']),   yoc_um=to_um(params['Y_OC']),
        zoc_um=to_um(params['Z_OC']),   aoc_mrad=to_mrad(params['A_OC']),
        boc_mrad=to_mrad(params['B_OC']),
        xoa_um=to_um(params['X_OA']),   yoa_um=to_um(params['Y_OA']),
        zoa_um=to_um(params['Z_OA']),   boa_mrad=to_mrad(params['B_OA']),
        coa_mrad=to_mrad(params['C_OA']),
        xoc_error_pct=pct(params['X_OC'], inj_xoc),
        aoc_error_pct=pct(params['A_OC'], inj_aoc),
        boa_error_pct=pct(params['B_OA'], inj_boa),
    )


def _build_pdge_result(params) -> PdgeResult:
    return PdgeResult(
        exc_amp_um=round(float(params['Runout_X_Amp']) * 1e6, 3),
        exc_phase_deg=round(float(np.degrees(params['Runout_X_Phase'])), 1),
        eyc_amp_um=round(float(params['Runout_Y_Amp']) * 1e6, 3),
        eyc_phase_deg=round(float(np.degrees(params['Runout_Y_Phase'])), 1),
        ezc_amp_um=round(float(params['Runout_Z_Amp']) * 1e6, 3),
        ezc_freq=round(float(params['Runout_Z_Freq']), 2),
        eac_mrad=round(float(params['Wobble_A_Amp']) * 1e3, 4),
        ebc_mrad=round(float(params['Wobble_B_Amp']) * 1e3, 4),
    )


def _build_rms_comparison(before, phys, ai) -> RmsComparison:
    imp = lambda b, a: round((1 - a/b) * 100, 1) if b > 0 else 0.0
    return RmsComparison(
        before_dx_um=round(float(before[0]), 2),
        before_dy_um=round(float(before[1]), 2),
        before_dz_um=round(float(before[2]), 2),
        after_phys_dx_um=round(float(phys[0]), 3),
        after_phys_dy_um=round(float(phys[1]), 3),
        after_phys_dz_um=round(float(phys[2]), 3),
        after_ai_dx_um=round(float(ai[0]), 3),
        after_ai_dy_um=round(float(ai[1]), 3),
        after_ai_dz_um=round(float(ai[2]), 3),
        phys_improvement_dx_pct=imp(before[0], phys[0]),
        phys_improvement_dy_pct=imp(before[1], phys[1]),
        phys_improvement_dz_pct=imp(before[2], phys[2]),
    )


def _parse_findings(raw_findings: list) -> list[DiagnosticFinding]:
    result = []
    for f in raw_findings:
        desc = f.get('desc', '')
        impact = f.get('impact', '')
        action = f.get('action', '')
        msg = f"{desc}\n影響：{impact}\n建議：{action}"
        
        result.append(DiagnosticFinding(
            severity=f.get('level', 'info'),  
            parameter='',                     
            value_str='',                     
            message=msg.strip(),              
            instrument=f.get('inst', ''),     
        ))
    return result


def _gen_session_id() -> str:
    import uuid
    return str(uuid.uuid4())[:8]
