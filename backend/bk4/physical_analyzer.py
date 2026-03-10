"""
physical_analyzer.py
物理層辨識器：與生成器使用相同的 HTM 數學模型
用非線性最小二乘法（scipy.optimize.least_squares）反算物理參數

辨識的誤差項：
    PIGE: X_OC, Y_OC, Z_OC, A_OC, B_OC  (C軸靜態偏差)
          X_OA, Y_OA, Z_OA, B_OA, C_OA  (A軸靜態偏差)
    PDGE: C_Runout_X_Amp/Phase, C_Runout_Y_Amp/Phase  (徑向跳動)
          C_Runout_Z_Amp/Freq                          (軸向竄動)
          C_Wobble_A_Amp, C_Wobble_B_Amp               (角度擺動)
"""
import numpy as np
from scipy.optimize import least_squares


# ──────────────────────────────────────────────────────────────
# HTM 工具函式
# ──────────────────────────────────────────────────────────────

def _htm(x, y, z, a, b, c):
    Ca, Sa = np.cos(a), np.sin(a)
    Cb, Sb = np.cos(b), np.sin(b)
    Cc, Sc = np.cos(c), np.sin(c)
    return np.array([
        [Cb*Cc,              -Cb*Sc,              Sb,    x],
        [Sa*Sb*Cc + Ca*Sc,  -Sa*Sb*Sc + Ca*Cc,  -Sa*Cb, y],
        [-Ca*Sb*Cc + Sa*Sc,  Ca*Sb*Sc + Sa*Cc,   Ca*Cb, z],
        [0, 0, 0, 1]
    ])

def _err_mat(dx, dy, dz, da, db, dc):
    return np.array([
        [1,   -dc,  db,  dx],
        [dc,   1,  -da,  dy],
        [-db,  da,   1,  dz],
        [0,    0,    0,   1]
    ])


# ──────────────────────────────────────────────────────────────
# 前向模型（Forward Model）
# 與 generator.py 中的模擬邏輯完全對應
# ──────────────────────────────────────────────────────────────

def forward_model(params, a_cmd, c_cmd, ball_x, ball_y, ball_z, tool_length):
    """
    給定一組物理參數，預測 BK4 路徑的誤差殘差
    """
    (X_OC, Y_OC, Z_OC, A_OC, B_OC,
     X_OA, Y_OA, Z_OA, B_OA, C_OA,
     Rx_amp, Rx_ph, Ry_amp, Ry_ph,
     Rz_amp, Rz_freq,
     Wa_amp, Wb_amp) = params

    # 1. 設置球心初始坐標與刀長(Z偏移)
    P_local = np.array([ball_x, ball_y, ball_z, 1.0])
    T_pivot = _htm(0, 0, tool_length, 0, 0, 0)

    # 靜態 A 軸誤差矩陣
    E_A = _err_mat(X_OA, Y_OA, Z_OA, 0.0, B_OA, C_OA)

    N = len(a_cmd)
    predicted = np.zeros((N, 3))
    zeroing_baseline = np.zeros(3)

    for i in range(N):
        c = c_cmd[i]
        a = a_cmd[i]

        # 理想位置 (無誤差)
        T_A = _htm(0, 0, 0, a, 0, 0)
        T_C = _htm(0, 0, 0, 0, 0, c)
        P_ideal = T_A @ T_pivot @ T_C @ P_local

        # 動態 PDGE
        exc = Rx_amp * np.cos(c + Rx_ph)
        eyc = Ry_amp * np.sin(c + Ry_ph)
        ezc = Rz_amp * np.sin(Rz_freq * c)
        eac = Wa_amp * np.cos(c)
        ebc = Wb_amp * np.sin(c)

        # 靜態 + 動態疊加 (C軸相對A軸)
        E_AC = _err_mat(X_OC + exc, Y_OC + eyc, Z_OC + ezc,
                        A_OC + eac, B_OC + ebc, 0.0)

        # 實際位置 (含誤差)
        P_actual = E_A @ T_A @ T_pivot @ E_AC @ T_C @ P_local
        
        # 絕對偏差 (實際與理想的差距)
        Err_abs = (P_actual - P_ideal)[:3]

        # 模擬 LRT 在 A=0, C=0 的歸零對心動作，確保辨識器與生成器基準一致
        if i == 0:
            zeroing_baseline = Err_abs
            
        predicted[i] = Err_abs - zeroing_baseline

    return predicted


