"""
dynamic_ai_learner.py
動態 AI 補償層 — 第三步（配合 nonlinear_residuals.py 的精確分解目標）

════════════════════════════════════════════════════════════════
【這個版本和舊版有什麼不同？】

舊版的問題：
    三個子模型雖然名義上負責不同誤差，但訓練目標都是從
    「整體殘差」手動加權切割出來的，例如 y_spike = residual * mask。
    這讓三個模型互相「搶著學」同一些東西，整體 R² 偏低。

這個版本的改進：
    利用 nonlinear_residuals.py 的 decompose_nonlinear_residuals()
    在「生成階段」就把非線性殘差分成三個獨立的 ground truth：
        .spike   → LSTM 的學習目標（只有反轉尖峰）
        .servo   → GRU 的學習目標（只有伺服不匹配）
        .hf_pdge → MLP 的學習目標（只有高頻 PDGEs）

    最終補償量 = LSTM_pred + GRU_pred + MLP_pred
    最終殘差   ≈ 量測雜訊（AI 層不應學這部分）

【模擬環境 vs 真實機台的差異】

    模擬環境（目前）：
        ground truth 來自 nonlinear_residuals.decompose_nonlinear_residuals()
        三種誤差的分解是精確的，AI 層的理論上限接近 100%。

    真實機台（未來）：
        需要用「訊號分離」技術從量測殘差中估計三種誤差的成分：
        - 反轉尖峰：在速度過零點附近取短窗口，其餘點設為 0
        - 伺服不匹配：對整體殘差做低通濾波（截止頻率 ≈ 伺服頻寬）
        - 高頻 PDGEs：用 C 軸角度做 FFT，找出 3× 以上的週期成分

════════════════════════════════════════════════════════════════

【特徵設計說明】

    LSTM / GRU 使用時序特徵（seq_len 步的滑動視窗，每步 8 維）：
        [a_cmd, c_cmd,             # 位置
         a_vel, c_vel,             # 速度
         a_acc, c_acc,             # 加速度（速度的差分）
         sign(a_vel), sign(c_vel)] # 速度方向符號

        為什麼需要加速度？
        速度從正到負的「過程」比「瞬間」更能預測尖峰：
        LSTM 能看到「速度在減小」這個前兆，提前 1-2 步預測換向。

    MLP 使用靜態特徵（單時間步，14 維）：
        高頻 PDGEs 只和「當前角度」有關，無需時序記憶。
        sin/cos 編碼讓 MLP 能學習任意週期函數。

════════════════════════════════════════════════════════════════

依賴：
    必要：numpy, scikit-learn, nonlinear_residuals.py（同目錄）
    可選：torch（沒有時 LSTM/GRU 自動降級為線性近似）
"""

import numpy as np
import warnings
warnings.filterwarnings('ignore')

# ── PyTorch：有就用完整版，沒有就降級 ───────────────────────────
try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False
    print("[警告] PyTorch 未安裝，LSTM/GRU 將使用線性近似版本。"
          "\n       完整功能請執行：pip install torch")

from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing  import StandardScaler
from sklearn.metrics         import r2_score


# ══════════════════════════════════════════════════════════════
#  特徵構建函式
# ══════════════════════════════════════════════════════════════

def build_static_features(a_cmd: np.ndarray,
                           c_cmd: np.ndarray) -> np.ndarray:
    """
    靜態特徵矩陣，供 MLP（高頻 PDGEs）使用。維度：(N, 14)。

    設計邏輯：
        高頻 PDGEs 是「角度相關」誤差，用 sin/cos 做角度編碼
        讓 MLP 能學習任意週期函數。
        二倍頻編碼（cos(2θ), sin(2θ)）幫助 MLP 捕捉 2× 以上的諧波。
        速度特徵保留是為了讓 MLP 吸收 LSTM/GRU 沒學到的殘餘。
    """
    a_vel = np.gradient(a_cmd)
    c_vel = np.gradient(c_cmd)

    return np.column_stack([
        # 1× 角度編碼（基頻週期）
        np.cos(a_cmd), np.sin(a_cmd),
        np.cos(c_cmd), np.sin(c_cmd),
        # 2× 角度編碼（捕捉二次諧波和軸承 2× 跳動）
        np.cos(2 * c_cmd), np.sin(2 * c_cmd),
        # 速度資訊
        a_vel, c_vel,
        np.sign(a_vel + 1e-10),   # 速度方向（+1 或 -1）
        np.sign(c_vel + 1e-10),
        np.abs(a_vel),             # 速度大小
        np.abs(c_vel),
        # 交叉項（捕捉 A/C 同動時的交互效應）
        np.cos(a_cmd) * np.cos(c_cmd),
        np.sin(a_cmd) * np.sin(c_cmd),
    ])   # (N, 14)


