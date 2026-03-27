---
name: precos-thesis
description: >
  PREC·OS 論文撰寫進度、章節架構與研究目標。
  當任務涉及以下內容時使用此 skill：討論論文撰寫、章節進度、
  研究貢獻與創新點、文獻回顧方向、論文用字規範、
  系統驗證目標、實驗設計，或任何涉及學術寫作與研究規劃的工作。
---

# 論文架構與進度

## 基本資訊

- **論文題目**：基於多模態知識圖譜與多源誤差解耦 Agent 之五軸工具機智慧診斷與補償系統
- **英文題目**：An Integrated Intelligent System for Five-Axis Machine Tool Diagnosis and Compensation Using Multimodal Knowledge Graph and Multi-Source Error Decoupling Agent
- **研究生**：張信哲（碩二）

## 章節進度

| 章節 | 標題 | 方法論 | 進度 |
|------|------|--------|------|
| 第一章 | 緒論 | 研究背景、動機、貢獻 | 30% |
| 第二章 | 文獻回顧 | 五軸誤差補償、RAG、LLM Agent | 20% |
| 第三章 | 五軸工具機運動學建模 | ISO HTM、PIGEs/PDGEs、AOC/BOC/BOA/COA | 60% |
| 第四章 | 多模態知識圖譜建置 | GraphRAG、Qdrant、Neo4j、圖文對齊 | 55% |
| 第五章 | 幾何誤差辨識與數位孿生補償 | 誤差辨識、背隙/伺服不匹配殘差、數位孿生 | 40% |
| 第六章 | 智慧診斷 Agent 設計 | Tool Calling、記憶模組、多輪診斷 | 30% |
| 第七章 | 實驗驗證與結果分析 | LRT 實機量測、端到端流程 | 10% |
| 第八章 | 結論與未來展望 | — | 5% |

## 系統目標

將傳統調機流程（5–7 天）縮短至**數小時內**，完成以下閉環：
```
LRT 架設引導 → BK4 路徑量測 → 三層次誤差解耦
→ 數位孿生補償模擬預覽 → 海德漢控制器參數輸出 → 再量測驗證
```

## 核心驗證指標

- 六項旋轉軸 PIGEs 模擬與參考數據差異 < 5×10⁻⁵ mm（已達成）
- 知識檢索回應時間 < 2 秒（已達成）
- 實機 LRT 補償前後 RMS 誤差改善率（待實機驗證）

## 用字規範

- 使用「解耦」非「約束」（指導教授意見）
- 英文：Multi-Source Error Decoupling Agent
- BK4 是量測路徑名稱，不是機台型號
