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
        
        effective_z = ball_z + pivot_z
        P_local = np.array([ball_x, ball_y, effective_z, 1.0])
        
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
        P_table = E_AC_inv @ E_A_inv @ P_local

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

            P_ideal = T_A_i @ self.pige_gen._get_htm(0, 0, 0, 0, 0, -c_rad) @ P_local
            
            if view_mode == "absolute":
                P_actual_abs = E_A_static @ T_A_i @ E_AC_dyn @ T_C_i @ P_local
                err_vec = (P_actual_abs - P_ideal)[:3]
            elif view_mode == "relative":
                P_actual = E_A_static @ T_A_i @ E_AC_dyn @ T_C_i @ P_table
                Err_abs = (P_actual - P_ideal)[:3]
                
                # LRT 架設在主軸上，Err_abs 就已經是感測器讀數！不需再做 Rx 投影。
                if i == 0:
                    zeroing_baseline = Err_abs
                
                err_vec = Err_abs - zeroing_baseline
            else:
                raise ValueError("view_mode 必須是 'absolute' 或 'relative'")

            results.append(err_vec)

        return np.array(results), a_cmd, c_cmd