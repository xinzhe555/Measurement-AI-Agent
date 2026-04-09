"""
static_analyzer.py
物理層辨識器：使用 HTM + Rodrigues 旋轉公式
用非線性最小二乘法（scipy.optimize.least_squares）反算物理誤差參數

辨識的誤差項（10 個 PIGE + 8 個 PDGE = 18 參數）：
    PIGE: XOC, YOC             (C 軸旋轉中心偏移)
          AOC, BOC             (C 軸偏擺)
          YOA, Z_OA_err        (A 軸旋轉中心偏移)
          BOA, COA             (A 軸偏擺)
    PDGE: C_Runout_X_Amp/Phase, C_Runout_Y_Amp/Phase  (徑向跳動)
          C_Runout_Z_Amp/Freq                          (軸向竄動)
          C_Wobble_A_Amp, C_Wobble_B_Amp               (角度擺動)

幾何距離（ZOC, ZOA）為輸入參數，非辨識目標：
    ZOC: C 軸與搖籃軸 Z 方向距離 → 影響偏擺誤差放大倍率
    ZOA: 搖籃軸 Z 方向距離
"""
import numpy as np
from scipy.optimize import least_squares


# ──────────────────────────────────────────────────────────────
# Rodrigues 旋轉公式
# ──────────────────────────────────────────────────────────────

def _rodrigues(k, theta):
    """繞單位向量 k 旋轉角度 theta"""
    kx, ky, kz = k
    ct = np.cos(theta)
    st = np.sin(theta)
    vt = 1.0 - ct
    return np.array([
        [kx*kx*vt + ct,     kx*ky*vt - kz*st,  kx*kz*vt + ky*st],
        [kx*ky*vt + kz*st,  ky*ky*vt + ct,      ky*kz*vt - kx*st],
        [kx*kz*vt - ky*st,  ky*kz*vt + kx*st,   kz*kz*vt + ct   ],
    ])


def _c_axis_vector(aoc, boc):
    """C 軸偏擺後軸向量：Rx(AOC) @ Ry(BOC) @ [0, 0, -1]"""
    sb, cb = np.sin(boc), np.cos(boc)
    sa, ca = np.sin(aoc), np.cos(aoc)
    return np.array([-sb, cb * sa, -cb * ca])


def _a_axis_vector(boa, coa):
    """A 軸偏擺後軸向量：Ry(BOA) @ Rz(COA) @ [-1, 0, 0]"""
    sb, cb = np.sin(boa), np.cos(boa)
    sc, cc = np.sin(coa), np.cos(coa)
    return np.array([-cc * cb, -sc, cc * sb])


K_C_IDEAL = np.array([0.0, 0.0, -1.0])
K_A_IDEAL = np.array([-1.0, 0.0, 0.0])


# ──────────────────────────────────────────────────────────────
# 前向模型（Forward Model）— HTM + Rodrigues
# ──────────────────────────────────────────────────────────────

