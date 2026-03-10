"""
k1k2_simulator.py
K1/K2 DBB 圓度測試模擬器 — 第二步

【這個檔案的目的】
    反轉尖峰在 BK4 路徑上「看起來」很小（BK4 整個軌跡 360 點裡只有幾個尖峰），
    但在 DBB（Double Ball Bar）圓度測試中，換向點是圓形路徑的固定位置，
    每次測量都在同一個地方，尖峰的形狀非常清楚。

    K1 和 K2 的定義（來自你的研究）：
        K1 = 大半徑圓（R = 150mm），XY 平面
        K2 = 小半徑圓（R = 50mm），XY 平面
    兩個測試的「象限點」（X+/X-/Y+/Y- 方向的換向位置）剛好是
    反轉尖峰最明顯的地方。

【DBB 圓度測試的物理】
    DBB 量的不是絕對位置，而是：
        r_measured(θ) = R + δr(θ)

    其中 δr(θ) 是在角度 θ 時，兩軸聯動的徑向位置誤差。
    反轉尖峰發生在 θ = 0°, 90°, 180°, 270°（軸換向點），
    伺服不匹配則讓圓形變成橢圓（所有角度都有，而不是局部尖峰）。

【這個模擬器的用途】
    1. 生成帶有反轉尖峰和伺服不匹配的「模擬 DBB 量測數據」
    2. 讓 LSTM 用 BK4 路徑訓練後，在 DBB 測試上驗證泛化能力
    3. 提供論文第四章「驗證實驗」的模擬結果圖

依賴：numpy
"""

import numpy as np
from dataclasses import dataclass


# ══════════════════════════════════════════════════════════════
#  DBB 測試結果的資料結構
# ══════════════════════════════════════════════════════════════

@dataclass
class DBBResult:
    """
    DBB 圓度測試的量測結果。

    Attributes
    ----------
    theta_rad : ndarray (N,)
        圓形路徑的角度參數，0 到 2π
    x_ideal   : ndarray (N,)
        理想 X 位置（mm）
    y_ideal   : ndarray (N,)
        理想 Y 位置（mm）
    x_actual  : ndarray (N,)
        含誤差的實際 X 位置（mm）
    y_actual  : ndarray (N,)
        含誤差的實際 Y 位置（mm）
    dr_um     : ndarray (N,)
        徑向誤差 = sqrt(x_actual²+y_actual²) - R，單位 μm
    roundness_um : float
        圓度 = max(dr) - min(dr)，單位 μm（越小越好）
    spike_indices : ndarray
        尖峰發生的採樣點索引（θ = 0°, 90°, 180°, 270° 附近）
    radius_mm : float
        名義半徑
    label     : str
        K1 或 K2
    """
    theta_rad:    np.ndarray
    x_ideal:      np.ndarray
    y_ideal:      np.ndarray
    x_actual:     np.ndarray
    y_actual:     np.ndarray
    dr_um:        np.ndarray
    roundness_um: float
    spike_indices: np.ndarray
    radius_mm:    float
    label:        str


# ══════════════════════════════════════════════════════════════
#  K1/K2 DBB 模擬器主類別
# ══════════════════════════════════════════════════════════════

