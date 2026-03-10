import numpy as np
import matplotlib.pyplot as plt

class AC_Trunnion_Physical_Simulator:
    def __init__(self):
        # ==========================================
        # 1. 機台基礎幾何 (Nominal Machine Geometry)
        # ==========================================
        # 定義依據: ISO 10791-6 A-C 搖籃式五軸
        self.L_pivot = 500.0   # A軸旋轉中心到主軸鼻端的距離 (Z向)
        self.R_ball = 200.0    # R-test 球心距離 C 軸中心的半徑
        self.Tool_Length = 150.0 # 標準刀具長度
        
        # ==========================================
        # 2. 誤差預算表 (Error Budget)
        # ==========================================
        self.errors = {
            # --- Layer 1: 組裝誤差 (PIGEs) ---
            # C 軸相對於 A 軸的安裝誤差 (靜態夾層)
            'dx_ac': 0.0, 'dy_ac': 0.0, 'dz_ac': 0.0, 
            'alpha_ac': 0.0, 'beta_ac': 0.0,
            # A 軸相對於機床原點的偏移
            'dy_oa': 0.0, 'dz_oa': 0.0, 'alpha_oa': 0.0,
            
            # --- Layer 2: 低階位置相關誤差 (PDGEs) ---
            # 模擬線性軸導軌的幾何缺陷
            'x_scale': 0.0,      # X軸比例誤差 (ppm)
            'x_straightness_amp': 0.0, # X軸真直度波峰 (um)
            
            # --- Layer 3: 準靜態重力變形 (Stiffness/Gravity) ---
            # A軸擺動導致的結構下垂 (Bow-tie effect source)
            'gravity_sag_y': 0.0, # um (與 sin(A) 成正比)
            
            # --- Layer 4: 刀具誤差 (Tool Errors) ---
            # 刀尖相對於主軸中心的偏差
            'tool_len_err': 0.0, 
            'tool_ecc_x': 0.0, 'tool_ecc_y': 0.0
        }

    def set_errors(self, **kwargs):
        """設定誤差參數"""
        for k, v in kwargs.items():
            if k in self.errors:
                self.errors[k] = v
            else:
                print(f"Warning: Ignored unknown param {k}")

    def reset_errors(self):
        """重置所有誤差為 0 (理想狀態)"""
        for k in self.errors:
            self.errors[k] = 0.0

    def _get_htm(self, x, y, z, a, b, c):
        """產生 4x4 齊次變換矩陣 (Euler XYZ: Rz*Ry*Rx)"""
        Ca, Sa = np.cos(a), np.sin(a)
        Cb, Sb = np.cos(b), np.sin(b)
        Cc, Sc = np.cos(c), np.sin(c)
        
        # 旋轉矩陣
        R = np.array([
            [Cb*Cc, -Cb*Sc, Sb, 0],
            [Sa*Sb*Cc + Ca*Sc, -Sa*Sb*Sc + Ca*Cc, -Sa*Cb, 0],
            [-Ca*Sb*Cc + Sa*Sc, Ca*Sb*Sc + Sa*Cc, Ca*Cb, 0],
            [0, 0, 0, 1]
        ])
        # 平移向量
        R[0, 3] = x; R[1, 3] = y; R[2, 3] = z
        return R

    def _get_error_matrix(self, dx, dy, dz, da, db, dc):
        """產生小量誤差矩陣 (Small Angle Approximation)"""
        return np.array([
            [1, -dc, db, dx],
            [dc, 1, -da, dy],
            [-db, da, 1, dz],
            [0, 0, 0, 1]
        ])

    def generate_bk4_trace(self, n_points=360):
        """
        核心引擎: 生成 BK4 R-Test 軌跡
        邏輯: 比較「實際刀尖位置」與「實際球心位置」的差值
        """
        t = np.linspace(0, 4*np.pi, n_points) # 兩個週期以觀察完整特徵
        
        # 1. 理想指令 (Nominal Command)
        # BK4: A 擺動 +/- 30度, C 旋轉 (頻率比 A:C = 1:2)
        a_cmd = np.deg2rad(30 * np.sin(t))
        c_cmd = np.deg2rad(90 * np.sin(2*t))
        
        P_ball_local = np.array([self.R_ball, 0, 0, 1])
        results = []
        
        # 預先計算靜態誤差矩陣 (提升效能並符合物理定義)
        # 這就是 "三明治" 結構的中間層: C 軸鎖在 A 軸上的誤差
        E_AC_Static = self._get_error_matrix(
            self.errors['dx_ac'], self.errors['dy_ac'], self.errors['dz_ac'],
            self.errors['alpha_ac'], self.errors['beta_ac'], 0
        )

        for i in range(n_points):
            # ---------------------------------------------------
            # Step A: 逆向運動學 (求理想指令 XYZ)
            # ---------------------------------------------------
            T_A_ideal = self._get_htm(0, 0, 0, a_cmd[i], 0, 0)
            T_C_ideal = self._get_htm(0, 0, 0, 0, 0, c_cmd[i])
            P_ball_mcs_ideal = T_A_ideal @ T_C_ideal @ P_ball_local
            
            # 理想狀態下，刀尖應該在球心
            cmd_x, cmd_y, cmd_z = P_ball_mcs_ideal[:3]
            
            # ---------------------------------------------------
            # Step B: 正向運動學 (工件端 Table Chain)
            # ---------------------------------------------------
            # Chain: Bed -> A_Axis -> [Error_AC] -> C_Axis -> Ball
            
            # 1. A 軸實際運動 (含 A 軸自身的幾何誤差)
            E_A_pige = self._get_error_matrix(0, self.errors['dy_oa'], self.errors['dz_oa'], self.errors['alpha_oa'], 0, 0)
            T_A_act = self._get_htm(0, 0, 0, a_cmd[i], 0, 0) @ E_A_pige
            
            # 2. C 軸實際運動
            T_C_act = self._get_htm(0, 0, 0, 0, 0, c_cmd[i])
            
            # 3. 合成實際球心位置 (注意 E_AC 被夾在中間)
            P_ball_actual_mcs = T_A_act @ E_AC_Static @ T_C_act @ P_ball_local
            
            # ---------------------------------------------------
            # Step C: 正向運動學 (刀具端 Tool Chain)
            # ---------------------------------------------------
            # Chain: Bed -> Y -> X -> Z -> Spindle -> Tool
            
            # 1. PDGEs (線性軸導軌誤差)
            # 模擬 X 軸真直度 (Straightness): 隨 X 位置變化的波浪
            ex_x = cmd_x * self.errors['x_scale'] * 1e-6 
            ey_x = self.errors['x_straightness_amp'] * 1e-3 * (cmd_x/200)**2 if abs(cmd_x)>1 else 0
            
            act_x = cmd_x + ex_x
            act_y = cmd_y + ey_x 
            act_z = cmd_z
            
            # 2. 重力變形 (Gravity Sag)
            # 物理: A 軸擺動導致重心改變，造成 Y 軸結構彈性下垂
            # 這會產生著名的 "蝴蝶結 (Bow-tie)" 或 "8字形" 誤差
            sag_y = np.sin(a_cmd[i]) * self.errors['gravity_sag_y'] * 1e-3
            act_y += sag_y
            
            # 3. 刀具幾何誤差 (Tool Errors)
            # 定義在主軸座標系下
            T_Spindle = self._get_htm(act_x, act_y, act_z, 0, 0, 0)
            E_Tool = self._get_htm(
                self.errors['tool_ecc_x']*1e-3, 
                self.errors['tool_ecc_y']*1e-3, 
                self.errors['tool_len_err']*1e-3, 
                0, 0, 0
            )
            P_tip_local = np.array([0, 0, 0, 1])
            P_tip_actual_mcs = T_Spindle @ E_Tool @ P_tip_local
            
            # ---------------------------------------------------
            # Step D: 計算 R-Test 誤差 (Result)
            # ---------------------------------------------------
            # 誤差 = 刀尖實際位置 - 球心實際位置
            diff = P_tip_actual_mcs - P_ball_actual_mcs
            results.append(diff[:3])
            
        return np.array(results)