def forward_model(params, a_cmd, c_cmd, ball_x, ball_y, ball_z,
                  zoc=0.0, zoa=0.0, tool_length=0.0,
                  # 保留舊介面相容
                  pivot_z=None):
    """
    Rodrigues 版前向模型，與 RodriguesLRTGenerator 物理一致。

    公式：
      P_error   = Rcr_err × ((Rc_err × (P - Q_actual) + Q_actual) - S_actual) + S_actual
      P_noerror = Rcr_ideal × ((Rc_ideal × (P - Q_geom) + Q_geom) - S_geom) + S_geom

    Parameters
    ----------
    params : array-like (18,)
        [XOC, YOC, AOC, BOC,
         YOA, Z_OA_err, BOA, COA,
         Rx_amp, Rx_ph, Ry_amp, Ry_ph, Rz_amp, Rz_freq,
         Wa_amp, Wb_amp,
         _reserved1, _reserved2]
    zoc : float
        C 軸與搖籃軸 Z 方向幾何距離 (mm)，非辨識目標
    zoa : float
        搖籃軸 Z 方向幾何距離 (mm)，非辨識目標
    """
    # 向後相容：如果呼叫者傳 pivot_z 但沒傳 zoc，用 pivot_z
    if pivot_z is not None and zoc == 0.0:
        zoc = pivot_z

    (XOC, YOC, AOC, BOC,
     YOA, Z_OA_err, BOA, COA,
     Rx_amp, Rx_ph, Ry_amp, Ry_ph,
     Rz_amp, Rz_freq,
     Wa_amp, Wb_amp,
     _r1, _r2) = params

    P = np.array([ball_x, ball_y, ball_z])

    # ── 幾何向量（控制器已知）────────────────────────────────────
    Q_geom = np.array([0.0, 0.0, zoc])
    S_geom = np.array([0.0, 0.0, zoa + tool_length])

    N = len(a_cmd)
    predicted = np.zeros((N, 3))
    zeroing_baseline = np.zeros(3)

    for i in range(N):
        a_rad = a_cmd[i]
        c_rad = c_cmd[i]

        # ── 動態 PDGE（隨 C 角度的諧波分量）────────────────────
        exc = Rx_amp * np.cos(c_rad + Rx_ph)
        eyc = Ry_amp * np.sin(c_rad + Ry_ph)
        ezc = Rz_amp * np.sin(Rz_freq * c_rad)
        eac = Wa_amp * np.cos(c_rad)
        ebc = Wb_amp * np.sin(c_rad)

        # ── C 軸：靜態 + 動態偏擺 ─────────────────────────────
        aoc_total = AOC + eac
        boc_total = BOC + ebc
        k_c = _c_axis_vector(aoc_total, boc_total)

        # ── A 軸：靜態偏擺 ─────────────────────────────────────
        k_a = _a_axis_vector(BOA, COA)

        # ── Q_actual / S_actual（含偏移誤差）───────────────────
        Q_actual = np.array([XOC + exc, YOC + eyc, zoc + ezc])
        S_actual = np.array([0.0, YOA, zoa + Z_OA_err + tool_length])

        # ── P_error：Rodrigues 含偏擺 + 偏移 ──────────────────
        Rc = _rodrigues(k_c, c_rad)
        Ra = _rodrigues(k_a, a_rad)
        P_error = Ra @ ((Rc @ (P - Q_actual) + Q_actual) - S_actual) + S_actual

        # ── P_noerror：理想旋轉 + 幾何距離 ────────────────────
        Rc_ideal = _rodrigues(K_C_IDEAL, c_rad)
        Ra_ideal = _rodrigues(K_A_IDEAL, a_rad)
        P_noerror = Ra_ideal @ ((Rc_ideal @ (P - Q_geom) + Q_geom) - S_geom) + S_geom

        Err_abs = P_error - P_noerror

        if i == 0:
            zeroing_baseline = Err_abs.copy()

        predicted[i] = Err_abs - zeroing_baseline

    return predicted


# ──────────────────────────────────────────────────────────────
# 物理層辨識器
# ──────────────────────────────────────────────────────────────

