"""
generator.py — 純 HTM 生成器
整合 PIGE + PDGE 的 BK4 軌跡模擬器
採用嚴格 HTM (齊次變換矩陣)，完美還原 LRT 相對量測機制

支援兩種機型：
  - "AC"：A/C 軸五軸工具機 (A 軸搖籃，預設)
  - "BC"：B/C 軸五軸工具機 (B 軸搖籃)

運動鏈（工件側）：
  AC 型：機床(0) → A軸(1) → C軸(2) → 球座(工件)
  BC 型：機床(0) → B軸(1) → C軸(2) → 球座(工件)

正確誤差鏈：
    E_cradle_pige @ E_cradle_pdge @ T_cradle @ T_pivot
    @ E_C_pige @ E_C_pdge @ T_C @ T_tool @ P_table

命名慣例：本模組為「純 HTM」生成器，
         對應 rodrigues_generator.py 的「HTM + Rodrigues」生成器
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
                 view_mode="relative", custom_errors=None,
                 enable_pdge=False,        # 整體開關（向後相容）
                 enable_a_pdge=False,      # A 軸 PDGEs 獨立開關
                 enable_c_pdge=False,      # C 軸 PDGEs 獨立開關
                 path_type="cone",
                 pivot_x=0.0, pivot_y=0.0, pivot_z=0.0,
                 tool_length=0.0,
                 match_senior_a_dir=True,
                 machine_type="AC"):
        """
        Parameters
        ----------
        machine_type : str
            "AC" (A 軸搖籃, 預設) 或 "BC" (B 軸搖籃)
            BC 型時，custom_errors 使用 XOB/ZOB/AOB/COB 鍵值
        """
        is_bc = (machine_type == "BC")

        # 整體開關優先：enable_pdge=True 時兩軸都開
        _use_cradle_pdge = enable_pdge or enable_a_pdge
        _use_c_pdge = enable_pdge or enable_c_pdge

        # ── 軌跡生成 ────────────────────────────────────────────────────────
        if path_type == "cone":
            c_deg = np.linspace(0, 360, n_points)
            cradle_deg = np.zeros_like(c_deg)
            for i, c in enumerate(c_deg):
                cradle_deg[i] = c / 2.0 if c <= 180 else (360 - c) / 2.0
            cradle_cmd = np.deg2rad(cradle_deg)
            c_cmd = np.deg2rad(c_deg)
        elif path_type == "K1":
            cradle_deg = np.arange(0, 91, 10).astype(float)
            c_deg = np.zeros_like(cradle_deg)
            cradle_cmd = np.deg2rad(cradle_deg)
            c_cmd = np.deg2rad(c_deg)
            n_points = len(cradle_cmd)
        elif path_type == "K2":
            c_deg = np.arange(0, 361, 20).astype(float)
            cradle_deg = np.zeros_like(c_deg)
            cradle_cmd = np.deg2rad(cradle_deg)
            c_cmd = np.deg2rad(c_deg)
            n_points = len(c_cmd)
        elif path_type == "sine":
            t = np.linspace(0, 4 * np.pi, n_points)
            cradle_cmd = np.deg2rad(30 * np.sin(t))
            c_cmd = np.deg2rad(90 * np.sin(2 * t))
        else:
            raise ValueError(f"未知的軌跡類型: {path_type}")

        # ── 幾何常數矩陣 ────────────────────────────────────────────────────
        P_local     = np.array([ball_x, ball_y, ball_z, 1.0])
        T_pivot     = self.pige_gen._get_htm(0, 0, pivot_z,     0, 0, 0)
        T_tool      = self.pige_gen._get_htm(0, 0, tool_length, 0, 0, 0)
        T_pivot_inv = np.linalg.inv(T_pivot)
        T_tool_inv  = np.linalg.inv(T_tool)

        # ── 靜態誤差參數 ────────────────────────────────────────────────────
        active_errors = self.pige_gen.errors.copy()
        if custom_errors:
            active_errors.update(custom_errors)

        # ── 搖籃軸 PIGEs（靜態）─────────────────────────────────────────────
        if is_bc:
            # BC 型：B 軸 PIGEs，YOB = 0（B 軸繞 Y 旋轉，沿旋轉軸不可量測）
            E_cradle_pige = self.pige_gen._get_error_matrix(
                active_errors.get('XOB', 0.0),
                0.0,
                active_errors.get('ZOB', 0.0),
                active_errors.get('AOB', 0.0),
                0.0,   # BOB = 0（自旋）
                active_errors.get('COB', 0.0)
            )
        else:
            # AC 型：A 軸 PIGEs，XOA = 0
            E_cradle_pige = self.pige_gen._get_error_matrix(
                0.0,
                active_errors.get('YOA', 0.0),
                active_errors.get('ZOA', 0.0),
                active_errors.get('AOA', 0.0),
                active_errors.get('BOA', 0.0),
                active_errors.get('COA', 0.0)
            )

        # ── C 軸 PIGEs（靜態）──────────────────────────────────────────────
        # ZOC = 0：C 軸沿旋轉軸方向（Z）的平移無法被 LRT 量測區分
        E_C_pige = self.pige_gen._get_error_matrix(
            active_errors.get('XOC', 0.0),
            active_errors.get('YOC', 0.0),
            0.0,
            active_errors.get('AOC', 0.0),
            active_errors.get('BOC', 0.0),
            active_errors.get('COC', 0.0)
        )

        # ── P_table：補償靜態 PIGEs 造成的基準偏移（模擬 LRT 歸零）──────────
        E_cradle_pige_inv = np.linalg.inv(E_cradle_pige)
        E_C_pige_inv = np.linalg.inv(E_C_pige)
        P_table = (
            T_tool_inv
            @ E_C_pige_inv
            @ T_pivot_inv
            @ E_cradle_pige_inv
            @ T_pivot
            @ T_tool
            @ P_local
        )

        # ── 主迴圈 ──────────────────────────────────────────────────────────
        results = []
        zeroing_baseline = np.zeros(3)

        for i in range(n_points):
            cradle_rad = cradle_cmd[i]
            c_rad = c_cmd[i]

            # 旋轉方向
            if is_bc:
                cradle_rot = cradle_rad   # B 軸正方向
            else:
                cradle_rot = -cradle_rad if match_senior_a_dir else cradle_rad
            c_rot = -c_rad

            # ── 搖籃軸 PDGEs（隨角度變化）────────────────────────────────────
            if _use_cradle_pdge and not is_bc:
                exa, eya, eza, eaa, eba, eca = self.pdge_gen.get_a_axis_pdge(cradle_rad)
            else:
                exa = eya = eza = eaa = eba = eca = 0.0

            # ── C 軸 PDGEs（隨 γ 變化）──────────────────────────────────────
            if _use_c_pdge:
                exc, eyc, ezc, eac, ebc, ecc = self.pdge_gen.get_c_axis_pdge(c_rad)
            else:
                exc = eyc = ezc = eac = ebc = ecc = 0.0

            # ── 誤差矩陣（PDGEs only，PIGEs 已單獨處理）──────────────────────
            E_cradle_pdge = self.pige_gen._get_error_matrix(exa, eya, eza, eaa, eba, eca)
            E_C_pdge = self.pige_gen._get_error_matrix(exc, eyc, ezc, eac, ebc, ecc)

            # ── 理想旋轉矩陣 ────────────────────────────────────────────────
            if is_bc:
                T_cradle_i = self.pige_gen._get_htm(0, 0, 0, 0, cradle_rot, 0)
            else:
                T_cradle_i = self.pige_gen._get_htm(0, 0, 0, cradle_rot, 0, 0)
            T_C_i = self.pige_gen._get_htm(0, 0, 0, 0, 0, c_rot)

            # ── 理想位置（無任何誤差的基準）──────────────────────────────────
            P_ideal = (
                T_cradle_i
                @ T_pivot
                @ self.pige_gen._get_htm(0, 0, 0, 0, 0, -c_rad)
                @ T_tool
                @ P_local
            )

            if view_mode == "absolute":
                P_actual = (
                    E_cradle_pige
                    @ E_cradle_pdge
                    @ T_cradle_i
                    @ T_pivot
                    @ E_C_pige
                    @ E_C_pdge
                    @ T_C_i
                    @ T_tool
                    @ P_local
                )
                err_vec = (P_actual - P_ideal)[:3]

            elif view_mode == "relative":
                P_actual = (
                    E_cradle_pige
                    @ E_cradle_pdge
                    @ T_cradle_i
                    @ T_pivot
                    @ E_C_pige
                    @ E_C_pdge
                    @ T_C_i
                    @ T_tool
                    @ P_table
                )
                Err_abs = (P_actual - P_ideal)[:3]

                if i == 0:
                    zeroing_baseline = Err_abs

                err_vec = Err_abs - zeroing_baseline
            else:
                raise ValueError("view_mode 必須是 'absolute' 或 'relative'")

            results.append(err_vec)

        return np.array(results), cradle_cmd, c_cmd