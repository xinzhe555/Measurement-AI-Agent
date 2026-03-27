---
name: precos-knowledge-graph
description: >
  PREC·OS 多模態知識圖譜模組（Qdrant + Neo4j + Hybrid RAG）。
  當任務涉及以下內容時使用此 skill：修改 neo4j_client.py、rag_engine.py、
  build_rag_db.py、kg_extractor.py、pdf_to_json_parser.py，
  討論 Qdrant 向量檢索、Neo4j 圖譜推理、GraphRAG、FAISS、
  知識節點切片、圖文對齊、LRT 操作手冊檢索、Heidenhain 控制器參數查詢，
  或任何涉及知識圖譜建置與檢索的工作。
---

# 多模態知識圖譜模組

## 架構

```
知識層  ─── Qdrant（向量資料庫，語意相似度檢索）
        ─── Neo4j（圖資料庫，Node-Edge 多跳路徑推理）
        ─── FAISS（本地向量索引，Hybrid RAG 快速檢索）
```

## 已建立的知識內容

- LRT 操作手冊：操作步驟的結構化節點切片
- Heidenhain 控制器參數說明書：參數定義與設定建議
- 操作步驟 ↔ 儀器圖片的雙向關聯（圖文對齊）
- 跨工業領域擴展性已驗證（協力廠商伺服/油壓刀具庫）

## Hybrid RAG 流程

1. 使用者提問 → FAISS 向量相似度檢索（快速召回）
2. 召回結果 → Neo4j 圖譜多跳推理（關聯擴展）
3. 合併結果 → LLM 生成回答
4. RAG 日誌記錄於 Agent memory，前端以摺疊區塊顯示

## 關鍵檔案

- [neo4j_client.py](backend/bk4/neo4j_client.py) — Neo4j 圖資料庫客戶端
- [rag_engine.py](backend/bk4/rag_engine.py) — Hybrid RAG 引擎（FAISS + Neo4j）
- [build_rag_db.py](backend/build_rag_db.py) — 建構 RAG 向量資料庫
- [kg_extractor.py](backend/kg_extractor.py) — 知識圖譜節點擷取器
- [pdf_to_json_parser.py](backend/pdf_to_json_parser.py) — PDF 文件解析器

## 驗證指標

- 知識檢索回應時間 < 2 秒（已達成，vs 傳統 30 分鐘人工查閱）
