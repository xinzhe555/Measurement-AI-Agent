"""
ai_residual_learner.py
AI 殘差學習層：學習物理層無法解析的非線性殘差
模擬目標：摩擦力非線性、伺服不匹配、象限突波等

使用規則模擬 AI 輸出（概念示意），並用 MLP 做殘差擬合驗證
"""
import numpy as np
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score


# ──────────────────────────────────────────────────────────────
# 規則模擬：在量測數據中注入非線性殘差（代表物理層無法補的部分）
# ──────────────────────────────────────────────────────────────

def inject_nonlinear_residuals(a_cmd, c_cmd, seed=42):
    """
    注入物理模型無法解析的非線性誤差（用於 Demo 驗證流程完整性）

    包含：
    1. 象限突波（Quadrant Spike）：速度方向反轉時的摩擦力突波
    2. 伺服不匹配（Servo Mismatch）：A/C 增益不匹配造成的幅值誤差
    3. 小幅隨機雜訊（量測雜訊）
    """
    rng = np.random.default_rng(seed)
    N = len(a_cmd)

    a_vel = np.gradient(a_cmd)
    c_vel = np.gradient(c_cmd)

    nonlinear = np.zeros((N, 3))

    # 1. 象限突波：速度過零點時出現尖峰
    a_sign_change = np.diff(np.sign(a_vel), prepend=np.sign(a_vel[0]))
    c_sign_change = np.diff(np.sign(c_vel), prepend=np.sign(c_vel[0]))
    spike_mask = (np.abs(a_sign_change) > 0) | (np.abs(c_sign_change) > 0)

    spike_amp = 0.008  # 8 um
    nonlinear[spike_mask, 0] += spike_amp * np.sign(a_vel[spike_mask] + 1e-10)
    nonlinear[spike_mask, 1] += spike_amp * np.sign(c_vel[spike_mask] + 1e-10)

    # 2. 伺服不匹配：與角速度大小相關的系統性誤差
    mismatch_gain = 0.003  # 3 um / (rad/sample)
    nonlinear[:, 0] += mismatch_gain * np.abs(a_vel) * np.sin(a_cmd)
    nonlinear[:, 1] += mismatch_gain * np.abs(c_vel) * np.cos(c_cmd)

    # 3. 量測雜訊（高頻，AI 層不應過擬合這部分）
    noise_std = 0.001  # 1 um
    nonlinear += rng.normal(0, noise_std, (N, 3))

    return nonlinear


# ──────────────────────────────────────────────────────────────
# AI 殘差學習器
# ──────────────────────────────────────────────────────────────

class AIResidualLearner:
    """
    用 MLP 學習物理補償後的非線性殘差

    特徵設計理念：
    - 角度的 sin/cos 編碼：捕捉週期性依賴
    - 速度與速度方向：捕捉摩擦力與伺服動態
    - 2倍頻編碼：捕捉高次諧波
    """

    def __init__(self):
        self.model = MLPRegressor(
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
        self.scaler_X = StandardScaler()
        self.scaler_y = StandardScaler()
        self.is_trained = False
        self.train_r2 = None

    def _build_features(self, a_cmd, c_cmd):
        """構建輸入特徵矩陣"""
        a_vel = np.gradient(a_cmd)
        c_vel = np.gradient(c_cmd)

        features = np.column_stack([
            # 角度編碼（週期性）
            np.cos(a_cmd), np.sin(a_cmd),
            np.cos(c_cmd), np.sin(c_cmd),
            np.cos(2 * c_cmd), np.sin(2 * c_cmd),
            # 速度（動態）
            a_vel, c_vel,
            # 速度方向（摩擦力符號）
            np.sign(a_vel + 1e-10),
            np.sign(c_vel + 1e-10),
            # 速度大小（伺服不匹配幅值）
            np.abs(a_vel), np.abs(c_vel),
            # 交叉項
            np.cos(a_cmd) * np.cos(c_cmd),
            np.sin(a_cmd) * np.sin(c_cmd),
        ])
        return features

    def train(self, a_cmd, c_cmd, residual_data, verbose=True):
        """
        訓練 AI 殘差模型

        Parameters
        ----------
        residual_data : ndarray (N, 3)  物理補償後的殘差，mm

        Returns
        -------
        ai_pred       : ndarray (N, 3)  AI 預測值
        final_residual: ndarray (N, 3)  AI 補償後的最終殘差
        """
        X = self._build_features(a_cmd, c_cmd)
        y = residual_data

        X_sc = self.scaler_X.fit_transform(X)
        y_sc = self.scaler_y.fit_transform(y)

        if verbose:
            print("\n" + "="*62)
            print("  [AI層] 殘差學習訓練中...")
            print("="*62)

        self.model.fit(X_sc, y_sc)

        y_pred_sc = self.model.predict(X_sc)
        ai_pred   = self.scaler_y.inverse_transform(y_pred_sc)
        final_res = residual_data - ai_pred

        self.train_r2 = r2_score(y, ai_pred)
        self.is_trained = True

        if verbose:
            rms_before = np.sqrt(np.mean(residual_data**2, axis=0)) * 1000
            rms_after  = np.sqrt(np.mean(final_res**2, axis=0))     * 1000
            print(f"  訓練 R² = {self.train_r2:.4f}  "
                  f"（迭代次數：{self.model.n_iter_}）")
            print(f"\n  {'軸':>4} | {'AI補償前':>10} | {'AI補償後':>10} | {'改善率':>8}")
            for i, ax in enumerate(['DX', 'DY', 'DZ']):
                b, a = rms_before[i], rms_after[i]
                rate = (1 - a / b) * 100 if b > 0 else 0
                print(f"  {ax:>4} | {b:>8.3f}um | {a:>8.3f}um | {rate:>6.1f}%")

        return ai_pred, final_res

    def predict(self, a_cmd, c_cmd):
        if not self.is_trained:
            raise RuntimeError("模型尚未訓練，請先呼叫 train()")
        X_sc = self.scaler_X.transform(self._build_features(a_cmd, c_cmd))
        return self.scaler_y.inverse_transform(self.model.predict(X_sc))