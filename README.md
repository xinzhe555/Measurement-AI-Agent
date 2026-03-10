# PREC·OS — BK4 五軸誤差診斷系統

## 專案結構

```
prec-os/
├── backend/                    ← FastAPI（Python）
│   ├── main.py                 ← 啟動入口
│   ├── routers/
│   │   ├── analyze.py          ← POST /api/analyze
│   │   └── session.py          ← POST /api/session/chat
│   ├── schemas/
│   │   ├── request.py          ← 請求格式
│   │   └── response.py         ← 回應格式
│   ├── core/
│   │   └── bk4_bridge.py       ← 橋接你的分析模組
│   ├── bk4/                    ← 你的現有程式碼（複製進來）
│   │   ├── pige_full_generator.py
│   │   ├── pdge_generator.py
│   │   ├── generator.py
│   │   ├── physical_analyzer.py
│   │   └── ai_residual_learner.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                   ← Next.js 14（TypeScript）
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx            ← 導向 /dashboard
│   │   ├── globals.css         ← 設計語言 Token
│   │   └── dashboard/
│   │       └── page.tsx        ← 主介面（三欄佈局）
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Header.tsx
│   │   │   ├── LeftPanel.tsx
│   │   │   └── RightPanel.tsx
│   │   ├── chat/
│   │   │   ├── MessageList.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   └── InputBar.tsx
│   │   └── cards/
│   │       ├── _CardShell.tsx
│   │       ├── PigeResultCard.tsx
│   │       ├── PdgeResultCard.tsx
│   │       ├── RmsCompareCard.tsx
│   │       └── AgentCard.tsx
│   ├── lib/
│   │   ├── api.ts              ← 呼叫後端的函式
│   │   └── types.ts            ← TypeScript 型別
│   ├── package.json
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   ├── next.config.js
│   └── Dockerfile
│
├── .env.local                  ← 本機開發環境變數
├── .env.production             ← 部署環境變數（改成你的網域）
├── docker-compose.yml          ← 一鍵部署（選用）
└── README.md
```

---

## 階段一：碩士 Demo（本機）

### 步驟 1 — 複製你現有的 Python 模組

```bash
cp bk4_system/pige_full_generator.py  prec-os/backend/bk4/
cp bk4_system/pdge_generator.py       prec-os/backend/bk4/
cp bk4_system/generator.py            prec-os/backend/bk4/
cp bk4_system/physical_analyzer.py    prec-os/backend/bk4/
cp bk4_system/ai_residual_learner.py  prec-os/backend/bk4/
```

### 步驟 2 — 啟動後端（終端機 A）

```bash
cd prec-os/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

成功後會看到：
```
INFO: Uvicorn running on http://0.0.0.0:8000
```

確認 API 正常：瀏覽器打開 `http://localhost:8000/docs`
（FastAPI 自動生成的互動式 API 文件）

### 步驟 3 — 啟動前端（終端機 B）

```bash
cd prec-os/frontend
npm install
npm run dev
```

成功後瀏覽器打開 `http://localhost:3000`

---

## 階段二：部署到自己的伺服器 + 網域

### 前置條件
- Ubuntu 22.04 伺服器
- 已購買網域，DNS A Record 指向伺服器 IP
- 伺服器安裝：`nginx`, `python3`, `node 20`, `certbot`

### 步驟

```bash
# 1. clone 到伺服器
git clone https://github.com/yourname/prec-os.git
cd prec-os

# 2. 編輯 .env.production，填入你的網域
nano .env.production

# 3. 後端（用 systemd 背景執行）
cd backend
pip install -r requirements.txt
# 建立 systemd service（參考下方設定）

# 4. 前端 build
cd frontend
npm install && npm run build

# 5. 申請 SSL 憑證
certbot --nginx -d your-domain.com -d api.your-domain.com

# 6. 設定 Nginx（參考下方設定）
```

### Nginx 設定範例（/etc/nginx/sites-available/prec-os）

```nginx
# 前端
server {
    listen 443 ssl;
    server_name your-domain.com;
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
    }
}

# 後端 API
server {
    listen 443 ssl;
    server_name api.your-domain.com;
    location / {
        proxy_pass http://localhost:8000;
    }
}
```

---

## 階段三：USB 安裝版（Electron 打包）

> 在階段二完成並穩定後才需要進行這步。

```bash
# 在 frontend/ 加入 Electron
npm install --save-dev electron electron-builder

# 用 PyInstaller 把後端打包成執行檔
pip install pyinstaller
cd backend
pyinstaller --onefile main.py

# Electron 啟動時自動在背景起動 Python 執行檔
# 詳細設定屆時提供
```

---

## API 端點速查

| 方法 | 路徑 | 說明 |
|------|------|------|
| POST | `/api/analyze` | 執行完整 PIGE+PDGE+AI 分析 |
| POST | `/api/session/chat` | 聊天問答（引用分析結果） |
| POST | `/api/session/save/:id` | 儲存 session |
| GET  | `/api/session/load/:id` | 載入 session |
| GET  | `/health` | 後端健康檢查 |

完整 API 文件：`http://localhost:8000/docs`（FastAPI Swagger UI）
