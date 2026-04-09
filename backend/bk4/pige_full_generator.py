"""
pige_full_generator.py
BK4 PIGE (Position Independent Geometric Error) 生成器
使用 HTM (Homogeneous Transformation Matrix) 注入靜態幾何誤差
"""
import numpy as np

# ==========================================
# ⚙️ 誤差參數設定（可調整）
# ==========================================
CONFIG = {
    'errors': {
        # [E_AC] C 軸相對於 A 軸的靜態誤差
        'XOC': 0.050,    # mm  C軸偏心X (50 um)
        'YOC': -0.020,   # mm  C軸偏心Y (-20 um)
        'ZOC': 0.000,
        'AOC': 0.0003,   # rad C/A垂直度 (≈0.017 deg)
        'BOC': 0.000,
        'COC': 0.000,

        # [E_A] A 軸相對於 Bed 的靜態誤差
        'XOA': 0.000,
        'YOA': 0.000,
        'ZOA': 0.000,
        'AOA': 0.000,
        'BOA': 0.0002,   # rad A軸歪斜 (≈0.011 deg)
        'COA': 0.000,
    }
}

class BK4_Full_PIGE_Generator:
    def __init__(self, config):
        self.cfg = config
        self.errors = config['errors']

    def _get_htm(self, x, y, z, a, b, c):
        """產生 4x4 齊次變換矩陣 (ZYX Euler)"""
        Ca, Sa = np.cos(a), np.sin(a)
        Cb, Sb = np.cos(b), np.sin(b)
        Cc, Sc = np.cos(c), np.sin(c)
        R = np.array([
            [Cb*Cc,              -Cb*Sc,              Sb,    x],
            [Sa*Sb*Cc + Ca*Sc,  -Sa*Sb*Sc + Ca*Cc,  -Sa*Cb, y],
            [-Ca*Sb*Cc + Sa*Sc,  Ca*Sb*Sc + Sa*Cc,   Ca*Cb, z],
            [0, 0, 0, 1]
        ])
        return R

    def _get_error_matrix(self, dx, dy, dz, da, db, dc):
        """產生小量誤差 HTM（一階近似）"""
        return np.array([
            [1,   -dc,  db,  dx],
            [dc,   1,  -da,  dy],
            [-db,  da,   1,  dz],
            [0,    0,    0,   1]
        ])

    def get_static_error_matrices(self):
        """取得靜態誤差矩陣 E_A, E_AC"""
        E_AC = self._get_error_matrix(
            self.errors['XOC'], self.errors['YOC'], self.errors['ZOC'],
            self.errors['AOC'], self.errors['BOC'], self.errors['COC']
        )
        E_A = self._get_error_matrix(
            self.errors['XOA'], self.errors['YOA'], self.errors['ZOA'],
            self.errors['AOA'], self.errors['BOA'], self.errors['COA']
        )
        return E_A, E_AC