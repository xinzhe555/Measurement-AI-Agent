"""
nonlinear_residuals.py
非線性殘差物理模型 — 第一步

【這個檔案的目的】
    HTM 物理層補償之後，剩下的殘差不是隨機雜訊，而是有物理來源的。
    這個檔案把三種主要的非線性誤差來源「分開建模」，
    讓 dynamic_ai_learner.py 的三個子模型（LSTM / GRU / MLP）
    各自有一個清楚的學習目標，不會互相混淆。

【為什麼要分開，不能混在一起？】
    原本的 inject_nonlinear_residuals() 把三種誤差加在同一個陣列，
    訓練時 LSTM 看到的目標是「反轉尖峰 + 伺服不匹配 + 雜訊」的混合，
    它沒辦法單獨學好其中一種。
    分開之後，我們可以：
    1. 獨立驗證每個子模型的學習效果
    2. 在論文中說明每種誤差的物理機制和對應的模型選擇理由
    3. 未來換成真實量測數據時，可以只替換對應的那一層

【三種誤差的物理來源】

    ① 反轉尖峰（Reversal Spike / Quadrant Glitch）
       來源：速度方向反轉瞬間，靜摩擦力 > 動摩擦力，
             伺服系統短暫「卡住」再「彈出」，
             在位置誤差上形成一個脈衝形狀的尖峰。
       特徵：只發生在速度過零的 1-3 個採樣點附近。
             幅值約 5-20 μm，與進給速度和潤滑狀態有關。
       對應模型：LSTM（需要記憶「速度即將過零」的前幾步資訊）

    ② 伺服不匹配（Servo Mismatch / Kv Mismatch）
       來源：A 軸和 C 軸的伺服控制器速度增益（Kv）不同，
             同動時兩軸的追蹤延遲不一樣，
             導致實際路徑和指令路徑之間有一個與速度成正比的偏移。
       特徵：緩慢變化，在整個運動過程中都存在。
             誤差大小 ∝ 速度，方向與運動方向有關。
             在 DBB 圓度測試中表現為軌跡傾斜橢圓。
       對應模型：GRU（比 LSTM 輕量，適合學習這種緩慢的動態關係）

    ③ 高頻 PDGEs（High-frequency Position-Dependent Geometric Errors）
       來源：軸承的高次諧波（2× 3× 旋轉頻率的跳動）、
             齒輪嚙合頻率、結構共振等。
       特徵：週期性，頻率固定，只與 C 軸角度有關，不隨速度變化。
             在 BK4 殘差的頻域分析中看得到明確的峰值。
       對應模型：MLP（靜態角度函數，不需要時序記憶）

依賴：numpy, scipy（scipy 只用在 LuGre 摩擦力積分，可選）
"""

import numpy as np
from typing import NamedTuple


# ══════════════════════════════════════════════════════════════
#  資料結構：把三種誤差的 ground truth 分開儲存
# ══════════════════════════════════════════════════════════════

class NonlinearComponents(NamedTuple):
    """
    三種非線性誤差的分解結果。
    使用 NamedTuple 讓呼叫端可以用 .spike / .servo / .hf_pdge 存取，
    不會搞混陣列順序。

    每個欄位都是 ndarray (N, 3)，對應 [DX, DY, DZ]，單位 mm。
    """
    spike:    np.ndarray   # 反轉尖峰
    servo:    np.ndarray   # 伺服不匹配
    hf_pdge:  np.ndarray   # 高頻 PDGEs
    noise:    np.ndarray   # 量測雜訊（AI 不應學這部分）
    total:    np.ndarray   # 以上四項的總和（給物理層補償後的殘差用）


# ══════════════════════════════════════════════════════════════
#  ① 反轉尖峰模型
# ══════════════════════════════════════════════════════════════