class PhysicalLayerAnalyzer:
    """
    用非線性最小二乘法，對量測殘差反算物理誤差參數
    前向模型使用 HTM + Rodrigues 旋轉公式
    """
    PARAM_NAMES = [
        'XOC', 'YOC', 'AOC', 'BOC',
        'YOA', 'Z_OA_err', 'BOA', 'COA',
        'Runout_X_Amp', 'Runout_X_Phase',
        'Runout_Y_Amp', 'Runout_Y_Phase',
        'Runout_Z_Amp', 'Runout_Z_Freq',
        'Wobble_A_Amp', 'Wobble_B_Amp',
        '_reserved1', '_reserved2',
    ]

    BOUNDS_LOWER = [
        # C 軸偏移 (mm)         C 軸偏擺 (rad)
        -0.5, -0.5,             -0.01, -0.01,
        # A 軸偏移 (mm)         A 軸偏擺 (rad)
        -0.5, -0.5,             -0.01, -0.01,
        # PDGE: Runout X/Y amp+phase, Z amp+freq, Wobble
         0.0, -np.pi,
         0.0, -np.pi,
         0.0,  1.0,
         0.0,  0.0,
        # reserved
        -1e-12, -1e-12,
    ]

    BOUNDS_UPPER = [
         0.5,  0.5,              0.01,  0.01,
         0.5,  0.5,              0.01,  0.01,
         0.5,  np.pi,
         0.5,  np.pi,
         0.5,  4.0,
         0.01, 0.01,
         1e-12,  1e-12,
    ]

    def __init__(self):
        self.identified_params = None
        self.residual_data = None
        self.fit_rms = None

    def identify(self, measured_error, a_cmd, c_cmd,
                 ball_x=200.0, ball_y=0.0, ball_z=0.0,
                 zoc=0.0, zoa=0.0, tool_length=0.0,
                 # 向後相容
                 pivot_z=None,
                 verbose=True):
        """
        主辨識入口

        Parameters
        ----------
        zoc : float
            C 軸與搖籃軸 Z 方向幾何距離 (mm)，非辨識目標，影響偏擺放大倍率
        zoa : float
            搖籃軸 Z 方向幾何距離 (mm)，非辨識目標
        """
        if pivot_z is not None and zoc == 0.0:
            zoc = pivot_z

        if verbose:
            print("\n" + "="*62)
            print("  [物理層] HTM + Rodrigues 非線性最小二乘辨識啟動")
            print(f"  ZOC={zoc:.1f} mm  ZOA={zoa:.1f} mm  ball=[{ball_x},{ball_y},{ball_z}]")
            print("="*62)

        x0 = np.zeros(18)
        x0[13] = 2.0   # Rz_freq 初始猜測

        def residual_fn(params):
            pred = forward_model(params, a_cmd, c_cmd, ball_x, ball_y, ball_z,
                                 zoc=zoc, zoa=zoa, tool_length=tool_length)
            return (pred - measured_error).ravel()

        sol = least_squares(
            residual_fn, x0,
            bounds=(self.BOUNDS_LOWER, self.BOUNDS_UPPER),
            method='trf',
            ftol=1e-12, xtol=1e-12, gtol=1e-12,
            max_nfev=8000,
            verbose=0
        )

        self.identified_params = dict(zip(self.PARAM_NAMES, sol.x))

        # 向後相容：產生舊的 key 名稱供 bk4_bridge 使用
        p = self.identified_params
        p['ZOC'] = 0.0      # ZOC 是幾何，不是誤差
        p['XOA'] = 0.0      # A 軸繞 X 旋轉，XOA 不可量測
        p['YOA'] = p.get('YOA', p.get('YOA', 0.0))
        p['ZOA'] = p.get('Z_OA_err', 0.0)
        p['XOC'] = p.get('XOC', 0.0)
        p['YOC'] = p.get('YOC', 0.0)
        p['AOC'] = p.get('AOC', 0.0)
        p['BOC'] = p.get('BOC', 0.0)
        p['BOA'] = p.get('BOA', 0.0)
        p['COA'] = p.get('COA', 0.0)

        identified_data = forward_model(sol.x, a_cmd, c_cmd, ball_x, ball_y, ball_z,
                                        zoc=zoc, zoa=zoa, tool_length=tool_length)
        self.residual_data = measured_error - identified_data

        rms_before = np.sqrt(np.mean(measured_error**2, axis=0)) * 1000
        rms_after  = np.sqrt(np.mean(self.residual_data**2, axis=0)) * 1000
        self.fit_rms = {'before': rms_before, 'after': rms_after}

        if verbose:
            self._print_report()

        return self.identified_params, self.residual_data

    def _print_report(self):
        p = self.identified_params
        rms = self.fit_rms

        print("\n【PIGE 辨識結果 — C軸】")
        print(f"  XOC = {p['XOC']*1000:+8.2f} um   "
              f"YOC = {p['YOC']*1000:+8.2f} um")
        print(f"  AOC = {np.degrees(p['AOC']):+8.4f} deg  "
              f"BOC = {np.degrees(p['BOC']):+8.4f} deg")

        print("\n【PIGE 辨識結果 — A軸(搖籃)】")
        print(f"  YOA = {p.get('YOA',0)*1000:+8.2f} um   "
              f"ZOA = {p.get('Z_OA_err',0)*1000:+8.2f} um")
        print(f"  BOA = {np.degrees(p['BOA']):+8.4f} deg  "
              f"COA = {np.degrees(p['COA']):+8.4f} deg")

        print("\n【PDGE 辨識結果 — C軸動態諧波】")
        print(f"  徑向跳動 X: Amp={p['Runout_X_Amp']*1000:6.2f} um  "
              f"Phase={np.degrees(p['Runout_X_Phase']):+7.1f}°")
        print(f"  徑向跳動 Y: Amp={p['Runout_Y_Amp']*1000:6.2f} um  "
              f"Phase={np.degrees(p['Runout_Y_Phase']):+7.1f}°")
        print(f"  軸向竄動 Z: Amp={p['Runout_Z_Amp']*1000:6.2f} um  "
              f"Freq={p['Runout_Z_Freq']:5.2f}x")
        print(f"  Wobble  A:  Amp={np.degrees(p['Wobble_A_Amp']):6.4f} deg  "
              f"B: Amp={np.degrees(p['Wobble_B_Amp']):6.4f} deg")

        print("\n【擬合效果 (RMS)】")
        print(f"  {'軸':>4} | {'補償前':>10} | {'補償後':>10} | {'改善率':>8}")
        for i, ax in enumerate(['DX', 'DY', 'DZ']):
            b, a = rms['before'][i], rms['after'][i]
            rate = (1 - a / b) * 100 if b > 0 else 0
            print(f"  {ax:>4} | {b:>8.3f}um | {a:>8.3f}um | {rate:>6.1f}%")


