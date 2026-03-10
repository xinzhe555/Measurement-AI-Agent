import numpy as np
import matplotlib.pyplot as plt

# ==========================================
# ⚙️ USER SETTINGS (使用者設定區)
# ==========================================
CONFIG = {
    # --- 機台幾何參數 (Machine Geometry) ---
    'L_pivot': 500.0,    # A軸旋轉中心到主軸鼻端的距離 (Z向, mm)
    
    # --- 測試情境設定 (Simulation Scenarios) ---
    'R_center': 0.0,     # 情境A: 球心在 C 軸中心 (R=0 mm)
    'R_eccentric': 200.0,# 情境B: 球心在 C 軸邊緣 (R=200 mm)
    
    # --- 誤差參數設定 (PIGE Error Budget) ---
    # 單位: mm (位置), rad (角度)
    # 建議: 1 um = 0.001 mm, 1 mrad = 0.001 rad
    'errors': {
        # C 軸相對於 A 軸的 PIGEs (ISO 230-1)
        'X_OC': 0.050,    # X向偏心 (50um) -> 造成 DC Offset
        'Y_OC': 0.050,    # Y向偏心 (50um) -> 造成波形
        'Z_OC': 0.050,    # Z向偏心 (50um) -> 造成波形
        
        'A_OC': 0.0002,   # 繞 X 傾角 (alpha, 0.2 mrad) -> 造成 Z 軸阿貝誤差
        'B_OC': 0.0,      # 繞 Y 傾角 (beta)
        'C_OC': 0.0,      # 繞 Z 傾角 (gamma)
        
        # A 軸本身的 PIGEs (暫時設為 0 以觀察 C 軸效應)
        'dy_oa': 0.0, 
        'dz_oa': 0.0, 
        'alpha_oa': 0.0
    }
}

# ==========================================
# 🏗️ SIMULATION CORE (模擬核心)
# ==========================================
class BK4_PIGE_Generator:
    def __init__(self, config):
        self.cfg = config
        self.errors = config['errors']
        self.L_pivot = config['L_pivot']

    def _get_htm(self, x, y, z, a, b, c):
        """產生 4x4 齊次變換矩陣"""
        Ca, Sa = np.cos(a), np.sin(a)
        Cb, Sb = np.cos(b), np.sin(b)
        Cc, Sc = np.cos(c), np.sin(c)
        
        R = np.array([
            [Cb*Cc, -Cb*Sc, Sb, 0],
            [Sa*Sb*Cc + Ca*Sc, -Sa*Sb*Sc + Ca*Cc, -Sa*Cb, 0],
            [-Ca*Sb*Cc + Sa*Sc, Ca*Sb*Sc + Sa*Cc, Ca*Cb, 0],
            [0, 0, 0, 1]
        ])
        R[0, 3] = x; R[1, 3] = y; R[2, 3] = z
        return R

    def _get_error_matrix(self, dx, dy, dz, da, db, dc):
        """產生小量誤差矩陣 (PIGE Matrix)"""
        # 使用 ISO 符號邏輯對應
        return np.array([
            [1, -dc, db, dx],
            [dc, 1, -da, dy],
            [-db, da, 1, dz],
            [0, 0, 0, 1]
        ])

    def generate_data(self, ball_radius):
        """
        生成 BK4 數據
        ball_radius: 球心距離 C 軸中心的半徑 (mm)
        """
        n_points = 360
        t = np.linspace(0, 4*np.pi, n_points)
        
        # BK4 指令生成 (A: +/-30 deg, C: +/-90 deg sync)
        a_cmd = np.deg2rad(30 * np.sin(t))
        c_cmd = np.deg2rad(90 * np.sin(2*t))
        
        # 設定球心位置 (Local Frame)
        P_ball_local = np.array([ball_radius, 0, 0, 1])
        
        results = []
        
        # 預先計算 PIGE 矩陣 (夾在中間的三明治層)
        # 對應 CONFIG 中的 X_OC, Y_OC...
        E_AC = self._get_error_matrix(
            self.errors['X_OC'], self.errors['Y_OC'], self.errors['Z_OC'],
            self.errors['A_OC'], self.errors['B_OC'], self.errors['C_OC']
        )
        # A 軸 PIGE
        E_A = self._get_error_matrix(
            0, self.errors['dy_oa'], self.errors['dz_oa'], 
            self.errors['alpha_oa'], 0, 0
        )

        for i in range(n_points):
            # 1. 理想路徑 (Inverse Kinematics)
            # 用理想矩陣算出刀尖應該在哪裡 (為了追到球)
            T_A_ideal = self._get_htm(0, 0, 0, a_cmd[i], 0, 0)
            T_C_ideal = self._get_htm(0, 0, 0, 0, 0, c_cmd[i])
            P_ball_mcs_ideal = T_A_ideal @ T_C_ideal @ P_ball_local
            
            # 2. 實際路徑 (Forward Kinematics with Errors)
            # Chain: Bed -> A -> [E_A] -> [E_AC] -> C -> Ball
            # 注意: E_A 通常作用在 A 軸運動之後，E_AC 作用在 C 軸之前
            T_A_act = self._get_htm(0, 0, 0, a_cmd[i], 0, 0) @ E_A
            T_C_act = self._get_htm(0, 0, 0, 0, 0, c_cmd[i])
            
            # 核心物理邏輯：誤差矩陣 E_AC 必須被 A 軸旋轉，且影響 C 軸位置
            P_ball_actual_mcs = T_A_act @ E_AC @ T_C_act @ P_ball_local
            
            # 3. 計算誤差 (R-Test Deviation)
            # Error = Ideal (Command) - Actual (Measured)
            # 這裡假設刀尖完美跟隨 Ideal，所以 R-Test 看到的是球跑掉了
            diff = P_ball_mcs_ideal - P_ball_actual_mcs
            
            results.append(diff[:3])
            
        return np.array(results)

