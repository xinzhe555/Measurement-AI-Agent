# PREC·OS 專題上下文文件
> 五軸工具機智慧診斷與補償系統 | FastAPI + Next.js | 研究生：張信哲（碩二）

---

## 關鍵防護規則

1. **一律以 Mode 1 為正確物理模型**（`P_actual_mode1`），Mode 2 保留但不修改、不以它為開發基礎。

2. **T_pivot 和 T_tool 的分離是待實作的關鍵修正**，目前 `bk4_bridge.py` 的 `pivot_z=tool_length` 是錯誤的混用，修正後兩者預設值均為 0。

3. **角度誤差（AOC/BOC/BOA/COA）的公式尚未確認**，`static_analyzer.py` 中已有辨識框架，但正向生成器缺乏正確公式，**不要自行假設角度誤差的插入方式**。

4. **PDGEs 是靜態幾何誤差**（位置相關但仍屬幾何誤差），不要與非線性殘差誤差（背隙、伺服不匹配）混淆。後者是 PIGEs + PDGEs 辨識完成後的殘差，由 `ai_residual_learner.py` 處理。

5. **BK4 是量測路徑名稱**，不是機台型號。研究機台是搖籃型（B Type）AC 軸五軸工具機。

6. **論文用字**：題目使用「解耦」非「約束」，英文為「Multi-Source Error Decoupling Agent」。

7. **模擬數據 xlsx 的 9 個 sheet**：XOC_50um、YOC_-20um、ZOC_0.05mm、XOA_0.05mm、YOA_0.05mm、ZOA_0.05mm、AOC_0.3度、BOC_0.03度、BOA_0.2度。

---

## 關鍵檔案清單

```
bk4/generator.py           ← HTM 正向模擬器（Mode 1 = 正確物理模型）
bk4/static_analyzer.py     ← 靜態幾何誤差辨識器（PIGEs + PDGEs，18 參數）
bk4/ai_residual_learner.py ← MLP 殘差學習器（背隙、伺服不匹配）
bk4/prec_agent.py          ← Agent 核心（Groq LLM + Tool Calling）
core/bk4_bridge.py         ← 橋接層（有 T_pivot/T_tool 混用 bug）
routers/simulate.py        ← POST /api/twin_simulate
routers/session.py         ← Chat session（PrecisionAgent）
schemas/request.py         ← Pydantic 請求模型
schemas/response.py        ← Pydantic 回應模型
```