def model_reversal_spike(
    a_cmd:      np.ndarray,
    c_cmd:      np.ndarray,
    amplitude_um: float = 8.0,
    decay_steps:  int   = 3,
) -> np.ndarray:
    """
    模擬反轉尖峰（Reversal Spike）。

    【物理機制】
        LuGre 摩擦力模型預測，當速度方向反轉時：
        1. 靜摩擦力（stiction）先讓軸「卡住」約 1-2 個控制週期
        2. 接著動摩擦力讓軸「彈出」，在位置上留下一個脈衝
        簡化模型：在速度過零點放一個指數衰減的脈衝。

    【參數說明】
        amplitude_um : 尖峰幅值（μm）。
                       真實機台通常 5-20 μm，取決於進給速度和潤滑。
        decay_steps  : 尖峰衰減需要幾個採樣步。
                       控制週期 4ms 時，decay_steps=3 代表約 12ms 衰減。

    【回傳值】
        spike : ndarray (N, 3)  [DX, DY, DZ]，單位 mm
    """
    N     = len(a_cmd)
    spike = np.zeros((N, 3))

    # 計算各軸速度（用差分近似，單位 rad/sample）
    a_vel = np.gradient(a_cmd)
    c_vel = np.gradient(c_cmd)

    # 找速度符號改變的位置（= 方向反轉的位置）
    # np.diff(np.sign(...)) 在過零點會得到 ±2，其他地方是 0
    a_sign_flip = np.abs(np.diff(np.sign(a_vel), prepend=np.sign(a_vel[0]))) > 0
    c_sign_flip = np.abs(np.diff(np.sign(c_vel), prepend=np.sign(c_vel[0]))) > 0
    reversal_idx = np.where(a_sign_flip | c_sign_flip)[0]

    amp_mm = amplitude_um * 1e-3   # 轉換成 mm

    for idx in reversal_idx:
        # 在反轉點後的 decay_steps 步內放一個指數衰減的脈衝
        for d in range(decay_steps):
            t = idx + d
            if t >= N:
                break
            # 衰減函數：e^(-d/1.5)，第 0 步最大，之後快速衰減
            decay = np.exp(-d / 1.5)

            # 尖峰方向：沿著各軸的運動方向
            # 物理上是因為靜摩擦力抵抗運動，所以誤差方向與速度方向相反
            a_dir = -np.sign(a_vel[idx] + 1e-10)
            c_dir = -np.sign(c_vel[idx] + 1e-10)

            # A 軸反轉 → 主要影響 X 方向（BK4 路徑的 X 分量）
            spike[t, 0] += amp_mm * a_dir * decay
            # C 軸反轉 → 影響 X 和 Y 方向（取決於 C 軸當前角度）
            spike[t, 0] += amp_mm * 0.5 * c_dir * np.cos(c_cmd[t]) * decay
            spike[t, 1] += amp_mm * 0.5 * c_dir * np.sin(c_cmd[t]) * decay

    return spike


# ══════════════════════════════════════════════════════════════
#  ② 伺服不匹配模型
# ══════════════════════════════════════════════════════════════

def model_servo_mismatch(
    a_cmd:      np.ndarray,
    c_cmd:      np.ndarray,
    kv_ratio:   float = 0.05,
    lag_steps:  int   = 2,
) -> np.ndarray:
    """
    模擬伺服不匹配（Servo Mismatch / Kv Mismatch）。

    【物理機制】
        速度前饋控制器的速度增益 Kv（單位：1/s）決定了追蹤誤差的大小：
            追蹤誤差 ≈ 速度 / Kv

        當 A 軸和 C 軸的 Kv 不同時，同動段（A 和 C 同時運動）會有：
            A 軸誤差 = a_vel / Kv_A
            C 軸誤差 = c_vel / Kv_C
            輪廓誤差 = A 誤差向量 - C 誤差向量 ≠ 0

        在 DBB 圓度測試中，這種不匹配會讓圓形軌跡變成橢圓，
        橢圓的主軸方向取決於 Kv 差異的符號。

    【參數說明】
        kv_ratio  : Kv 不匹配比例（無因次）。
                    0.05 代表 A 軸 Kv 比 C 軸 Kv 高 5%。
                    真實機台通常 2-10%。
        lag_steps : 伺服延遲的採樣步數（模擬延遲時間）。
                    控制週期 4ms、lag_steps=2 代表 8ms 延遲。

    【回傳值】
        servo : ndarray (N, 3)  [DX, DY, DZ]，單位 mm
    """
    N     = len(a_cmd)
    servo = np.zeros((N, 3))

    a_vel = np.gradient(a_cmd)
    c_vel = np.gradient(c_cmd)

    # 延遲版的速度（模擬伺服系統的相位延遲）
    # np.roll 把序列往右移 lag_steps 步，前面補邊界值
    a_vel_lag = np.roll(a_vel, lag_steps)
    a_vel_lag[:lag_steps] = a_vel_lag[lag_steps]   # 用第一個有效值填充
    c_vel_lag = np.roll(c_vel, lag_steps)
    c_vel_lag[:lag_steps] = c_vel_lag[lag_steps]

    # 不匹配誤差 = 實際速度 - 延遲速度（代表追蹤誤差的差異）
    # 乘以 kv_ratio 代表 A 軸的 Kv 比 C 軸快了 kv_ratio 這麼多
    a_mismatch = kv_ratio * (a_vel - a_vel_lag)
    c_mismatch = kv_ratio * (c_vel - c_vel_lag)

    # 把不匹配誤差投影到 BK4 路徑的 XYZ 方向
    # A 軸不匹配主要影響 X 方向，C 軸不匹配影響 XY 平面
    # 投影係數來自 BK4 運動學的一階近似
    servo[:, 0] = a_mismatch * 0.8 + c_mismatch * np.cos(c_cmd) * 0.3
    servo[:, 1] = c_mismatch * np.sin(c_cmd) * 0.3
    servo[:, 2] = a_mismatch * np.sin(a_cmd) * 0.2   # Z 向影響較小

    # 幅值校正：讓 servo 的 RMS 落在合理範圍（約 1-3 μm）
    # 這裡用一個簡單的縮放因子，真實標定時從 DBB 量測數據估算
    scale = 0.003 / (np.sqrt(np.mean(servo**2)) + 1e-9)
    servo *= min(scale, 10.0)   # 最多放大 10 倍，避免異常值

    return servo


