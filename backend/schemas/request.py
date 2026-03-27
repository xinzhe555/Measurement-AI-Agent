"""
schemas/request.py
前端送進來的請求格式定義
"""
from pydantic import BaseModel, Field
from typing import Optional, List


class AnalyzeRequest(BaseModel):
    """
    前端送來的分析請求。
    兩種模式：
      1. 直接給 measured_error（已有量測數據）
      2. 給 inject_params（用模擬器生成數據，Demo 用）
    """
    mode: str = Field("simulate", description="'simulate' | 'upload'")
    path_type: str = Field("cone", description="軌跡類型: 'cone' | 'sine' | 'custom'")
    view_mode: str = Field("relative", description="觀測視角: 'relative' | 'absolute'")
    ball_x: float = Field(200.0, description="量測球初始 X 坐標 (mm)")
    ball_y: float = Field(0.0, description="量測球初始 Y 坐標 (mm)")
    ball_z: float = Field(0.0, description="量測球初始 Z 坐標 (mm)")
    pivot_z: float = Field(0.0, description="A軸旋轉中心到C軸轉盤面的固定幾何距離 (mm)")
    tool_length: float = Field(0.0, description="LRT刀長 (mm)")

    # ── simulate 模式用 ──
    inject_xoc:  Optional[float] = Field(0.050,   description="注入 XOC (m)")
    inject_yoc:  Optional[float] = Field(-0.020,  description="注入 YOC (m)")
    inject_aoc:  Optional[float] = Field(0.0003,  description="注入 AOC (rad — 內部單位)")
    inject_boa:  Optional[float] = Field(0.0002,  description="注入 BOA (rad — 內部單位)")
    inject_exc:  Optional[float] = Field(10e-6,   description="注入 EXC 振幅 (m)")
    inject_eyc:  Optional[float] = Field(10e-6,   description="注入 EYC 振幅 (m)")
    inject_ezc:  Optional[float] = Field(5e-6,    description="注入 EZC 振幅 (m)")
    run_ai_layer: bool = Field(True, description="是否執行 AI 殘差層")

    # ── upload 模式用（之後真實機台接入）──
    dx: Optional[List[float]] = Field(None, description="量測 DX 序列 (m)")
    dy: Optional[List[float]] = Field(None, description="量測 DY 序列 (m)")
    dz: Optional[List[float]] = Field(None, description="量測 DZ 序列 (m)")
    a_cmd: Optional[List[float]] = Field(None, description="A軸指令序列 (rad)")
    c_cmd: Optional[List[float]] = Field(None, description="C軸指令序列 (rad)")


class ChatRequest(BaseModel):
    """聊天訊息請求"""
    message: str
    session_id: str = "default"
    context: Optional[dict] = None
