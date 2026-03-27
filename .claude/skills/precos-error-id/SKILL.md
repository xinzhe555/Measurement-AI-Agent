---
name: precos-error-id
description: >
  PREC·OS 靜態幾何誤差辨識系統（PIGEs + PDGEs）與非線性殘差學習。
  當任務涉及以下內容時使用此 skill：修改 static_analyzer.py、ai_residual_learner.py，
  討論 PIGEs 參數（XOC/YOC/ZOC/AOC/BOC/XOA/YOA/ZOA/BOA/COA）、
  PDGEs 參數（徑向跳動 Runout、軸向竄動、角度擺動 Wobble）、
  非線性最小二乘辨識、誤差解耦、背隙 Backlash、伺服不匹配 Servo Mismatch、
  MLP 殘差學習，或任何涉及誤差辨識與補償的工作。
---

# 靜態幾何誤差辨識系統

## 辨識參數（共 18 項，全部屬於靜態幾何誤差）

### PIGEs — 位置無關幾何誤差（10 項）

| 參數 | 物理意義 |
|------|----------|
| X_OC, Y_OC, Z_OC | C 軸旋轉中心的位移偏差 |
| A_OC, B_OC | C 軸的角度垂直度誤差 |
| X_OA, Y_OA, Z_OA | A 軸旋轉中心的位移偏差 |
| B_OA, C_OA | A 軸的角度垂直度誤差 |

### PDGEs — 位置相關幾何誤差（8 項）

| 參數 | 物理意義 |
|------|----------|
| C_Runout_X_Amp, C_Runout_X_Phase | C 軸 X 方向徑向跳動（振幅 + 相位）|
| C_Runout_Y_Amp, C_Runout_Y_Phase | C 軸 Y 方向徑向跳動（振幅 + 相位）|
| C_Runout_Z_Amp, C_Runout_Z_Freq | C 軸 Z 方向軸向竄動（振幅 + 頻率）|
| C_Wobble_A_Amp, C_Wobble_B_Amp | C 軸角度擺動（A 方向 + B 方向）|

**重要**：PDGEs 是靜態幾何誤差的一環，描述旋轉軸在不同角度位置下幾何偏差隨位置變化的規律（如轉盤的徑向跳動），物理上仍屬於機台的靜態幾何特性。不要與非線性殘差誤差混淆。

## 辨識方法

- 使用 `scipy.optimize.least_squares` 非線性最小二乘法
- 輸入：量測誤差波形（dx, dy, dz）+ 軸角度命令（a_cmd, c_cmd）
- 輸出：18 項辨識參數 + 殘差

## 非線性殘差層（HTM + PDGEs 辨識後的殘差）

PIGEs + PDGEs 辨識完成後的殘差，由 `ai_residual_learner.py` 處理：

- **背隙（Backlash）**：A 軸換向點（A=90°）附近的尖峰誤差，DBB 量測 + 非線性擬合
- **伺服不匹配（Servo Mismatch）**：A/C 軸 Kv 差異，速度 + 方向符號特徵 + MLP
- 框架已存在，待具體特徵工程設計

## 關鍵檔案

- [static_analyzer.py](backend/bk4/static_analyzer.py) — 靜態幾何誤差辨識器（PIGEs + PDGEs，非線性最小二乘）
- [ai_residual_learner.py](backend/bk4/ai_residual_learner.py) — MLP 殘差學習器（背隙、伺服不匹配）
- [pdge_generator.py](backend/bk4/pdge_generator.py) — PDGEs 生成器（徑向跳動、軸向竄動、角度擺動）
