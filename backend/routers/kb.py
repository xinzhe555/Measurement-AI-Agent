"""
routers/kb.py
知識庫管理 API — 上傳 PDF、查看處理狀態、預覽 Markdown、刪除
"""
import os
import uuid
import shutil

from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.responses import PlainTextResponse

from schemas.kb import KBFileInfo, KBFileListResponse
import kb_pipeline

router = APIRouter(prefix="/api/kb", tags=["knowledge-base"])

KB_FILES_DIR = os.path.join(os.path.dirname(__file__), "..", "kb_files")


@router.post("/upload", response_model=KBFileInfo)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    equipment: str = Form(...),
):
    """上傳 PDF 並啟動背景處理 Pipeline"""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="僅接受 PDF 檔案")

    file_id = uuid.uuid4().hex[:8]
    file_dir = os.path.join(KB_FILES_DIR, file_id)
    os.makedirs(file_dir, exist_ok=True)

    # 儲存 PDF
    pdf_path = os.path.join(file_dir, "original.pdf")
    content = await file.read()
    with open(pdf_path, "wb") as f:
        f.write(content)

    # 註冊狀態
    kb_pipeline.register_upload(file_id, file.filename, equipment)

    # 啟動背景處理
    background_tasks.add_task(kb_pipeline.run_pipeline, file_id, pdf_path, equipment)

    status = kb_pipeline.get_all_files()
    info = next((s for s in status if s["file_id"] == file_id), None)
    return KBFileInfo(**info)


@router.get("/files", response_model=KBFileListResponse)
async def list_files():
    """回傳所有已上傳檔案清單及處理狀態"""
    files = kb_pipeline.get_all_files()
    return KBFileListResponse(files=[KBFileInfo(**f) for f in files])


@router.get("/files/{file_id}/markdown")
async def get_markdown(file_id: str):
    """回傳轉換後的 Markdown 內容（供前端預覽）"""
    md_path = os.path.join(KB_FILES_DIR, file_id, "content.md")
    if not os.path.exists(md_path):
        raise HTTPException(status_code=404, detail="Markdown 尚未生成或檔案不存在")
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
    return PlainTextResponse(content)


@router.delete("/files/{file_id}")
async def delete_file(file_id: str):
    """刪除檔案及其所有衍生資料"""
    all_status = kb_pipeline._read_status()
    if file_id not in all_status:
        raise HTTPException(status_code=404, detail="檔案不存在")

    equipment = all_status[file_id].get("equipment", "")
    kb_pipeline.delete_file_data(file_id, equipment)
    return {"deleted": True, "file_id": file_id}


@router.post("/rebuild-index")
async def rebuild_index(background_tasks: BackgroundTasks):
    """手動觸發重建 FAISS index"""
    import json
    manuals_path = os.path.join(os.path.dirname(__file__), "..", "rag_data", "manuals.json")
    if not os.path.exists(manuals_path):
        raise HTTPException(status_code=404, detail="manuals.json 不存在")

    def _rebuild():
        import faiss
        import numpy as np
        from sentence_transformers import SentenceTransformer
        with open(manuals_path, "r", encoding="utf-8") as f:
            docs = json.load(f)
        model = SentenceTransformer("shibing624/text2vec-base-chinese")
        texts = [f"{d['equipment']} {d['topic']} {d['content']}" for d in docs]
        embeddings = model.encode(texts)
        index = faiss.IndexFlatL2(embeddings.shape[1])
        index.add(np.array(embeddings).astype("float32"))
        rag_dir = os.path.dirname(manuals_path)
        faiss.write_index(index, os.path.join(rag_dir, "index.faiss"))

    background_tasks.add_task(_rebuild)
    return {"status": "rebuilding"}


