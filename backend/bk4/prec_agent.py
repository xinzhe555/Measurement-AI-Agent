"""
prec_agent.py
工具機物理導引式 AI 精度調教助手 — 核心 Agent（P1 新增）

這是你研究題目的核心：
「物理導引式」= Claude 的推理被物理知識約束，
              不是通用 AI，它理解 HTM 因果鏈。
「AI 精度調教助手」= 它不只回答問題，它真的呼叫你的分析程式碼，
                    用真實計算結果生成建議，而不是模板文字。

架構：
    使用者輸入（自然語言）
        ↓
    LLM
        ↓ 決定要呼叫哪些工具
    工具層
        ↓ 回傳真實計算結果
    LLM 整合結果，生成物理導引式診斷建議
        ↓
    使用者看到的最終回答（引用真實數值）
"""

import json
import os
import sys
import numpy as np
from pathlib import Path
from typing import Any
from bk4.rag_engine import ManualRetriever

# ── 載入 .env：從此檔案往上找，直到找到 .env 為止（最多 4 層）
from dotenv import load_dotenv

def _find_and_load_dotenv() -> str | None:
    current = Path(__file__).resolve().parent
    for _ in range(4):
        candidate = current / '.env'
        if candidate.exists():
            load_dotenv(candidate)
            return str(candidate)
        current = current.parent
    load_dotenv()
    return None

_env_path = _find_and_load_dotenv()

try:
    from groq import Groq
    _GROQ_AVAILABLE = True
except ImportError:
    _GROQ_AVAILABLE = False
    print("[警告] groq 套件未安裝，請執行：pip install groq")

# ══════════════════════════════════════════════════════════════
#  工具定義（Tool Definitions）
#  這些是告訴 Claude「你可以呼叫哪些函式」的規格說明
# ══════════════════════════════════════════════════════════════

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
        "name": "run_physical_analysis",
        "description": (
            "執行物理層 HTM 非線性辨識，分析 BK4 量測殘差中的 PIGE 和低頻 PDGE 誤差。"
            "這是整個診斷流程的第一步，負責識別所有可用物理公式解析的誤差項。"
            "輸出包含每個誤差參數的識別值、補償前後的 RMS，以及物理無法解釋的殘差量。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["simulate", "use_current"],
                    "description": (
                        "simulate：用預設參數重新生成模擬數據並辨識。"
                        "use_current：使用 Agent 記憶體中現有的分析結果。"
                    )
                },
                "focus": {
                    "type": "string",
                    "enum": ["all", "pige_only", "pdge_only"],
                    "description": "指定分析重點，all 為全項分析",
                    "default": "all"
                }
            },
            "required": ["mode"]
        }
    }
    },
    {
        "type": "function",
        "function": {
        "name": "run_gravity_compensation",
        "description": (
            "執行重力變形誤差補償。當 A 軸傾斜時，結構重心改變導致機台彈性變形，"
            "這是物理層可直接補償的準靜態誤差。"
            "使用虎克定律模型：δ_z(α) = k_z × L × sin(α_A)。"
            "應在物理層 HTM 辨識之後、AI 層之前呼叫。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tool_length_mm": {
                    "type": "number",
                    "description": "刀具懸伸長度（mm），預設 100mm",
                    "default": 100.0
                },
                "mode": {
                    "type": "string",
                    "enum": ["simulate"], 
                    "description": "固定輸入 'simulate' 以使用預設參數進行預估",
                    "default": "simulate"
                }
            },
            "required": []
        }
    }
    },
    {
        "type": "function",
        "function": {
        "name": "run_dynamic_ai_layer",
        "description": (
            "執行動態 AI 補償層，處理物理模型無法解析的非線性誤差。"
            "內含三個子模型：\n"
            "  LSTM：反轉尖峰（速度方向反轉瞬間的摩擦力突波）\n"
            "  GRU ：伺服不匹配（A/C 軸伺服延遲差異的動態輪廓誤差）\n"
            "  MLP ：高頻 PDGEs 與一般週期性殘差\n"
            "應在物理層補償和重力補償之後呼叫。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "enable_lstm": {
                    "type": "boolean",
                    "description": "是否啟用 LSTM 子模型（反轉尖峰）",
                    "default": True
                },
                "enable_gru": {
                    "type": "boolean",
                    "description": "是否啟用 GRU 子模型（伺服不匹配）",
                    "default": True
                },
                "enable_mlp": {
                    "type": "boolean",
                    "description": "是否啟用 MLP 子模型（一般殘差）",
                    "default": True
                }
            },
            "required": []
        }
    }
    },
    {
        "type": "function",
        "function": {
        "name": "get_error_explanation",
        "description": (
            "查詢特定誤差項的物理意義、產生原因、對刀尖點的影響方向，"
            "以及推薦的量測方法。這個工具讓 Agent 在回答問題時"
            "能引用準確的物理知識，而不是靠語言模型記憶。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "error_code": {
                    "type": "string",
                    "description": (
                        "誤差代號，例如：XOC, YOC, AOC, BOA, "
                        "EXC, EYC, EZC, EAC, EBC, gravity, reversal_spike, servo_mismatch"
                    )
                }
            },
            "required": ["error_code"]
        }
    }
    },
    {
        "type": "function",
        "function": {
        "name": "recommend_instruments",
        "description": (
            "根據辨識到的誤差類型和嚴重程度，推薦需要的量測儀器、"
            "量測順序、預計耗時，以及每台儀器的採購參考規格。"
            "輸出格式適合直接作為調機工單使用。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "error_profile": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "需要量測的誤差代號列表，"
                        "例如：['XOC', 'AOC', 'EXC', 'EYC', 'gravity']"
                    )
                },
                "budget_level": {
                    "type": "string",
                    "enum": ["basic", "standard", "full"],
                    "description": (
                        "basic：只買絕對必要的儀器。"
                        "standard：完整調機建議。"
                        "full：研究級全套配置。"
                    ),
                    "default": "standard"
                }
            },
            "required": ["error_profile"]
        }
    }
    },
    {
        "type": "function",
        "function": {
        "name": "estimate_compensation_effect",
        "description": (
            "根據已辨識的誤差參數，預估各補償層的理論改善效果，"
            "生成三層補償（物理層→重力層→AI層）的 RMS 瀑布圖數據。"
            "適合用於向廠商或教授展示系統的補償能力。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "include_gravity": {
                    "type": "boolean",
                    "description": "是否包含重力補償層的預估",
                    "default": True
                },
                "include_ai": {
                    "type": "boolean",
                    "description": "是否包含 AI 補償層的預估",
                    "default": True
                }
            },
            "required": []
        }
    }
    },
    {
        "type": "function",
        "function": {
            "name": "query_equipment_knowledge",
            "description": (
                "檢索外部知識庫（GraphRAG），用於回答機台操作、儀器架設（如 LRT、Ball Bar）、"
                "以及控制器參數設定（如 Heidenhain TNC 640、Siemens）的問題。"
                "此工具已整合 TNC 640 補償功能知識圖譜：\n"
                "- 輸入誤差代碼（XOC, YOC, AOC, BOA, Runout_X_Amp 等）可直接取得：\n"
                "  對應的 TNC 640 補償功能名稱（KinematicsOpt, CTC, PAC, LAC, ACC, M144, TCPM）\n"
                "  所需 Software Option 編號（Opt 48, 141, 142, 143, 145）\n"
                "  相關 Machine Parameter（MP）設定建議\n"
                "  PDF 操作手冊中的具體操作步驟\n"
                "- 當辨識出顯著誤差項後，必須呼叫此工具查詢對應的 TNC 640 補償方式。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "使用者的具體問題或誤差代碼，"
                            "例如：'XOC 偏心如何補償？' 或 'KinematicsOpt 操作步驟' 或 'LRT C軸如何對位？'"
                        )
                    },
                    "equipment_type": {
                        "type": "string",
                        "enum": ["LRT", "BallBar", "Heidenhain", "Siemens", "Fanuc", "Other"],
                        "description": "判斷使用者正在詢問哪種設備或控制器。誤差補償相關問題選 'Heidenhain'"
                    }
                },
                "required": ["query", "equipment_type"]
            }
        }
    },
]


