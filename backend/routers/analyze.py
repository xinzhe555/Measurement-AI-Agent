"""
routers/analyze.py
/api/analyze  ← 前端送量測數據進來，後端跑完整分析後回傳結果
"""
import numpy as np
from fastapi import APIRouter, HTTPException
from schemas.request import AnalyzeRequest
from schemas.response import AnalyzeResponse
from core.bk4_bridge import run_full_analysis

router = APIRouter(prefix="/api/analyze", tags=["analyze"])


@router.post("", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    """
    主要分析端點。

    前端（Next.js）呼叫方式：
        POST /api/analyze
        Body: { mode: "simulate", ball_x: 200, tool_length: 0, ... }

    回傳：完整的 PIGE/PDGE 辨識結果 + RMS 比較 + Agent 建議
    """
    try:
        if req.mode == "simulate":
            result = run_full_analysis(
                ball_x=req.ball_x,             
                ball_y=req.ball_y,
                ball_z=req.ball_z,
                tool_length=req.tool_length,  
                path_type=req.path_type,
                view_mode=req.view_mode, 
                inject_xoc=req.inject_xoc,
                inject_yoc=req.inject_yoc,
                inject_aoc=req.inject_aoc,
                inject_boa=req.inject_boa,
                inject_exc=req.inject_exc,
                inject_eyc=req.inject_eyc,
                inject_ezc=req.inject_ezc,
                run_ai=req.run_ai_layer,
            )

        elif req.mode == "upload":
            # 真實機台上傳量測數據
            if not all([req.dx, req.dy, req.dz, req.a_cmd, req.c_cmd]):
                raise HTTPException(
                    status_code=422,
                    detail="upload 模式需要提供 dx, dy, dz, a_cmd, c_cmd"
                )
            measured = np.column_stack([req.dx, req.dy, req.dz])
            result = run_full_analysis(
                ball_x=req.ball_x,             
                ball_y=req.ball_y,
                ball_z=req.ball_z,
                tool_length=req.tool_length,   
                path_type=req.path_type,
                view_mode=req.view_mode,
                run_ai=req.run_ai_layer,
                measured_error=measured,
                a_cmd_ext=np.array(req.a_cmd),
                c_cmd_ext=np.array(req.c_cmd),
            )
        else:
            raise HTTPException(status_code=422, detail=f"未知 mode: {req.mode}")

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))