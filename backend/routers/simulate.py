from fastapi import APIRouter
from pydantic import BaseModel
from bk4.generator import Integrated_BK4_Simulator
import pandas as pd # 確保有 import pandas
import numpy as np

router = APIRouter()

class TwinSimulationRequest(BaseModel):
    # 平移誤差 (um)
    x_oc: float = 0.0; y_oc: float = 0.0; z_oc: float = 0.0
    x_oa: float = 0.0; y_oa: float = 0.0; z_oa: float = 0.0
    # 角度誤差 (mrad)
    a_oc: float = 0.0; b_oc: float = 0.0; c_oc: float = 0.0
    a_oa: float = 0.0; b_oa: float = 0.0; c_oa: float = 0.0
    
    # ── 修正：移除舊的 pivot_x/y/z，改為標準的球心與刀長定義 ──
    ball_x: float = 200.0
    ball_y: float = 0.0
    ball_z: float = 0.0
    tool_length: float = 0.0

    view_mode: str = "relative"
    enable_pdge: bool = False
    path_type: str = "cone"

@router.post("/api/twin_simulate")
async def run_twin_simulation(req: TwinSimulationRequest):
    # 將 um 和 mrad 轉為 mm 和 rad 供矩陣計算
    custom_err = {
        'X_OC': req.x_oc / 1000.0, 'Y_OC': req.y_oc / 1000.0, 'Z_OC': req.z_oc / 1000.0,
        'X_OA': req.x_oa / 1000.0, 'Y_OA': req.y_oa / 1000.0, 'Z_OA': req.z_oa / 1000.0,
        'A_OC': req.a_oc / 1000.0, 'B_OC': req.b_oc / 1000.0, 'C_OC': req.c_oc / 1000.0,
        'A_OA': req.a_oa / 1000.0, 'B_OA': req.b_oa / 1000.0, 'C_OA': req.c_oa / 1000.0,
    }
    
    sim = Integrated_BK4_Simulator()
    
    # ── 修正：正確帶入 ball_x/y/z，並把 tool_length 傳給 pivot_z ──
    errors, a_cmd, c_cmd = sim.generate(
        ball_x=req.ball_x,
        ball_y=req.ball_y,
        ball_z=req.ball_z,
        pivot_z=req.tool_length,  # 刀長等效於旋轉中心 Z 偏移
        view_mode=req.view_mode,
        custom_errors=custom_err,
        enable_pdge=req.enable_pdge,
        path_type=req.path_type
    )
    
    # 將模擬資料寫入暫存檔，供 Agent 讀取盲解
    df = pd.DataFrame({
        'A': a_cmd * 180 / np.pi,
        'C': c_cmd * 180 / np.pi,
        'X': errors[:, 0],
        'Y': errors[:, 1],
        'Z': errors[:, 2]
    })
    # 存檔至後端目錄 (請確保路徑與你的分析器讀取路徑一致)
    df.to_csv("simulated_temp_data.csv", index=False)
    # ======================================================

    return {
        "status": "success",
        "data": {
            "dx_um": (errors[:, 0] * 1000).tolist(),
            "dy_um": (errors[:, 1] * 1000).tolist(),
            "dz_um": (errors[:, 2] * 1000).tolist(),
        }
    }