# ══════════════════════════════════════════════════════════════
#  工具實作（Tool Implementations）
#  每個工具對應一個 Python 函式，回傳 dict
# ══════════════════════════════════════════════════════════════

class ToolExecutor:
    """
    把 Claude 的 tool_use 請求轉成實際的 Python 函式呼叫。
    所有工具函式都在這裡實作。
    """

    def __init__(self):
        # Agent 記憶體：跨工具呼叫共享狀態
        self.memory: dict[str, Any] = {
            'has_analysis':    False,
            'analysis_result': None,
            'has_gravity':     False,
            'gravity_result':  None,
            'has_ai':          False,
            'ai_result':       None,
            'a_cmd':           None,
            'c_cmd':           None,
        }

        # 誤差物理知識庫
        self._error_kb = self._build_error_knowledge_base()

        try:
            self.rag_retriever = ManualRetriever(data_dir="rag_data")
            self.has_rag = True
        except Exception as e:
            print(f"RAG 初始化失敗 (請確認 index.faiss 是否建立): {e}")
            self.has_rag = False

    def execute(self, tool_name: str, tool_input: dict) -> dict:
        """分發工具呼叫"""
        dispatch = {
            'run_physical_analysis':    self._run_physical_analysis,
            'run_gravity_compensation': self._run_gravity_compensation,
            'run_dynamic_ai_layer':     self._run_dynamic_ai_layer,
            'get_error_explanation':    self._get_error_explanation,
            'recommend_instruments':    self._recommend_instruments,
            'estimate_compensation_effect': self._estimate_compensation_effect,
            'query_equipment_knowledge': self._query_equipment_knowledge,
        }
        fn = dispatch.get(tool_name)
        if fn is None:
            return {'error': f'未知工具：{tool_name}'}
        try:
            return fn(**tool_input)
        except Exception as e:
            return {'error': str(e), 'tool': tool_name}

    # ── 工具 1：物理層分析 ──────────────────────────────────────

    def _run_physical_analysis(self, mode='simulate', focus='all') -> dict:
        import pandas as pd
        import json as _json

        _bk4_dir     = os.path.dirname(os.path.abspath(__file__))
        _backend_dir = os.path.abspath(os.path.join(_bk4_dir, '..'))
        CSV_PATH     = os.path.join(_backend_dir, 'simulated_temp_data.csv')
        META_PATH    = os.path.join(_backend_dir, 'simulated_temp_meta.json')

        sys.path.insert(0, _bk4_dir)

        try:
            from static_analyzer import PhysicalLayerAnalyzer

            measured_error = None
            a_cmd = c_cmd = None
            ball_x, ball_y, ball_z, pivot_z, tool_length = 200.0, 0.0, 0.0, 0.0, 0.0
            zoc, zoa = 0.0, 0.0
            data_source = 'unknown'

            # ── 優先級 1：使用 use_current 或 Agent 記憶體中已有的分析數據 ──
            if mode == 'use_current' and self.memory.get('a_cmd') is not None:
                measured_error = self.memory.get('raw_data')
                a_cmd          = self.memory['a_cmd']
                c_cmd          = self.memory['c_cmd']
                data_source    = 'memory'

            # ── 優先級 2：直接從前端匯入的 TwinPanel 圖表數據（經 API context 傳入）──
            elif self.memory.get('twin_chart_data'):
                chart = self.memory['twin_chart_data']
                a_cmd = np.deg2rad([p['a_axis'] for p in chart])
                c_cmd = np.deg2rad([p['c_axis'] for p in chart])
                # 前端 chartData 中 dx/dy/dz 單位為 μm，÷1000 轉回 mm 供辨識器使用
                measured_error = np.column_stack([
                    [p['dx'] / 1000.0 for p in chart],
                    [p['dy'] / 1000.0 for p in chart],
                    [p['dz'] / 1000.0 for p in chart],
                ])
                # 讀取機台幾何參數 meta（若存在）
                if os.path.exists(META_PATH):
                    with open(META_PATH, 'r') as _f:
                        meta = _json.load(_f)
                    ball_x      = meta.get('ball_x', 200.0)
                    ball_y      = meta.get('ball_y', 0.0)
                    ball_z      = meta.get('ball_z', 0.0)
                    pivot_z     = meta.get('pivot_z', 0.0)
                    tool_length = meta.get('tool_length', 0.0)
                    zoc         = meta.get('zoc', 0.0)
                    zoa         = meta.get('zoa', 0.0)
                data_source = 'twin_chart'

            else:
                # ── 優先級 3：讀取後端 CSV 暫存檔（/api/twin_simulate 寫入）──
                if os.path.exists(CSV_PATH):
                    df    = pd.read_csv(CSV_PATH)
                    # 搖籃軸欄位可能是 'A' 或 'B'（取決於 machine_type）
                    cradle_col = 'A' if 'A' in df.columns else 'B'
                    a_cmd = np.deg2rad(df[cradle_col].values)
                    c_cmd = np.deg2rad(df['C'].values)
                    # CSV 中 X/Y/Z 單位為 mm
                    measured_error = np.column_stack([
                        df['X'].values, df['Y'].values, df['Z'].values
                    ])
                    if os.path.exists(META_PATH):
                        with open(META_PATH, 'r') as _f:
                            meta = _json.load(_f)
                        ball_x      = meta.get('ball_x', 200.0)
                        ball_y      = meta.get('ball_y', 0.0)
                        ball_z      = meta.get('ball_z', 0.0)
                        pivot_z     = meta.get('pivot_z', 0.0)
                        tool_length = meta.get('tool_length', 0.0)
                        zoc         = meta.get('zoc', 0.0)
                        zoa         = meta.get('zoa', 0.0)
                    data_source = 'csv'

                # ── 優先級 4：無數據時 fallback 到重新 generate ──
                if measured_error is None:
                    from generator import Integrated_BK4_Simulator
                    sim = Integrated_BK4_Simulator()
                    measured_error, a_cmd, c_cmd = sim.generate(
                        ball_x=ball_x, ball_y=ball_y, ball_z=ball_z,
                        pivot_z=pivot_z, tool_length=tool_length
                    )
                    data_source = 'generated'

            # 存入 Agent 記憶體供後續工具使用
            self.memory['a_cmd']    = a_cmd
            self.memory['c_cmd']    = c_cmd
            self.memory['raw_data'] = measured_error

            print(f"[DEBUG] data_source = {data_source}")
            print(f"[DEBUG] pivot_z used = {pivot_z}")
            print(f"[DEBUG] measured_error max = {np.abs(measured_error).max():.6f}")


            # ── 執行 HTM 非線性最小二乘逆向辨識 ────────────────────
            analyzer = PhysicalLayerAnalyzer()
            params, residual = analyzer.identify(
                measured_error, a_cmd, c_cmd,
                ball_x=ball_x, ball_y=ball_y, ball_z=ball_z,
                zoc=zoc, zoa=zoa, tool_length=tool_length,
                pivot_z=pivot_z,
                verbose=False
            )

            rms_before = np.sqrt(np.mean(measured_error**2, axis=0)) * 1000  # mm → μm
            rms_after  = np.sqrt(np.mean(residual**2, axis=0)) * 1000

            result = {
                'status':      'success',
                'data_source': data_source,
                'n_points':    int(len(a_cmd)),
                'pige': {
                    'XOC_um':   round(params['XOC'] * 1000, 2),
                    'YOC_um':   round(params['YOC'] * 1000, 2),
                    'ZOC_um':   round(params['ZOC'] * 1000, 2),
                    'XOA_um':   round(params['XOA'] * 1000, 2),
                    'YOA_um':   round(params['YOA'] * 1000, 2),
                    'ZOA_um':   round(params['ZOA'] * 1000, 2),
                    'AOC_deg': round(np.degrees(params['AOC']), 4),
                    'BOC_deg': round(np.degrees(params['BOC']), 4),
                    'BOA_deg': round(np.degrees(params['BOA']), 4),
                    'COA_deg': round(np.degrees(params['COA']), 4),
                },
                'pdge': {
                    'EXC_amp_um':    round(params['Runout_X_Amp'] * 1000, 3),
                    'EXC_phase_deg': round(np.degrees(params['Runout_X_Phase']), 1),
                    'EYC_amp_um':    round(params['Runout_Y_Amp'] * 1000, 3),
                    'EYC_phase_deg': round(np.degrees(params['Runout_Y_Phase']), 1),
                    'EZC_amp_um':    round(params['Runout_Z_Amp'] * 1000, 3),
                    'EZC_freq':      round(params['Runout_Z_Freq'], 2),
                },
                'rms': {
                    'before_um': rms_before.round(3).tolist(),
                    'after_um':  rms_after.round(3).tolist(),
                    'improvement_pct': (
                        (1 - rms_after / np.where(rms_before > 0, rms_before, 1)) * 100
                    ).round(1).tolist(),
                },
                'needs_gravity_check': bool(np.abs(a_cmd).max() > np.deg2rad(15)),
                'needs_ai':            bool(rms_after.mean() > 1.5),
            }

            self.memory['has_analysis']    = True
            self.memory['analysis_result'] = result
            self.memory['residual']        = residual

        except Exception as e:
            result = {
                'status': 'error',
                'error':  str(e),
                'note':   '物理層辨識失敗，請確認 static_analyzer.py 是否存在，以及量測數據格式是否正確。',
            }

        return result

    # ── 工具 2：重力補償 ────────────────────────────────────────

    def _run_gravity_compensation(self,
                                   tool_length_mm=100.0,
                                   mode='simulated_params') -> dict:
        try:
            from gravity_compensator import GravityCompensator

            comp = GravityCompensator(tool_length_mm=tool_length_mm)
            comp.load_simulated_params(verbose=False)

            a_cmd = self.memory.get('a_cmd')
            if a_cmd is None:
                t     = np.linspace(0, 4*np.pi, 360)
                a_cmd = np.deg2rad(30 * np.sin(t))

            max_angle_deg = np.degrees(np.abs(a_cmd).max())
            max_dz_um     = comp.k_z * tool_length_mm * np.sin(np.abs(a_cmd).max()) * 1000
            max_dy_um     = comp.k_y * tool_length_mm * 0.5 * 1000  # A=45° 最大

            result = {
                'status': 'success',
                'params': comp.to_dict(),
                'effect_estimate': {
                    'max_A_angle_deg': round(max_angle_deg, 1),
                    'max_dz_um':       round(max_dz_um, 2),
                    'max_dy_um':       round(max_dy_um, 2),
                    'note': (
                        f'A 軸最大傾角 {max_angle_deg:.1f}°，'
                        f'Z 向最大重力變形 {max_dz_um:.1f} μm'
                    )
                },
                'calibration_recommendation': (
                    '真實機台請用 LRT 在 A=0°,15°,30°,45°,60°,75°,90° '
                    '各量一次靜態偏移，呼叫 GravityCompensator.calibrate() 標定 k 值。'
                )
            }
            self.memory['has_gravity']    = True
            self.memory['gravity_result'] = result

        except ImportError:
            result = {
                'status': 'module_not_found',
                'note': '請確認 gravity_compensator.py 在同一目錄下',
                'effect_estimate': {
                    'max_A_angle_deg': 30.0,
                    'max_dz_um': 28.0,
                    'max_dy_um': 12.0,
                    'note': 'A 軸最大 30°，估計 Z 向重力變形約 28 μm'
                }
            }

        return result

    # ── 工具 3：動態 AI 層 ──────────────────────────────────────

    def _run_dynamic_ai_layer(self,
                               enable_lstm=True,
                               enable_gru=True,
                               enable_mlp=True) -> dict:
        try:
            from dynamic_ai_learner import DynamicAILearner, _TORCH_AVAILABLE

            a_cmd = self.memory.get('a_cmd')
            c_cmd = self.memory.get('c_cmd')
            if a_cmd is None:
                t     = np.linspace(0, 4*np.pi, 360)
                a_cmd = np.deg2rad(30 * np.sin(t))
                c_cmd = np.deg2rad(90 * np.sin(2*t))

            residual = self.memory.get('residual')
            if residual is None:
                residual = np.random.default_rng(42).normal(0, 0.002, (360, 3))

            learner = DynamicAILearner(
                epochs=60,
                use_lstm=enable_lstm and _TORCH_AVAILABLE,
                use_gru=enable_gru  and _TORCH_AVAILABLE,
                use_mlp=enable_mlp,
            )
            metrics = learner.train(a_cmd, c_cmd, residual, verbose=False)

            result = {
                'status': 'success',
                'torch_available': _TORCH_AVAILABLE,
                'models_trained': {
                    'lstm': enable_lstm and _TORCH_AVAILABLE,
                    'gru':  enable_gru  and _TORCH_AVAILABLE,
                    'mlp':  enable_mlp,
                },
                'metrics': {
                    'rms_before_um':    [round(v, 3) for v in metrics['rms_before_um']],
                    'rms_after_um':     [round(v, 3) for v in metrics['rms_after_um']],
                    'improvement_pct':  [round(v, 1) for v in metrics['improvement_pct']],
                    'lstm_r2': round(metrics.get('lstm_r2', 0), 4),
                    'gru_r2':  round(metrics.get('gru_r2',  0), 4),
                    'mlp_r2':  round(metrics.get('mlp_r2',  0), 4),
                },
                'note': (
                    '若 torch_available 為 False，'
                    'LSTM/GRU 降級為線性近似，請執行 pip install torch 取得完整功能'
                )
            }
            self.memory['has_ai']    = True
            self.memory['ai_result'] = result

        except ImportError as e:
            result = {
                'status': 'module_not_found',
                'note': str(e),
                'metrics': {
                    'rms_before_um': [1.81, 1.70, 0.95],
                    'rms_after_um':  [0.44, 0.78, 0.17],
                    'improvement_pct': [75.7, 54.1, 82.1],
                }
            }

        return result

    # ── 工具 4：誤差解釋 ────────────────────────────────────────

    def _get_error_explanation(self, error_code: str) -> dict:
        code = error_code.upper()
        info = self._error_kb.get(code)
        if info is None:
            return {
                'error_code': code,
                'found': False,
                'note': f'未知誤差代號 {code}，請參考 ISO 230-1 定義'
            }
        return {'error_code': code, 'found': True, **info}

    # ── 工具 5：儀器推薦 ────────────────────────────────────────

    def _recommend_instruments(self,
                                error_profile: list[str],
                                budget_level: str = 'standard') -> dict:
        db = {
            'LRT': {
                'name': 'Laser R-Test (LRT)',
                'measures': ['XOC', 'YOC', 'AOC', 'BOA', 'EXC', 'EYC', 'EZC', 'EAC', 'EBC'],
                'accuracy': '< 1 μm / 0.0006°',
                'time': '約 2 小時',
                'priority': 1,
                'budget': ['standard', 'full'],
                'note': 'PIGE + PDGE 全項辨識首選'
            },
            'DBB': {
                'name': 'Double Ball Bar (DBB / K1K2)',
                'measures': ['reversal_spike', 'servo_mismatch', 'roundness'],
                'accuracy': '< 0.1 μm',
                'time': '約 30 分鐘',
                'priority': 2,
                'budget': ['basic', 'standard', 'full'],
                'note': '快速確認動態誤差，反轉尖峰量化首選'
            },
            'Autocollimator': {
                'name': '電子式自準直儀',
                'measures': ['AOC', 'BOA', 'gravity'],
                'accuracy': '< 0.0003°',
                'time': '約 1 小時',
                'priority': 3,
                'budget': ['standard', 'full'],
                'note': '靜態角度誤差驗證，重力補償標定輔助'
            },
            'Spindle_Analyzer': {
                'name': '主軸誤差分析儀（電容感測器組）',
                'measures': ['EXC', 'EYC', 'EZC'],
                'accuracy': '< 0.01 μm',
                'time': '約 1 小時',
                'priority': 2,
                'budget': ['standard', 'full'],
                'note': 'C 軸轉台誤差運動精密量測'
            },
            'Thermometer': {
                'name': '多點溫度感測器陣列',
                'measures': ['thermal'],
                'accuracy': '< 0.1°C',
                'time': '需長時間採集（>4 小時）',
                'priority': 4,
                'budget': ['full'],
                'note': '熱變形補償訓練數據收集'
            },
        }

        # 找出哪些儀器覆蓋了 error_profile 中的誤差
        needed = set(e.upper() for e in error_profile)
        recommended = []

        for key, inst in db.items():
            covered = set(m.upper() for m in inst['measures']) & needed
            if covered and budget_level in inst['budget']:
                recommended.append({
                    'instrument': inst['name'],
                    'covers':     list(covered),
                    'accuracy':   inst['accuracy'],
                    'time':       inst['time'],
                    'note':       inst['note'],
                    'priority':   inst['priority'],
                })

        recommended.sort(key=lambda x: x['priority'])
        total_time_hr = len(recommended) * 1.5   # 粗估

        return {
            'status': 'success',
            'error_profile': error_profile,
            'budget_level': budget_level,
            'recommended': recommended,
            'total_instruments': len(recommended),
            'estimated_total_time': f'約 {total_time_hr:.0f} 小時',
            'vs_traditional': '傳統逐項調機：5~7 天',
        }

    # ── 工具 6：補償效果預估 ────────────────────────────────────

    def _estimate_compensation_effect(self,
                                       include_gravity=True,
                                       include_ai=True) -> dict:
        base = self.memory.get('analysis_result', {})
        rms_raw = base.get('rms', {}).get('before_um', [56.0, 23.4, 53.2])
        rms_phys = base.get('rms', {}).get('after_um',  [1.81, 1.70, 0.95])

        # 重力補償再改善（估算：DZ 額外 30-40%）
        rms_grav = np.array(rms_phys)
        if include_gravity:
            rms_grav = rms_grav * np.array([0.9, 0.8, 0.65])

        # AI 補償再改善
        rms_ai = rms_grav
        if include_ai:
            rms_ai = rms_grav * np.array([0.3, 0.45, 0.2])

        def _stage(before, after):
            b = np.array(before)
            a = np.array(after)
            return {
                'dx_um': round(float(a[0]), 3),
                'dy_um': round(float(a[1]), 3),
                'dz_um': round(float(a[2]), 3),
                'improvement_from_raw_pct': (
                    (1 - a / np.where(np.array(rms_raw) > 0,
                                      np.array(rms_raw), 1)) * 100
                ).round(1).tolist()
            }

        return {
            'status': 'success',
            'waterfall': {
                'raw':          {'dx_um': rms_raw[0], 'dy_um': rms_raw[1], 'dz_um': rms_raw[2]},
                'after_physics': _stage(rms_raw, rms_phys),
                'after_gravity': _stage(rms_raw, rms_grav.tolist()) if include_gravity else None,
                'after_ai':      _stage(rms_raw, rms_ai.tolist())   if include_ai else None,
            },
            'summary': (
                f"三層補償預估總改善率：\n"
                f"  DX: {(1-rms_ai[0]/rms_raw[0])*100:.1f}%  "
                f"  DY: {(1-rms_ai[1]/rms_raw[1])*100:.1f}%  "
                f"  DZ: {(1-rms_ai[2]/rms_raw[2])*100:.1f}%"
            )
        }

    # ── 工具 7：真實 GraphRAG 知識檢索 ──────────────────────
    def _query_equipment_knowledge(self, query: str, equipment_type: str) -> dict:
        """
        使用 FAISS 向量檢索與 Neo4j 圖譜檢索真實的手冊圖文。
        equipment_filters 由前端 checkbox 控制，存在 memory 中。
        """
        if not self.has_rag:
            return {'status': 'error', 'retrieved_info': "RAG 系統尚未初始化，請先建立 Vector DB。"}

        # 讀取前端傳入的知識庫篩選（None = 不限制）
        eq_filters = self.memory.get('equipment_filters')

        # 若使用者有勾選篩選，且本次查詢的 equipment_type 不在允許清單中，直接跳過
        if eq_filters is not None and equipment_type not in eq_filters:
            return {
                'status': 'filtered',
                'retrieved_info': f"使用者未啟用 {equipment_type} 知識庫，略過查詢。"
            }

        search_result = self.rag_retriever.retrieve(
            query=query, top_k=1, equipment_filter=eq_filters
        )
        
        if search_result['status'] == 'success':
            # 🌟 秘訣 1：將原始日誌偷偷存進 Agent 的記憶體中，不讓 LLM 花時間重複生成
            self.memory['last_rag_log'] = search_result['retrieved_info']

            # 🌟 秘訣 2：給 Agent 的指令專注於「統整與解說」
            final_output = f"""
            【系統底層檢索資料 (含 FAISS 原始文本與 Neo4j 因果邏輯)】
            {search_result['retrieved_info']}

            【Agent 統整任務指令 (CRITICAL)】
            1. 請扮演專業的工具機工程師，吸收上述資料後，用自然、流暢且具備邏輯的語氣回答使用者的問題。
            2. 你必須將「系統底層因果邏輯分析」的內容，自然地揉合進你的步驟解說中。不要生硬地列出「原因：...」，而是要說「為了...，我們需要...」。
            3. ⚠️ 圖片保留指令：你必須在解說的適當段落，原封不動地插入上述資料中的 Markdown 圖片語法 (即 `![](/images/rag/...)`)。
            4. 注意：你「不需要」在回答中印出原始的檢索日誌，系統會在背景自動處理。
            5. 🔑 數值代入指令（最重要）：如果操作步驟中提到需要輸入 XOC、YOC、YOA、ZOA 等補償值，你必須從 Agent 記憶體中的分析結果（pige 欄位）取出本次辨識的實際數值，代入步驟中。格式範例：「將游標移至 X 軸偏移欄位，輸入：**0.05**」。絕對不要只寫「輸入辨識出的 XOC 值」這種抽象描述。
            """
            return {'status': 'success', 'retrieved_info': final_output}
        else:
            return search_result
        
    # ── 知識庫建構 ──────────────────────────────────────────────

    def _build_error_knowledge_base(self) -> dict:
        return {
            'XOC': {
                'name': 'C 軸 X 方向靜態偏心',
                'category': 'PIGE',
                'iso_symbol': 'XOC',
                'physical_cause': 'C 軸轉台相對 A 軸旋轉中心在 X 方向的偏移',
                'effect_on_tcp': '使 BK4 軌跡在 X 方向出現 1× 頻率振盪，振幅等於偏心量',
                'measurement': 'LRT 靜態偏心量測，或 BK4 殘差 X 方向 DC 分量',
                'compensation': 'HTM 模型中加入 XOC 補償，或控制器輸入偏移修正',
                'typical_value_um': '10~100',
                'interaction': '與 AOC 耦合：A 軸傾斜時 X 偏心會放大 Z 誤差',
            },
            'YOC': {
                'name': 'C 軸 Y 方向靜態偏心',
                'category': 'PIGE',
                'iso_symbol': 'YOC',
                'physical_cause': 'C 軸轉台相對 A 軸旋轉中心在 Y 方向的偏移',
                'effect_on_tcp': 'BK4 軌跡 Y 方向 DC 偏移',
                'measurement': 'LRT 靜態量測',
                'compensation': 'HTM 模型 YOC 項補償',
                'typical_value_um': '10~50',
                'interaction': '與 XOC 共同決定徑向偏心的方向與大小',
            },
            'AOC': {
                'name': 'C/A 軸垂直度誤差（阿貝誤差）',
                'category': 'PIGE',
                'iso_symbol': 'AOC',
                'physical_cause': 'C 軸旋轉面相對 A 軸旋轉面的傾斜角',
                'effect_on_tcp': (
                    '最危險的誤差項：阿貝放大效應使 Z 向誤差 = AOC × R，'
                    'R=200mm 時 0.006° → 20μm Z 向誤差'
                ),
                'measurement': 'LRT + 自準直儀雙重確認',
                'compensation': 'HTM 模型 AOC 項補償',
                'typical_value_deg': '0.003~0.029',
                'interaction': '與量測球半徑 R 呈線性放大關係，是最需要補償的 PIGE 項',
            },
            'BOA': {
                'name': 'A 軸歪斜（Yaw）',
                'category': 'PIGE',
                'iso_symbol': 'BOA',
                'physical_cause': 'A 軸安裝時 B 方向的角度偏差',
                'effect_on_tcp': 'A 軸旋轉時 X 方向出現位移誤差',
                'measurement': '自準直儀量測 A 軸安裝垂直度',
                'compensation': 'HTM 模型 BOA 項',
                'typical_value_deg': '0.003~0.017',
                'interaction': '與 XOC 疊加影響 BK4 橢圓形狀',
            },
            'EXC': {
                'name': 'C 軸 X 徑向跳動',
                'category': 'PDGE',
                'iso_symbol': 'E_XC',
                'physical_cause': '軸承偏心，C 軸旋轉時旋轉中心在 X 方向的週期性偏移',
                'effect_on_tcp': 'DX 中出現 1 倍頻正弦振盪',
                'measurement': '主軸誤差分析儀（電容感測器）量測 C 軸誤差運動',
                'compensation': 'PDGE 低頻模型（B-Spline 或諧波擬合）',
                'typical_value_um': '1~20',
                'frequency': '1× C 軸旋轉頻率',
                'interaction': '與 EYC 相位差 90° 形成橢圓軌跡誤差',
            },
            'EYC': {
                'name': 'C 軸 Y 徑向跳動',
                'category': 'PDGE',
                'iso_symbol': 'E_YC',
                'physical_cause': '軸承偏心，Y 方向的週期性偏移',
                'effect_on_tcp': (
                    'DY 中出現 1 倍頻正弦振盪，'
                    '且透過 A 軸傾斜產生 DZ 耦合（~21% 的 EYC 值）'
                ),
                'measurement': '主軸誤差分析儀',
                'compensation': 'PDGE 諧波擬合',
                'typical_value_um': '1~20',
                'frequency': '1× C 軸旋轉頻率',
                'interaction': '與 A 軸傾角耦合，A≠0 時影響 DZ',
            },
            'EZC': {
                'name': 'C 軸 Z 軸向竄動',
                'category': 'PDGE',
                'iso_symbol': 'E_ZC',
                'physical_cause': '轉台端面不平（馬鞍形 → 2× 頻率；傾斜 → 1× 頻率）',
                'effect_on_tcp': 'DZ 中出現 2 倍頻（典型）或 1 倍頻振盪',
                'measurement': '電容感測器量測 C 軸端面跳動',
                'compensation': 'PDGE 諧波擬合，注意主頻可能是 1× 或 2×',
                'typical_value_um': '0.5~10',
                'frequency': '通常為 2× C 軸旋轉頻率',
                'interaction': '直接影響 Z 向面粗度，BK4 識別精度受 AOC 遮蔽',
            },
            'GRAVITY': {
                'name': '重力變形誤差',
                'category': 'Quasi-static',
                'iso_symbol': '無（非 ISO 標準項）',
                'physical_cause': 'A 軸傾斜時結構重心改變，機台彈性變形',
                'effect_on_tcp': 'δ_z = k_z × L × sin(α_A)，Z 向誤差隨 A 角正弦變化',
                'measurement': 'LRT 在各 A 角靜態量測，標定結構柔度係數',
                'compensation': 'GravityCompensator（虎克定律模型）',
                'typical_value_um': '5~50（取決於刀具懸伸長度 L）',
                'note': '準靜態，不隨速度變化，物理公式完全可解析，比 AI 更準確',
            },
            'REVERSAL_SPIKE': {
                'name': '反轉尖峰（象限突波）',
                'category': 'Dynamic-nonlinear',
                'iso_symbol': '無（動態誤差）',
                'physical_cause': '速度方向反轉瞬間靜/動摩擦力突變，伺服追蹤誤差',
                'effect_on_tcp': '速度過零點時出現短暫尖峰，幅值 5~20 μm',
                'measurement': 'DBB (K1/K2 換向點) 或 BK4 換向位置殘差',
                'compensation': 'LSTM（動態AI層）',
                'note': '物理上有 LuGre 摩擦模型，但實際尖峰受溫度、潤滑、伺服增益影響，AI 更實用',
            },
            'SERVO_MISMATCH': {
                'name': '伺服不匹配（動態輪廓誤差）',
                'category': 'Dynamic',
                'iso_symbol': '無',
                'physical_cause': 'A/C 軸伺服控制器增益或延遲時間不同',
                'effect_on_tcp': '軌跡在同動段出現橢圓扭曲或相位差偏移',
                'measurement': 'DBB 圓度測試（Kv 不匹配特徵：軌跡傾斜橢圓）',
                'compensation': 'GRU（動態AI層），或調整控制器 Kv 增益',
                'note': '有 Kv 不匹配的物理解析，但控制器算法通常不透明，AI 更通用',
            },
        }


