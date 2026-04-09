from fastapi import APIRouter
from pydantic import BaseModel
from core.bk4_bridge import Integrated_BK4_Simulator
from bk4.rodrigues_generator import RodriguesLRTGenerator
import pandas as pd
import numpy as np
import json

router = APIRouter()

class TwinSimulationRequest(BaseModel):
    # ── 模型選擇 ──────────────────────────────────────────────────────────────
    model_type: str = "pure_htm"      # "pure_htm" | "htm_rodrigues"
    machine_type: str = "AC"          # "AC" | "BC"

    # ── C 軸 PIGEs（單位：mm / deg）────────────────────────────────────────
    xoc: float = 0.0
    yoc: float = 0.0
    zoc: float = 0.0    # C 軸與搖籃軸 Z 方向距離（論文 ZOC）
    aoc: float = 0.0   # deg
    boc: float = 0.0   # deg
    coc: float = 0.0   # deg

    # ── A 軸 PIGEs（AC 機型，單位：mm / deg）──────────────────────────────
    # XOA 不存在：A 軸旋轉中心可沿 X 軸任意定義
    yoa: float = 0.0
    zoa: float = 0.0
    aoa: float = 0.0   # deg
    boa: float = 0.0   # deg
    coa: float = 0.0   # deg

    # ── B 軸 PIGEs（BC 機型，單位：mm / deg）──────────────────────────────
    # YOB 不存在：B 軸旋轉中心可沿 Y 軸任意定義
    xob: float = 0.0
    zob: float = 0.0
    aob: float = 0.0   # deg
    cob: float = 0.0   # deg

    # ── 機台幾何尺寸（單位：mm）────────────────────────────────────────────
    ball_x: float = 200.0
    ball_y: float = 0.0
    ball_z: float = 0.0
    pivot_z: float = 0.0
    tool_length: float = 0.0
    zoa_geom: float = 0.0    # 搖籃軸 Z 方向幾何距離 (Rodrigues 用)

    # ── C 軸 PDGEs（單位：mm / deg / 倍頻）────────────────────────────────
    c_runout_x_amp:   float = 0.010    # mm
    c_runout_x_phase: float = 0.0     # deg
    c_runout_y_amp:   float = 0.010    # mm
    c_runout_y_phase: float = 90.0    # deg
    c_runout_z_amp:   float = 0.005    # mm
    c_runout_z_freq:  float = 2.0     # 倍頻
    c_wobble_a_amp:   float = 0.0001  # rad
    c_wobble_b_amp:   float = 0.0001  # rad

    # ── A 軸 PDGEs（單位：mm / deg / 倍頻）────────────────────────────────
    a_runout_y_amp:   float = 0.005    # mm
    a_runout_y_phase: float = 0.0     # deg
    a_runout_z_amp:   float = 0.005    # mm
    a_runout_z_phase: float = 90.0    # deg
    a_runout_x_amp:   float = 0.002    # mm
    a_runout_x_freq:  float = 1.0     # 倍頻
    a_wobble_b_amp:   float = 0.00005  # rad
    a_wobble_c_amp:   float = 0.00005  # rad

    # ── PDGEs 開關 ──────────────────────────────────────────────────────────
    enable_c_pdge: bool = False
    enable_a_pdge: bool = False

    # ── 其他 ────────────────────────────────────────────────────────────────
    view_mode: str = "relative"
    path_type: str = "cone"
    n_points:  int = 19