# ══════════════════════════════════════════════════════════════
#  ③ 高頻 PDGEs 模型
# ══════════════════════════════════════════════════════════════

def model_hf_pdge(
    c_cmd:          np.ndarray,
    harmonics:      list[dict] | None = None,
) -> np.ndarray:
    """
    模擬高頻 PDGEs（軸承高次諧波 + 齒輪嚙合頻率）。

    【物理機制】
        C 軸軸承的滾子數（通常 8-16 個）決定了諧波頻率：
            滾子頻率 = 旋轉頻率 × 滾子數 / 2
        齒輪箱的齒數決定了嚙合頻率。

        這些誤差的特點是「角度相關」（Position-Dependent），
        也就是說，每轉到同一個角度，誤差值都一樣，
        和速度、加速度無關，純粹是幾何問題。

        注意：低頻 PDGEs（1× 2× 頻率的跳動）已經由 PhysicalLayerAnalyzer 補償。
        這裡只模擬 3× 以上的高頻成分。

    【參數說明】
        harmonics : 諧波列表，每個元素是一個 dict：
            {
                'freq': 頻率倍數（相對於 C 軸旋轉頻率）,
                'amp_um': 幅值（μm）,
                'phase_deg': 初相位（度）,
                'axis': 影響哪個軸（'x', 'y', 'z' 或 'xy'）
            }
            None 時使用預設的典型軸承諧波。

    【回傳值】
        hf_pdge : ndarray (N, 3)  [DX, DY, DZ]，單位 mm
    """
    N = len(c_cmd)

    # 預設諧波：模擬一個典型的 C 軸轉台
    # 頻率 3×：軸承滾子的前幾個諧波
    # 頻率 5×：另一組諧波
    # 頻率 7×：高次項，幅值通常更小
    if harmonics is None:
        harmonics = [
            # 3× 諧波：軸承外圈波紋的典型頻率
            {'freq': 3, 'amp_um': 1.5,  'phase_deg': 20,  'axis': 'xy'},
            # 5× 諧波：滾子通過頻率的二次諧波
            {'freq': 5, 'amp_um': 0.8,  'phase_deg': -45, 'axis': 'xy'},
            # 4× 諧波：齒輪嚙合的典型頻率（齒數 = 4 的倍數時）
            {'freq': 4, 'amp_um': 1.0,  'phase_deg': 10,  'axis': 'z'},
            # 6× 諧波：端面跳動的高次項
            {'freq': 6, 'amp_um': 0.5,  'phase_deg': 90,  'axis': 'z'},
            # 7× 諧波：高次，幅值很小
            {'freq': 7, 'amp_um': 0.3,  'phase_deg': 135, 'axis': 'xy'},
        ]

    hf_pdge = np.zeros((N, 3))

    for h in harmonics:
        freq  = h['freq']
        amp   = h['amp_um'] * 1e-3   # μm → mm
        phase = np.deg2rad(h['phase_deg'])
        axis  = h.get('axis', 'xy')

        # 諧波的角度參數是 C 軸指令角度的倍頻
        theta = freq * c_cmd + phase

        if axis in ('x', 'xy'):
            hf_pdge[:, 0] += amp * np.cos(theta)
        if axis in ('y', 'xy'):
            # X 和 Y 方向的相位差 90°，形成橢圓形的高頻跳動
            hf_pdge[:, 1] += amp * np.sin(theta)
        if axis in ('z',):
            hf_pdge[:, 2] += amp * np.cos(theta)

    return hf_pdge