def build_sequence_features(a_cmd:   np.ndarray,
                              c_cmd:   np.ndarray,
                              seq_len: int = 10) -> np.ndarray:
    """
    時序特徵矩陣，供 LSTM（反轉尖峰）和 GRU（伺服不匹配）使用。
    維度：(N, seq_len, 8)。

    滑動視窗邏輯：
        對每個時間步 i，取過去 seq_len 步的運動狀態作為輸入。
        邊界處理：不足 seq_len 步時，前端補零（zero-padding）。

    輸入特徵（每步 8 維）：
        [a_cmd, c_cmd,              # 位置（角度）
         a_vel, c_vel,              # 速度（有符號）
         a_acc, c_acc,              # 加速度
         sign(a_vel), sign(c_vel)]  # 速度方向符號
    """
    N     = len(a_cmd)
    a_vel = np.gradient(a_cmd)
    c_vel = np.gradient(c_cmd)
    a_acc = np.gradient(a_vel)   # 速度的差分 = 加速度
    c_acc = np.gradient(c_vel)

    step_feat = np.column_stack([
        a_cmd, c_cmd,
        a_vel, c_vel,
        a_acc, c_acc,
        np.sign(a_vel + 1e-10),
        np.sign(c_vel + 1e-10),
    ])   # (N, 8)

    # 滑動視窗：對每個時間步，收集過去 seq_len 步
    X_seq = np.zeros((N, seq_len, step_feat.shape[1]))
    for i in range(N):
        start  = max(0, i - seq_len + 1)
        window = step_feat[start : i + 1]   # 長度 min(i+1, seq_len)
        X_seq[i, -len(window):] = window     # 靠右對齊，左邊補零
    return X_seq   # (N, seq_len, 8)


# ══════════════════════════════════════════════════════════════
#  PyTorch 模型定義
# ══════════════════════════════════════════════════════════════

if _TORCH_AVAILABLE:

    class _LSTMModel(nn.Module):
        """
        反轉尖峰專用 LSTM。

        架構選擇理由：
            LSTM 比 GRU 多「遺忘門」，能更精確控制要記住哪些資訊。
            反轉尖峰需要記住「速度在減小」，等到速度過零時觸發預測。
            2 層 LSTM：第一層學速度模式，第二層學尖峰觸發條件。
            hidden=32：在精度和過擬合（訓練集只有 360 點）之間的平衡點。

        輸入：(batch, seq_len, 8)
        輸出：(batch, 3)  DX/DY/DZ 三軸的尖峰預測值（mm）
        """
        def __init__(self, input_size=8, hidden=32,
                     num_layers=2, output=3):
            super().__init__()
            self.lstm = nn.LSTM(
                input_size, hidden, num_layers,
                batch_first=True,
                dropout=0.15   # 防止過擬合
            )
            self.fc = nn.Sequential(
                nn.Linear(hidden, 16),
                nn.Tanh(),
                nn.Dropout(0.1),
                nn.Linear(16, output),
            )

        def forward(self, x):
            out, _ = self.lstm(x)
            return self.fc(out[:, -1, :])   # 只取最後一步輸出

    class _GRUModel(nn.Module):
        """
        伺服不匹配專用 GRU。

        架構選擇理由：
            GRU 比 LSTM 少一個門，參數更少，訓練更快。
            伺服不匹配是「緩慢變化」的訊號，不需要 LSTM 那樣精細的記憶，
            GRU 已足夠。
            1 層，hidden=24：伺服不匹配的時間尺度長，不需要深層特徵。

        輸入：(batch, seq_len, 8)
        輸出：(batch, 3)
        """
        def __init__(self, input_size=8, hidden=24,
                     num_layers=1, output=3):
            super().__init__()
            self.gru = nn.GRU(
                input_size, hidden, num_layers,
                batch_first=True,
                dropout=0.0   # 只有 1 層，加 dropout 沒用
            )
            self.fc = nn.Sequential(
                nn.Linear(hidden, 12),
                nn.Tanh(),
                nn.Linear(12, output),
            )

        def forward(self, x):
            out, _ = self.gru(x)
            return self.fc(out[:, -1, :])