def _run_pure_htm(req: TwinSimulationRequest):
    """使用純 HTM 生成器"""
    is_bc = (req.machine_type == "BC")

    # ── PIGEs：mm 直接使用，deg 轉 rad ──────────────────────────────────────
    custom_err = {
        'XOC': req.xoc,
        'YOC': req.yoc,
        'AOC': np.deg2rad(req.aoc),
        'BOC': np.deg2rad(req.boc),
        'COC': np.deg2rad(req.coc),
    }

    if is_bc:
        custom_err.update({
            'XOB': req.xob,
            'ZOB': req.zob,
            'AOB': np.deg2rad(req.aob),
            'COB': np.deg2rad(req.cob),
        })
    else:
        custom_err.update({
            'YOA': req.yoa,
            'ZOA': req.zoa,
            'AOA': np.deg2rad(req.aoa),
            'BOA': np.deg2rad(req.boa),
            'COA': np.deg2rad(req.coa),
        })

    # ── PDGEs 覆蓋 ──────────────────────────────────────────────────────────
    custom_pdge = {
        'C_Runout_X_Amp':   req.c_runout_x_amp,
        'C_Runout_X_Phase': np.deg2rad(req.c_runout_x_phase),
        'C_Runout_Y_Amp':   req.c_runout_y_amp,
        'C_Runout_Y_Phase': np.deg2rad(req.c_runout_y_phase),
        'C_Runout_Z_Amp':   req.c_runout_z_amp,
        'C_Runout_Z_Freq':  req.c_runout_z_freq,
        'C_Wobble_A_Amp':   req.c_wobble_a_amp,
        'C_Wobble_B_Amp':   req.c_wobble_b_amp,
        'A_Runout_Y_Amp':   req.a_runout_y_amp,
        'A_Runout_Y_Phase': np.deg2rad(req.a_runout_y_phase),
        'A_Runout_Z_Amp':   req.a_runout_z_amp,
        'A_Runout_Z_Phase': np.deg2rad(req.a_runout_z_phase),
        'A_Runout_X_Amp':   req.a_runout_x_amp,
        'A_Runout_X_Freq':  req.a_runout_x_freq,
        'A_Wobble_B_Amp':   req.a_wobble_b_amp,
        'A_Wobble_C_Amp':   req.a_wobble_c_amp,
    }

    sim = Integrated_BK4_Simulator()
    sim.pdge_gen.params.update(custom_pdge)

    errors, cradle_cmd, c_cmd = sim.generate(
        ball_x=req.ball_x,
        ball_y=req.ball_y,
        ball_z=req.ball_z,
        pivot_z=req.pivot_z,
        tool_length=req.tool_length,
        view_mode=req.view_mode,
        custom_errors=custom_err,
        enable_pdge=req.enable_c_pdge or req.enable_a_pdge,
        enable_a_pdge=req.enable_a_pdge,
        enable_c_pdge=req.enable_c_pdge,
        path_type=req.path_type,
        n_points=req.n_points,
        machine_type=req.machine_type,
    )
    return errors, cradle_cmd, c_cmd


def _run_rodrigues(req: TwinSimulationRequest):
    """使用 HTM + Rodrigues 生成器"""
    gen = RodriguesLRTGenerator(machine_type=req.machine_type)

    errors, cradle_cmd, c_cmd = gen.generate(
        ball_x=req.ball_x,
        ball_y=req.ball_y,
        ball_z=req.ball_z,
        tool_length=req.tool_length,
        # 幾何距離
        zoc=req.zoc,            # C 軸與搖籃軸 Z 方向幾何距離
        zoa=req.zoa_geom,       # 搖籃軸 Z 方向幾何距離
        # C 軸中心偏移誤差
        xoc=req.xoc,
        yoc=req.yoc,
        # C 軸偏擺
        aoc=np.deg2rad(req.aoc),
        boc=np.deg2rad(req.boc),
        # BC 型：B 軸
        xob=req.xob,
        zob_err=req.zob,
        aob=np.deg2rad(req.aob),
        cob=np.deg2rad(req.cob),
        # AC 型：A 軸
        yoa=req.yoa,
        zoa_err=req.zoa,
        boa=np.deg2rad(req.boa),
        coa=np.deg2rad(req.coa),
        # 軌跡
        n_points=req.n_points,
        path_type=req.path_type,
        view_mode=req.view_mode,
    )
    return errors, cradle_cmd, c_cmd


@router.post("/api/twin_simulate")
async def run_twin_simulation(req: TwinSimulationRequest):

    # ── 選擇生成器 ────────────────────────────────────────────────────────────
    if req.model_type == "htm_rodrigues":
        errors, cradle_cmd, c_cmd = _run_rodrigues(req)
    else:
        errors, cradle_cmd, c_cmd = _run_pure_htm(req)

    # ── 搖籃軸標籤 ────────────────────────────────────────────────────────────
    cradle_label = "B" if req.machine_type == "BC" else "A"

    # 暫存供 Agent 使用
    df = pd.DataFrame({
        cradle_label: cradle_cmd * 180 / np.pi,
        'C': c_cmd * 180 / np.pi,
        'X': errors[:, 0],
        'Y': errors[:, 1],
        'Z': errors[:, 2]
    })
    df.to_csv("simulated_temp_data.csv", index=False)

    meta = {
        "ball_x":       req.ball_x,
        "ball_y":       req.ball_y,
        "ball_z":       req.ball_z,
        "pivot_z":      req.pivot_z,
        "tool_length":  req.tool_length,
        "model_type":   req.model_type,
        "machine_type": req.machine_type,
        "zoc":          req.zoc,
        "zoa":          req.zoa_geom,
    }
    with open("simulated_temp_meta.json", "w") as f:
        json.dump(meta, f)

    return {
        "status": "success",
        "machine_type": req.machine_type,
        "model_type": req.model_type,
        "cradle_label": cradle_label,
        "data": {
            "dx_um": (errors[:, 0] * 1000).tolist(),
            "dy_um": (errors[:, 1] * 1000).tolist(),
            "dz_um": (errors[:, 2] * 1000).tolist(),
            "cradle_deg": (cradle_cmd * 180 / np.pi).tolist(),
            "c_deg": (c_cmd * 180 / np.pi).tolist(),
            # 向後相容（前端可能用 a_deg）
            "a_deg": (cradle_cmd * 180 / np.pi).tolist(),
        }
    }
