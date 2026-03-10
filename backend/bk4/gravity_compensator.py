"""
gravity_compensator.py
重力變形誤差補償器（P1 新增）

物理背景：
    當 A 軸傾斜時，結構重心偏移，機台產生彈性變形。
    這是「準靜態」行為，可用物理公式直接預測並補償，
    不需要 AI，精度比 AI 更高、更可解釋。

補償模型（虎克定律 + 三角函數）：

    δ_z(α) = k_z × L × sin(α_A)
    δ_y(α) = k_y × L × sin(α_A) × cos(α_A)
    δ_x(α) = k_x × L × sin²(α_A)

    其中：
        α_A  = A 軸指令角度（rad）
        L    = 刀具懸伸長度（mm），預設 100mm
        k_z  = Z 向結構柔度係數（mm/mm），待標定
        k_y  = Y 向結構柔度係數
        k_x  = X 向結構柔度係數

標定方式（真實機台）：
    用 LRT 在 A = 0°, 15°, 30°, 45°, 60°, 75°, 90°
    各量一次靜態偏移，代入最小二乘求解 k_z / k_y / k_x。

    simulate 模式下提供預設模擬標定值供 Demo 使用。
"""

import numpy as np
# scipy.optimize 已不需要（改用各軸獨立線性擬合）


# ──────────────────────────────────────────────────────────────
# 預設模擬標定值（代表一台中型五軸機台的典型剛性）
# 真實機台請用 calibrate() 方法從量測數據標定
# ──────────────────────────────────────────────────────────────
DEFAULT_STIFFNESS = {
    'k_z': 2.8e-4,   # Z 向柔度：A=90° 時 L=100mm → δ_z ≈ 28 um
    'k_y': 1.2e-4,   # Y 向柔度
    'k_x': 0.5e-4,   # X 向柔度（通常最小，主軸方向）
}