# ──────────────────────────────────────────────────────────────
# Agent 診斷報告
# ──────────────────────────────────────────────────────────────

class AgentDiagnosticReport:
    """
    根據物理層辨識結果自動生成診斷報告
    告訴使用者：需要量什麼誤差、用什麼儀器、優先順序
    """
    THRESHOLDS = {
        'XOC':        0.010,   # mm  10 um
        'YOC':        0.010,
        'AOC':        0.0001,  # rad ≈ 0.006 deg
        'BOC':        0.0001,
        'BOA':        0.0001,
        'Runout_1x':   5.0,     # um
        'Runout_Z_2x': 3.0,
        'Residual_AI': 2.0,     # um  物理補償後殘差門檻 → 觸發AI層
    }

    INSTRUMENTS = {
        'LRT': {
            'name': 'Laser R-Test (LRT)',
            'measures': ['C軸徑向跳動', 'A/C同動誤差', 'PIGE全項辨識'],
            'accuracy': '< 1 um / 0.0006°',
            'time': '約 2 小時',
        },
        'DBB': {
            'name': 'Double Ball Bar (DBB)',
            'measures': ['圓度誤差', '伺服不匹配', '象限突波'],
            'accuracy': '< 0.1 um',
            'time': '約 30 分鐘',
        },
        'Autocollimator': {
            'name': '電子式水平儀 / 自準直儀',
            'measures': ['A軸直線度', 'A/C垂直度', '靜態角度誤差'],
            'accuracy': '< 0.0003°',
            'time': '約 1 小時',
        },
        'Spindle_Analyzer': {
            'name': '主軸誤差分析儀',
            'measures': ['徑向跳動', '軸向竄動', 'Wobble'],
            'accuracy': '< 0.01 um',
            'time': '約 1 小時',
        },
    }

    def generate(self, identified_params, residual_rms_after, verbose=True):
        p = identified_params
        findings, instruments = [], set()

        # ── 靜態偏心
        for key, label in [('XOC', 'C軸偏心X'), ('YOC', 'C軸偏心Y')]:
            if abs(p.get(key, 0)) > self.THRESHOLDS.get(key, 0.01):
                findings.append({
                    'level': '🔴 嚴重',
                    'desc': f'{label} = {p[key]*1000:+.1f} um（門檻 ±{self.THRESHOLDS[key]*1000:.0f} um）',
                    'impact': '工件圓度誤差、加工半徑偏移',
                    'action': '→ 控制器輸入 XOC/YOC 偏心補償，或機械調整夾頭',
                    'inst': 'LRT',
                })
                instruments.add('LRT')

        # ── C 軸偏擺 AOC
        if abs(p.get('AOC', 0)) > self.THRESHOLDS['AOC']:
            findings.append({
                'level': '🔴 嚴重',
                'desc': f'C 軸偏擺 AOC = {np.degrees(p["AOC"]):+.4f} deg',
                'impact': 'Z 向週期性誤差，影響輪廓精度與面粗度',
                'action': '→ LRT 靜態量測確認，控制器輸入 AOC 補償值',
                'inst': 'LRT',
            })
            instruments.add('LRT')

        # ── C 軸偏擺 BOC
        if abs(p.get('BOC', 0)) > self.THRESHOLDS['BOC']:
            findings.append({
                'level': '🔴 嚴重',
                'desc': f'C 軸偏擺 BOC = {np.degrees(p["BOC"]):+.4f} deg',
                'impact': 'X 向週期性誤差，影響圓弧輪廓',
                'action': '→ LRT 靜態量測確認，控制器輸入 BOC 補償值',
                'inst': 'LRT',
            })
            instruments.add('LRT')

        # ── A 軸偏擺 BOA
        if abs(p.get('BOA', 0)) > self.THRESHOLDS['BOA']:
            findings.append({
                'level': '🟡 警告',
                'desc': f'A 軸偏擺 BOA = {np.degrees(p["BOA"]):+.4f} deg',
                'impact': 'A 軸旋轉面不垂直，X 方向出現位移誤差',
                'action': '→ 自準直儀靜態量測 A 軸安裝垂直度，機械調整或補償',
                'inst': 'Autocollimator',
            })
            instruments.add('Autocollimator')

        # ── 徑向跳動
        avg_runout = (p.get('Runout_X_Amp', 0) + p.get('Runout_Y_Amp', 0)) / 2 * 1000
        if avg_runout > self.THRESHOLDS['Runout_1x']:
            findings.append({
                'level': '🟡 警告',
                'desc': f'C 軸徑向跳動 {avg_runout:.1f} um（1 倍頻）',
                'impact': '量測球軌跡呈橢圓，加工圓弧產生誤差',
                'action': '→ 主軸誤差分析儀量測 C 軸誤差運動，檢查軸承預壓',
                'inst': 'Spindle_Analyzer',
            })
            instruments.add('Spindle_Analyzer')

        # ── 軸向竄動
        if p.get('Runout_Z_Amp', 0) * 1000 > self.THRESHOLDS['Runout_Z_2x']:
            findings.append({
                'level': '🟡 警告',
                'desc': (f'C 軸軸向竄動 {p["Runout_Z_Amp"]*1000:.1f} um，'
                         f'{p["Runout_Z_Freq"]:.1f} 倍頻（馬鞍形）'),
                'impact': 'Z 向週期性波動，影響平面銑削面粗度',
                'action': '→ 電容感測器量測 C 軸端面跳動，檢查轉台盤面平面度',
                'inst': 'Spindle_Analyzer',
            })
            instruments.add('Spindle_Analyzer')

        # ── AI 層觸發
        needs_ai = residual_rms_after > self.THRESHOLDS['Residual_AI']
        if needs_ai:
            findings.append({
                'level': '🔵 AI層',
                'desc': f'物理補償後平均殘差 RMS = {residual_rms_after:.2f} um',
                'impact': '含摩擦力非線性、伺服不匹配等物理模型無法解析的誤差',
                'action': '→ 啟動 AI 殘差學習層；DBB 量測象限突波量化摩擦力',
                'inst': 'DBB',
            })
            instruments.add('DBB')

        if verbose:
            self._print(findings, instruments, needs_ai)

        return {
            'findings': findings,
            'instruments': list(instruments),
            'needs_ai': needs_ai,
        }

    def _print(self, findings, instruments, needs_ai):
        print("\n" + "="*62)
        print("  [Agent] 智能診斷報告")
        print("="*62)
        for i, f in enumerate(findings):
            print(f"\n  [{i+1}] {f['level']}  {f['desc']}")
            print(f"       影響：{f['impact']}")
            print(f"       {f['action']}")

        print("\n" + "─"*62)
        print("【建議量測儀器（一次到位調機清單）】")
        for key in instruments:
            if key in self.INSTRUMENTS:
                d = self.INSTRUMENTS[key]
                print(f"\n  {d['name']}")
                print(f"     量測：{', '.join(d['measures'])}")
                print(f"     精度：{d['accuracy']}   預計耗時：{d['time']}")

        if needs_ai:
            print("\n" + "─"*62)
            print("【AI 補償層建議】")
            print("  輸入特徵：(A角度, C角度, A速度方向, C速度方向, |速度|)")
            print("  輸出：    (DX_res, DY_res, DZ_res)")
            print("  建議模型：MLP (tanh) 或 Gaussian Process Regression")

        print("\n" + "="*62)
