"""
kb_pipeline.py
知識庫處理 Pipeline：PDF → Markdown → Chunks → FAISS + Neo4j

被 routers/kb.py 的 BackgroundTask 呼叫。
"""
import json
import os
import re
import shutil
import traceback
from datetime import datetime

# ── 路徑常數 ─────────────────────────────────────────────────────
BASE_DIR       = os.path.dirname(__file__)
KB_FILES_DIR   = os.path.join(BASE_DIR, "kb_files")
KB_DATA_DIR    = os.path.join(BASE_DIR, "kb_data")
RAG_DATA_DIR   = os.path.join(BASE_DIR, "rag_data")
MANUALS_JSON   = os.path.join(RAG_DATA_DIR, "manuals.json")
STATUS_JSON    = os.path.join(KB_DATA_DIR, "status.json")
# 前端 public 目錄（圖片需要放在這裡才能被瀏覽器存取）
FRONTEND_IMG   = os.path.join(BASE_DIR, "..", "frontend", "public", "images", "kb")


# ═══════════════════════════════════════════════════════════════════
#  狀態管理
# ═══════════════════════════════════════════════════════════════════

def _read_status() -> dict:
    os.makedirs(KB_DATA_DIR, exist_ok=True)
    if os.path.exists(STATUS_JSON):
        with open(STATUS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _write_status(data: dict):
    os.makedirs(KB_DATA_DIR, exist_ok=True)
    with open(STATUS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _update_file_status(file_id: str, **kwargs):
    """更新單一檔案的狀態欄位"""
    all_status = _read_status()
    if file_id in all_status:
        all_status[file_id].update(kwargs)
        _write_status(all_status)


def register_upload(file_id: str, filename: str, equipment: str):
    """註冊一筆新上傳"""
    all_status = _read_status()
    all_status[file_id] = {
        "file_id": file_id,
        "filename": filename,
        "equipment": equipment,
        "upload_time": datetime.now().isoformat(timespec="seconds"),
        "status": "uploaded",
        "error_message": None,
        "chunk_count": None,
    }
    _write_status(all_status)


def get_all_files() -> list:
    """回傳所有檔案狀態"""
    return list(_read_status().values())


def remove_file_status(file_id: str):
    all_status = _read_status()
    all_status.pop(file_id, None)
    _write_status(all_status)


# ═══════════════════════════════════════════════════════════════════
#  Stage 1：PDF → Markdown
# ═══════════════════════════════════════════════════════════════════

def _stage_pdf_to_markdown(file_id: str, pdf_path: str) -> str:
    """用 PyMuPDF (fitz) 將 PDF 轉為 Markdown，回傳 md 檔路徑"""
    import fitz

    _update_file_status(file_id, status="converting")

    file_dir = os.path.join(KB_FILES_DIR, file_id)
    img_dir  = os.path.join(file_dir, "images")
    os.makedirs(img_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    md_parts = []
    img_counter = 0
    extracted_xrefs = set()  # 避免重複提取同一張圖

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)

        # ── 先提取此頁所有圖片（用 get_images，最可靠的方式）──
        page_img_refs = []
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            if xref in extracted_xrefs:
                continue
            try:
                base_img = doc.extract_image(xref)
                w, h = base_img["width"], base_img["height"]
                if w > 50 and h > 50:
                    ext = base_img["ext"]
                    img_name = f"p{page_num + 1}_img_{img_counter:04d}.{ext}"
                    img_path = os.path.join(img_dir, img_name)
                    with open(img_path, "wb") as f_img:
                        f_img.write(base_img["image"])
                    page_img_refs.append(
                        f"![page{page_num + 1}_img{img_counter}](/images/kb/{file_id}/{img_name})"
                    )
                    img_counter += 1
                    extracted_xrefs.add(xref)
            except Exception:
                pass

        # ── 提取此頁文字 ──
        blocks = page.get_text("dict", sort=True)["blocks"]
        page_text_parts = []

        for block in blocks:
            if block["type"] != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                line_text = "".join(s["text"] for s in spans).strip()
                if not line_text:
                    continue

                # 依字體大小判斷標題層級
                max_size = max(s["size"] for s in spans)
                is_bold = any("bold" in s.get("font", "").lower() for s in spans)

                if max_size >= 18:
                    page_text_parts.append(f"\n# {line_text}\n")
                elif max_size >= 14 and is_bold:
                    page_text_parts.append(f"\n## {line_text}\n")
                elif max_size >= 12 and is_bold:
                    page_text_parts.append(f"\n### {line_text}\n")
                else:
                    page_text_parts.append(line_text)

        # 組合：文字 + 該頁圖片（附在文字區段尾端）
        page_md = "\n".join(page_text_parts)
        if page_img_refs:
            page_md += "\n\n" + "\n\n".join(page_img_refs)

        if page_md.strip():
            md_parts.append(page_md)

    doc.close()
    md_text = "\n\n".join(md_parts)

    # 儲存 Markdown
    md_path = os.path.join(file_dir, "content.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_text)

    # 複製圖片到前端 public 目錄
    fe_img_dir = os.path.join(FRONTEND_IMG, file_id)
    os.makedirs(fe_img_dir, exist_ok=True)
    for img_file in os.listdir(img_dir):
        src = os.path.join(img_dir, img_file)
        dst = os.path.join(fe_img_dir, img_file)
        if os.path.isfile(src):
            shutil.copy2(src, dst)

    return md_path


# ═══════════════════════════════════════════════════════════════════
#  Stage 2：Markdown → 語意分段
# ═══════════════════════════════════════════════════════════════════

def _stage_markdown_to_chunks(file_id: str, md_path: str, equipment: str) -> list:
    """依標題層級切割 Markdown 為語意 chunks"""
    _update_file_status(file_id, status="chunking")

    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    # 依 # 和 ## 標題切割
    heading_pattern = re.compile(r'^(#{1,2})\s+(.+)$', re.MULTILINE)
    matches = list(heading_pattern.finditer(md_text))

    chunks = []
    for i, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md_text)
        content = md_text[start:end].strip()

        if not content or len(content) < 20:
            continue

        # 提取圖片路徑
        img_refs = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', content)

        # 超長 section 分段（> 1500 字）
        if len(content) > 1500:
            paragraphs = re.split(r'\n\n+', content)
            sub_chunks = []
            current = ""
            for para in paragraphs:
                if len(current) + len(para) > 1500 and current:
                    sub_chunks.append(current.strip())
                    current = para
                else:
                    current = current + "\n\n" + para if current else para
            if current.strip():
                sub_chunks.append(current.strip())

            for j, sub in enumerate(sub_chunks):
                sub_imgs = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', sub)
                chunk_id = f"{equipment}_{file_id}_{len(chunks):03d}"
                suffix = f" (Part {j+1})" if len(sub_chunks) > 1 else ""
                chunks.append({
                    "id": chunk_id,
                    "equipment": equipment,
                    "topic": f"{title}{suffix}",
                    "content": sub,
                    "image_paths": sub_imgs,
                })
        else:
            chunk_id = f"{equipment}_{file_id}_{len(chunks):03d}"
            chunks.append({
                "id": chunk_id,
                "equipment": equipment,
                "topic": title,
                "content": content,
                "image_paths": img_refs,
            })

    # 儲存 chunks
    chunks_path = os.path.join(KB_FILES_DIR, file_id, "chunks.json")
    with open(chunks_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    _update_file_status(file_id, chunk_count=len(chunks))
    return chunks


# ═══════════════════════════════════════════════════════════════════
#  Stage 3：向量化（FAISS）
# ═══════════════════════════════════════════════════════════════════

def _stage_vectorize(file_id: str, chunks: list):
    """追加 chunks 到 manuals.json 並重建 FAISS index"""
    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer

    _update_file_status(file_id, status="vectorizing")

    # 讀取現有 manuals.json，移除同 file_id 的舊 chunks
    existing = []
    if os.path.exists(MANUALS_JSON):
        with open(MANUALS_JSON, "r", encoding="utf-8") as f:
            existing = json.load(f)
    existing = [c for c in existing if not c.get("id", "").startswith(f"{chunks[0]['equipment']}_{file_id}_")]

    all_chunks = existing + chunks
    with open(MANUALS_JSON, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    # 重建 FAISS
    model = SentenceTransformer("shibing624/text2vec-base-chinese")
    texts = [f"{d['equipment']} {d['topic']} {d['content']}" for d in all_chunks]
    embeddings = model.encode(texts)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(np.array(embeddings).astype("float32"))
    faiss.write_index(index, os.path.join(RAG_DATA_DIR, "index.faiss"))


# ═══════════════════════════════════════════════════════════════════
#  Stage 4：圖譜萃取（Neo4j）
# ═══════════════════════════════════════════════════════════════════

def _stage_graph_extract(file_id: str, chunks: list, equipment: str):
    """對每個 chunk 呼叫 LLM 萃取因果關係，寫入 Neo4j"""
    import asyncio

    _update_file_status(file_id, status="extracting")

    try:
        from kg_extractor import extract_causality
        from bk4.neo4j_client import CausalGraphClient

        async def _run():
            client = CausalGraphClient()
            for chunk in chunks:
                chunk_id = chunk["id"]
                content = chunk["content"]

                # LLM 因果萃取
                relations = await extract_causality(content)
                for rel in relations:
                    cause = rel.get("cause", "")
                    effect = rel.get("effect", "")
                    reason = rel.get("reason", "")
                    if cause and effect:
                        await client.ingest_chunk_causality(
                            doc_id=equipment,
                            chunk_id=chunk_id,
                            cause_text=cause,
                            effect_text=effect,
                            reason=reason,
                        )
            await client.close()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_run())
        loop.close()

    except Exception as e:
        print(f"[kb_pipeline] Graph extraction warning (non-fatal): {e}")


# ═══════════════════════════════════════════════════════════════════
#  主 Pipeline
# ═══════════════════════════════════════════════════════════════════

def run_pipeline(file_id: str, pdf_path: str, equipment: str):
    """
    完整 Pipeline（被 BackgroundTask 呼叫）。
    任何階段失敗會標記 error 狀態但不中斷後續可選階段。
    """
    try:
        # Stage 1
        md_path = _stage_pdf_to_markdown(file_id, pdf_path)

        # Stage 2
        chunks = _stage_markdown_to_chunks(file_id, md_path, equipment)
        if not chunks:
            _update_file_status(file_id, status="error", error_message="Markdown 分段後無有效 chunk")
            return

        # Stage 3
        _stage_vectorize(file_id, chunks)

        # Stage 4（非致命，失敗不阻擋）
        try:
            _stage_graph_extract(file_id, chunks, equipment)
        except Exception as e:
            print(f"[kb_pipeline] Graph extraction skipped: {e}")

        _update_file_status(file_id, status="done")

    except Exception as e:
        traceback.print_exc()
        _update_file_status(file_id, status="error", error_message=str(e)[:300])


# ═══════════════════════════════════════════════════════════════════
#  刪除清理
# ═══════════════════════════════════════════════════════════════════

def delete_file_data(file_id: str, equipment: str):
    """刪除一個 KB 檔案的所有衍生資料"""
    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer

    # 1. 從 manuals.json 移除
    if os.path.exists(MANUALS_JSON):
        with open(MANUALS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        prefix = f"{equipment}_{file_id}_"
        data = [c for c in data if not c.get("id", "").startswith(prefix)]
        with open(MANUALS_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # 重建 FAISS
        if data:
            model = SentenceTransformer("shibing624/text2vec-base-chinese")
            texts = [f"{d['equipment']} {d['topic']} {d['content']}" for d in data]
            embeddings = model.encode(texts)
            index = faiss.IndexFlatL2(embeddings.shape[1])
            index.add(np.array(embeddings).astype("float32"))
            faiss.write_index(index, os.path.join(RAG_DATA_DIR, "index.faiss"))

    # 2. 刪除 kb_files/{file_id}/
    file_dir = os.path.join(KB_FILES_DIR, file_id)
    if os.path.exists(file_dir):
        shutil.rmtree(file_dir)

    # 3. 刪除前端圖片
    fe_img_dir = os.path.join(FRONTEND_IMG, file_id)
    if os.path.exists(fe_img_dir):
        shutil.rmtree(fe_img_dir)

    # 4. 從 status.json 移除
    remove_file_status(file_id)