class GravityCompensator:
    """
    重力變形誤差補償器

    使用流程：
        1. comp = GravityCompensator()
        2. comp.calibrate(a_angles, measured_offsets)  ← 真實機台
           或
           comp.load_simulated_params()                ← Demo 模式
        3. correction = comp.predict(a_cmd)
        4. corrected_error = raw_error - correction
    """

    def __init__(self, tool_length_mm: float = 100.0):
        """
        Parameters
        ----------
        tool_length_mm : float
            刀具懸伸長度（mm）。
            實際加工時此值從 NC 程式或刀具管理系統讀取。
        """
        self.L = tool_length_mm
        self.k_z: float = 0.0
        self.k_y: float = 0.0
        self.k_x: float = 0.0
        self.is_calibrated: bool = False
        self.calibration_rms_um: float = float('nan')

    # ── 標定 ────────────────────────────────────────────────────

    def calibrate(self,
                  a_angles_deg: np.ndarray,
                  measured_dx: np.ndarray,
                  measured_dy: np.ndarray,
                  measured_dz: np.ndarray,
                  verbose: bool = True) -> dict:
        """
        從靜態量測數據標定結構柔度係數。

        Parameters
        ----------
        a_angles_deg    : ndarray (M,)  LRT 量測時的 A 軸角度（度）
        measured_dx/y/z : ndarray (M,)  各角度下的靜態偏移量（mm）
                          （純重力項，已去除 PIGE 基準偏移）

        Returns
        -------
        params : dict   標定結果 {k_z, k_y, k_x}
        """
        a_rad = np.deg2rad(a_angles_deg)

        # 三個軸的方程式完全獨立，用各軸獨立線性最小二乘
        # （比 joint least_squares 精度更高，避免耦合造成的識別誤差）
        def _fit_axis(basis: np.ndarray, measured: np.ndarray) -> float:
            """單軸線性擬合：k = meas·basis / (basis·basis)"""
            denom = np.dot(basis, basis)
            return float(np.dot(measured, basis) / denom) if denom > 1e-12 else 0.0

        basis_z = self.L * np.sin(a_rad)
        basis_y = self.L * np.sin(a_rad) * np.cos(a_rad)
        basis_x = self.L * np.sin(a_rad) ** 2

        self.k_z = _fit_axis(basis_z, measured_dz)
        self.k_y = _fit_axis(basis_y, measured_dy)
        self.k_x = _fit_axis(basis_x, measured_dx)

        # 確保物理合理（柔度係數不能為負）
        self.k_z = max(self.k_z, 0.0)
        self.k_y = max(self.k_y, 0.0)
        self.k_x = max(self.k_x, 0.0)

        self.is_calibrated = True

        # 計算擬合殘差
        pred_z = self.k_z * basis_z
        pred_y = self.k_y * basis_y
        pred_x = self.k_x * basis_x
        residuals = np.concatenate([
            measured_dx - pred_x,
            measured_dy - pred_y,
            measured_dz - pred_z,
        ])
        self.calibration_rms_um = float(np.sqrt(np.mean(residuals**2)) * 1000)

        if verbose:
            self._print_calibration()

        return {'k_z': self.k_z, 'k_y': self.k_y, 'k_x': self.k_x,
                'rms_um': self.calibration_rms_um}

    def load_simulated_params(self,
                              k_z: float = DEFAULT_STIFFNESS['k_z'],
                              k_y: float = DEFAULT_STIFFNESS['k_y'],
                              k_x: float = DEFAULT_STIFFNESS['k_x'],
                              verbose: bool = True):
        """
        載入模擬標定值（Demo / 單元測試用）。
        不需要真實 LRT 量測數據。
        """
        self.k_z = k_z
        self.k_y = k_y
        self.k_x = k_x
        self.is_calibrated = True
        self.calibration_rms_um = 0.0  # 模擬值無量測誤差

        if verbose:
            print("\n[重力補償] 載入模擬標定值")
            self._print_calibration()

    # ── 預測 ────────────────────────────────────────────────────

    def predict(self, a_cmd: np.ndarray) -> np.ndarray:
        """
        給定 A 軸指令序列，預測重力變形補償量。

        Parameters
        ----------
        a_cmd : ndarray (N,)  A 軸指令角度（rad）

        Returns
        -------
        correction : ndarray (N, 3)  [δ_x, δ_y, δ_z]（mm）
                     從量測殘差中應減去此量
        """
        if not self.is_calibrated:
            raise RuntimeError(
                "GravityCompensator 尚未標定，"
                "請先呼叫 calibrate() 或 load_simulated_params()"
            )

        dz = self.k_z * self.L * np.sin(a_cmd)
        dy = self.k_y * self.L * np.sin(a_cmd) * np.cos(a_cmd)
        dx = self.k_x * self.L * np.sin(a_cmd) ** 2

        return np.column_stack([dx, dy, dz])

    def apply(self,
              measured_error: np.ndarray,
              a_cmd: np.ndarray,
              verbose: bool = True) -> tuple[np.ndarray, dict]:
        """
        對量測殘差應用重力補償，回傳補償後殘差與效果統計。

        Parameters
        ----------
        measured_error : ndarray (N, 3)  補償前殘差（mm）
        a_cmd          : ndarray (N,)    A 軸指令（rad）

        Returns
        -------
        corrected : ndarray (N, 3)  重力補償後殘差
        stats     : dict            補償前後 RMS
        """
        correction = self.predict(a_cmd)
        corrected  = measured_error - correction

        rms_before = np.sqrt(np.mean(measured_error**2, axis=0)) * 1000
        rms_after  = np.sqrt(np.mean(corrected**2, axis=0)) * 1000
        improvement = (1 - rms_after / np.where(rms_before > 0, rms_before, 1)) * 100

        stats = {
            'rms_before_um': rms_before,
            'rms_after_um':  rms_after,
            'improvement_pct': improvement,
            'correction_max_um': np.abs(correction).max(axis=0) * 1000,
        }

        if verbose:
            self._print_apply_result(stats)

        return corrected, stats

    # ── 報告 ────────────────────────────────────────────────────

    def _print_calibration(self):
        print("=" * 55)
        print("  [重力補償] 結構柔度係數標定結果")
        print("=" * 55)
        print(f"  刀具懸伸長度 L = {self.L:.1f} mm")
        print(f"  k_z (Z向柔度) = {self.k_z:.2e}  "
              f"→ A=90°時 δ_z = {self.k_z * self.L * 1000:.1f} um")
        print(f"  k_y (Y向柔度) = {self.k_y:.2e}  "
              f"→ A=45°時 δ_y = {self.k_y * self.L * np.sin(np.pi/4) * np.cos(np.pi/4) * 1000:.1f} um")
        print(f"  k_x (X向柔度) = {self.k_x:.2e}")
        if self.calibration_rms_um > 0:
            print(f"  標定殘差 RMS  = {self.calibration_rms_um:.3f} um")
        print("=" * 55)

    def _print_apply_result(self, stats):
        print("\n  [重力補償] 應用效果")
        print(f"  {'軸':>4} | {'補償前':>10} | {'補償後':>10} | "
              f"{'最大修正量':>10} | {'改善率':>8}")
        for i, ax in enumerate(['DX', 'DY', 'DZ']):
            b  = stats['rms_before_um'][i]
            a  = stats['rms_after_um'][i]
            mx = stats['correction_max_um'][i]
            r  = stats['improvement_pct'][i]
            print(f"  {ax:>4} | {b:>8.3f}um | {a:>8.3f}um | "
                  f"{mx:>8.2f}um   | {r:>6.1f}%")

    def to_dict(self) -> dict:
        """序列化供 FastAPI / Agent 工具回傳用"""
        return {
            'calibrated': self.is_calibrated,
            'tool_length_mm': self.L,
            'k_z': self.k_z,
            'k_y': self.k_y,
            'k_x': self.k_x,
            'calibration_rms_um': self.calibration_rms_um,
        }


