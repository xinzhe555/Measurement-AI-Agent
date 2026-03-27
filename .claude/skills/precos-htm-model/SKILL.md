---
name: precos-htm-model
description: >
  PREC·OS 五軸工具機 HTM 運動學模型的完整公式與設計細節。
  當任務涉及以下內容時使用此 skill：修改 generator.py、bk4_bridge.py，
  討論 HTM 運動鏈公式、齊次轉換矩陣、誤差矩陣 E_AC / E_A、
  P_actual / P_ideal / P_table 預補償、T_pivot / T_tool 分離修正、
  Mode 1 / Mode 2、旋轉方向約定、zeroing_baseline，
  或任何涉及五軸運動學正向模擬的工作。
---

# HTM 運動學模型

## 核心運動鏈（Mode 1，正確物理模型）

```
P_actual = E_A × T_A(θa) × T_pivot × E_AC × T_C(θc) × T_tool × P_table
P_ideal  =       T_A(θa) × T_pivot ×        T_C(θc) × T_tool × P_local
誤差向量 = (P_actual − P_ideal)[:3] − zeroing_baseline
```

- `P_local = [ball_x, ball_y, ball_z, 1]`：感測球在 C 軸轉盤座標系中的初始位置
- `zeroing_baseline`：第零點（C=0°, A=0°）的絕對誤差，用於還原 LRT 相對量測

## 誤差矩陣結構（小角度一階線性化）

```
E_AC = [ 1,    -Coc,   Boc,  xoc ]      E_A = [ 1,    -Coa,   Boa,  xoa ]
       [ Coc,   1,    -Aoc,  yoc ]             [ Coa,   1,    -Aoa,  yoa ]
       [-Boc,   Aoc,   1,    zoc ]             [-Boa,   Aoa,   1,    zoa ]
       [ 0,     0,     0,    1   ]             [ 0,     0,     0,    1   ]
```

- 小寫（xoc, yoc, ...）：位移誤差，單位 mm
- 大寫（Aoc, Boc, ...）：角度誤差，單位 rad

## P_table 預補償

還原 LRT 相對量測的歸零機制，確保第零點在有誤差存在時仍能正確歸零：

```
P_table = T_tool⁻¹ × E_AC⁻¹ × T_pivot⁻¹ × E_A⁻¹ × T_pivot × T_tool × P_local
```

## T_pivot vs T_tool（待修正）

| 參數 | 物理意義 | 目前狀態 |
|------|----------|----------|
| `T_pivot` | A 軸旋轉中心 → C 軸轉盤面的**機台固定幾何距離**（與刀具無關）| 被錯誤地設為 tool_length |
| `T_tool` | C 軸轉盤面 → 感測球中心的**LRT 刀長 L** | 應獨立傳入 |

**修正方案**（已設計，待實作）：
- `generator.py`：`generate()` 加入 `tool_length=0.0`，新增 `T_tool` 矩陣
- `bk4_bridge.py`：拆分 `pivot_z=tool_length` 為兩個獨立參數
- `simulate.py` / `request.py`：新增 `pivot_z` 欄位

**T_tool 的力臂效應**：刀長 L 會放大角度誤差（阿貝效應），學長驗證數據均以 L=0，因此此問題當時未被發現。

## 旋轉方向約定

```python
a_rot = -a_rad   # match_senior_a_dir=True
c_rot = -c_rad   # 固定
```

## Mode 1 vs Mode 2

- **Mode 1**（`P_actual_mode1`）：正確物理模型，E_A 和 E_AC 為靜態偏差矩陣，不隨軸旋轉
- **Mode 2**（`P_actual_mode2`）：學長疑似的 Wobble 模型，保留但**不修改、不擴充、不以此為開發基礎**

## 關鍵檔案

- [generator.py](backend/bk4/generator.py) — HTM 正向模擬器（Mode 1 = 正確物理模型）
- [bk4_bridge.py](backend/core/bk4_bridge.py) — 橋接層（有 T_pivot/T_tool 混用 bug）
- [simulate.py](backend/routers/simulate.py) — POST /api/twin_simulate
- [request.py](backend/schemas/request.py) — Pydantic 請求模型