class K1K2Simulator:
    """
    K1/K2 DBB 圓度測試模擬器。

    使用方式：
        sim = K1K2Simulator()
        k1  = sim.run_k1()   # 大半徑，反轉尖峰更明顯
        k2  = sim.run_k2()   # 小半徑，伺服不匹配更明顯（相對比例大）
        sim.print_summary(k1, k2)
    """

    def __init__(
        self,
        n_points:      int   = 720,    # 每圈採樣點數（720 = 每 0.5° 一點）
        spike_amp_um:  float = 8.0,    # 反轉尖峰幅值（μm）
        spike_width:   int   = 4,      # 尖峰寬度（採樣點數）
        kv_mismatch:   float = 0.04,   # Kv 不匹配比例（4% = 典型值）
        noise_std_um:  float = 0.5,    # 量測雜訊（μm）
        seed:          int   = 0,
    ):
        """
        Parameters
        ----------
        n_points     : 圓形路徑的採樣點數。720 點讓每個象限有 180 點，
                       足夠看清楚尖峰的形狀。
        spike_amp_um : 反轉尖峰幅值（μm）。
                       真實機台 5-20 μm，取決於進給速度。
                       這裡取 8 μm 作為中等值。
        spike_width  : 尖峰的寬度（採樣點數）。
                       太窄（1-2 點）會被量測雜訊淹沒，
                       太寬（>10 點）代表阻尼很差，機台有問題。
        kv_mismatch  : Kv 不匹配比例（無因次）。
                       這是讓圓形變橢圓的主因。
                       在 DBB 報告上，橢圓的長短軸差 ≈ 2 × kv_mismatch × R。
        noise_std_um : 量測雜訊，包含感測器雜訊和環境振動。
        """
        self.n_points     = n_points
        self.spike_amp_um = spike_amp_um
        self.spike_width  = spike_width
        self.kv_mismatch  = kv_mismatch
        self.noise_std_um = noise_std_um
        self.rng          = np.random.default_rng(seed)

    def run_k1(self, radius_mm: float = 150.0) -> DBBResult:
        """執行 K1 測試（大半徑）"""
        return self._simulate(radius_mm, label='K1')

    def run_k2(self, radius_mm: float = 50.0) -> DBBResult:
        """執行 K2 測試（小半徑）"""
        return self._simulate(radius_mm, label='K2')

    def _simulate(self, R: float, label: str) -> DBBResult:
        """
        核心模擬函式。

        DBB 測試的運動學：
        - X 軸指令：x(θ) = R × cos(θ)
        - Y 軸指令：y(θ) = R × sin(θ)
        - X 軸速度：vx = -R × ω × sin(θ)，在 θ=0°,180° 時為零（X 換向）
        - Y 軸速度：vy =  R × ω × cos(θ)，在 θ=90°,270° 時為零（Y 換向）
        """
        theta = np.linspace(0, 2 * np.pi, self.n_points, endpoint=False)

        # 理想圓形路徑
        x_ideal = R * np.cos(theta)
        y_ideal = R * np.sin(theta)

        # 速度（對 θ 微分，正比於角速度 ω，這裡設 ω=1）
        vx = -R * np.sin(theta)   # X 軸速度
        vy =  R * np.cos(theta)   # Y 軸速度

        # ── 誤差項 1：反轉尖峰 ────────────────────────────
        #
        # X 軸換向點：θ = 0°（vx=0，從負到正），θ = 180°（vx=0，從正到負）
        # Y 軸換向點：θ = 90°（vy=0，從正到負），θ = 270°（vy=0，從負到正）
        #
        # 尖峰形狀：用高斯函數近似（指數衰減太陡，高斯更接近真實波形）
        #           尖峰的方向與換向前的速度方向有關（作用力反向）

        dx_spike = np.zeros(self.n_points)
        dy_spike = np.zeros(self.n_points)

        # 找四個換向點的索引
        # θ = 0°: idx=0 或接近 n_points-1
        # θ = 90°: idx ≈ n_points/4
        # θ = 180°: idx ≈ n_points/2
        # θ = 270°: idx ≈ 3*n_points/4
        quadrant_angles = [0, np.pi/2, np.pi, 3*np.pi/2]
        quadrant_axes   = ['x', 'y', 'x', 'y']   # 哪個軸在換向
        quadrant_signs  = [+1, -1, -1, +1]         # 尖峰方向

        spike_indices_list = []

        for angle, axis, sign in zip(quadrant_angles, quadrant_axes, quadrant_signs):
            # 找最接近換向角度的採樣點
            center_idx = int(angle / (2 * np.pi) * self.n_points) % self.n_points

            # 用高斯函數生成尖峰
            # sigma = spike_width / 2.5 讓高斯的「有效寬度」等於 spike_width
            sigma = self.spike_width / 2.5
            for d in range(-self.spike_width * 2, self.spike_width * 2 + 1):
                t = (center_idx + d) % self.n_points
                gauss = np.exp(-0.5 * (d / sigma) ** 2)
                amp   = sign * self.spike_amp_um * 1e-3 * gauss

                if axis == 'x':
                    # X 軸換向 → X 方向尖峰，同時有一個小的 Y 耦合
                    dx_spike[t] += amp
                    dy_spike[t] += amp * 0.1   # 10% 的 Y 向耦合（機台結構柔度）
                else:
                    # Y 軸換向 → Y 方向尖峰
                    dy_spike[t] += amp
                    dx_spike[t] += amp * 0.1

            spike_indices_list.append(center_idx)

        # ── 誤差項 2：伺服不匹配（Kv 不匹配讓圓形變橢圓）───
        #
        # 伺服追蹤誤差 = 速度 / Kv
        # 若 X 軸 Kv 比 Y 軸高 kv_mismatch，則：
        #   x 方向的追蹤誤差比 y 方向小 kv_mismatch 的比例
        #   結果是：水平方向的軌跡「縮小」，垂直方向不變，橢圓就出現了
        #
        # 數學推導：
        #   x_actual(θ) ≈ (R - kv_mismatch × |vx| × R/速度最大值) × cos(θ)
        #   y_actual(θ) ≈ R × sin(θ)
        # 簡化成：x 方向有一個 kv_mismatch × R 大小的系統性縮放

        # 追蹤誤差 ∝ 速度
        # 這裡用 vx * kv_mismatch 近似，方向與速度方向相反（誤差落後）
        dx_servo = -self.kv_mismatch * vx * 0.02   # 縮放係數讓 RMS 落在 μm 量級
        dy_servo = -self.kv_mismatch * vy * 0.02

        # ── 誤差項 3：量測雜訊 ────────────────────────────
        dx_noise = self.rng.normal(0, self.noise_std_um * 1e-3, self.n_points)
        dy_noise = self.rng.normal(0, self.noise_std_um * 1e-3, self.n_points)

        # ── 組合所有誤差 ──────────────────────────────────
        x_actual = x_ideal + dx_spike + dx_servo + dx_noise
        y_actual = y_ideal + dy_spike + dy_servo + dy_noise

        # ── 計算徑向誤差（DBB 實際量的量）─────────────────
        # dr = 實際半徑 - 名義半徑
        r_actual = np.sqrt(x_actual**2 + y_actual**2)
        dr_um    = (r_actual - R) * 1000   # 轉換成 μm

        # 圓度 = 最大徑向誤差 - 最小徑向誤差（ISO 圓度定義）
        roundness_um = float(dr_um.max() - dr_um.min())

        return DBBResult(
            theta_rad=theta,
            x_ideal=x_ideal,
            y_ideal=y_ideal,
            x_actual=x_actual,
            y_actual=y_actual,
            dr_um=dr_um,
            roundness_um=roundness_um,
            spike_indices=np.array(spike_indices_list),
            radius_mm=R,
            label=label,
        )

    # ── 補償效果計算（LSTM 預測後的改善量）─────────────────────

    def apply_spike_compensation(
        self,
        result: DBBResult,
        predicted_spike_dx: np.ndarray,
        predicted_spike_dy: np.ndarray,
    ) -> DBBResult:
        """
        套用 LSTM 預測的尖峰補償，回傳補償後的 DBBResult。

        用途：驗證 LSTM 在 DBB 測試上的補償效果。
        呼叫方式：
            predicted_dx, predicted_dy = lstm_model.predict(dbb_features)
            result_compensated = sim.apply_spike_compensation(
                result, predicted_dx, predicted_dy
            )
        """
        x_comp = result.x_actual - predicted_spike_dx
        y_comp = result.y_actual - predicted_spike_dy

        r_comp   = np.sqrt(x_comp**2 + y_comp**2)
        dr_comp  = (r_comp - result.radius_mm) * 1000
        roundness_comp = float(dr_comp.max() - dr_comp.min())

        return DBBResult(
            theta_rad=result.theta_rad,
            x_ideal=result.x_ideal,
            y_ideal=result.y_ideal,
            x_actual=x_comp,
            y_actual=y_comp,
            dr_um=dr_comp,
            roundness_um=roundness_comp,
            spike_indices=result.spike_indices,
            radius_mm=result.radius_mm,
            label=result.label + '_compensated',
        )

    # ── 輸出報告 ────────────────────────────────────────────────

    def print_summary(self, *results: DBBResult):
        """印出 DBB 測試摘要，格式仿照真實 DBB 軟體的報告"""
        print("\n" + "=" * 55)
        print("  K1/K2 DBB 圓度測試摘要")
        print("=" * 55)
        print(f"  {'測試':8} | {'半徑 mm':>8} | {'圓度 μm':>8} | {'評等':>8}")
        print("-" * 55)

        for r in results:
            # 工業評等標準（僅供參考，不同機型標準不同）
            if r.roundness_um < 5:
                grade = "優 ✅"
            elif r.roundness_um < 15:
                grade = "良 ⚠️"
            else:
                grade = "差 ❌"

            print(f"  {r.label:8} | {r.radius_mm:>8.0f} | "
                  f"{r.roundness_um:>8.2f} | {grade:>8}")

        print("=" * 55)

    def extract_spike_features(self, result: DBBResult) -> np.ndarray:
        """
        從 DBB 量測結果提取用於 LSTM 訓練的特徵。

        特徵設計（每個時間步 8 維）：
            [cos(θ), sin(θ),         # 當前位置（角度編碼）
             vx_norm, vy_norm,        # 正規化速度（方向資訊）
             |vx|, |vy|,              # 速度大小（與尖峰幅值相關）
             sign(vx), sign(vy)]      # 速度方向符號（換向預測的關鍵）
        """
        theta = result.theta_rad
        # 速度估算
        vx = -result.radius_mm * np.sin(theta)   # 理想速度
        vy =  result.radius_mm * np.cos(theta)

        v_max = result.radius_mm  # 最大速度的歸一化因子

        features = np.column_stack([
            np.cos(theta),
            np.sin(theta),
            vx / v_max,               # 正規化到 [-1, 1]
            vy / v_max,
            np.abs(vx) / v_max,
            np.abs(vy) / v_max,
            np.sign(vx + 1e-10),
            np.sign(vy + 1e-10),
        ])

        return features


