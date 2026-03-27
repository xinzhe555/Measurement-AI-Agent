---
name: precos-lrt
description: >
  PREC·OS Laser R-Test (LRT) 量測原理與設計特性。
  當任務涉及以下內容時使用此 skill：LRT 量測概念、相對量測與歸零機制、
  zeroing_baseline、BK4 Cone 路徑定義、ball_x / ball_y / ball_z 設定、
  感測球與雷射頭的安裝位置、搖籃型 B Type 機台的運動鏈方向、
  Heidenhain 控制器 KinematicsOpt Cycle 450/451，
  或任何涉及 LRT 量測架設、路徑規劃的工作。
---

# Laser R-Test (LRT) 量測原理

## 1. 相對量測，第零點歸零

LRT 量測的是感測球從**第零點出發的相對位移**，而非絕對座標。

- 模型必須實作 `zeroing_baseline`：取第零點（C=0°, A=0°）的絕對誤差作為基線，後續所有點均減去此基線
- `P_table` 預補償機制正是為了在有誤差存在時確保第零點能在相對量測下正確歸零

## 2. 感測球與雷射頭安裝

- **玻璃球透鏡**：安裝於**工作臺**，隨 A/C 軸運動
- **雷射頭與感測頭**：整合裝置固定於**主軸端**，追蹤球心位置
- 數學模型描述的是「工作臺端球心在空間中的運動軌跡」
- `P_local = [ball_x, ball_y, ball_z, 1]` 代表球心在 C 軸轉盤座標系中的初始位置

## 3. 搖籃型（B Type）機台運動鏈

兩個旋轉軸（A、C）均在工作臺側，主軸不參與旋轉運動。

- A 軸：繞 X 軸旋轉（搖籃傾斜）
- C 軸：繞 Z 軸旋轉（轉盤旋轉）
- 運動鏈從球心出發，先經 C 軸轉動，再經 A 軸傾斜
- 在 HTM 中，C 軸誤差矩陣 E_AC 位於 T_C 之前，A 軸誤差矩陣 E_A 位於 T_A 之前

## 4. T_pivot 與 T_tool 的物理分離

- `T_pivot`：A 軸旋轉中心到 C 軸轉盤面的**機台固定幾何距離**，與刀具無關
- `T_tool`：C 軸轉盤面到感測球中心的距離，即每次架設 LRT 時量測的**刀長 L**
- LRT 刀長計算：`L = (主軸鼻端到機床距離) − (玻璃球座高度) − (感測器中心下降距離)`
- 兩者不可混用：T_tool 的力臂效應會放大角度誤差（阿貝效應）

## 5. BK4 Cone 路徑定義

```python
c_deg = linspace(0, 360, n_points)
a_deg = where(c_deg <= 180, c_deg / 2, (360 - c_deg) / 2)
```

- A 軸範圍：0° → 90° → 0°
- C 軸範圍：0° → 360°
- 標準設定：ball_x = 200 mm，n_points = 19（稀疏）或 360（密集）

## 6. 旋轉方向約定

```python
a_rot = -a_rad   # match_senior_a_dir=True
c_rot = -c_rad   # 固定
```

## 量測設定

- 機台：搖籃型 B Type AC 軸五軸工具機
- 控制器：Heidenhain（KinematicsOpt Cycle 450/451）
- 量測儀器：LRT（BK4 Cone 路徑）
- 感測球安裝於工作臺，雷射頭安裝於主軸端