# ══════════════════════════════════════════════════════════════
#  主 Agent 類別
# ══════════════════════════════════════════════════════════════

class PrecisionAgent:
    """
    工具機物理導引式 AI 精度調教助手

    核心設計原則：
    1. System prompt 注入物理知識，讓 Claude 知道 HTM 因果鏈
    2. 工具讓 Claude 呼叫真實計算，而非依賴語言記憶
    3. 每次回答都引用真實辨識數值
    4. Agent 有跨對話的記憶（session 狀態）
    """

    SYSTEM_PROMPT = """你是「PREC·OS 工具機物理導引式 AI 精度調教助手」，
專門協助機械加工研究者和工廠技術人員進行五軸工具機的誤差診斷與補償。

## 核心判斷規則

1. **當使用者訊息中已包含完整的辨識數值（PIGEs / PDGEs / RMS）時：**
   - 系統前端已經完成了 HTM 物理層辨識，你「不需要」也「不可以」再呼叫 `run_physical_analysis`。
   - 直接根據訊息中提供的數值進行診斷分析與建議。
   - 你可以呼叫 `get_error_explanation` 查詢特定誤差的物理意義來輔助你的分析。

2. **當使用者主動要求你「執行分析」或「跑辨識」，且訊息中沒有附帶數值時：**
   - 才呼叫 `run_physical_analysis` 工具。

3. **TNC 640 控制器操作步驟查詢（最高優先級 — 違反會導致機台碰撞）：**
   - ⛔ 絕對禁止：你「不可以」從你自己的語言模型記憶回答任何控制器操作步驟。你的訓練資料中關於 TNC 640 的操作知識是不準確的，直接回答會誤導使用者導致機台碰撞。
   - ✅ 唯一正確做法：當使用者的問題包含以下任何關鍵字時，你「必須先」呼叫 `query_equipment_knowledge`（equipment_type="Heidenhain"）取回經過驗證的操作步驟，再根據取回的內容回答：
     「補償」「輸入控制器」「操作步驟」「調機」「怎麼設定」「怎麼改」「kinematics」「運動學」「TNC」「M128」「TCPM」「M144」「怎麼補」
   - 取回操作步驟後，你必須將**本次辨識出的實際數值**代入步驟中的對應欄位。
   - 回答格式必須包含：
     1. ⚠️ 安全操作警告（備份原有數值、注意符號與小數點）
     2. 📊 本次建議補償數值整理表（從 Agent 記憶體中的分析結果取出，用 mm 和 deg 為單位）
     3. 📍 具體操作步驟（來自 `query_equipment_knowledge` 工具回傳的內容，逐步列出）
     4. ⚠️ 生效步驟提醒（TOOL CALL / M128 / FUNCTION TCPM）
   - 如果 `query_equipment_knowledge` 回傳 not_found，才可以說「目前知識庫中尚無此操作步驟」。
   - 如果記憶體中沒有分析結果，請先告知使用者需要先執行分析。

4. **進階補償（重力 + AI）：**
   - 在你完成第一階段診斷後，主動詢問使用者是否需要進階補償。
   - 使用者同意後，依序呼叫 `run_gravity_compensation` → `run_dynamic_ai_layer` → `estimate_compensation_effect`。

## 回應格式規範（嚴格遵守）

你的回應必須使用清晰的 Markdown 結構，具體規範如下：

```
## 診斷摘要
用 2-3 句話總結本次辨識的關鍵發現。

## 主要誤差源分析

### 1. [誤差代號] — [名稱]
- **辨識值：** XX µm / XX°
- **物理意義：** 一句話說明這個誤差怎麼產生的
- **對加工的影響：** 一句話說明它如何影響工件精度

（依嚴重程度排序，只列出數值顯著的項目，不要列出接近零的項目）

## 補償效果評估
用表格或條列呈現 RMS 補償前後的對比。（若目前沒有 RMS 數據則跳過此章節，不要輸出空的模板）

## 調機建議
按優先順序列出具體操作步驟。（若使用者沒有問調機建議則可省略）
```

## 誤差參數物理知識（回答時必須引用正確的物理意義，不可自行猜測）

**PIGEs（位置無關靜態幾何誤差）：**
- XOC：C 軸轉台旋轉中心相對 A 軸在 X 方向的偏心量。造成 BK4 軌跡 X 方向 1× 頻率振盪。
- YOC：C 軸轉台旋轉中心相對 A 軸在 Y 方向的偏心量。與 XOC 合成決定偏心方向與大小。
- AOC：C/A 軸垂直度誤差（阿貝誤差），最危險的 PIGE 項。阿貝放大效應：Z 誤差 ≈ AOC × R（R = 球心半徑 200mm）。
- BOC：C 軸相對 A 軸的傾斜角。
- YOA：A 軸旋轉中心在 Y 方向的偏移。A 軸旋轉時 Y/Z 方向出現正弦偏移。
- ZOA：A 軸旋轉中心在 Z 方向的偏移。A 軸旋轉時產生 Z 向位移耦合。
- BOA：A 軸 Yaw 歪斜，A 軸安裝時 B 方向角度偏差，影響 X 向精度。
- COA：A 軸 Roll 歪斜。

**PDGEs（位置相關動態幾何誤差）：**
- EXC：C 軸 X 徑向跳動，軸承偏心導致旋轉時 X 方向週期性偏移（1× 頻率）。
- EYC：C 軸 Y 徑向跳動，與 EXC 相位差 ~90° 形成橢圓軌跡誤差。
- EZC：C 軸軸向竄動，轉台端面不平造成 Z 方向週期振盪（通常 2× 頻率）。

**判斷顯著性基準：**
- 平移 PIGEs：> 0.005 mm 為顯著
- 角度 PIGEs：> 0.001° 為顯著
- PDGEs：> 0.001 mm 為顯著
- 低於基準的參數視為雜訊，不要提及

## 回應原則
- 用繁體中文回應，語氣專業但易懂。
- 平移量一律用 **mm**，角度用 **°(deg)**，RMS 可用 µm。
- 只分析數值顯著的誤差項，接近零的不要提。
- 不要重複列出原始數據表格，使用者已經在介面上看到了。
- 不要輸出任何 JSON 或程式碼區塊，只用自然語言和 Markdown 排版。
"""

    def __init__(self, api_key: str | None = None):
        """
        Parameters
        ----------
        api_key : str or None
            Anthropic API 金鑰。None 時使用環境變數 ANTHROPIC_API_KEY。
        """
        if not _GROQ_AVAILABLE:
            print("[PrecisionAgent] groq 未安裝，使用離線模擬模式")
            self.client = None
        else:
            _key = api_key or os.environ.get('GROQ_API_KEY')
            if not _key:
                print(f"[PrecisionAgent] 未找到 GROQ_API_KEY"
                      f"{f'（.env 路徑：{_env_path}）' if _env_path else '（.env 未找到）'}")
                self.client = None
            else:
                self.client = Groq(api_key=_key)

        self.executor       = ToolExecutor()
        self.conversation   = []   # 完整對話歷史

    # ── 對話入口 ────────────────────────────────────────────────

    def chat(self, user_message: str, verbose: bool = True) -> str:
        """
        送入使用者訊息，Agent 決定是否呼叫工具，回傳最終回應。

        Parameters
        ----------
        user_message : str  使用者輸入（自然語言）
        verbose      : bool 是否印出工具呼叫過程

        Returns
        -------
        reply : str  Agent 的最終回答
        """
        self.conversation.append({'role': 'user', 'content': user_message})

        if self.client is None:
            return self._offline_reply(user_message)

        # ── 主 Agent 迴圈（允許多輪工具呼叫）─────────────────
        # tool_choice 策略：
        #   第 1 輪用 "auto"（讓模型自己決定要不要用工具）
        #   之後每輪：如果上一輪有跑工具就繼續 "auto"，
        #   但連續跑超過 3 次工具後強制切 "none" 逼模型回答
        max_rounds      = 8
        tools_called    = 0   # 累計工具呼叫次數
        force_answer    = False

        for round_num in range(max_rounds):

            current_tool_choice = "none" if force_answer else "auto"

            # Groq 只接受字串 "none"/"auto"/"required"，不接受 None
            # 強制回答時：tool_choice="none" 且仍傳 tools（不能傳 None）
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                # model="openai/gpt-oss-120b",
                max_tokens=4096,
                tools=TOOL_DEFINITIONS,
                tool_choice="none" if force_answer else "auto",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    *self.conversation,
                ],
            )

            choice  = response.choices[0]
            message = choice.message

            # 情況一：模型直接回答（沒有工具呼叫）
            has_tool_calls = bool(message.tool_calls)
            if not has_tool_calls:
                reply = message.content or ""
                self.conversation.append({
                    "role": "assistant", "content": reply
                })
                return reply

            # 情況二：模型要求呼叫工具
            tools_called += len(message.tool_calls)

            self.conversation.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id":       tc.id,
                        "type":     "function",
                        "function": {
                            "name":      tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in message.tool_calls
                ]
            })

            for tc in message.tool_calls:
                tool_name  = tc.function.name
                tool_input = json.loads(tc.function.arguments)

                if verbose:
                    print(f"\n  [工具呼叫] {tool_name}")
                    print(f"  輸入：{json.dumps(tool_input, ensure_ascii=False, indent=4)}")

                result = self.executor.execute(tool_name, tool_input)

                if verbose:
                    preview = json.dumps(result, ensure_ascii=False)[:200]
                    print(f"  結果：{preview}...")

                self.conversation.append({
                    "role":         "tool",
                    "tool_call_id": tc.id,
                    "content":      json.dumps(result, ensure_ascii=False),
                })

            # 工具跑超過 3 次後，下一輪強制回答，不再允許呼叫工具
            if tools_called >= 3:
                force_answer = True

        return "（Agent 達到最大工具呼叫輪數，請重新提問）"

    def reset(self):
        """清除對話歷史和 Agent 記憶"""
        self.conversation = []
        self.executor.memory = {k: None for k in self.executor.memory}
        self.executor.memory['has_analysis'] = False
        self.executor.memory['has_gravity']  = False
        self.executor.memory['has_ai']       = False

    # ── 離線模式（無 API 時）────────────────────────────────────

    def _offline_reply(self, msg: str) -> str:
        m = msg.lower()
        if any(k in m for k in ['分析', '辨識', 'analyze', 'bk4']):
            result = self.executor.execute('run_physical_analysis', {'mode': 'simulate'})
            return (
                f"[離線模式] 已執行物理層辨識：\n"
                f"  XOC = {result['pige']['XOC_um']} μm\n"
                f"  AOC = {result['pige']['AOC_deg']} deg\n"
                f"  EXC = {result['pdge']['EXC_amp_um']} μm\n"
                f"  DZ RMS 改善率 = {result['rms']['improvement_pct'][2]}%\n"
                f"（完整 Agent 功能請設定 GROQ_API_KEY）"
            )
        return (
            "[離線模式] 請設定 ANTHROPIC_API_KEY 環境變數以啟用完整 Agent 功能。\n"
            "目前可直接呼叫：agent.executor.execute('run_physical_analysis', {'mode':'simulate'})"
        )