# ══════════════════════════════════════════════════════════════
#  主函式：組合三種誤差，取代原本的 inject_nonlinear_residuals
# ══════════════════════════════════════════════════════════════

def decompose_nonlinear_residuals(
    a_cmd:          np.ndarray,
    c_cmd:          np.ndarray,
    spike_amp_um:   float = 8.0,
    kv_ratio:       float = 0.05,
    noise_std_um:   float = 0.8,
    seed:           int   = 42,
) -> NonlinearComponents:
    """
    生成三種非線性誤差的分解版本。

    【這個函式和原本的 inject_nonlinear_residuals 有什麼不同？】
        原本的版本直接回傳 total，三種誤差混在一起，
        training 時 LSTM / GRU / MLP 都去擬合同一個目標。

        這個版本把每種誤差分開存放在 NonlinearComponents 裡，
        讓 dynamic_ai_learner.py 可以：
        - 用 .spike 訓練 LSTM
        - 用 .servo 訓練 GRU
        - 用 .hf_pdge 訓練 MLP
        最後三個模型的預測加總，才是完整的非線性補償量。

    【參數說明】
        a_cmd, c_cmd  : A/C 軸指令序列（rad）
        spike_amp_um  : 反轉尖峰幅值（μm），典型值 5-20
        kv_ratio      : Kv 不匹配比例，典型值 0.02-0.10
        noise_std_um  : 量測雜訊標準差（μm），典型值 0.5-2
        seed          : 隨機種子（讓雜訊可重現）

    【回傳值】
        NonlinearComponents，包含 .spike .servo .hf_pdge .noise .total
    """
    rng = np.random.default_rng(seed)
    N   = len(a_cmd)

    # 各子項
    spike   = model_reversal_spike(a_cmd, c_cmd, amplitude_um=spike_amp_um)
    servo   = model_servo_mismatch(a_cmd, c_cmd, kv_ratio=kv_ratio)
    hf_pdge = model_hf_pdge(c_cmd)
    noise   = rng.normal(0, noise_std_um * 1e-3, (N, 3))

    # 總和（給 PhysicalLayerAnalyzer 的殘差用）
    total = spike + servo + hf_pdge + noise

    return NonlinearComponents(
        spike=spike,
        servo=servo,
        hf_pdge=hf_pdge,
        noise=noise,
        total=total,
    )


def inject_nonlinear_residuals(a_cmd, c_cmd, seed=42) -> np.ndarray:
    """
    向下相容的包裝函式。

    原本 ai_residual_learner.py 和 prec_agent.py 呼叫的是這個名字，
    保留介面讓舊程式碼不需要修改，內部改用 decompose_nonlinear_residuals。

    如果你只需要總和（不需要分解），繼續用這個函式就好。
    如果你需要分解結果（給 dynamic_ai_learner.py 用），
    改呼叫 decompose_nonlinear_residuals()。
    """
    components = decompose_nonlinear_residuals(a_cmd, c_cmd, seed=seed)
    return components.total


# ══════════════════════════════════════════════════════════════
#  統計工具：分析三種誤差的頻率特徵
# ══════════════════════════════════════════════════════════════

