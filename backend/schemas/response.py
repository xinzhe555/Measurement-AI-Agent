"""
schemas/response.py
後端回傳給前端的資料格式定義
"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class PigeResult(BaseModel):
    """PIGE 辨識結果"""
    xoc_um: float
    yoc_um: float
    zoc_um: float
    aoc_deg: float
    boc_deg: float
    xoa_um: float
    yoa_um: float
    zoa_um: float
    boa_deg: float
    coa_deg: float
    # 識別誤差（有注入值時才有）
    xoc_error_pct: Optional[float] = None
    aoc_error_pct: Optional[float] = None
    boa_error_pct: Optional[float] = None


class PdgeResult(BaseModel):
    """PDGE 辨識結果（EXC / EYC / EZC 各自獨立）"""
    exc_amp_um: float     # EXC 振幅
    exc_phase_deg: float  # EXC 相位
    eyc_amp_um: float     # EYC 振幅
    eyc_phase_deg: float  # EYC 相位
    ezc_amp_um: float     # EZC 振幅
    ezc_freq: float       # EZC 頻率（倍頻數）
    eac_deg: float       # Wobble A
    ebc_deg: float       # Wobble B


class RmsComparison(BaseModel):
    """補償前後 RMS 比較"""
    before_dx_um: float
    before_dy_um: float
    before_dz_um: float
    after_phys_dx_um: float
    after_phys_dy_um: float
    after_phys_dz_um: float
    after_ai_dx_um: Optional[float] = None
    after_ai_dy_um: Optional[float] = None
    after_ai_dz_um: Optional[float] = None
    phys_improvement_dx_pct: float
    phys_improvement_dy_pct: float
    phys_improvement_dz_pct: float


class DiagnosticFinding(BaseModel):
    """單條診斷結論"""
    severity: str        # "critical" | "warning" | "info"
    parameter: str       # "XOC", "AOC" ...
    value_str: str       # "+43.8 μm"
    message: str
    instrument: str      # 建議使用的儀器


class AnalyzeResponse(BaseModel):
    """完整分析回應"""
    success: bool
    session_id: str
    pige: PigeResult
    pdge: PdgeResult
    rms: RmsComparison
    findings: List[DiagnosticFinding]
    ai_r2: Optional[float] = None
    error_message: Optional[str] = None


class ChatResponse(BaseModel):
    """聊天回應"""
    reply: str
    has_analysis: bool = False
    analysis: Optional[Dict[str, Any]] = None
    used_tools: Optional[list[str]] = []
    rag_sources: Optional[str] = None  # RAG 參考來源（Markdown 格式，供前端摺疊顯示）