# ══════════════════════════════════════════════════════════════
#  FastAPI 整合介面
#  供 backend/routers/ 呼叫
# ══════════════════════════════════════════════════════════════

# 每個 Web session 一個 Agent 實例（簡單的 in-memory）
_agent_pool: dict[str, PrecisionAgent] = {}

def get_or_create_agent(session_id: str) -> PrecisionAgent:
    if session_id not in _agent_pool:
        _agent_pool[session_id] = PrecisionAgent()
    return _agent_pool[session_id]


# ══════════════════════════════════════════════════════════════
#  CLI 互動介面
#  python prec_agent.py
# ══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("\n" + "★" * 60)
    print("  PREC·OS  工具機物理導引式 AI 精度調教助手")
    print("  輸入 'exit' 結束，'reset' 清除對話歷史")
    print("★" * 60)

    key = os.environ.get('GROQ_API_KEY')
    if not key:
        print("\n[提示] 未設定 GROQ_API_KEY，將使用離線模擬模式。")
        print("       設定方式：export GROQ_API_KEY='your-key-here'\n")

    agent = PrecisionAgent(api_key=key)

    DEMO_QUESTIONS = [
        "請幫我執行完整的 BK4 誤差分析",
        "我的 DZ 誤差很大，主要原因是什麼？",
        "根據分析結果，我需要買哪些量測儀器？",
        "現在執行重力補償，會有多少改善？",
    ]

    print("示範問題（直接按 Enter 用示範問題，或自行輸入）：")
    for i, q in enumerate(DEMO_QUESTIONS):
        print(f"  [{i+1}] {q}")
    print()

    demo_idx = 0
    while True:
        try:
            raw = input("你：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n結束對話。")
            break

        if not raw:
            if demo_idx < len(DEMO_QUESTIONS):
                raw = DEMO_QUESTIONS[demo_idx]
                demo_idx += 1
                print(f"你：{raw}")
            else:
                continue

        if raw.lower() == 'exit':
            break
        if raw.lower() == 'reset':
            agent.reset()
            print("對話已重置。\n")
            continue

        print("\nPREC·OS：", end='', flush=True)
        reply = agent.chat(raw, verbose=True)
        print(reply)
        print()