# ==========================================
# 執行與繪圖 (Execution)
# ==========================================
def run_comparison():
    # 初始化模擬器
    sim = BK4_PIGE_Generator(CONFIG)
    
    # 1. 生成數據
    data_center = sim.generate_data(ball_radius=CONFIG['R_center'])
    data_eccentric = sim.generate_data(ball_radius=CONFIG['R_eccentric'])
    
    # 數據換算成 um
    dx_center_um = data_center[:, 0] * 1000
    dx_eccentric_um = data_eccentric[:, 0] * 1000
    
    # 2. 繪圖
    fig, axes = plt.subplots(3, 1, figsize=(10, 12), sharex=True)
    
    # --- X 軸誤差 (DX) 修正版 ---
    axes[0].plot(dx_center_um, 'b--', label=f'Center (R={CONFIG["R_center"]})', alpha=0.7)
    axes[0].plot(dx_eccentric_um, 'r-', label=f'Eccentric (R={CONFIG["R_eccentric"]})')
    axes[0].set_ylabel('DX (um)')
    axes[0].legend()
    axes[0].grid(True)
    
    # 自動計算中心點，並鎖定顯示範圍
    # 我們取紅線的平均值作為中心
    center_val = np.mean(dx_eccentric_um)
    view_range = 1.0 # 上下各顯示 1 um
    
    # 強制設定 Y 軸範圍
    axes[0].set_ylim(center_val - view_range, center_val + view_range)
    
    # 更新標題顯示目前範圍
    axes[0].set_title(f"DX (Fixed Range: {center_val:.1f} ± {view_range} um) - Noise Filtered")

    # --- Y 軸誤差 (DY) ---
    axes[1].plot(data_center[:, 1]*1000, 'b--', alpha=0.7)
    axes[1].plot(data_eccentric[:, 1]*1000, 'r-')
    axes[1].set_ylabel('DY (um)')
    axes[1].set_title(f"DY: Angular/Position Coupling")
    axes[1].grid(True)

    # --- Z 軸誤差 (DZ) ---
    axes[2].plot(data_center[:, 2]*1000, 'b--', alpha=0.7)
    axes[2].plot(data_eccentric[:, 2]*1000, 'r-')
    axes[2].set_ylabel('DZ (um)')
    axes[2].set_title(f"DZ: Abbe Error")
    axes[2].set_xlabel('Sample Points')
    axes[2].grid(True)
    
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    run_comparison()