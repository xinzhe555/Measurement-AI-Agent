"""
routers/session.py
/api/session  — 對話 session，呼叫 PrecisionAgent（真正的工具呼叫 AI）
"""
from fastapi import APIRouter, HTTPException
from schemas.request  import ChatRequest
from schemas.response import ChatResponse
from typing import Dict, Any
import sys, os

router = APIRouter(prefix="/api/session", tags=["session"])

# ── 載入 PrecisionAgent ──────────────────────────────────────
_BK4_DIR = os.path.join(os.path.dirname(__file__), '..', 'bk4')
sys.path.insert(0, os.path.abspath(_BK4_DIR))

try:
    from bk4.prec_agent import get_or_create_agent
    _AGENT_AVAILABLE = True
except Exception as e:
    _AGENT_AVAILABLE = False
    print(f"[session.py] 警告：無法載入 PrecisionAgent（{e}），降級為規則式回應")

_sessions: Dict[str, Dict[str, Any]] = {}


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if _AGENT_AVAILABLE:
        return await _agent_reply(req)
    session = _sessions.get(req.session_id, {})
    reply, has_analysis = _rule_reply(req.message, session)
    return ChatResponse(reply=reply, has_analysis=has_analysis)


async def _agent_reply(req: ChatRequest) -> ChatResponse:
    try:
        agent = get_or_create_agent(req.session_id)

        if req.context:
            _inject_context(agent, req.context)

        import asyncio
        reply = await asyncio.get_event_loop().run_in_executor(
            None, lambda: agent.chat(req.message, verbose=True)
        )

        # ==========================================
        # 攔截 Agent 的回覆，把 RAG 日誌用摺疊標籤接在最後面
        # ==========================================
        rag_log = agent.executor.memory.get('last_rag_log')
        if rag_log:
            # 使用 Markdown 與 HTML 的 details/summary 標籤製作摺疊區塊
            collapsible_log = (
                f"\n\n---\n"
                f"<details>\n"
                f"<summary>⚙️ <b>點擊展開：系統底層檢索日誌 (Hybrid RAG)</b></summary>\n\n"
                f"```text\n{rag_log}\n```\n"
                f"</details>\n"
            )
            reply = collapsible_log + reply
            
            # 用完就清掉，避免下次無關的對話又重複出現這段日誌
            agent.executor.memory['last_rag_log'] = None

        used_tools = []
        for msg in reversed(agent.conversation):
            if msg.get("role") == "user":
                break  # 碰到使用者的提問就停止往回找
            if msg.get("role") == "assistant" and "tool_calls" in msg:
                for tc in msg["tool_calls"]:
                    used_tools.append(tc["function"]["name"])

        return ChatResponse(
            reply=reply or "（Agent 無回應，請重試）",
            has_analysis=agent.executor.memory.get('has_analysis', False),
            analysis=_snapshot_memory(agent),
            used_tools=used_tools,
        )
    except Exception as e:
        return ChatResponse(reply=f"系統暫時無法回應（{e}），請稍後再試。", has_analysis=False)


def _inject_context(agent, context: dict):
    mem = agent.executor.memory

    # ── 注入 TwinPanel 圖表數據（來自前端 chartData，已包含 a_axis/c_axis/dx/dy/dz）──
    twin_data = context.get('twin_chart_data')
    if twin_data:
        mem['twin_chart_data'] = twin_data

    la  = context.get('last_analysis', {})
    if not la:
        return
    mem['has_analysis']    = True
    mem['analysis_result'] = {
        'status': 'injected_from_frontend',
        'pige': {
            'X_OC_um':   la.get('pige', {}).get('xoc_um', 0),
            'Y_OC_um':   la.get('pige', {}).get('yoc_um', 0),
            'A_OC_deg': la.get('pige', {}).get('aoc_deg', 0),
            'B_OC_deg': la.get('pige', {}).get('boc_deg', 0),
            'B_OA_deg': la.get('pige', {}).get('boa_deg', 0),
        },
        'pdge': {
            'EXC_amp_um':    la.get('pdge', {}).get('exc_amp_um', 0),
            'EXC_phase_deg': la.get('pdge', {}).get('exc_phase_deg', 0),
            'EYC_amp_um':    la.get('pdge', {}).get('eyc_amp_um', 0),
            'EYC_phase_deg': la.get('pdge', {}).get('eyc_phase_deg', 0),
            'EZC_amp_um':    la.get('pdge', {}).get('ezc_amp_um', 0),
            'EZC_freq':      la.get('pdge', {}).get('ezc_freq', 2.0),
        },
        'rms': {
            'before_um': [
                la.get('rms', {}).get('before_dx_um', 0),
                la.get('rms', {}).get('before_dy_um', 0),
                la.get('rms', {}).get('before_dz_um', 0),
            ],
            'after_um': [
                la.get('rms', {}).get('after_phys_dx_um', 0),
                la.get('rms', {}).get('after_phys_dy_um', 0),
                la.get('rms', {}).get('after_phys_dz_um', 0),
            ],
            'improvement_pct': [
                la.get('rms', {}).get('phys_improvement_dx_pct', 0),
                la.get('rms', {}).get('phys_improvement_dy_pct', 0),
                la.get('rms', {}).get('phys_improvement_dz_pct', 0),
            ],
        },
        'needs_gravity_check': True,
        'needs_ai': True,
    }


def _snapshot_memory(agent) -> dict | None:
    mem = agent.executor.memory
    
    # 檢查是否有跑過分析
    if not mem.get('has_analysis'):
        return None
    
    # 安全提取物理層結果 (避免是 None)
    phys_res = mem.get('analysis_result') or {}
    if not phys_res:
        return None
        
    # 安全提取 AI 層結果 (避免是 None)
    ai_res = mem.get('ai_result') or {}

    # 動態整理 findings
    findings = []
    if mem.get('has_analysis'):
        findings.append("已完成 PIGE/PDGE 幾何誤差解耦")
    if mem.get('has_gravity'):
        findings.append("已完成 Z 向重力變形量估算 (虎克定律模型)")
    if mem.get('has_ai'):
        findings.append("已完成 LSTM/GRU 換向背隙與伺服動態特徵學習")

    return {
        'pige': phys_res.get('pige', {}),
        'pdge': phys_res.get('pdge', {}),
        'rms':  phys_res.get('rms', {}),
        # 安全地提取 ai_r2
        'ai_r2': ai_res.get('metrics', {}).get('lstm_r2', 0),
        'findings': findings
    }


@router.post("/save/{session_id}")
async def save_session(session_id: str, data: dict):
    _sessions[session_id] = data
    return {"saved": True}


@router.get("/load/{session_id}")
async def load_session(session_id: str):
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session 不存在")
    return _sessions[session_id]


@router.delete("/reset/{session_id}")
async def reset_session(session_id: str):
    if _AGENT_AVAILABLE:
        try:
            get_or_create_agent(session_id).reset()
        except Exception:
            pass
    _sessions.pop(session_id, None)
    return {"reset": True}


def _rule_reply(msg: str, session: dict) -> tuple[str, bool]:
    m        = msg.lower()
    analysis = session.get("last_analysis")
    if "xoc" in m and analysis:
        xoc = analysis.get("pige", {}).get("xoc_um", "N/A")
        return (f"根據本次辨識，XOC = {xoc} μm。", False)
    if any(k in m for k in ["儀器", "量測設備", "採購"]):
        return ("建議配置：① Laser R-Test  ② 電子自準直儀  ③ 主軸誤差分析儀", False)
    return (f"請先執行分析，系統便能根據具體辨識結果給您更精確的回答。", False)
