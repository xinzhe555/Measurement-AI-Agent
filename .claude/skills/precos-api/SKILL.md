---
name: precos-api
description: >
  PREC·OS FastAPI 後端路由、Pydantic schema 與前後端資料流架構。
  當任務涉及以下內容時使用此 skill：修改 routers/ 下的路由檔案、
  schemas/ 下的 request.py / response.py、core/bk4_bridge.py 橋接層、
  討論 API 端點設計（/api/analyze、/api/twin_simulate、/api/session）、
  前後端資料流（TwinPanel → Agent、chartData 傳遞）、
  PrecisionAgent tool calling 架構、session 管理，
  或任何涉及 API 設計與系統整合的工作。
---

# API 架構與資料流

## 系統三層架構

```
決策層  ─── 多源誤差解耦 Agent 模組
              LLM (Groq) + Tool Calling + 記憶模組
知識層  ─── 多模態知識圖譜模組
              Qdrant（向量檢索）+ Neo4j（圖譜推理）
運算層  ─── 工具機運動學模組
              HTM 正向模擬器 + 靜態幾何誤差辨識器（PIGEs + PDGEs）
```

## FastAPI 路由

| 路由 | 方法 | 功能 |
|------|------|------|
| `/api/analyze` | POST | 完整分析流程（物理層 + AI 層）|
| `/api/twin_simulate` | POST | 數位孿生正向模擬（注入誤差 → 生成波形）|
| `/api/session/chat` | POST | Agent 對話（PrecisionAgent + Tool Calling）|
| `/api/session/save/{id}` | POST | 儲存 session 狀態 |
| `/api/session/load/{id}` | GET | 載入 session 狀態 |
| `/api/session/reset/{id}` | DELETE | 重置 session |

## 資料流：數位孿生 → Agent 分析

```
TwinPanel (前端)
  → chartData [{index, a_axis, c_axis, dx, dy, dz}]  (μm)
  → sendChat({ context: { twin_chart_data: chartData } })
  → session.py._inject_context() → Agent memory['twin_chart_data']
  → Agent._run_physical_analysis() 讀取 twin_chart_data
  → static_analyzer.identify() 執行 HTM 逆向辨識
  → 回傳 PIGE/PDGE 辨識結果
```

## 資料源優先級（Agent 物理分析）

1. `twin_chart_data`（前端 API context 直接傳入）
2. `simulated_temp_data.csv` + `simulated_temp_meta.json`（CSV 檔案）
3. 即時生成（最後手段）

## 關鍵檔案

- [analyze.py](backend/routers/analyze.py) — POST /api/analyze
- [simulate.py](backend/routers/simulate.py) — POST /api/twin_simulate
- [session.py](backend/routers/session.py) — Chat session（PrecisionAgent）
- [bk4_bridge.py](backend/core/bk4_bridge.py) — 橋接層（連接各模組與 FastAPI）
- [request.py](backend/schemas/request.py) — Pydantic 請求模型
- [response.py](backend/schemas/response.py) — Pydantic 回應模型
- [prec_agent.py](backend/bk4/prec_agent.py) — Agent 核心（Groq LLM + Tool Calling）
