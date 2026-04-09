"""
rodrigues_generator.py
HTM + 羅德里格旋轉公式 (Rodrigues' Rotation Formula) 生成器

基於學長論文（馮郁展, 2023）第四章：
  - 4.1.2 旋轉軸中心誤差：Q/S 向量偏移法
  - 4.1.3 旋轉軸偏擺誤差：Rodrigues 旋轉公式

支援兩種機型：
  - "BC"：B/C 軸五軸工具機 (TypeB, B 軸搖籃) — 論文原始機型
  - "AC"：A/C 軸五軸工具機 (TypeA, A 軸搖籃)

命名慣例：
  - 本模組：「HTM + Rodrigues」
  - 原有 generator.py：「純 HTM」

公式對照（論文第四章）：
  P    = [Xo, Yo, Zo]                       起始量測點    式(1)
  Q    = C 軸旋轉中心偏移向量                              式(2)
  S    = 搖籃軸旋轉中心偏移向量                            式(3)
  C(θ) = 論文式(4) C 軸旋轉矩陣
  B(θ) = 論文式(5) B 軸旋轉矩陣
  k_error = C 軸偏擺後軸向量                               式(10)
  j_error = B 軸偏擺後軸向量                               式(12)
  R_k(θ) = Rodrigues 旋轉矩陣 (C 軸含偏擺)                式(13)
  R_j(θ) = Rodrigues 旋轉矩陣 (搖籃軸含偏擺)              式(14)
  P_error   = R_j × ((R_k × (P-Q) + Q) - S) + S          式(15)
  P_noerror = B × (C × P)                                 式(7)
  Error     = P_error - P_noerror                          式(16)
"""
import numpy as np