# ──────────────────────────────────────────────────────────────
# 獨立驗證腳本
# python gravity_compensator.py
# ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))

    print("\n" + "★" * 55)
    print("  重力補償器驗證（模擬模式）")
    print("★" * 55)

    # ── 模擬 BK4 路徑的 A 軸指令
    t     = np.linspace(0, 4 * np.pi, 360)
    a_cmd = np.deg2rad(30 * np.sin(t))   # ±30° 擺動

    # ── 生成模擬重力誤差（作為「真值」）
    TRUE_KZ, TRUE_KY, TRUE_KX = 3.0e-4, 1.5e-4, 0.6e-4
    L = 100.0
    true_gz = np.column_stack([
        TRUE_KX * L * np.sin(a_cmd) ** 2,
        TRUE_KY * L * np.sin(a_cmd) * np.cos(a_cmd),
        TRUE_KZ * L * np.sin(a_cmd),
    ])

    # ── 模擬 7 點靜態標定量測（LRT 在各 A 角度下量測）
    cal_angles = np.array([0, 15, 30, 45, 60, 75, 90])
    cal_a_rad  = np.deg2rad(cal_angles)
    noise      = np.random.default_rng(0).normal(0, 0.0005, (7,))  # 0.5um 雜訊

    cal_dz = TRUE_KZ * L * np.sin(cal_a_rad) + noise
    cal_dy = TRUE_KY * L * np.sin(cal_a_rad) * np.cos(cal_a_rad) + noise
    cal_dx = TRUE_KX * L * np.sin(cal_a_rad) ** 2 + noise

    # ── 標定
    comp = GravityCompensator(tool_length_mm=L)
    result = comp.calibrate(cal_angles, cal_dx, cal_dy, cal_dz)

    print(f"\n  標定誤差：")
    print(f"    k_z: 真值={TRUE_KZ:.2e}  識別={comp.k_z:.2e}  "
          f"誤差={abs(comp.k_z-TRUE_KZ)/TRUE_KZ*100:.1f}%")
    print(f"    k_y: 真值={TRUE_KY:.2e}  識別={comp.k_y:.2e}  "
          f"誤差={abs(comp.k_y-TRUE_KY)/TRUE_KY*100:.1f}%")

    # ── 補償效果驗證
    rng   = np.random.default_rng(1)
    dummy_error = true_gz + rng.normal(0, 0.001, true_gz.shape)  # 加入量測雜訊
    corrected, stats = comp.apply(dummy_error, a_cmd)

    print(f"\n  重力補償效果驗證完成 ✓")
    print(f"  DZ 改善率 = {stats['improvement_pct'][2]:.1f}%")
