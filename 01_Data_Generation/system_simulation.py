import numpy as np
import matplotlib.pyplot as plt

class AC_Trunnion_HTM_Simulator:
    def __init__(self):
        # 機台結構參數 (mm)
        self.L_pivot = 500.0   # A軸旋轉中心到主軸鼻端的 Z 向距離
        self.Y_pivot = 0.0     # A軸旋轉中心到立柱的 Y 向距離
        self.R_ball = 200.0    # R-test 球心距離 C 軸中心的半徑
        
        # 誤差參數 (PIGEs & PDGEs & Dynamics)
        self.errors = {
            # --- PIGEs: 位置無關幾何誤差 (8項核心) ---
            # 定義：C 軸相對於 A 軸的誤差
            'dx_ac': 0.0, 
            'dy_ac': 0.0, 
            'dz_ac': 0.0, 
            'alpha_ac': 0.0, # (rad)
            'beta_ac': 0.0, # (rad)
            
            # 定義：A 軸相對於 Y/Z 軸 (主軸) 的誤差 (Pivot Offset)
            'dy_oa': 0.0, 
            'dz_oa': 0.0, 
            'alpha_oa': 0.0, # A 軸本身的傾角誤差
            
            # --- Dynamics: 動態誤差 (維持 Sprint 4 的物理層) ---
            'backlash_a': 0.0,  # A 軸背隙 (rad)
            'stiffness_y': 1e9, # Y 軸剛性 (N/um), 預設剛體
            'mass_effect': 0.0  # 質量慣性係數
        }

    def _get_htm(self, x, y, z, a, b, c):
        """產生 4x4 齊次變換矩陣 (XYZ + ABC Euler Angles)"""
        # 簡化版：假設小角度誤差，cos~1, sin~theta
        # T = Translation * Rotation
        # 這裡寫完整版以求精確
        
        Ca, Sa = np.cos(a), np.sin(a)
        Cb, Sb = np.cos(b), np.sin(b)
        Cc, Sc = np.cos(c), np.sin(c)
        
        # 旋轉矩陣 R (ZYX order or specific machine order)
        # 對於誤差矩陣，通常假設 R = I + skew(epsilon)
        R = np.array([
            [Cb*Cc, -Cb*Sc, Sb, 0],
            [Sa*Sb*Cc + Ca*Sc, -Sa*Sb*Sc + Ca*Cc, -Sa*Cb, 0],
            [-Ca*Sb*Cc + Sa*Sc, Ca*Sb*Sc + Sa*Cc, Ca*Cb, 0],
            [0, 0, 0, 1]
        ])
        
        # 平移部分
        R[0, 3] = x
        R[1, 3] = y
        R[2, 3] = z
        
        return R

    def _get_error_matrix(self, dx, dy, dz, da, db, dc):
        """產生誤差的小量矩陣"""
        return np.array([
            [1, -dc, db, dx],
            [dc, 1, -da, dy],
            [-db, da, 1, dz],
            [0, 0, 0, 1]
        ])

    def generate_bk4_data(self, n_points=360):
        """
        生成 BK4 運動數據 (修正版: 符合 ISO 多體運動學鏈)
        鏈結結構: Bed -> [A_Motion] -> [A-C_Static_Error] -> [C_Motion] -> Workpiece
        """
        t = np.linspace(0, 2*np.pi, n_points)
        
        # 1. 指令生成 (與原版相同)
        a_cmd = np.deg2rad(30 * np.sin(t))
        c_cmd = np.deg2rad(90 * np.sin(2*t))
        
        # 理想球心位置 (在 C 盤面座標系 Local Frame)
        P_ball_local = np.array([self.R_ball, 0, 0, 1])
        
        measured_errors = []
        
        # --- 預先定義靜態誤差矩陣 (PIGEs) ---
        # 這是 C 軸相對於 A 軸的安裝誤差 (不隨時間改變！)
        # 對應報告中的: dx_ac, dy_ac, dz_ac, alpha_ac, beta_ac
        E_AC_static = self._get_error_matrix(
            self.errors['dx_ac'], self.errors['dy_ac'], self.errors['dz_ac'],
            self.errors['alpha_ac'], self.errors['beta_ac'], 0
        )

        for i in range(n_points):
            # =================================================
            # A. 工件端 (Workpiece Side) - 真實運動鏈
            # =================================================
            
            # --- 1. A 軸部分 (Bed -> A) ---
            # 注入背隙 (Backlash): 影響 A 軸的 "角度"
            # 判斷速度方向 (簡單版: 當前-上一個)
            if i > 0 and (a_cmd[i] - a_cmd[i-1]) < 0:
                a_actual_angle = a_cmd[i] - np.deg2rad(self.errors['backlash_a'])
            else:
                a_actual_angle = a_cmd[i]
            
            # A 軸運動矩陣 (包含 A 軸自身的 PIGE: Pivot Offset)
            # 鏈結: A_Motion * E_A_Geometry
            T_A_motion = self._get_htm(0, 0, 0, a_actual_angle, 0, 0)
            E_A_geometry = self._get_error_matrix(
                0, self.errors['dy_oa'], self.errors['dz_oa'], 
                self.errors['alpha_oa'], 0, 0
            )
            # 合成 A 軸總變換 (從 Bed 到 A 軸盤面)
            T_A_total = T_A_motion @ E_A_geometry

            # --- 2. C 軸部分 (A -> C) ---
            # C 軸運動矩陣 (假設 C 軸本身無背隙或已補償)
            T_C_motion = self._get_htm(0, 0, 0, 0, 0, c_cmd[i])
            
            # --- 3. 運動學鏈總合成 ---
            # 關鍵修正： [A總成] @ [A-C安裝誤差] @ [C運動] @ [球]
            # 這保證了 E_AC 會跟著 A 轉，但不會跟著 C 轉
            P_ball_mcs = T_A_total @ E_AC_static @ T_C_motion @ P_ball_local
            
            # =================================================
            # B. 刀具端 (Tool Side) - 理想追隨 + 動態誤差
            # =================================================
            
            # 計算理想指令 (無誤差) 用於逆向解或作為目標基準
            # 理想鏈結: T_A_ideal @ Identity @ T_C_ideal
            T_A_ideal = self._get_htm(0, 0, 0, a_cmd[i], 0, 0)
            T_C_ideal = self._get_htm(0, 0, 0, 0, 0, c_cmd[i])
            P_target_mcs = T_A_ideal @ T_C_ideal @ P_ball_local # 這是刀尖「應該」去的地方
            
            # 注入刀具端動態誤差 (剛性/伺服落後)
            # Y 軸剛性誤差：受 A 軸角度影響 (重力分量)
            gravity_force_y = np.sin(a_cmd[i]) * self.errors['mass_effect'] # 修正為使用 mass_effect 係數
            deflection_y = gravity_force_y / self.errors['stiffness_y']
            
            P_tool_actual = P_target_mcs.copy()
            P_tool_actual[1] += deflection_y 

            # =================================================
            # C. 計算 R-Test 誤差
            # =================================================
            # 誤差向量 = 刀尖實際 - 球心實際
            delta = P_tool_actual - P_ball_mcs
            measured_errors.append(delta[:3])
            
        return np.array(measured_errors)

# ==========================================
# 驗證 HTM 模型的 PIGE 特徵
# ==========================================
def verify_htm_model():
    sim = AC_Trunnion_HTM_Simulator()
    
    # 設定誤差：C 軸相對於 A 軸有偏心 (PIGE)
    # 這應該會在 BK4 測試中產生顯著的幾何誤差波形
    sim.errors['dx_ac'] = 0.050 # 50 um
    sim.errors['alpha_ac'] = 0.0001 # 微小傾角
    
    # 生成數據
    errors = sim.generate_bk4_data()
    
    # 繪圖
    plt.figure(figsize=(10, 6))
    plt.plot(errors[:, 0]*1000, label='DX (um)')
    plt.plot(errors[:, 1]*1000, label='DY (um)')
    plt.plot(errors[:, 2]*1000, label='DZ (um)')
    
    plt.title("BK4 R-Test Simulation (HTM Based)\nSignature of PIGE Errors", fontsize=14)
    plt.xlabel("Sample Point")
    plt.ylabel("Error (um)")
    plt.grid(True, linestyle='--')
    plt.legend()
    plt.show()

if __name__ == "__main__":
    verify_htm_model()