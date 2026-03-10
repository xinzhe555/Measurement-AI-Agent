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

    def execute(self, tool_name: str, tool_input: dict) -> dict:
        """分發工具呼叫"""
        dispatch = {
            'run_physical_analysis':    self._run_physical_analysis,
            'run_gravity_compensation': self._run_gravity_compensation,
            'run_dynamic_ai_layer':     self._run_dynamic_ai_layer,
            'get_error_explanation':    self._get_error_explanation,
            'recommend_instruments':    self._recommend_instruments,
            'estimate_compensation_effect': self._estimate_compensation_effect,
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
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from generator          import Integrated_BK4_Simulator
            from physical_analyzer  import PhysicalLayerAnalyzer

            if mode == 'simulate' or self.memory['a_cmd'] is None:
                sim  = Integrated_BK4_Simulator()
                data, a_cmd, c_cmd = sim.generate(
                    ball_x=200.0, ball_y=0.0, ball_z=0.0, pivot_z=0.0
                )
                self.memory['a_cmd'] = a_cmd
                self.memory['c_cmd'] = c_cmd
            else:
                data  = self.memory.get('raw_data')
                a_cmd = self.memory['a_cmd']
                c_cmd = self.memory['c_cmd']

            analyzer = PhysicalLayerAnalyzer()
            params, residual = analyzer.identify(
                data, a_cmd, c_cmd, 
                ball_x=200.0, ball_y=0.0, ball_z=0.0, tool_length=0.0, 
                verbose=False
            )

            rms_before = np.sqrt(np.mean(data**2, axis=0)) * 1000
            rms_after  = np.sqrt(np.mean(residual**2, axis=0)) * 1000

            result = {
                'status': 'success',
                'pige': {
                    'X_OC_um': round(params['X_OC'] * 1000, 2),
                    'Y_OC_um': round(params['Y_OC'] * 1000, 2),
                    'A_OC_mrad': round(params['A_OC'] * 1000, 4),
                    'B_OC_mrad': round(params['B_OC'] * 1000, 4),
                    'B_OA_mrad': round(params['B_OA'] * 1000, 4),
                },
                'pdge': {
                    'EXC_amp_um':   round(params['Runout_X_Amp'] * 1000, 3),
                    'EXC_phase_deg': round(np.degrees(params['Runout_X_Phase']), 1),
                    'EYC_amp_um':   round(params['Runout_Y_Amp'] * 1000, 3),
                    'EYC_phase_deg': round(np.degrees(params['Runout_Y_Phase']), 1),
                    'EZC_amp_um':   round(params['Runout_Z_Amp'] * 1000, 3),
                    'EZC_freq':     round(params['Runout_Z_Freq'], 2),
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
                'status': 'simulated_fallback',
                'note': f'無法載入 Python 模組（{e}），回傳示意數值',
                'pige': {
                    'X_OC_um': 43.8, 'Y_OC_um': -19.6,
                    'A_OC_mrad': 0.302, 'B_OC_mrad': 0.015, 'B_OA_mrad': 0.197
                },
                'pdge': {
                    'EXC_amp_um': 10.02, 'EXC_phase_deg': -1.9,
                    'EYC_amp_um': 9.59,  'EYC_phase_deg': 88.2,
                    'EZC_amp_um': 0.78,  'EZC_freq': 2.0,
                },
                'rms': {
                    'before_um': [56.0, 23.4, 53.2],
                    'after_um':  [1.81, 1.70, 0.95],
                    'improvement_pct': [96.8, 92.7, 98.2],
                },
                'needs_gravity_check': True,
                'needs_ai': True,
            }
            self.memory['has_analysis'] = True
            self.memory['analysis_result'] = result

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
                'accuracy': '< 1 μm / 0.01 mrad',
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
                'accuracy': '< 0.005 mrad',
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

    # ── 知識庫建構 ──────────────────────────────────────────────

    def _build_error_knowledge_base(self) -> dict:
        return {
            'XOC': {
                'name': 'C 軸 X 方向靜態偏心',
                'category': 'PIGE',
                'iso_symbol': 'X_OC',
                'physical_cause': 'C 軸轉台相對 A 軸旋轉中心在 X 方向的偏移',
                'effect_on_tcp': '使 BK4 軌跡在 X 方向出現 1× 頻率振盪，振幅等於偏心量',
                'measurement': 'LRT 靜態偏心量測，或 BK4 殘差 X 方向 DC 分量',
                'compensation': 'HTM 模型中加入 X_OC 補償，或控制器輸入偏移修正',
                'typical_value_um': '10~100',
                'interaction': '與 A_OC 耦合：A 軸傾斜時 X 偏心會放大 Z 誤差',
            },
            'YOC': {
                'name': 'C 軸 Y 方向靜態偏心',
                'category': 'PIGE',
                'iso_symbol': 'Y_OC',
                'physical_cause': 'C 軸轉台相對 A 軸旋轉中心在 Y 方向的偏移',
                'effect_on_tcp': 'BK4 軌跡 Y 方向 DC 偏移',
                'measurement': 'LRT 靜態量測',
                'compensation': 'HTM 模型 Y_OC 項補償',
                'typical_value_um': '10~50',
                'interaction': '與 XOC 共同決定徑向偏心的方向與大小',
            },
            'AOC': {
                'name': 'C/A 軸垂直度誤差（阿貝誤差）',
                'category': 'PIGE',
                'iso_symbol': 'A_OC',
                'physical_cause': 'C 軸旋轉面相對 A 軸旋轉面的傾斜角',
                'effect_on_tcp': (
                    '最危險的誤差項：阿貝放大效應使 Z 向誤差 = A_OC × R，'
                    'R=200mm 時 0.1mrad → 20μm Z 向誤差'
                ),
                'measurement': 'LRT + 自準直儀雙重確認',
                'compensation': 'HTM 模型 A_OC 項補償',
                'typical_value_mrad': '0.05~0.5',
                'interaction': '與量測球半徑 R 呈線性放大關係，是最需要補償的 PIGE 項',
            },
            'BOA': {
                'name': 'A 軸歪斜（Yaw）',
                'category': 'PIGE',
                'iso_symbol': 'B_OA',
                'physical_cause': 'A 軸安裝時 B 方向的角度偏差',
                'effect_on_tcp': 'A 軸旋轉時 X 方向出現位移誤差',
                'measurement': '自準直儀量測 A 軸安裝垂直度',
                'compensation': 'HTM 模型 B_OA 項',
                'typical_value_mrad': '0.05~0.3',
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

    SYSTEM_PROMPT = """你是一台「工具機物理導引式 AI 精度調教助手」，
專門協助機械加工研究者和工廠技術人員進行五軸工具機的誤差診斷與補償。

## 你的核心能力
你能夠呼叫以下工具來做真實的物理計算：
- 執行 HTM（齊次變換矩陣）非線性辨識，識別所有 PIGE 和 PDGE 誤差項
- 計算並應用重力變形補償
- 訓練並應用動態 AI 補償層（LSTM/GRU/MLP）
- 查詢誤差的物理定義和因果關係
- 生成量測儀器採購建議

## 你的物理知識框架
五軸工具機的誤差遵循以下因果鏈：

**運動學鏈**：P_actual = E_A · T_A · E_AC(θ_C) · T_C · P_local
- E_A：A 軸相對 Bed 的靜態誤差（PIGEs A 軸群）
- T_A：A 軸的理想旋轉矩陣
- E_AC：C 軸相對 A 軸的靜態 + 動態誤差（PIGEs C 軸群 + PDGEs）
- T_C：C 軸的理想旋轉矩陣

**最重要的誤差交互作用**：
- AOC（C/A 垂直度）× R（量測球半徑）= 阿貝放大誤差（Z 向）
- EYC × sin(α_A) = EYC 對 DZ 的耦合（A 軸傾斜時才出現）
- 重力變形 δ_z = k_z × L × sin(α_A)

**三層補償架構**：
1. 物理層（HTM 辨識）：消除 PIGE + 低頻 PDGE
2. 重力補償層：消除準靜態重力變形
3. 動態 AI 層（LSTM+GRU+MLP）：補償反轉尖峰、伺服不匹配、高頻 PDGEs

## 回應原則
1. 遇到技術問題，優先呼叫工具取得真實數據，再基於數據回答
2. 解釋誤差時，說明物理機制（為什麼，不只是是什麼）
3. 給出的建議必須是具體可執行的（哪台儀器、哪個參數、多少精度）
4. 用繁體中文回應
5. 數值後面標注單位（μm、mrad、mm）
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
                f"  XOC = {result['pige']['X_OC_um']} μm\n"
                f"  AOC = {result['pige']['A_OC_mrad']} mrad\n"
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