@router.get("/graph-stats")
async def graph_stats(equipment: str = None):
    """
    回傳知識圖譜統計：chunks 數量、Neo4j 節點/邊數、依 equipment 分組。
    可選 ?equipment=LRT 過濾。
    """
    import json as _json

    manuals_path = os.path.join(os.path.dirname(__file__), "..", "rag_data", "manuals.json")

    # FAISS chunks 統計
    chunks_by_eq = {}
    if os.path.exists(manuals_path):
        with open(manuals_path, "r", encoding="utf-8") as f:
            docs = _json.load(f)
        for d in docs:
            eq = d.get("equipment", "Unknown")
            chunks_by_eq[eq] = chunks_by_eq.get(eq, 0) + 1

    total_chunks = sum(chunks_by_eq.values())

    # Neo4j 統計（直接 await，不另開 event loop）
    neo4j_stats = {}
    try:
        import sys as _sys
        _sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from bk4.neo4j_client import CausalGraphClient
        client = CausalGraphClient()

        async with client.driver.session() as session:
            for label in ["Chunk", "Event", "Document", "TNCFunction", "ErrorType", "MeasurementPhenomenon"]:
                if equipment and label == "Chunk":
                    r = await session.run(
                        f"MATCH (n:{label}) WHERE n.chunk_id STARTS WITH $eq RETURN count(n) AS cnt",
                        eq=equipment
                    )
                else:
                    r = await session.run(f"MATCH (n:{label}) RETURN count(n) AS cnt")
                rec = await r.single()
                neo4j_stats[label] = rec["cnt"]

            for rel_type in ["CAUSAL_LINK", "MENTIONS", "COMPENSATED_BY", "PROCEDURE_STEP"]:
                r = await session.run(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS cnt")
                rec = await r.single()
                neo4j_stats[f"edge_{rel_type}"] = rec["cnt"]

        await client.close()
    except Exception as e:
        neo4j_stats = {"error": str(e)}

    return {
        "total_chunks": total_chunks,
        "chunks_by_equipment": chunks_by_eq,
        "neo4j": neo4j_stats,
    }


@router.get("/graph-data")
async def graph_data(
    equipment: str = None,
    node_type: str = None,
    limit: int = 200,
):
    """
    回傳 Neo4j 中的節點與邊，供前端 force-graph 視覺化。
    可選篩選：?equipment=LRT / ?node_type=Event / ?limit=100
    """
    try:
        import sys as _sys
        _sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from bk4.neo4j_client import CausalGraphClient
        client = CausalGraphClient()

        nodes = []
        links = []
        seen_ids = set()

        async with client.driver.session() as session:
            # 建構 WHERE 條件
            where_parts = []
            params = {"lim": limit}
            if equipment:
                where_parts.append(
                    "((n:Chunk AND n.chunk_id STARTS WITH $eq) OR "
                    "(n:Document AND n.doc_id = $eq) OR "
                    "(NOT n:Chunk AND NOT n:Document))"
                )
                params["eq"] = equipment
            if node_type:
                where_parts.append(f"n:{node_type}")

            where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

            # 查詢節點
            cypher_nodes = f"""
            MATCH (n)
            {where_clause}
            RETURN
                elementId(n) AS id,
                labels(n) AS labels,
                properties(n) AS props
            LIMIT $lim
            """
            result = await session.run(cypher_nodes, **params)
            records = await result.data()

            for rec in records:
                nid = rec["id"]
                label = rec["labels"][0] if rec["labels"] else "Unknown"
                props = rec["props"]
                name = (
                    props.get("text", "")[:50] or
                    props.get("chunk_id", "") or
                    props.get("doc_id", "") or
                    props.get("name", "") or
                    props.get("description", "")[:50] or
                    props.get("code", "") or
                    props.get("opt_id", "") or
                    props.get("mp_id", "") or
                    label
                )
                nodes.append({
                    "id": nid,
                    "label": label,
                    "name": name,
                })
                seen_ids.add(nid)

            # 查詢這些節點之間的邊
            if seen_ids:
                cypher_edges = """
                MATCH (a)-[r]->(b)
                WHERE elementId(a) IN $ids AND elementId(b) IN $ids
                RETURN
                    elementId(a) AS source,
                    elementId(b) AS target,
                    type(r) AS rel_type
                """
                result = await session.run(cypher_edges, ids=list(seen_ids))
                edge_records = await result.data()
                for erec in edge_records:
                    links.append({
                        "source": erec["source"],
                        "target": erec["target"],
                        "type": erec["rel_type"],
                    })

        await client.close()
        return {"nodes": nodes, "links": links}

    except Exception as e:
        return {"nodes": [], "links": [], "error": str(e)}
