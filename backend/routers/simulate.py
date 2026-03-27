from fastapi import APIRouter
from pydantic import BaseModel
from core.bk4_bridge import Integrated_BK4_Simulator
from bk4.heidenhain_generator_v2 import HeidenhainLRTGenerator
import pandas as pd
import numpy as np
import json

router = APIRouter()

class TwinSimulationRequest(BaseModel):
    # 平移誤差 (um)
    x_oc: float = 0.0; y_oc: float = 0.0; z_oc: float = 0.0
    x_oa: float = 0.0; y_oa: float = 0.0; z_oa: float = 0.0
    # 角度誤差 (deg)
    a_oc: float = 0.0; b_oc: float = 0.0; c_oc: float = 0.0
    a_oa: float = 0.0; b_oa: float = 0.0; c_oa: float = 0.0
    
    ball_x: float = 200.0
    ball_y: float = 0.0
    ball_z: float = 0.0
    pivot_z: float = 0.0
    tool_length: float = 0.0

    view_mode: str = "relative"
    enable_pdge: bool = False
    path_type: str = "cone"

    # 取樣點數
    n_points: int = 19

@router.post("/api/twin_simulate")
async def run_twin_simulation(req: TwinSimulationRequest):
    # 將 um 和 deg 轉為 mm 和 rad 供矩陣計算
    custom_err = {
        'X_OC': req.x_oc / 1000.0, 'Y_OC': req.y_oc / 1000.0, 'Z_OC': req.z_oc / 1000.0,
        'X_OA': req.x_oa / 1000.0, 'Y_OA': req.y_oa / 1000.0, 'Z_OA': req.z_oa / 1000.0,
        'A_OC': np.deg2rad(req.a_oc), 'B_OC': np.deg2rad(req.b_oc), 'C_OC': np.deg2rad(req.c_oc),
        'A_OA': np.deg2rad(req.a_oa), 'B_OA': np.deg2rad(req.b_oa), 'C_OA': np.deg2rad(req.c_oa),
    }

    sim = Integrated_BK4_Simulator()
    errors, a_cmd, c_cmd = sim.generate(
        ball_x=req.ball_x,
        ball_y=req.ball_y,
        ball_z=req.ball_z,
        pivot_z=req.pivot_z,
        tool_length=req.tool_length,
        view_mode=req.view_mode,
        custom_errors=custom_err,
        enable_pdge=req.enable_pdge,
        path_type=req.path_type,
        n_points=req.n_points,
    )
    
    # gen = HeidenhainLRTGenerator(
    #     XOC = custom_err.get('X_OC', 0.0),
    #     YOC = custom_err.get('Y_OC', 0.0),
    #     YOA = custom_err.get('Y_OA', 0.0),
    #     ZOA = custom_err.get('Z_OA', 0.0),
    #     L   = req.tool_length,
    #     ball_x = req.ball_x,
    #     ball_y = req.ball_y,
    #     ball_z = req.ball_z,
    #     n_points = req.n_points,
    # )
    # errors, a_cmd, c_cmd = gen.generate()
    
    # 將模擬資料寫入暫存檔，供 Agent 讀取盲解
    df = pd.DataFrame({
        'A': a_cmd * 180 / np.pi,
        'C': c_cmd * 180 / np.pi,
        'X': errors[:, 0],
        'Y': errors[:, 1],
        'Z': errors[:, 2]
    })
    df.to_csv("simulated_temp_data.csv", index=False)

    # 同步儲存機台幾何參數，供 PhysicalLayerAnalyzer 逆向辨識時使用
    meta = {
        "ball_x":      req.ball_x,
        "ball_y":      req.ball_y,
        "ball_z":      req.ball_z,
        "pivot_z":     req.pivot_z,
        "tool_length": req.tool_length,
    }
    with open("simulated_temp_meta.json", "w") as f:
        json.dump(meta, f)
    # ======================================================

    return {
        "status": "success",
        "data": {
            "dx_um": (errors[:, 0] * 1000).tolist(),
            "dy_um": (errors[:, 1] * 1000).tolist(),
            "dz_um": (errors[:, 2] * 1000).tolist(),
            "a_deg": (a_cmd * 180 / np.pi).tolist(),  
            "c_deg": (c_cmd * 180 / np.pi).tolist(),  
        }
    }