# ══════════════════════════════════════════════════════════════
#  NumPy 降級近似（無 PyTorch 時）
# ══════════════════════════════════════════════════════════════

class _LinearSeqApproximator:
    """
    沒有 PyTorch 時的降級方案。

    原理：把時序特徵 (N, seq_len, 8) 攤平成 (N, seq_len*8)，
    用 np.linalg.lstsq 求出線性映射，等同於對過去幾步做加權平均。
    能捕捉趨勢，但捕捉不了非線性的尖峰形狀。
    """
    def __init__(self):
        self.weights = None
        self.bias    = None

    def fit(self, X_seq: np.ndarray, y: np.ndarray):
        N     = X_seq.shape[0]
        X_aug = np.hstack([X_seq.reshape(N, -1), np.ones((N, 1))])
        W     = np.linalg.lstsq(X_aug, y, rcond=None)[0]
        self.weights = W[:-1]
        self.bias    = W[-1]

    def predict(self, X_seq: np.ndarray) -> np.ndarray:
        if self.weights is None:
            return np.zeros((X_seq.shape[0], 3))
        return X_seq.reshape(X_seq.shape[0], -1) @ self.weights + self.bias


# ══════════════════════════════════════════════════════════════
#  主類別：DynamicAILearner
# ══════════════════════════════════════════════════════════════

