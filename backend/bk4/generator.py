"""
generator.py
整合 PIGE + PDGE 的 BK4 軌跡模擬器
採用嚴格 HTM (齊次變換矩陣)，完美還原 LRT 相對量測機制
"""
import numpy as np
from bk4.pige_full_generator import BK4_Full_PIGE_Generator, CONFIG
from bk4.pdge_generator import Physical_PDGE_Generator

class Integrated_BK4_Simulator:
    def __init__(self, config=None):
        cfg = config if config is not None else CONFIG
        self.pige_gen = BK4_Full_PIGE_Generator(cfg)
        self.pdge_gen = Physical_PDGE_Generator()

    def generate(self, ball_x=0.0, ball_y=0.0, ball_z=0.0, n_points=360, 
             view_mode="relative", custom_errors=None, enable_pdge=False, 
             path_type="cone", pivot_x=0.0, pivot_y=0.0, pivot_z=0.0,
             tool_length=0.0,
             match_senior_a_dir=True):
        
        if path_type == "cone":
            c_deg = np.linspace(0, 360, n_points)
            a_deg = np.zeros_like(c_deg)
            for i, c in enumerate(c_deg):
                if c <= 180:
                    a_deg[i] = c / 2.0         
                else:
                    a_deg[i] = (360 - c) / 2.0 
            a_cmd = np.deg2rad(a_deg)
            c_cmd = np.deg2rad(c_deg)
        elif path_type == "sine":
            t = np.linspace(0, 4 * np.pi, n_points)
            a_cmd = np.deg2rad(30 * np.sin(t))
            c_cmd = np.deg2rad(90 * np.sin(2 * t))
        else:
            raise ValueError(f"未知的軌跡類型: {path_type}")
        
        # ball_z : C 軸力臂，測量球中心到 C 軸盤面的高度
        P_local = np.array([ball_x, ball_y, ball_z, 1.0])
        
        # pivot_z : A 軸旋轉中心到 C 軸轉盤面的固定幾何距離
        T_pivot = self.pige_gen._get_htm(0, 0, pivot_z, 0, 0, 0)
        T_pivot_inv = np.linalg.inv(T_pivot)

        # tool_length : C 軸轉盤面到感測球中心的距離（LRT 刀長）
        T_tool = self.pige_gen._get_htm(0, 0, tool_length, 0, 0, 0)
        T_tool_inv = np.linalg.inv(T_tool)

        active_errors = self.pige_gen.errors.copy()
        if custom_errors:
            active_errors.update(custom_errors)
            
        E_A_static = self.pige_gen._get_error_matrix(
            active_errors.get('X_OA', 0.0), active_errors.get('Y_OA', 0.0), active_errors.get('Z_OA', 0.0),
            active_errors.get('A_OA', 0.0), active_errors.get('B_OA', 0.0), active_errors.get('C_OA', 0.0)
        )
        E_AC_static = self.pige_gen._get_error_matrix(
            active_errors.get('X_OC', 0.0), active_errors.get('Y_OC', 0.0), active_errors.get('Z_OC', 0.0),
            active_errors.get('A_OC', 0.0), active_errors.get('B_OC', 0.0), active_errors.get('C_OC', 0.0)
        )

        E_A_inv = np.linalg.inv(E_A_static)
        E_AC_inv = np.linalg.inv(E_AC_static)
        P_table = T_tool_inv @ E_AC_inv @ T_pivot_inv @ E_A_inv @ T_pivot @ T_tool @ P_local
        # P_table = P_local

        results = []
        zeroing_baseline = np.zeros(3)

        for i in range(n_points):
            a_rad = a_cmd[i]
            c_rad = c_cmd[i]
            
            # 旋轉方向精確匹配學長物理定義
            a_rot = -a_rad if match_senior_a_dir else a_rad
            c_rot = -c_rad  

            if enable_pdge:
                exc, eyc, ezc, eac, ebc, ecc = self.pdge_gen.get_c_axis_pdge(c_rad)
            else:
                exc = eyc = ezc = eac = ebc = ecc = 0.0

            E_AC_dyn = self.pige_gen._get_error_matrix(
                active_errors.get('X_OC', 0.0) + exc, 
                active_errors.get('Y_OC', 0.0) + eyc, 
                active_errors.get('Z_OC', 0.0) + ezc,
                active_errors.get('A_OC', 0.0) + eac, 
                active_errors.get('B_OC', 0.0) + ebc, 
                active_errors.get('C_OC', 0.0) + ecc
            )

            T_A_i = self.pige_gen._get_htm(0, 0, 0, a_rot, 0, 0)
            T_C_i = self.pige_gen._get_htm(0, 0, 0, 0, 0, c_rot)

            P_ideal = T_A_i @ T_pivot @ self.pige_gen._get_htm(0, 0, 0, 0, 0, -c_rad) @ T_tool @ P_local
            
            if view_mode == "absolute":
                P_actual_abs = E_A_static @ T_A_i @ T_pivot @ E_AC_dyn @ T_C_i @ T_tool @ P_local
                err_vec = (P_actual_abs - P_ideal)[:3]
                
            elif view_mode == "relative":
                # ==========================================
                # 🛠️ 核心測試區：切換「數位孿生物理模型」與「學長模型」
                # ==========================================
                
                # -----------------------------------------------------------------
                # 【模式 1：您的數位孿生模型 (正確的 ISO 剛體物理模型)】
                # 說明：E_A 在 T_A 之前 (絕對座標)，E_AC 在 T_C 之前 (靜態組裝不隨軸轉)
                # -----------------------------------------------------------------
                P_actual_mode1 = E_A_static @ T_A_i @ T_pivot @ E_AC_dyn @ T_C_i @ T_tool @ P_table
                
                # -----------------------------------------------------------------
                # 【模式 2：學長疑似的模型 (靜態誤差被錯誤定義為「動態偏擺 Wobble」)】
                # 說明：將誤差矩陣放到了旋轉矩陣「之後」，導致誤差跟著座標軸一起旋轉
                # -> AOC/BOC 會產生 C 軸正弦波，BOA/ZOA 會產生 A 軸的局部耦合
                # -----------------------------------------------------------------
                # 注意這裡的矩陣乘法順序完全顛倒了：T_A_i 在前，T_C_i 在前
                P_actual_mode2 = T_A_i @ E_A_static @ T_pivot @ T_C_i @ E_AC_dyn @ T_tool @ P_table

                # 👇 在這裡切換你想測試的模型 (將另一個註解掉即可)
                P_actual = P_actual_mode1  # <--- 啟用此行：測試您正確的物理模型
                # P_actual = P_actual_mode2    # <--- 啟用此行：測試學長的 Wobble 耦合模型

                Err_abs = (P_actual - P_ideal)[:3]
                
                if i == 0:
                    # 模擬實機 LRT 歸零 (Zeroing)
                    zeroing_baseline = Err_abs
                
                err_vec = Err_abs - zeroing_baseline
            else:
                raise ValueError("view_mode 必須是 'absolute' 或 'relative'")

            results.append(err_vec)

        return np.array(results), a_cmd, c_cmd