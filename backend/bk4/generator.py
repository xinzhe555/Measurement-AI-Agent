"""
generator.py
整合 PIGE + PDGE 的 BK4 軌跡模擬器
採用嚴格 HTM 差值法 (Absolute Difference Method) 解決相對觀測系的動態力臂投影問題
"""
import numpy as np

# 請確保您的 import 路徑與您的專案架構相符
from bk4.pige_full_generator import BK4_Full_PIGE_Generator, CONFIG
from bk4.pdge_generator import Physical_PDGE_Generator

class Integrated_BK4_Simulator:
    """
    整合 PIGE + PDGE 的 BK4 軌跡模擬器
    """
    def __init__(self, config=None):
        cfg = config if config is not None else CONFIG
        self.pige_gen = BK4_Full_PIGE_Generator(cfg)
        self.pdge_gen = Physical_PDGE_Generator()

    def generate(self, ball_x=200.0, ball_y=0.0, ball_z=0.0, n_points=360, view_mode="relative", custom_errors=None, enable_pdge=False, path_type="cone", pivot_x=0.0, pivot_y=0.0, pivot_z=0.0, match_senior_a_dir=True):
        """
        生成 BK4 路徑的複合誤差殘差

        Parameters
        ----------
        ball_x/y/z : float
            檢測球心在工作台的初始坐標 (學長設定為 200, 0, 0，刀長為 0)
        n_points : int
            採樣點數量
        view_mode : str
            "absolute" : 機台絕對座標系（反映純粹物理幾何瑕疵）
            "relative" : 儀器相對座標系（完全模擬 LRT 歸零特性與觀測視角）
        match_senior_a_dir : bool
            是否反轉 A 軸旋轉矩陣方向以匹配學長的 Z 軸反向特徵 (預設為 True)
        """
        # 1. 生成軌跡角度
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
        
        # 2. 定義硬體結構位置
        P_local = np.array([ball_x, ball_y, ball_z, 1.0])
        T_pivot = self.pige_gen._get_htm(pivot_x, pivot_y, pivot_z, 0, 0, 0)
        
        active_errors = self.pige_gen.errors.copy()
        if custom_errors:
            active_errors.update(custom_errors)
            
        # 取得靜態 A 軸誤差矩陣 E_A
        E_A = self.pige_gen._get_error_matrix(
            active_errors['X_OA'], active_errors['Y_OA'], active_errors['Z_OA'],
            active_errors['A_OA'], active_errors['B_OA'], active_errors['C_OA']
        )

        results = []
        zeroing_baseline = np.zeros(3)

        for i in range(n_points):
            a_rad = a_cmd[i]
            c_rad = c_cmd[i]
            
            # 【關鍵修正一】：解決 Z 軸正負號相反問題
            # 若學長機台的 A 軸旋轉定義與標準右手定則相反，此處加上負號以匹配學長輸出
            a_rot = -a_rad if match_senior_a_dir else a_rad
            
            # 3. 動態 PDGE 擷取
            if enable_pdge:
                exc, eyc, ezc, eac, ebc, ecc = self.pdge_gen.get_c_axis_pdge(c_rad)
            else:
                exc = eyc = ezc = eac = ebc = ecc = 0.0

            # C 軸誤差 = 靜態 PIGE + 動態 PDGE
            total_x_oc = active_errors.get('X_OC', 0.0) + exc
            total_y_oc = active_errors.get('Y_OC', 0.0) + eyc
            total_z_oc = active_errors.get('Z_OC', 0.0) + ezc
            total_a_oc = active_errors.get('A_OC', 0.0) + eac
            total_b_oc = active_errors.get('B_OC', 0.0) + ebc
            total_c_oc = active_errors.get('C_OC', 0.0) + ecc

            E_AC_dyn = self.pige_gen._get_error_matrix(
                total_x_oc, total_y_oc, total_z_oc, 
                total_a_oc, total_b_oc, total_c_oc
            )

            # 產生此角度的理想 HTM
            T_A_i = self.pige_gen._get_htm(0, 0, 0, a_rot, 0, 0)
            T_C_i = self.pige_gen._get_htm(0, 0, 0, 0, 0, c_rad)

            # ── 【關鍵修正二與三】：嚴格物理核心，捨棄手動近似算法 ──
            # 理想軌跡點 (無誤差)
            P_ideal = T_A_i @ T_pivot @ T_C_i @ P_local
            
            # 實際軌跡點 (注入所有誤差)
            P_actual = E_A @ T_A_i @ T_pivot @ E_AC_dyn @ T_C_i @ P_local
            
            # 計算機台座標系下的「絕對偏差向量」
            Err_abs = (P_actual - P_ideal)[:3]
            
            # ── 觀測視角輸出 ──
            if view_mode == "absolute":
                err_vec = Err_abs
            elif view_mode == "relative":
                # 模擬 LRT 在 A=0, C=0 時按下的「歸零對心」動作
                if i == 0:
                    zeroing_baseline = Err_abs
                
                # 相對視角 = 當下絕對偏差 - 歸零點偏差
                err_vec = Err_abs - zeroing_baseline
            else:
                raise ValueError("view_mode 必須是 'absolute' 或 'relative'")

            results.append(err_vec)

        return np.array(results), a_cmd, c_cmd