class DynamicAILearner:
    """
    三模型動態 AI 補償層。

    ┌─────────────────────────────────────────────────────┐
    │  子模型        │ 學習目標     │ 物理來源              │
    ├─────────────────────────────────────────────────────┤
    │  LSTM（時序）   │ .spike      │ 靜/動摩擦力切換尖峰   │
    │  GRU （時序）   │ .servo      │ A/C 軸 Kv 不匹配      │
    │  MLP （靜態）   │ .hf_pdge   │ 軸承高次諧波           │
    └─────────────────────────────────────────────────────┘

    最終補償量 = LSTM_pred + GRU_pred + MLP_pred
    最終殘差   ≈ 量測雜訊（不可補償項）

    使用流程（模擬環境）：
        from nonlinear_residuals import decompose_nonlinear_residuals
        components = decompose_nonlinear_residuals(a_cmd, c_cmd)
        learner    = DynamicAILearner()
        metrics    = learner.train(a_cmd, c_cmd, components)

    使用流程（真實機台，只有整體殘差）：
        metrics = learner.train(a_cmd, c_cmd, total_residual_array)
    """

    def __init__(self,
                 seq_len:     int   = 10,
                 lstm_hidden: int   = 32,
                 gru_hidden:  int   = 24,
                 epochs:      int   = 80,
                 lr:          float = 5e-3,
                 use_lstm:    bool  = True,
                 use_gru:     bool  = True,
                 use_mlp:     bool  = True):
        """
        Parameters
        ----------
        seq_len     : LSTM/GRU 時序視窗長度（步）。
                      10 步 × 4ms/步 = 40ms，足夠捕捉反轉尖峰前兆。
        lstm_hidden : LSTM 隱藏單元數。32 是精度和過擬合的平衡點。
        gru_hidden  : GRU 隱藏單元數。24 比 LSTM 小，任務更簡單。
        epochs      : 最大訓練迭代次數（有 early stopping，通常不會跑滿）。
        lr          : Adam 初始學習率。5e-3 對小數據集收斂較快。
        use_lstm/gru/mlp : 可獨立啟用/停用，方便消融實驗。
        """
        self.seq_len     = seq_len
        self.lstm_hidden = lstm_hidden
        self.gru_hidden  = gru_hidden
        self.epochs      = epochs
        self.lr          = lr
        self.use_lstm    = use_lstm
        self.use_gru     = use_gru
        self.use_mlp     = use_mlp

        self._lstm = None
        self._gru  = None
        self._mlp: MLPRegressor | None = None

        # 標準化器：神經網路對輸入量級敏感，標準化後收斂更快
        self._sc_seq_X   = StandardScaler()   # 時序特徵（LSTM/GRU 共用）
        self._sc_spike_y = StandardScaler()   # LSTM 輸出標準化
        self._sc_servo_y = StandardScaler()   # GRU 輸出標準化
        self._sc_mlp_X   = StandardScaler()   # MLP 輸入標準化
        self._sc_mlp_y   = StandardScaler()   # MLP 輸出標準化

        self.is_trained = False
        self.metrics: dict = {}

    # ──────────────────────────────────────────────────────────
    #  訓練
    # ──────────────────────────────────────────────────────────

    def train(self,
              a_cmd:         np.ndarray,
              c_cmd:         np.ndarray,
              residual_input,
              verbose:       bool = True) -> dict:
        """
        訓練三個子模型。

        Parameters
        ----------
        residual_input : 有兩種格式：
            1. NonlinearComponents（推薦，模擬環境）：
               有精確的 .spike / .servo / .hf_pdge 分解，
               每個子模型用對應的 ground truth 訓練。

            2. ndarray (N, 3)（真實機台，只有整體殘差）：
               退回「加權分離」近似做法。
        """
        if verbose:
            print("\n" + "=" * 60)
            print("  [動態AI層] 三模型分層訓練啟動")
            print("=" * 60)

        # 判斷輸入格式
        has_decomposed = hasattr(residual_input, 'spike')

        if has_decomposed:
            # 精確模式：直接用 ground truth 分解
            # .noise 不進入訓練，避免 AI 學到不可消除的雜訊
            y_spike   = residual_input.spike
            y_servo   = residual_input.servo
            y_hf_pdge = residual_input.hf_pdge
            y_total   = residual_input.total
            if verbose:
                print("  模式：精確分解（NonlinearComponents ground truth）")
        else:
            # 近似模式：從整體殘差手動分離（真實機台的替代方案）
            y_total   = residual_input
            a_vel     = np.gradient(a_cmd)
            c_vel     = np.gradient(c_cmd)
            vel_mag   = np.sqrt(a_vel**2 + c_vel**2)

            # 反轉尖峰：速度符號改變點附近的殘差
            a_flip     = np.abs(np.diff(np.sign(a_vel), prepend=np.sign(a_vel[0]))) > 0
            c_flip     = np.abs(np.diff(np.sign(c_vel), prepend=np.sign(c_vel[0]))) > 0
            spike_mask = a_flip | c_flip
            y_spike    = y_total * spike_mask[:, None]

            # 伺服不匹配：與速度大小相關的成分
            w          = vel_mag / (vel_mag.max() + 1e-10)
            y_servo    = y_total * w[:, None]

            # 高頻 PDGEs：整體殘差（MLP 學剩餘部分）
            y_hf_pdge  = y_total

            if verbose:
                print("  模式：近似分離（整體殘差加權估計）")

        # 構建特徵矩陣
        X_seq    = build_sequence_features(a_cmd, c_cmd, self.seq_len)
        X_static = build_static_features(a_cmd, c_cmd)

        # 時序特徵標準化（LSTM 和 GRU 共用同一個 scaler，輸入空間一致）
        N, S, F  = X_seq.shape
        X_flat   = X_seq.reshape(N, -1)
        X_scaled = self._sc_seq_X.fit_transform(X_flat).reshape(N, S, F)

        self.metrics = {}

        # ── 子模型 1：LSTM 學反轉尖峰 ─────────────────────────────
        if self.use_lstm:
            if verbose:
                rms = np.sqrt(np.mean(y_spike**2)) * 1000
                print(f"\n  [1/3] LSTM 訓練（目標：反轉尖峰，RMS = {rms:.3f} μm）")
            if _TORCH_AVAILABLE:
                self._lstm, r2 = self._train_torch(
                    _LSTMModel(F, self.lstm_hidden),
                    X_scaled, y_spike, self._sc_spike_y,
                    name="LSTM", verbose=verbose
                )
            else:
                self._lstm = _LinearSeqApproximator()
                self._lstm.fit(X_seq, y_spike)
                r2 = float(r2_score(y_spike, self._lstm.predict(X_seq)))
                if verbose:
                    print(f"  LSTM（線性降級）R² = {r2:.4f}")
            self.metrics['lstm_r2'] = r2

        # ── 子模型 2：GRU 學伺服不匹配 ────────────────────────────
        if self.use_gru:
            if verbose:
                rms = np.sqrt(np.mean(y_servo**2)) * 1000
                print(f"\n  [2/3] GRU 訓練（目標：伺服不匹配，RMS = {rms:.3f} μm）")
            if _TORCH_AVAILABLE:
                self._gru, r2 = self._train_torch(
                    _GRUModel(F, self.gru_hidden),
                    X_scaled, y_servo, self._sc_servo_y,
                    name="GRU", verbose=verbose
                )
            else:
                self._gru = _LinearSeqApproximator()
                self._gru.fit(X_seq, y_servo)
                r2 = float(r2_score(y_servo, self._gru.predict(X_seq)))
                if verbose:
                    print(f"  GRU（線性降級）R² = {r2:.4f}")
            self.metrics['gru_r2'] = r2

        # ── 子模型 3：MLP 學高頻 PDGEs ────────────────────────────
        if self.use_mlp:
            if verbose:
                rms = np.sqrt(np.mean(y_hf_pdge**2)) * 1000
                print(f"\n  [3/3] MLP 訓練（目標：高頻 PDGEs，RMS = {rms:.3f} μm）")

            X_sc = self._sc_mlp_X.fit_transform(X_static)
            y_sc = self._sc_mlp_y.fit_transform(y_hf_pdge)

            # 超參數選擇：
            # (128,64,32)：三層漸縮，捕捉非線性週期函數
            # tanh：輸出有界，比 relu 更適合預測有正負的誤差值
            # early_stopping：防止在小數據集上過擬合
            mlp = MLPRegressor(
                hidden_layer_sizes=(128, 64, 32),
                activation='tanh',
                max_iter=3000,
                random_state=42,
                learning_rate_init=0.001,
                early_stopping=True,
                validation_fraction=0.15,
                n_iter_no_change=30,
                tol=1e-6,
            )
            mlp.fit(X_sc, y_sc)
            y_pred = self._sc_mlp_y.inverse_transform(mlp.predict(X_sc))
            self._mlp = mlp
            r2 = float(r2_score(y_hf_pdge, y_pred))
            self.metrics['mlp_r2'] = r2
            if verbose:
                print(f"  MLP R² = {r2:.4f}，迭代 = {mlp.n_iter_}")

        # ── 整體效果評估 ──────────────────────────────────────────
        total_pred = self.predict(
            a_cmd, c_cmd,
            _X_seq_scaled=X_scaled,
            _X_static=X_static,
        )
        final_res  = y_total - total_pred

        rms_before  = np.sqrt(np.mean(y_total**2,   axis=0)) * 1000
        rms_after   = np.sqrt(np.mean(final_res**2, axis=0)) * 1000
        improvement = (
            (1 - rms_after / np.where(rms_before > 0, rms_before, 1)) * 100
        )

        self.metrics.update({
            'rms_before_um':   rms_before.tolist(),
            'rms_after_um':    rms_after.tolist(),
            'improvement_pct': improvement.tolist(),
        })
        self.is_trained = True

        if verbose:
            self._print_summary()

        return self.metrics

    # ──────────────────────────────────────────────────────────
    #  預測
    # ──────────────────────────────────────────────────────────

    def predict(self,
                a_cmd:          np.ndarray,
                c_cmd:          np.ndarray,
                _X_seq_scaled:  np.ndarray | None = None,
                _X_static:      np.ndarray | None = None) -> np.ndarray:
        """
        預測三個子模型補償量加總。

        Returns
        -------
        total_pred : ndarray (N, 3)  補償預測值（mm）
                     套用：compensated_residual = original_residual - total_pred
        """
        N = len(a_cmd)
        total = np.zeros((N, 3))

        if _X_seq_scaled is None:
            X_seq = build_sequence_features(a_cmd, c_cmd, self.seq_len)
            N2, S, F = X_seq.shape
            X_flat = X_seq.reshape(N2, -1)
            _X_seq_scaled = self._sc_seq_X.transform(X_flat).reshape(N2, S, F)

        if _X_static is None:
            _X_static = build_static_features(a_cmd, c_cmd)

        if self._lstm is not None and self.use_lstm:
            total += self._predict_seq(self._lstm, _X_seq_scaled, self._sc_spike_y)

        if self._gru is not None and self.use_gru:
            total += self._predict_seq(self._gru, _X_seq_scaled, self._sc_servo_y)

        if self._mlp is not None and self.use_mlp:
            X_sc   = self._sc_mlp_X.transform(_X_static)
            y_pred = self._mlp.predict(X_sc)
            total += self._sc_mlp_y.inverse_transform(y_pred)

        return total

    # ──────────────────────────────────────────────────────────
    #  內部工具
    # ──────────────────────────────────────────────────────────

    def _train_torch(self, model, X_seq, y_raw, scaler_y,
                     name="", verbose=True):
        """
        PyTorch 訓練迴圈（LSTM 和 GRU 共用）。

        訓練策略：
        - Adam：對稀疏梯度表現好（尖峰只在少數點）
        - ReduceLROnPlateau：loss 不改善時自動降低學習率
        - Early stopping（patience=20）：防止過擬合
        - Gradient clipping（1.0）：防止 RNN 的梯度爆炸
        """
        y_sc  = scaler_y.fit_transform(y_raw)
        X_t   = torch.FloatTensor(X_seq)
        y_t   = torch.FloatTensor(y_sc)

        dataset   = TensorDataset(X_t, y_t)
        loader    = DataLoader(dataset, batch_size=64, shuffle=True)
        optimizer = torch.optim.Adam(model.parameters(), lr=self.lr)
        criterion = nn.MSELoss()
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, patience=10, factor=0.5, verbose=False
        )

        best_loss  = float('inf')
        no_improve = 0
        patience   = 20

        for epoch in range(self.epochs):
            model.train()
            epoch_loss = 0.0
            for xb, yb in loader:
                optimizer.zero_grad()
                loss = criterion(model(xb), yb)
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                epoch_loss += loss.item()

            avg_loss = epoch_loss / len(loader)
            scheduler.step(avg_loss)

            if avg_loss < best_loss - 1e-6:
                best_loss  = avg_loss
                no_improve = 0
            else:
                no_improve += 1
            if no_improve >= patience:
                if verbose:
                    print(f"  {name} early stop @epoch {epoch+1}，"
                          f"best_loss={best_loss:.6f}")
                break

        model.eval()
        with torch.no_grad():
            y_pred_sc = model(X_t).numpy()
        y_pred = scaler_y.inverse_transform(y_pred_sc)
        r2     = float(r2_score(y_raw, y_pred))

        if verbose:
            print(f"  {name} R² = {r2:.4f}")

        return model, r2

    def _predict_seq(self, model, X_seq_scaled, scaler_y) -> np.ndarray:
        """時序模型推理（自動判斷 PyTorch 或線性降級）"""
        if _TORCH_AVAILABLE and isinstance(model, nn.Module):
            model.eval()
            with torch.no_grad():
                y_sc = model(torch.FloatTensor(X_seq_scaled)).numpy()
            return scaler_y.inverse_transform(y_sc)
        else:
            # 線性降級版不需要 scaler_y
            return model.predict(X_seq_scaled)

    def _print_summary(self):
        m = self.metrics
        print("\n" + "─" * 60)
        print("  [動態AI層] 三模型整體補償效果")
        print(f"  {'軸':>4} | {'補償前 μm':>10} | {'補償後 μm':>10} | {'改善率':>8}")
        print("  " + "─" * 50)
        for i, ax in enumerate(['DX', 'DY', 'DZ']):
            b = m['rms_before_um'][i]
            a = m['rms_after_um'][i]
            r = m['improvement_pct'][i]
            quality = "OK" if r > 50 else "?"
            print(f"  {ax:>4} | {b:>10.3f} | {a:>10.3f} | {r:>6.1f}% {quality}")

        models_info = []
        if self.use_lstm:
            backend = 'torch' if _TORCH_AVAILABLE else 'linear'
            models_info.append(f"LSTM(R²={m.get('lstm_r2',0):.3f},{backend})")
        if self.use_gru:
            backend = 'torch' if _TORCH_AVAILABLE else 'linear'
            models_info.append(f"GRU(R²={m.get('gru_r2',0):.3f},{backend})")
        if self.use_mlp:
            models_info.append(f"MLP(R²={m.get('mlp_r2',0):.3f})")

        print(f"\n  子模型：{' + '.join(models_info)}")
        print("─" * 60)

    def to_dict(self) -> dict:
        return {
            'is_trained':      self.is_trained,
            'torch_available': _TORCH_AVAILABLE,
            'models_enabled':  {'lstm': self.use_lstm, 'gru': self.use_gru,
                                'mlp': self.use_mlp},
            'metrics': self.metrics,
        }