# ──────────────────────────────────────────────────────────────
# 物理層辨識器
# ──────────────────────────────────────────────────────────────

class PhysicalLayerAnalyzer:
    """
    用非線性最小二乘法，對量測殘差反算物理誤差參數
    """
    PARAM_NAMES = [
        'X_OC', 'Y_OC', 'Z_OC', 'A_OC', 'B_OC',
        'X_OA', 'Y_OA', 'Z_OA', 'B_OA', 'C_OA',
        'Runout_X_Amp', 'Runout_X_Phase',
        'Runout_Y_Amp', 'Runout_Y_Phase',
        'Runout_Z_Amp', 'Runout_Z_Freq',
        'Wobble_A_Amp', 'Wobble_B_Amp',
    ]
    BOUNDS_LOWER = [
        -0.5, -0.5, -0.5, -0.005, -0.005,
        -0.5, -0.5, -0.5, -0.005, -0.005,
        0.0,  -np.pi,
        0.0,  -np.pi,
        0.0,   1.0,
        0.0,   0.0,
    ]
    BOUNDS_UPPER = [
        0.5,  0.5,  0.5,  0.005,  0.005,
        0.5,  0.5,  0.5,  0.005,  0.005,
        0.5,  np.pi,
        0.5,  np.pi,
        0.5,  4.0,
        0.005, 0.005,
    ]

    def __init__(self):
        self.identified_params = None
        self.residual_data = None
        self.fit_rms = None

    def identify(self, measured_error, a_cmd, c_cmd, ball_x=200.0, ball_y=0.0, ball_z=0.0, tool_length=0.0,
                 verbose=True):
        """
        主辨識入口
        """
        if verbose:
            print("\n" + "="*62)
            print("  [物理層] HTM 非線性最小二乘辨識啟動")
            print("="*62)

        x0 = np.zeros(18)
        x0[15] = 2.0   

        def residual_fn(params):
            pred = forward_model(params, a_cmd, c_cmd, ball_x, ball_y, ball_z, tool_length)
            return (pred - measured_error).ravel()

        sol = least_squares(
            residual_fn, x0,
            bounds=(self.BOUNDS_LOWER, self.BOUNDS_UPPER),
            method='trf',
            ftol=1e-10, xtol=1e-10, gtol=1e-10,
            max_nfev=5000,
            verbose=0
        )

        self.identified_params = dict(zip(self.PARAM_NAMES, sol.x))
        identified_data = forward_model(sol.x, a_cmd, c_cmd, ball_x, ball_y, ball_z, tool_length)
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

        print("\n【PIGE 辨識結果 — C軸相對A軸】")
        print(f"  X_OC = {p['X_OC']*1000:+8.2f} um   "
              f"Y_OC = {p['Y_OC']*1000:+8.2f} um   "
              f"Z_OC = {p['Z_OC']*1000:+8.2f} um")
        print(f"  A_OC = {p['A_OC']*1000:+8.4f} mrad  "
              f"B_OC = {p['B_OC']*1000:+8.4f} mrad")

        print("\n【PIGE 辨識結果 — A軸相對Bed】")
        print(f"  X_OA = {p['X_OA']*1000:+8.2f} um   "
              f"Y_OA = {p['Y_OA']*1000:+8.2f} um")
        print(f"  B_OA = {p['B_OA']*1000:+8.4f} mrad  "
              f"C_OA = {p['C_OA']*1000:+8.4f} mrad")

        print("\n【PDGE 辨識結果 — C軸動態諧波】")
        print(f"  徑向跳動 X: Amp={p['Runout_X_Amp']*1000:6.2f} um  "
              f"Phase={np.degrees(p['Runout_X_Phase']):+7.1f}°")
        print(f"  徑向跳動 Y: Amp={p['Runout_Y_Amp']*1000:6.2f} um  "
              f"Phase={np.degrees(p['Runout_Y_Phase']):+7.1f}°")
        print(f"  軸向竄動 Z: Amp={p['Runout_Z_Amp']*1000:6.2f} um  "
              f"Freq={p['Runout_Z_Freq']:5.2f}x")
        print(f"  Wobble  A:  Amp={p['Wobble_A_Amp']*1000:6.4f} mrad  "
              f"B: Amp={p['Wobble_B_Amp']*1000:6.4f} mrad")

        print("\n【HTM 辨識擬合效果 (RMS)】")
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
        'X_OC':        0.010,   # mm  10 um
        'Y_OC':        0.010,
        'A_OC':        0.0001,  # rad 0.1 mrad
        'B_OA':        0.0001,
        'Runout_1x':   5.0,     # um
        'Runout_Z_2x': 3.0,
        'Residual_AI': 2.0,     # um  物理補償後殘差門檻 → 觸發AI層
    }

    INSTRUMENTS = {
        'LRT': {
            'name': 'Laser R-Test (LRT)',
            'measures': ['C軸徑向跳動', 'A/C同動誤差', 'PIGE全項辨識'],
            'accuracy': '< 1 um / 0.01 mrad',
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
            'accuracy': '< 0.005 mrad',
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
        for key, label in [('X_OC', 'C軸偏心X'), ('Y_OC', 'C軸偏心Y')]:
            if abs(p[key]) > self.THRESHOLDS[key]:
                findings.append({
                    'level': '🔴 嚴重',
                    'desc': f'{label} = {p[key]*1000:+.1f} um（門檻 ±{self.THRESHOLDS[key]*1000:.0f} um）',
                    'impact': '工件圓度誤差、加工半徑偏移',
                    'action': '→ 控制器輸入 X_OC/Y_OC 偏心補償，或機械調整夾頭',
                    'inst': 'LRT',
                })
                instruments.add('LRT')

        # ── C/A 垂直度
        if abs(p['A_OC']) > self.THRESHOLDS['A_OC']:
            findings.append({
                'level': '🔴 嚴重',
                'desc': f'C/A 垂直度誤差 A_OC = {p["A_OC"]*1000:+.4f} mrad',
                'impact': 'Z 向週期性誤差，影響輪廓精度與面粗度',
                'action': '→ LRT 靜態量測確認，控制器輸入 A_OC 補償值',
                'inst': 'LRT',
            })
            instruments.add('LRT')
            instruments.add('Autocollimator')

        # ── A 軸歪斜
        if abs(p['B_OA']) > self.THRESHOLDS['B_OA']:
            findings.append({
                'level': '🟡 警告',
                'desc': f'A 軸歪斜 B_OA = {p["B_OA"]*1000:+.4f} mrad',
                'impact': 'A 軸旋轉面不垂直，X 方向出現位移誤差',
                'action': '→ 自準直儀靜態量測 A 軸安裝垂直度，機械調整或補償',
                'inst': 'Autocollimator',
            })
            instruments.add('Autocollimator')

        # ── 徑向跳動
        avg_runout = (p['Runout_X_Amp'] + p['Runout_Y_Amp']) / 2 * 1000
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
        if p['Runout_Z_Amp'] * 1000 > self.THRESHOLDS['Runout_Z_2x']:
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
                print(f"\n  ✅ {d['name']}")
                print(f"     量測：{', '.join(d['measures'])}")
                print(f"     精度：{d['accuracy']}   預計耗時：{d['time']}")

        if needs_ai:
            print("\n" + "─"*62)
            print("【AI 補償層建議】")
            print("  輸入特徵：(A角度, C角度, A速度方向, C速度方向, |速度|)")
            print("  輸出：    (DX_res, DY_res, DZ_res)")
            print("  建議模型：MLP (tanh) 或 Gaussian Process Regression")
            print("  訓練數據：至少 5 組不同條件的 BK4 量測數據")

        print("\n" + "="*62)
        print("  預估調機時間：傳統 5~7 天  →  本系統 ≤ 1 天")
        print("="*62)