def analyze_residual_components(components: NonlinearComponents) -> dict:
    """
    計算各誤差分量的 RMS 和頻率特徵，用於驗證模型是否合理。

    主要用途：
    - 確認三種誤差的幅值比例是否符合真實機台的典型值
    - 論文中的「模擬誤差參數設定」表格可以從這裡的輸出生成
    """
    def rms_um(arr):
        return np.sqrt(np.mean(arr**2, axis=0)) * 1000

    return {
        'spike_rms_um':   rms_um(components.spike).round(3).tolist(),
        'servo_rms_um':   rms_um(components.servo).round(3).tolist(),
        'hf_pdge_rms_um': rms_um(components.hf_pdge).round(3).tolist(),
        'noise_rms_um':   rms_um(components.noise).round(3).tolist(),
        'total_rms_um':   rms_um(components.total).round(3).tolist(),
        'spike_pct':  (rms_um(components.spike)   / (rms_um(components.total) + 1e-9) * 100).round(1).tolist(),
        'servo_pct':  (rms_um(components.servo)   / (rms_um(components.total) + 1e-9) * 100).round(1).tolist(),
        'hfpdge_pct': (rms_um(components.hf_pdge) / (rms_um(components.total) + 1e-9) * 100).round(1).tolist(),
    }


# ══════════════════════════════════════════════════════════════
#  獨立驗證腳本：python nonlinear_residuals.py
# ══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    print("=" * 60)
    print("  非線性殘差物理模型驗證")
    print("=" * 60)

    # 生成和 BK4 一樣的指令序列
    t     = np.linspace(0, 4 * np.pi, 360)
    a_cmd = np.deg2rad(30 * np.sin(t))
    c_cmd = np.deg2rad(90 * np.sin(2 * t))

    # 生成三種誤差的分解
    comp  = decompose_nonlinear_residuals(a_cmd, c_cmd)
    stats = analyze_residual_components(comp)

    print("\n各誤差分量的 RMS（μm）：")
    print(f"  {'誤差類型':12} | {'DX':>8} | {'DY':>8} | {'DZ':>8} | {'佔比 DX':>8}")
    for name, key_rms, key_pct in [
        ('反轉尖峰',   'spike_rms_um',   'spike_pct'),
        ('伺服不匹配', 'servo_rms_um',   'servo_pct'),
        ('高頻 PDGE',  'hf_pdge_rms_um', 'hfpdge_pct'),
        ('量測雜訊',   'noise_rms_um',   None),
    ]:
        r = stats[key_rms]
        p = stats[key_pct][0] if key_pct else '-'
        print(f"  {name:12} | {r[0]:>8.3f} | {r[1]:>8.3f} | {r[2]:>8.3f} | {str(p):>7}%")

    print(f"\n  {'總殘差':12} | "
          f"{stats['total_rms_um'][0]:>8.3f} | "
          f"{stats['total_rms_um'][1]:>8.3f} | "
          f"{stats['total_rms_um'][2]:>8.3f}")

    # 驗證反轉尖峰只發生在速度過零點附近
    a_vel = np.gradient(a_cmd)
    spike_nonzero = np.where(np.abs(comp.spike[:, 0]) > 1e-6)[0]
    reversal_pts  = np.where(np.abs(np.diff(np.sign(a_vel),
                             prepend=np.sign(a_vel[0]))) > 0)[0]
    print(f"\n反轉尖峰驗證：")
    print(f"  A 軸速度過零點數量：{len(reversal_pts)}")
    print(f"  尖峰非零點數量：{len(spike_nonzero)}")
    print(f"  每個反轉點約 {len(spike_nonzero)/max(len(reversal_pts),1):.1f} 個非零步（應接近 decay_steps=3）")

    # 繪圖
    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
    labels = ['反轉尖峰 (LSTM 學習目標)',
              '伺服不匹配 (GRU 學習目標)',
              '高頻 PDGEs (MLP 學習目標)',
              '總殘差（三項之和 + 雜訊）']
    data   = [comp.spike, comp.servo, comp.hf_pdge, comp.total]
    colors = ['#e74c3c', '#3498db', '#2ecc71', '#95a5a6']

    for ax, label, d, c in zip(axes, labels, data, colors):
        ax.plot(d[:, 0] * 1000, color=c, lw=1.2, label='DX')
        ax.plot(d[:, 1] * 1000, color=c, lw=0.8, alpha=0.6, label='DY')
        ax.set_ylabel('μm', fontsize=9)
        ax.set_title(label, fontsize=10)
        ax.legend(fontsize=8, loc='upper right')
        ax.grid(True, alpha=0.3)
        ax.axhline(0, color='black', lw=0.5)

    axes[-1].set_xlabel('採樣點')
    plt.tight_layout()
    plt.savefig('/tmp/nonlinear_residuals_validation.png', dpi=120)
    print(f"\n驗證圖已存至：/tmp/nonlinear_residuals_validation.png")
    print("\n✅ 驗證完成")