# ══════════════════════════════════════════════════════════════
#  獨立驗證腳本：python dynamic_ai_learner.py
# ══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from nonlinear_residuals import (
        decompose_nonlinear_residuals,
        analyze_residual_components,
    )

    print("\n" + "★" * 30)
    print("  DynamicAILearner 驗證（精確分解 vs 近似分離）")
    print("★" * 30)

    t     = np.linspace(0, 4 * np.pi, 360)
    a_cmd = np.deg2rad(30 * np.sin(t))
    c_cmd = np.deg2rad(90 * np.sin(2 * t))

    components = decompose_nonlinear_residuals(a_cmd, c_cmd)
    stats      = analyze_residual_components(components)

    print("\n各成分 RMS（DX）：")
    print(f"  反轉尖峰:   {stats['spike_rms_um'][0]:.3f} μm（LSTM 目標）")
    print(f"  伺服不匹配: {stats['servo_rms_um'][0]:.3f} μm（GRU 目標）")
    print(f"  高頻 PDGE:  {stats['hf_pdge_rms_um'][0]:.3f} μm（MLP 目標）")
    print(f"  量測雜訊:   {stats['noise_rms_um'][0]:.3f} μm（不訓練）")
    print(f"  總殘差:     {stats['total_rms_um'][0]:.3f} μm")

    # 測試一：精確模式
    print("\n" + "─" * 40)
    print("  測試一：精確模式（NonlinearComponents）")
    print("─" * 40)
    l1 = DynamicAILearner(epochs=60, use_lstm=_TORCH_AVAILABLE,
                           use_gru=_TORCH_AVAILABLE, use_mlp=True)
    m1 = l1.train(a_cmd, c_cmd, components, verbose=True)

    # 測試二：近似模式
    print("\n" + "─" * 40)
    print("  測試二：近似模式（整體殘差）")
    print("─" * 40)
    l2 = DynamicAILearner(epochs=60, use_lstm=_TORCH_AVAILABLE,
                           use_gru=_TORCH_AVAILABLE, use_mlp=True)
    m2 = l2.train(a_cmd, c_cmd, components.total, verbose=True)

    print("\n" + "=" * 60)
    print("  精確 vs 近似 比較（DX 改善率）")
    print(f"  精確模式：{m1['improvement_pct'][0]:.1f}%")
    print(f"  近似模式：{m2['improvement_pct'][0]:.1f}%")
    diff = m1['improvement_pct'][0] - m2['improvement_pct'][0]
    print(f"  差距：{diff:.1f}%（差距越小代表近似分離越準確）")
    print("=" * 60)
    print("\n✅ 驗證完成")
