"""
pdge_generator.py
BK4 PDGE (Position Dependent Geometric Error) 生成器
模擬旋轉軸的動態週期性誤差：徑向跳動、軸向竄動、Wobble
"""
import numpy as np

class Physical_PDGE_Generator:
    """
    生成物理層可解析的低頻 PDGEs
    所有參數單位：mm（位置）、rad（角度）
    """
    def __init__(self):
        self.params = {
            # C 軸徑向跳動 (Radial Runout) → X/Y 1倍頻
            'C_Runout_X_Amp':   0.010,      # 10 um
            'C_Runout_X_Phase': 0.0,
            'C_Runout_Y_Amp':   0.010,      # 10 um
            'C_Runout_Y_Phase': np.pi / 2,  # 90° → 橢圓軌跡

            # C 軸軸向竄動 (Axial Runout) → Z 2倍頻
            'C_Runout_Z_Amp':  0.005,       # 5 um
            'C_Runout_Z_Freq': 2.0,

            # C 軸角度擺動 (Wobble) → 放大阿貝誤差
            'C_Wobble_A_Amp':  0.0001,      # ≈0.006 deg
            'C_Wobble_B_Amp':  0.0001,
        }

    def get_c_axis_pdge(self, theta_c_rad):
        """
        回傳 C 軸在角度 theta_c_rad 下的 6-DOF PDGE
        支援純量或 numpy 陣列輸入
        """
        t = theta_c_rad
        p = self.params

        exc = p['C_Runout_X_Amp'] * np.cos(t + p['C_Runout_X_Phase'])
        eyc = p['C_Runout_Y_Amp'] * np.sin(t + p['C_Runout_Y_Phase'])
        ezc = p['C_Runout_Z_Amp'] * np.sin(p['C_Runout_Z_Freq'] * t)
        eac = p['C_Wobble_A_Amp'] * np.cos(t)
        ebc = p['C_Wobble_B_Amp'] * np.sin(t)
        ecc = np.zeros_like(np.atleast_1d(t)).squeeze() if np.ndim(t) == 0 else np.zeros_like(t)

        return exc, eyc, ezc, eac, ebc, ecc