# ==========================================
# 執行模擬並繪圖 (Main Execution)
# ==========================================
def run_simulation_report():
    sim = AC_Trunnion_Physical_Simulator()
    cases = []
    
    # --- Case 1: 組裝誤差 (PIGE) ---
    # 物理特徵: 低頻正弦波 (阿貝誤差) + 直流偏置
    sim.reset_errors()
    sim.set_errors(dx_ac=0.050, alpha_ac=0.0002) # 50um 偏心, 0.2mrad 傾角
    cases.append(('1. Assembly PIGEs (Geometric)', sim.generate_bk4_trace()))
    
    # --- Case 2: 位置相關誤差 (PDGE) ---
    # 物理特徵: 二次曲線或高頻波浪
    sim.reset_errors()
    sim.set_errors(x_straightness_amp=20.0) # 20um 真直度
    cases.append(('2. PDGEs (Linear Waviness)', sim.generate_bk4_trace()))
    
    # --- Case 3: 重力變形 (Stiffness) ---
    # 物理特徵: 跟隨 A 軸頻率的慢波 (Butterfly shape source)
    sim.reset_errors()
    sim.set_errors(gravity_sag_y=30.0) # 30um 下垂
    cases.append(('3. Gravity Sag (Stiffness)', sim.generate_bk4_trace()))
    
    # --- Case 4: 刀具誤差 (Tool) ---
    # 物理特徵: 固定偏置 (Offset)
    sim.reset_errors()
    sim.set_errors(tool_len_err=100.0, tool_ecc_x=20.0)
    cases.append(('4. Tool Errors (Offset)', sim.generate_bk4_trace()))
    
    # --- Case 5: 真實疊加 (Superimposed) ---
    # 物理特徵: 複雜耦合波形 (髒數據)
    sim.reset_errors()
    sim.set_errors(
        dx_ac=0.050, alpha_ac=0.0002,      # Layer 1
        x_straightness_amp=20.0,           # Layer 2
        gravity_sag_y=30.0,                # Layer 3
        tool_len_err=100.0, tool_ecc_x=20.0 # Layer 4
    )
    cases.append(('5. Total Superimposed Error', sim.generate_bk4_trace()))
    
    # --- 繪圖設定 ---
    fig, axes = plt.subplots(len(cases), 3, figsize=(16, 14), sharex=True)
    plt.subplots_adjust(hspace=0.4, wspace=0.3)
    
    colors = ['#d62728', '#2ca02c', '#1f77b4'] # RGB colors
    axis_labels = ['DX', 'DY', 'DZ']
    
    data_export = {} # 用於儲存 npz
    
    for i, (title, data) in enumerate(cases):
        data_um = data * 1000 # mm -> um
        data_export[title] = data_um
        
        for j in range(3): # X, Y, Z columns
            ax = axes[i, j]
            ax.plot(data_um[:, j], color=colors[j], linewidth=1.5)
            ax.set_title(f"{axis_labels[j]} ({title})", fontsize=10)
            ax.grid(True, linestyle='--', alpha=0.6)
            ax.set_ylabel("Error (um)")
            
            # 強調 Case 1 的 DX 特徵 (直線驗證)
            if i == 0 and j == 0:
                ax.text(len(data)/2, np.mean(data_um[:,0]), "DC Offset (Correct!)", 
                        ha='center', va='bottom', color='red', fontweight='bold')

    axes[-1, 1].set_xlabel('Sample Points (Time Step)', fontsize=12)
    plt.suptitle('Physics-Based BK4 Data Generation: Layered Error Decomposition', fontsize=16, y=0.98)
    
    # 儲存
    plt.savefig('BK4_Physical_Decomposition.png', dpi=300)
    np.savez('BK4_Simulation_Data.npz', **data_export)
    print("✅ Simulation Completed!")
    print("   - Image saved: BK4_Physical_Decomposition.png")
    print("   - Data saved:  BK4_Simulation_Data.npz")
    plt.show()

if __name__ == "__main__":
    run_simulation_report()