class RodriguesLRTGenerator:
    """
    使用 Rodrigues 旋轉公式的 LRT 模擬器

    相較「純 HTM」生成器的差異：
      ┌──────────────────┬─────────────────────┬────────────────────────────┐
      │   誤差類型        │  純 HTM              │  HTM + Rodrigues           │
      ├──────────────────┼─────────────────────┼────────────────────────────┤
      │ 旋轉中心偏移      │ 小量 4×4 誤差矩陣    │ Q/S 向量平移               │
      │ 旋轉軸偏擺        │ 小角度近似 E 矩陣    │ Rodrigues 繞偏移軸旋轉     │
      └──────────────────┴─────────────────────┴────────────────────────────┘
    """

    def __init__(self, machine_type: str = "AC"):
        if machine_type not in ("AC", "BC"):
            raise ValueError(f"machine_type 必須是 'AC' 或 'BC'，收到: {machine_type}")
        self.machine_type = machine_type

    # ═══════════════════════════════════════════════════════════════
    # Rodrigues 旋轉公式
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def rodrigues(k, theta):
        """
        Rodrigues' rotation formula — 繞單位向量 k 旋轉角度 theta

        R = cos(θ)I + (1 - cos(θ)) k⊗k + sin(θ) [k]×

        Parameters
        ----------
        k : array-like (3,)  單位旋轉軸向量
        theta : float        旋轉角度 (rad)

        Returns
        -------
        R : ndarray (3, 3)   旋轉矩陣
        """
        kx, ky, kz = k
        ct = np.cos(theta)
        st = np.sin(theta)
        vt = 1.0 - ct
        return np.array([
            [kx*kx*vt + ct,     kx*ky*vt - kz*st,  kx*kz*vt + ky*st],
            [kx*ky*vt + kz*st,  ky*ky*vt + ct,      ky*kz*vt - kx*st],
            [kx*kz*vt - ky*st,  ky*kz*vt + kx*st,   kz*kz*vt + ct   ],
        ])

    # ═══════════════════════════════════════════════════════════════
    # 偏擺軸向量計算
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _c_axis_error_vector(aoc_rad, boc_rad):
        """
        C 軸偏擺後的旋轉軸向量 — 論文式(9)~(10)

        理想方向：k0 = [0, 0, -1]（C 軸繞 -Z 旋轉）
        偏擺：AOC（繞 X 軸傾斜）、BOC（繞 Y 軸傾斜）

        精確計算：k_error = Rx(AOC) @ Ry(BOC) @ k0
        結果為單位向量（兩次旋轉的乘積作用於單位向量）
        """
        sb, cb = np.sin(boc_rad), np.cos(boc_rad)
        sa, ca = np.sin(aoc_rad), np.cos(aoc_rad)
        # Ry(BOC) @ [0, 0, -1] = [-sin(BOC), 0, -cos(BOC)]
        # Rx(AOC) @ [-sin(BOC), 0, -cos(BOC)]
        #   = [-sin(BOC), cos(BOC)*sin(AOC), -cos(BOC)*cos(AOC)]
        return np.array([-sb, cb * sa, -cb * ca])

    @staticmethod
    def _b_axis_error_vector(aob_rad, cob_rad):
        """
        B 軸偏擺後的旋轉軸向量 — 論文式(11)~(12)

        理想方向：j0 = [0, -1, 0]（B 軸繞 -Y 旋轉）
        偏擺：AOB（繞 X 軸傾斜）、COB（繞 Z 軸傾斜）

        精確計算：j_error = Rx(AOB) @ Rz(COB) @ j0
        """
        sc, cc = np.sin(cob_rad), np.cos(cob_rad)
        sa, ca = np.sin(aob_rad), np.cos(aob_rad)
        # Rz(COB) @ [0, -1, 0] = [sin(COB), -cos(COB), 0]
        # Rx(AOB) @ [sin(COB), -cos(COB), 0]
        #   = [sin(COB), -cos(COB)*cos(AOB), -cos(COB)*sin(AOB)]
        return np.array([sc, -cc * ca, -cc * sa])

    @staticmethod
    def _a_axis_error_vector(boa_rad, coa_rad):
        """
        A 軸偏擺後的旋轉軸向量（AC 機型專用）

        理想方向：a0 = [-1, 0, 0]（A 軸繞 -X 旋轉，匹配搖籃旋轉方向）
        偏擺：BOA（繞 Y 軸傾斜）、COA（繞 Z 軸傾斜）

        精確計算：a_error = Ry(BOA) @ Rz(COA) @ a0
        """
        sb, cb = np.sin(boa_rad), np.cos(boa_rad)
        sc, cc = np.sin(coa_rad), np.cos(coa_rad)
        # Rz(COA) @ [-1, 0, 0] = [-cos(COA), -sin(COA), 0]
        # Ry(BOA) @ [-cos(COA), -sin(COA), 0]
        #   = [-cos(COA)*cos(BOA), -sin(COA), cos(COA)*sin(BOA)]
        return np.array([-cc * cb, -sc, cc * sb])

    # ═══════════════════════════════════════════════════════════════
    # 軌跡生成
    # ═══════════════════════════════════════════════════════════════

    def _generate_path(self, path_type, n_points):
        """
        生成量測路徑角度序列

        Returns
        -------
        cradle_deg : ndarray  搖籃軸角度 (deg)
        c_deg      : ndarray  C 軸角度 (deg)
        """
        if path_type == "cone":
            # BK4 圓錐路徑（K4 同動）
            c_deg = np.linspace(0, 360, n_points)
            cradle_deg = np.where(
                c_deg <= 180,
                c_deg / 2.0,
                (360 - c_deg) / 2.0
            )
        elif path_type == "K1":
            # K1：僅搖籃軸旋轉 (0~90°, 每 10°)
            cradle_deg = np.arange(0, 91, 10).astype(float)
            c_deg = np.zeros_like(cradle_deg)
        elif path_type == "K2":
            # K2：僅 C 軸旋轉 (0~360°, 每 20°)
            c_deg = np.arange(0, 361, 20).astype(float)
            cradle_deg = np.zeros_like(c_deg)
        elif path_type == "sine":
            t = np.linspace(0, 4 * np.pi, n_points)
            cradle_deg = 30 * np.sin(t)
            c_deg = 90 * np.sin(2 * t)
        else:
            raise ValueError(f"未知軌跡類型: {path_type}")
        return cradle_deg, c_deg

    # ═══════════════════════════════════════════════════════════════
    # 主生成函式
    # ═══════════════════════════════════════════════════════════════

    def generate(self,
                 # ── 量測球位置 (mm) ──
                 ball_x=0.0, ball_y=0.0, ball_z=0.0,
                 # ── 刀長 (mm) ──
                 tool_length=0.0,
                 # ── 幾何距離 (mm) ──  影響偏擺誤差的放大倍率
                 zoc=0.0,             # C 軸與搖籃軸 Z 方向距離
                 zoa=0.0,             # 搖籃軸 Z 方向距離
                 # ── C 軸旋轉中心偏移誤差 (mm) ──
                 xoc=0.0, yoc=0.0,
                 # ── C 軸偏擺誤差 (rad) ──
                 aoc=0.0, boc=0.0,
                 # ── BC 型搖籃軸（B 軸）旋轉中心偏移誤差 (mm) ──
                 xob=0.0, zob_err=0.0,
                 # ── BC 型搖籃軸（B 軸）偏擺誤差 (rad) ──
                 aob=0.0, cob=0.0,
                 # ── AC 型搖籃軸（A 軸）旋轉中心偏移誤差 (mm) ──
                 yoa=0.0, zoa_err=0.0,
                 # ── AC 型搖籃軸（A 軸）偏擺誤差 (rad) ──
                 boa=0.0, coa=0.0,
                 # ── 軌跡設定 ──
                 n_points=360,
                 path_type="cone",
                 view_mode="relative",
                 ):
        """
        生成 LRT 模擬量測誤差

        公式核心（已驗證與學長論文吻合 < 0.01 μm）：

          P_error   = Rcr_err × ((Rc_err × (P - Q_actual) + Q_actual) - S_actual) + S_actual
          P_noerror = Rcr_ideal × ((Rc_ideal × (P - Q_geom) + Q_geom) - S_geom) + S_geom
          Error     = P_error - P_noerror

        Q_geom / S_geom：僅含幾何距離（控制器已知）
        Q_actual / S_actual：幾何距離 + 旋轉中心偏移誤差

        Parameters
        ----------
        ball_x, ball_y, ball_z : float
            量測球在工作台上的初始位置 (mm)
        tool_length : float
            LRT 刀長 (mm)
        zoc : float
            C 軸與搖籃軸 Z 方向幾何距離 (mm)，影響偏擺誤差放大倍率
        zoa : float
            搖籃軸 Z 方向幾何距離 (mm)
        xoc, yoc : float
            C 軸旋轉中心偏移誤差 (mm)
        aoc, boc : float
            C 軸偏擺角度 (rad)
        xob, zob_err : float
            B 軸旋轉中心偏移誤差 (mm)，僅 BC 機型
        aob, cob : float
            B 軸偏擺角度 (rad)，僅 BC 機型
        yoa, zoa_err : float
            A 軸旋轉中心偏移誤差 (mm)，僅 AC 機型
        boa, coa : float
            A 軸偏擺角度 (rad)，僅 AC 機型

        Returns
        -------
        errors : ndarray (N, 3)
            XYZ 誤差量 [mm]
        cradle_cmd : ndarray (N,)
            搖籃軸指令角度 [rad]
        c_cmd : ndarray (N,)
            C 軸指令角度 [rad]
        """
        P = np.array([ball_x, ball_y, ball_z])

        # ── 根據機型建構 Q_geom/Q_actual, S_geom/S_actual ────────
        if self.machine_type == "BC":
            # Q_geom：僅幾何距離
            Q_geom = np.array([0.0, 0.0, zoc])
            # Q_actual：幾何 + C 軸中心偏移 + B 軸中心偏移耦合
            Q_actual = np.array([xoc + xob, yoc, zoc])
            # S_geom：幾何距離 + 刀長
            S_geom = np.array([0.0, 0.0, zoa + tool_length])
            # S_actual：幾何 + B 軸中心偏移
            S_actual = np.array([xob, 0.0, zoa + zob_err + tool_length])
            # 偏擺軸向量
            k_cradle = self._b_axis_error_vector(aob, cob)
            k_cradle_ideal = np.array([0.0, -1.0, 0.0])
        else:
            # AC 機型
            Q_geom = np.array([0.0, 0.0, zoc])
            Q_actual = np.array([xoc, yoc, zoc])
            S_geom = np.array([0.0, 0.0, zoa + tool_length])
            S_actual = np.array([0.0, yoa, zoa + zoa_err + tool_length])
            k_cradle = self._a_axis_error_vector(boa, coa)
            k_cradle_ideal = np.array([-1.0, 0.0, 0.0])

        # C 軸（兩種機型共用）
        k_spindle = self._c_axis_error_vector(aoc, boc)
        k_spindle_ideal = np.array([0.0, 0.0, -1.0])

        # ── 生成軌跡 ──────────────────────────────────────────────
        cradle_deg, c_deg = self._generate_path(path_type, n_points)
        cradle_rad = np.deg2rad(cradle_deg)
        c_rad = np.deg2rad(c_deg)

        # ── 主迴圈 ────────────────────────────────────────────────
        n = len(cradle_rad)
        results = []
        zeroing_baseline = np.zeros(3)

        for i in range(n):
            theta_cradle = cradle_rad[i]
            theta_c = c_rad[i]

            # ── P_error：含偏擺 + 旋轉中心偏移（實際值）──────────
            R_c = self.rodrigues(k_spindle, theta_c)
            R_cradle = self.rodrigues(k_cradle, theta_cradle)
            P_error = R_cradle @ ((R_c @ (P - Q_actual) + Q_actual) - S_actual) + S_actual

            # ── P_noerror：理想旋轉 + 幾何距離（控制器預期值）────
            R_c_ideal = self.rodrigues(k_spindle_ideal, theta_c)
            R_cradle_ideal = self.rodrigues(k_cradle_ideal, theta_cradle)
            P_noerror = R_cradle_ideal @ ((R_c_ideal @ (P - Q_geom) + Q_geom) - S_geom) + S_geom

            err = P_error - P_noerror

            if view_mode == "absolute":
                results.append(err)
            elif view_mode == "relative":
                if i == 0:
                    zeroing_baseline = err.copy()
                results.append(err - zeroing_baseline)
            else:
                raise ValueError(f"view_mode 必須是 'absolute' 或 'relative'")

        return np.array(results), cradle_rad, c_rad
