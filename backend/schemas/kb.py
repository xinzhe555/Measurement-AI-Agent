"""
schemas/kb.py
知識庫管理的請求/回應格式
"""
from pydantic import BaseModel
from typing import Optional, List


class KBFileInfo(BaseModel):
    """單一知識庫檔案的狀態"""
    file_id: str
    filename: str
    equipment: str
    upload_time: str
    status: str  # uploaded | converting | chunking | vectorizing | extracting | done | error
    error_message: Optional[str] = None
    chunk_count: Optional[int] = None


class KBFileListResponse(BaseModel):
    """檔案清單回應"""
    files: List[KBFileInfo]
