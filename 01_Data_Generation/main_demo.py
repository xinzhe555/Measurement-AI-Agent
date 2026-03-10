"""
main_demo.py
BK4 五軸誤差智能診斷系統 — 完整流程入口

執行方式：
    python main_demo.py

需要在同一目錄下：
    pige_full_generator.py
    pdge_generator.py
    generator.py
    physical_analyzer.py
    ai_residual_learner.py

依賴套件（pip install）：
    numpy matplotlib scipy scikit-learn
"""
import numpy as np
import matplotlib
matplotlib.use('Agg')           # 無顯示器環境改為 'TkAgg' 或 'Qt5Agg'
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.font_manager as fm
import warnings
warnings.filterwarnings('ignore')

# ──────────────────────────────────────────────────────────────
# 中文字型設定（優先順序：系統內找第一個可用的 CJK 字型）
# ──────────────────────────────────────────────────────────────
def _setup_chinese_font():
    """自動偵測並設定中文字型，跨平台相容（Linux / macOS / Windows）"""
    candidates = [
        # Linux (Noto / WenQuanYi)
        'Noto Sans CJK JP', 'Noto Sans CJK TC', 'Noto Sans CJK SC',
        'WenQuanYi Zen Hei', 'WenQuanYi Micro Hei',
        # macOS
        'PingFang TC', 'PingFang SC', 'Heiti TC', 'Heiti SC',
        'STHeiti', 'Arial Unicode MS',
        # Windows
        'Microsoft JhengHei', 'Microsoft YaHei', 'SimHei', 'NSimSun',
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in available:
            matplotlib.rcParams['font.family'] = name
            matplotlib.rcParams['axes.unicode_minus'] = False
            return name
    # 找不到時 fallback：直接用字型檔案路徑
    ttc_paths = [
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
    ]
    import os
    for path in ttc_paths:
        if os.path.exists(path):
            prop = fm.FontProperties(fname=path)
            matplotlib.rcParams['font.family'] = prop.get_name()
            matplotlib.rcParams['axes.unicode_minus'] = False
            return path
    return None  # 找不到就讓 matplotlib 自己處理（可能仍有亂碼）

_setup_chinese_font()

from generator          import Integrated_BK4_Simulator
from pige_full_generator import CONFIG
from physical_analyzer  import PhysicalLayerAnalyzer, AgentDiagnosticReport
from ai_residual_learner import AIResidualLearner, inject_nonlinear_residuals


# ══════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════

def run_demo(ball_radius=200.0, save_fig=True, fig_path='bk4_demo_report.png'):

    banner("BK4 五軸誤差智能診斷系統  —  完整 Demo", char="★")

    # ─────────────────────────────────────────
    # Step 1  生成量測數據
    # ─────────────────────────────────────────
    section("Step 1  生成 BK4 量測數據（PIGE + PDGE）")

    sim = Integrated_BK4_Simulator(CONFIG)
    raw_data, a_cmd, c_cmd = sim.generate(ball_radius=ball_radius)

    true_err = CONFIG['errors']
    print(f"  數據點數：{len(raw_data)} 點  |  球半徑：{ball_radius} mm")
    print(f"  注入 PIGE — X_OC={true_err['X_OC']*1000:+.0f}um  "
          f"Y_OC={true_err['Y_OC']*1000:+.0f}um  "
          f"A_OC={true_err['A_OC']*1000:+.1f}mrad  "
          f"B_OA={true_err['B_OA']*1000:+.1f}mrad")
    print(f"  注入 PDGE — Runout_X=10um  Runout_Y=10um  "
          f"Runout_Z=5um(@2x)  Wobble=0.1mrad")

    # 額外注入非線性殘差（模擬真實機台的摩擦力、伺服不匹配）
    nonlinear = inject_nonlinear_residuals(a_cmd, c_cmd)
    measured_data = raw_data + nonlinear

    # ─────────────────────────────────────────
    # Step 2  物理層辨識（HTM 非線性最小二乘）
    # ─────────────────────────────────────────
    section("Step 2  物理層辨識（HTM 非線性最小二乘）")

    analyzer = PhysicalLayerAnalyzer()
    identified_params, phys_residual = analyzer.identify(
        measured_data, a_cmd, c_cmd, ball_radius
    )

    # ─────────────────────────────────────────
    # Step 3  AI 殘差學習層
    # ─────────────────────────────────────────
    section("Step 3  AI 殘差學習層（MLP 訓練）")

    ai_learner = AIResidualLearner()
    ai_pred, final_residual = ai_learner.train(a_cmd, c_cmd, phys_residual)

    # ─────────────────────────────────────────
    # Step 4  Agent 診斷報告
    # ─────────────────────────────────────────
    section("Step 4  Agent 智能診斷報告")

    rms_after_phys = np.mean(
        np.sqrt(np.mean(phys_residual**2, axis=0)) * 1000
    )
    agent = AgentDiagnosticReport()
    report = agent.generate(identified_params, rms_after_phys)

    # ─────────────────────────────────────────
    # Step 5  可視化
    # ─────────────────────────────────────────
    section("Step 5  生成可視化報告")

    visualize(measured_data, phys_residual, final_residual,
              a_cmd, c_cmd, identified_params, true_err, report,
              save_fig, fig_path)

    # ─────────────────────────────────────────
    # 最終摘要
    # ─────────────────────────────────────────
    banner("摘要", char="─")
    rms_raw  = np.sqrt(np.mean(measured_data**2,    axis=0)) * 1000
    rms_phy  = np.sqrt(np.mean(phys_residual**2,    axis=0)) * 1000
    rms_fin  = np.sqrt(np.mean(final_residual**2,   axis=0)) * 1000
    print(f"  {'軸':>4} | {'原始 RMS':>10} | {'物理補償後':>10} | {'AI補償後':>10}")
    for i, ax in enumerate(['DX', 'DY', 'DZ']):
        print(f"  {ax:>4} | {rms_raw[i]:>8.2f}um | {rms_phy[i]:>8.2f}um | {rms_fin[i]:>8.2f}um")
    print(f"\n  圖表已儲存：{fig_path}")
    print("  ✅ Demo 完成\n")

    return identified_params, report


# ══════════════════════════════════════════════════════════════
# 可視化
# ══════════════════════════════════════════════════════════════

def visualize(raw, phys_res, final_res, a_cmd, c_cmd,
              id_params, true_err, report, save, path):

    DARK_BG  = '#0d1117'
    PANEL_BG = '#161b27'
    GRID_C   = '#222233'
    C_RAW    = '#ff4d4d'
    C_PHYS   = '#ffd700'
    C_AI     = '#00e676'
    C_TEXT   = '#e0e0e0'
    C_DIM    = '#888888'

    fig = plt.figure(figsize=(22, 17), facecolor=DARK_BG)
    gs  = gridspec.GridSpec(4, 3, figure=fig,
                             hspace=0.50, wspace=0.32,
                             top=0.93, bottom=0.05,
                             left=0.07, right=0.97)

    axis_names = ['DX', 'DY', 'DZ']
    datasets   = [
        (raw     * 1000, C_RAW,  '① 原始量測殘差'),
        (phys_res* 1000, C_PHYS, '② 物理層補償後'),
        (final_res*1000, C_AI,   '③ AI層補償後'),
    ]
    x = np.arange(len(raw))

    # ── Rows 0–2：三層誤差時序
    for row, (data, color, row_label) in enumerate(datasets):
        for col, ax_name in enumerate(axis_names):
            ax = fig.add_subplot(gs[row, col])
            _style(ax, PANEL_BG, GRID_C, C_DIM)
            ax.plot(x, data[:, col], color=color, lw=1.2, alpha=0.9)
            ax.axhline(0, color='white', lw=0.5, alpha=0.25)
            rms = np.sqrt(np.mean(data[:, col]**2))
            ax.set_title(f'{row_label} — {ax_name}\nRMS = {rms:.2f} μm',
                         color=C_TEXT, fontsize=9.5, pad=5)
            ax.set_ylabel('誤差 (μm)', color=C_DIM, fontsize=8)
            if row == 2:
                ax.set_xlabel('樣本點', color=C_DIM, fontsize=8)

    # ── Row 3, Col 0：RMS 柱狀圖
    ax_bar = fig.add_subplot(gs[3, 0])
    _style(ax_bar, PANEL_BG, GRID_C, C_DIM)

    rms_r = np.sqrt(np.mean(raw      * 1000**2, axis=0)) if False else \
            np.array([np.sqrt(np.mean((raw     *1000)[:,i]**2)) for i in range(3)])
    rms_p = np.array([np.sqrt(np.mean((phys_res*1000)[:,i]**2)) for i in range(3)])
    rms_f = np.array([np.sqrt(np.mean((final_res*1000)[:,i]**2)) for i in range(3)])
    # 重新算（避免上面的算法複雜）
    rms_r = np.sqrt(np.mean((raw     *1000)**2, axis=0))
    rms_p = np.sqrt(np.mean((phys_res*1000)**2, axis=0))
    rms_f = np.sqrt(np.mean((final_res*1000)**2, axis=0))

    xb, w = np.arange(3), 0.25
    ax_bar.bar(xb - w, rms_r, width=w, color=C_RAW,  alpha=0.85, label='原始')
    ax_bar.bar(xb,     rms_p, width=w, color=C_PHYS, alpha=0.85, label='物理補償')
    ax_bar.bar(xb + w, rms_f, width=w, color=C_AI,   alpha=0.85, label='AI補償')
    ax_bar.set_xticks(xb)
    ax_bar.set_xticklabels(axis_names, color=C_TEXT)
    ax_bar.set_ylabel('RMS 誤差 (μm)', color=C_DIM, fontsize=8)
    ax_bar.set_title('三層補償 RMS 比較', color=C_TEXT, fontsize=10)
    ax_bar.legend(fontsize=7.5, facecolor='#1a1a2e',
                  edgecolor='none', labelcolor=C_TEXT)

    # ── Row 3, Col 1：PIGE 辨識 vs 注入值
    ax_pige = fig.add_subplot(gs[3, 1])
    _style(ax_pige, PANEL_BG, GRID_C, C_DIM)

    keys = ['X_OC', 'Y_OC', 'A_OC', 'B_OA']
    scale = [1000, 1000, 1000, 1000]   # mm→um / rad→mrad×1000
    xlbls = ['X_OC\n(μm)', 'Y_OC\n(μm)', 'A_OC\n(×10⁻¹mrad)', 'B_OA\n(×10⁻¹mrad)']

    true_vals = [true_err.get(k, 0) * s for k, s in zip(keys, scale)]
    id_vals   = []
    for k, s in zip(keys, scale):
        # B_OA 在 identified_params 中的 key
        kk = k if k in id_params else k.replace('B_OA', 'B_OA')
        id_vals.append(id_params.get(kk, 0) * s)

    xp = np.arange(len(keys))
    ax_pige.bar(xp - 0.18, true_vals, width=0.32, color='#4fc3f7',
                alpha=0.85, label='注入值（真值）')
    ax_pige.bar(xp + 0.18, id_vals,   width=0.32, color='#f48fb1',
                alpha=0.85, label='辨識值')
    ax_pige.set_xticks(xp)
    ax_pige.set_xticklabels(xlbls, color=C_TEXT, fontsize=8)
    ax_pige.set_title('PIGE 辨識精度驗證', color=C_TEXT, fontsize=10)
    ax_pige.legend(fontsize=7.5, facecolor='#1a1a2e',
                   edgecolor='none', labelcolor=C_TEXT)
    ax_pige.axhline(0, color='white', lw=0.5, alpha=0.25)

    # ── Row 3, Col 2：Agent 建議清單
    ax_agent = fig.add_subplot(gs[3, 2])
    ax_agent.set_facecolor(PANEL_BG)
    ax_agent.axis('off')
    ax_agent.set_title('Agent 建議量測清單', color=C_TEXT,
                        fontsize=10, pad=10)

    from physical_analyzer import AgentDiagnosticReport as _ADR
    inst_db = _ADR.INSTRUMENTS
    y_pos = 0.93
    for key in report['instruments']:
        if key not in inst_db:
            continue
        d = inst_db[key]
        ax_agent.text(0.02, y_pos, f"✅ {d['name']}",
                      transform=ax_agent.transAxes,
                      color=C_AI, fontsize=8.5, fontweight='bold')
        y_pos -= 0.11
        ax_agent.text(0.05, y_pos,
                      f"精度：{d['accuracy']}  |  {d['time']}",
                      transform=ax_agent.transAxes,
                      color=C_DIM, fontsize=7.5)
        y_pos -= 0.15
        if y_pos < 0.02:
            break

    if report['needs_ai']:
        ax_agent.text(0.02, max(y_pos, 0.05),
                      "🔵 已啟動 AI 殘差學習層",
                      transform=ax_agent.transAxes,
                      color='#64b5f6', fontsize=8.5, fontweight='bold')

    # ── 總標題
    fig.suptitle(
        'BK4 五軸誤差智能診斷系統｜物理層 HTM 辨識 + AI 殘差學習 雙層補償架構',
        color=C_TEXT, fontsize=13, fontweight='bold', y=0.97
    )

    # ── 行標籤（左側）
    for idx, (label, color) in enumerate(zip(
        ['① 原始', '② 物理補償後', '③ AI補償後'],
        [C_RAW, C_PHYS, C_AI]
    )):
        fig.text(0.005, 0.865 - idx * 0.228, label,
                 color=color, fontsize=8.5, fontweight='bold',
                 rotation=90, va='center')

    plt.savefig(path, dpi=150, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    print(f"  圖表已儲存：{path}")
    plt.close()


# ══════════════════════════════════════════════════════════════
# 輔助函式
# ══════════════════════════════════════════════════════════════

def _style(ax, bg, grid_c, tick_c):
    ax.set_facecolor(bg)
    ax.tick_params(colors=tick_c, labelsize=7.5)
    for sp in ax.spines.values():
        sp.set_edgecolor('#2a2a3e')
    ax.grid(True, color=grid_c, lw=0.5, alpha=0.7)

def banner(text, char='='):
    line = char * 62
    print(f"\n{line}\n  {text}\n{line}")

def section(text):
    print(f"\n{'─'*62}\n  {text}\n{'─'*62}")


# ══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    run_demo(
        ball_radius=200.0,
        save_fig=True,
        fig_path='bk4_demo_report.png',
    )