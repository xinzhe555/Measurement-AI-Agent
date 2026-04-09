"""
main.py
FastAPI 應用程式入口點

啟動方式：
    uvicorn main:app --reload --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

load_dotenv()

from routers.analyze import router as analyze_router
from routers.session import router as session_router
from routers.simulate import router as simulate_router
from routers.kb import router as kb_router

app = FastAPI(
    title="PREC·OS Backend",
    description="BK4 五軸誤差診斷系統 API",
    version="2.1.0",
)

# ── CORS 設定 ─────────────────────────────────────────────────
# 開發時允許 Next.js dev server（port 3000）跨域呼叫
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 路由 ──────────────────────────────────────────────────────
app.include_router(analyze_router)
app.include_router(session_router)
app.include_router(simulate_router)
app.include_router(kb_router)


@app.get("/health")
async def health():
    """健康檢查，部署時 Nginx / Docker 用"""
    return {"status": "ok", "version": "2.1.0"}
