"""
pdge_generator.py
BK4 PDGE (Position Dependent Geometric Error) 生成器
模擬旋轉軸的動態週期性誤差：徑向跳動、軸向竄動、Wobble

params 字典可在外部直接覆蓋（simulate.py 透過 sim.pdge_gen.params.update() 注入前端數值）
所有 Amp 單位：mm；Phase/Wobble 單位：rad；Freq：倍頻（無單位）
"""
import numpy as np


class Physical_PDGE_Generator:
    """
    生成物理層可解析的低頻 PDGEs
    所有參數單位：mm（位置）、rad（角度）
    """
    def __init__(self):
        self.params = {
            # ── C 軸 PDGEs ────────────────────────────────────────────────
            # 徑向跳動 (Radial Runout) → EXC / EYC  1倍頻
            'C_Runout_X_Amp':   0.010,
            'C_Runout_X_Phase': 0.0,
            'C_Runout_Y_Amp':   0.010,
            'C_Runout_Y_Phase': np.pi / 2,   # 90 deg → 橢圓軌跡

            # 軸向竄動 (Axial Runout) → EZC  N倍頻
            'C_Runout_Z_Amp':  0.005,
            'C_Runout_Z_Freq': 2.0,

            # 角度擺動 (Wobble) → EAC / EBC
            'C_Wobble_A_Amp':  0.0001,       # ≈ 0.006 deg
            'C_Wobble_B_Amp':  0.0001,

            # ── A 軸 PDGEs ────────────────────────────────────────────────
            # A 軸旋轉軸為 X 軸：
            #   徑向跳動在 YZ 平面 → EYA / EZA
            #   軸向竄動沿 X 軸   → EXA
            #   Wobble 繞 Y/Z 軸  → EBA / ECA
            #   EAA（自旋誤差）無法量測，固定為 0

            # 徑向跳動 → EYA / EZA  1倍頻
            'A_Runout_Y_Amp':   0.005,
            'A_Runout_Y_Phase': 0.0,
            'A_Runout_Z_Amp':   0.005,
            'A_Runout_Z_Phase': np.pi / 2,

            # 軸向竄動 → EXA  N倍頻
            'A_Runout_X_Amp':  0.002,
            'A_Runout_X_Freq': 1.0,

            # 角度擺動 (Wobble) → EBA / ECA
            'A_Wobble_B_Amp':  0.00005,      # ≈ 0.003 deg
            'A_Wobble_C_Amp':  0.00005,
        }

    def get_c_axis_pdge(self, theta_c_rad):
        """
        回傳 C 軸在角度 theta_c_rad 下的 6-DOF PDGE
        回傳順序：(EXC, EYC, EZC, EAC, EBC, ECC)
        支援純量或 numpy 陣列輸入
        """
        t = theta_c_rad
        p = self.params

        exc = p['C_Runout_X_Amp'] * np.cos(t + p['C_Runout_X_Phase'])
        eyc = p['C_Runout_Y_Amp'] * np.sin(t + p['C_Runout_Y_Phase'])
        ezc = p['C_Runout_Z_Amp'] * np.sin(p['C_Runout_Z_Freq'] * t)
        eac = p['C_Wobble_A_Amp'] * np.cos(t)
        ebc = p['C_Wobble_B_Amp'] * np.sin(t)
        ecc = (np.zeros_like(np.atleast_1d(t)).squeeze()
               if np.ndim(t) == 0 else np.zeros_like(t))

        return exc, eyc, ezc, eac, ebc, ecc

    def get_a_axis_pdge(self, theta_a_rad):
        """
        回傳 A 軸在角度 theta_a_rad 下的 6-DOF PDGE
        回傳順序：(EXA, EYA, EZA, EAA, EBA, ECA)

        物理對應：
          EXA : 軸向竄動（沿 A 軸旋轉軸 X 方向）
          EYA : 徑向跳動 Y 分量
          EZA : 徑向跳動 Z 分量
          EAA : 自旋誤差（繞 X 軸，無法量測，固定為 0）
          EBA : Wobble 繞 Y 軸
          ECA : Wobble 繞 Z 軸

        支援純量或 numpy 陣列輸入
        """
        t = theta_a_rad
        p = self.params

        exa = p['A_Runout_X_Amp'] * np.sin(p['A_Runout_X_Freq'] * t)
        eya = p['A_Runout_Y_Amp'] * np.cos(t + p['A_Runout_Y_Phase'])
        eza = p['A_Runout_Z_Amp'] * np.sin(t + p['A_Runout_Z_Phase'])
        eaa = (np.zeros_like(np.atleast_1d(t)).squeeze()
               if np.ndim(t) == 0 else np.zeros_like(t))
        eba = p['A_Wobble_B_Amp'] * np.cos(t)
        eca = p['A_Wobble_C_Amp'] * np.sin(t)

        return exa, eya, eza, eaa, eba, eca