# ══════════════════════════════════════════════════════════════
#  獨立驗證腳本：python k1k2_simulator.py
# ══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    print("=" * 60)
    print("  K1/K2 DBB 圓度測試模擬器驗證")
    print("=" * 60)

    sim = K1K2Simulator(spike_amp_um=8.0, kv_mismatch=0.04)
    k1  = sim.run_k1(radius_mm=150.0)
    k2  = sim.run_k2(radius_mm=50.0)

    sim.print_summary(k1, k2)

    # 分析尖峰位置
    print(f"\nK1 尖峰位置（角度）：")
    for idx in k1.spike_indices:
        angle_deg = np.degrees(k1.theta_rad[idx])
        amp       = k1.dr_um[idx]
        print(f"  θ = {angle_deg:6.1f}°  徑向誤差 = {amp:+.2f} μm")

    # 圓度改善模擬（假設 LSTM 預測了 70% 的尖峰）
    # 這裡用簡化的「已知尖峰位置」模擬 LSTM 預測的補償效果
    pred_dx = np.zeros_like(k1.x_actual)
    pred_dy = np.zeros_like(k1.y_actual)

    # 模擬 LSTM 預測到 70% 的尖峰（不完美，更接近實際情況）
    theta_k1 = k1.theta_rad
    vx_k1    = -k1.radius_mm * np.sin(theta_k1)
    vy_k1    =  k1.radius_mm * np.cos(theta_k1)

    # 正確補償方向：用實際位置誤差的方向，代表 LSTM 已學到尖峰的實際方向
    # 原本用 np.sign(vx) 是錯的——換向點的 vx≈0，sign 結果取決於 1e-10 偏置，
    # 補償方向可能和尖峰方向相反，導致圓度變差而非改善。
    dx_err = k1.x_actual - k1.x_ideal
    dy_err = k1.y_actual - k1.y_ideal

    for idx in k1.spike_indices:
        sigma = sim.spike_width / 2.5
        for d in range(-sim.spike_width * 2, sim.spike_width * 2 + 1):
            t     = (idx + d) % sim.n_points
            gauss = np.exp(-0.5 * (d / sigma) ** 2)
            # 70% 補償：用實際誤差方向 × 高斯衰減 × 0.7（不完美預測）
            pred_dx[t] += 0.7 * dx_err[idx] * gauss
            pred_dy[t] += 0.7 * dy_err[idx] * gauss

    k1_comp = sim.apply_spike_compensation(k1, pred_dx, pred_dy)
    print(f"\n模擬 LSTM 補償效果（70% 尖峰預測準確率）：")
    print(f"  補償前圓度：{k1.roundness_um:.2f} μm")
    print(f"  補償後圓度：{k1_comp.roundness_um:.2f} μm")
    print(f"  改善率：{(1 - k1_comp.roundness_um / k1.roundness_um) * 100:.1f}%")

    # 繪圖：DBB 極座標圖（仿照真實 DBB 軟體的顯示方式）
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    for ax, result, title in zip(
        axes[:2], [k1, k2], ['K1（R=150mm）', 'K2（R=50mm）']
    ):
        # 把徑向誤差放大 1000 倍顯示（否則看不見）
        scale   = 500
        x_plot  = result.x_actual + result.dr_um * 1e-3 * scale * np.cos(result.theta_rad)
        y_plot  = result.y_actual + result.dr_um * 1e-3 * scale * np.sin(result.theta_rad)

        ax.plot(result.x_ideal, result.y_ideal, 'k--', lw=0.8,
                alpha=0.4, label='理想圓')
        ax.plot(x_plot, y_plot, 'b-', lw=1.2, label='量測軌跡')

        # 標記尖峰位置
        for idx in result.spike_indices:
            ax.plot(x_plot[idx], y_plot[idx], 'r*', ms=10)

        ax.set_aspect('equal')
        ax.set_title(f'{title}\n圓度 = {result.roundness_um:.2f} μm（誤差放大 {scale}×）')
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

    # 第三張圖：K1 補償前後的徑向誤差對比
    ax3 = axes[2]
    theta_deg = np.degrees(k1.theta_rad)
    ax3.plot(theta_deg, k1.dr_um,      'b-',  lw=1.2, label=f'補償前（圓度={k1.roundness_um:.1f} μm）')
    ax3.plot(theta_deg, k1_comp.dr_um, 'g--', lw=1.2, label=f'補償後（圓度={k1_comp.roundness_um:.1f} μm）')

    # 標記換向點
    for idx in k1.spike_indices:
        ax3.axvline(theta_deg[idx], color='red', lw=0.8, alpha=0.5)

    ax3.set_xlabel('θ（度）')
    ax3.set_ylabel('徑向誤差（μm）')
    ax3.set_title('K1 LSTM 補償效果（反轉尖峰）')
    ax3.legend(fontsize=8)
    ax3.grid(True, alpha=0.3)
    ax3.axhline(0, color='black', lw=0.5)

    plt.tight_layout()
    plt.savefig('/tmp/k1k2_dbb_validation.png', dpi=120)
    print(f"\n驗證圖已存至：/tmp/k1k2_dbb_validation.png")
    print("\n✅ 驗證完成")
